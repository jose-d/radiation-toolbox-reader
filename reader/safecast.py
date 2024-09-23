"""Safecast Reader Library

(C) 2015-2024 by OpenGeoLabs s.r.o.

Read the file LICENCE.md for details.

.. sectionauthor:: Martin Landa <martin.landa opengeolabs.cz>
"""
from builtins import object

import os
import csv
import time
from collections import OrderedDict
from datetime import datetime, timedelta

import pyproj
from dateutil import tz

from .exceptions import ReaderError
from .logger import ReaderLogger
from . import ReaderBase

class SafecastReader(ReaderBase):
    """Reader class for reading Safecast format (LOG files).
    """
    _scan_attributes = False

    def __init__(self, filepath, computed_attributes=True):
        """Constructor.

        Check format, version and deadtime.
        
        :param str filepath: file name to be imported
        :param bool compute_attributes: compute additional attributes
        """
        self.format_version = None
        self.deadtime = None
        self.nlines = 0
        # default for safecast
        self.callibration_coefficient = 0.0029940119760479

        try:
            super().__init__(filepath, computed_attributes=computed_attributes)
            self.nlines = self._count('\n')
            self.nlines -= self._read_header()
        except (IOError, ReaderError) as e:
            raise ReaderError("{}".format(e))

        self._items = None
        self._item_idx = -1

    def _next_data_item_(self):
        """Read next data item.
        """
        while True:
            line = self._fd.readline().rstrip(os.linesep)
            if not line:
                # EOF
                return None

            item = OrderedDict()
            if line.startswith('#'):
                continue

            data = list(csv.reader([line]))[0]
            last_item = data[-1].split('*')
            data[-1] = last_item[0]
            data.append('*' + last_item[1])
            attrs = list(self._attributes.keys())
            for idx in range(len(data)):
                k = attrs[idx]
                item[k] = self._attributes[k]['type'](data[idx]) if self._attributes else data[idx]

            if self.computed_attributes:
                for k, v in self._attributes.items():
                    if v['computed'] == 1: # may be computed per item
                        item[k] = self._compute_attribute(k, item)

            return item

    def _next_data_item(self):
        """Read next data item.
        """
        if self.computed_attributes:
            # all items must be loaded into memory because of attributes
            # that can only be calculated at the end
            if self._items is None:
                self._items = []
                while True:
                    item = self._next_data_item_()
                    if item is None:
                        break # EOF
                    self._items.append(item)

                self._compute_attributes(self._items)

            self._item_idx += 1
            return self._items[self._item_idx] if self._item_idx < len(self._items) else None
        else:
            return self._next_data_item_()

    def _read_header(self):
        """Read LOG header and store metadata items.
        """
        # TODO: be less pedantic
        def _read_header_line(line, header_line):
            line = line.rstrip('\r\n')
            if header_line == 0 and line != "# NEW LOG":
                raise ReaderError("Unable to read '{}': "
                                  "Invalid format".format(self.filename))
            elif header_line == 1 : # -> version
                if not line.startswith('# format'):
                    raise ReaderError("Unable to read '{}': "
                                      "Unknown version".format(self.filename))
                else:
                    self.format_version = line.split('=')[1]
            elif header_line == 2: # -> deadtime
                if not line.startswith('# deadtime'):
                    raise ReaderError("Unable to read '{}': "
                                      "Unknown deadtime".format(self.filename))
                else:
                    self.deadtime = line.split('=')[1]
            elif header_line == 3:
                device_code = tuple(csv.reader([line]))[0][0]
                if device_code == '$CZRA1':
                    # device type is czechrad, change callibration coefficient
                    self.callibration_coefficient = 0.0030441400304414
                    # keep default otherwise

        header_line = 0
        self.reset()
        for line in self._fd:
            if line.startswith('#'):
                _read_header_line(line, header_line)
                header_line += 1
            if header_line == 3:
                ReaderLogger.debug("LOG header correct")
                # read one more line to get the device id
                _read_header_line(next(self._fd), header_line)
                break
        self.reset()

        return header_line

    def count(self):
        """Get data item count.
        """
        return self.nlines

    def _compute_attribute(self, attribute, item):
        """Compute attribute for single item.

        :param str attribute: attribute name to be computed
        :param OrderedDict item: record item

        :return computed value
        """
        value = None
        if attribute == "ader_microsvh":
            try:
                if item['pulses5s'] > 0:
                    value = item['pulses5s'] * 12
                else:
                    value = item['cpm']
                value *= self.callibration_coefficient
            except ValueError:
                value = -1
        elif attribute == "time_local":
            try:
                value = self._datetime2localtime(item['date_time'])
            except ValueError:
                value = "unknown"

        if value is None:
            raise ReaderError(f"Unknown computed attribute: {attribute}")
        return value

    @staticmethod
    def _datetime2localtime(datetime_value):
        """Convert datetime value to local time.

        :datetime_value: date time value (eg. '2016-05-16T18:22:26Z')

        :return: local time as a string (eg. '20:22:26')
        """
        from_zone = tz.tzutc()
        to_zone = tz.tzlocal()

        utc = datetime.strptime(datetime_value, '%Y-%m-%dT%H:%M:%SZ')
        utc = utc.replace(tzinfo=from_zone)
        local = utc.astimezone(to_zone)

        return local.strftime('%H:%M:%S')

    def _check_date(self, fdate):
        """Check if date is valid.

        :param fdate: date to be checked

        :return: True if date is valid otherwise False
        """
        minyear = 2011
        maxyear = datetime.now().year
        myear = self._datetime2year(fdate)
        if myear < minyear or myear > maxyear:
            return False
        return True

    @staticmethod
    def _datetime2year(datetime_value):
        """Convert datatime value to year.

        :datetime_value: date time value (eg. '2016-05-16T18:22:26Z')

        :return: local time as a int (2016)
        """
        try:
            return datetime.strptime(
                datetime_value, '%Y-%m-%dT%H:%M:%SZ'
            ).year
        except ValueError:
            return 0

    @staticmethod
    def _datetimediff(datetime_value1, datetime_value2, timeonly=False):
        """Compute datetime difference in sec.

        :param datetime_value1: first value
        :param datetime_value2: second value

        :return: time difference in sec
        """
        if timeonly:
            t1 = datetime.strptime(datetime_value1.split('T', 1)[1], '%H:%M:%SZ')
            t2 = datetime.strptime(datetime_value2.split('T', 1)[1], '%H:%M:%SZ')
            val1 = datetime.combine(date.today(), t1.time())
            val2 = datetime.combine(date.today(), t2.time())
        else:
            val1 = datetime.strptime(datetime_value1, '%Y-%m-%dT%H:%M:%SZ')
            val2 = datetime.strptime(datetime_value2, '%Y-%m-%dT%H:%M:%SZ')

        return val2 - val1

    def _validate_date(self, curr_datetime, prev_datetime, first_valid_date):
        """Validate date.

        :param curr_datetime: date to be validated
        :param prev_datetime: previous date or None
        :param first_valid_date: first valid date (if prev_datetime is None)

        :return: validate date, update flag
        """
        if self._check_date(curr_datetime):
            return curr_datetime, False

        if prev_datetime:
            timediff = self._datetimediff(
                prev_datetime, curr_datetime, timeonly=True
            ).total_seconds()
            fdate = datetime.strptime(
                prev_datetime, "%Y-%m-%dT%H:%M:%SZ"
            ).date()
        else:
            timediff = 0
            fdate = first_valid_date

        if timediff < 0:
            # next date
            fdate += timedelta(days=1)

        return datetime.strftime(
            datetime.combine(
                fdate,
                datetime.strptime(curr_datetime.split('T', 1)[1], "%H:%M:%SZ").time()
            ),
            '%Y-%m-%dT%H:%M:%SZ'
        ), True

    @staticmethod
    def _td2str(td):
        """Convert timedelta objects to a HH:MM string with (+/-) sign

        Taken from: https://stackoverflow.com/questions/538666/python-format-timedelta-to-string
        """
        tdhours, rem = divmod(td.total_seconds(), 3600)
        tdminutes, rem = divmod(rem, 60)

        return '{0:02d}:{1:02d}:{2:02d}'.format(
            int(tdhours), int(tdminutes), int(rem)
        )

    @staticmethod
    def _distance(p1, p2):
        """Compute distance between two points.

        :param tuple p1: first point
        :param tuple p2: second point

        :return float distance
        """
        geod = pyproj.Geod(ellps='WGS84')
        _, _, distance = geod.inv(p1[0], p1[1], p2[0], p2[1])

        return distance

    @staticmethod
    def _coords_float(coord, ne):
        """Convert coordinates to DMS.

        :param coord: coordinates as a string
        :param ne: longitude/latitude indicator

        :return: coordinate value
        """
        ddmm, s = coord.split('.', 1)
        val = int(ddmm[:-2]) + int(ddmm[-2:])/60. + float('0.'+s)/60.
        if ne in ('S', 'W'):
            val *= -1
        return val

    def _compute_attributes(self, items):
        # get first valid datetime
        first_valid_date = None
        for item in items:
            if self._check_date(item["date_time"]):
                first_valid_date = datetime.strptime(item["date_time"], "%Y-%m-%dT%H:%M:%SZ").date()
                break
        if first_valid_date is None:
            ReaderLogger.warning("No valid date found. Unable to fix datetime.")

        # compute attributes
        ader_max = None
        ader_cum = 0
        speed_cum = 0
        dist_cum = 0
        time_cum = 0
        count = 0
        dose_cum = 0
        speed = 0
        prev_date_time = None
        prev_point = None
        prev = None  # previous item
        dose_inc = 0
        start = time.perf_counter()
        for item in items:
            # fix date if invalid
            date_time, newdt = self._validate_date(item["date_time"], prev_date_time, first_valid_date)
            # compute ader stats
            if ader_max is None or ader_max < item["ader_microsvh"]:
                ader_max = item["ader_microsvh"]
            ader_cum += item["ader_microsvh"]

            # compute local time (from datetime)
            try:
                time_local = self._datetime2localtime(date_time)
            except ValueError:
                time_local = self._layer.tr("unknown")

            # compute coordinates
            point = (
                self._coords_float(item['long_deg'], item['east_west']),
                self._coords_float(item['lat_deg'], item['hemisphere'])
            )
            if prev is not None:
                timediff = self._datetimediff(
                    prev_date_time,
                    date_time
                ).total_seconds() / (60 * 60)

                dose_inc = item["ader_microsvh"] * timediff

                # speed
                dist = self._distance(point, prev_point)
                dist_cum += dist

                # workaround: setting up precision causes in QGIS 2
                # problems when exporing data into other formats, see
                # https://lists.osgeo.org/pipermail/qgis-developer/2017-December/050969.html
                # disabled
                # see https://bitbucket.org/opengeolabs/qgis-safecast-plugin-dev/issues/14/decrease-the-number-of-decimal-places-in
                # speed = float('{0:.2f}'.format((dist / 1e3) / timediff)) # kmph
                if timediff > 0:
                    speed = (dist / 1e3) / timediff # kmph
                else:
                    speed = 0
                speed_cum += speed

                # time cumulative
                time_cum += timediff

            if dose_inc > 0:
                dose_cum += dose_inc

            # set previous feature for next run
            prev = item
            prev_date_time = date_time
            prev_point = point

            attrs = OrderedDict([
                ("speed_kmph", speed),
                ("dose_increment", dose_inc),
                ("time_cumulative", self._td2str(timedelta(hours=time_cum))),
                ("dose_cumulative", dose_cum),
            ])
            if newdt:
                attrs["date_time"] = date_time

            # update items
            item.update(attrs)

            for k, v in self._attributes.items():
                if v['computed'] > 1 and k not in attrs:
                    raise ReaderError(f"Attribute {k} not computed")

            count += 1
