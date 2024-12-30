"""Safecast Reader Library

(C) 2015-2024 by OpenGeoLabs s.r.o.

Read the file LICENCE.md for details.

.. sectionauthor:: Martin Landa <martin.landa opengeolabs.cz>
"""
from builtins import object

import os
import csv
import time
from datetime import datetime, timedelta, date
from collections import OrderedDict

import pyproj
from dateutil import tz

from .exceptions import ReaderError
from .logger import ReaderLogger
from . import RecordBase, ReaderBase, ComputedAttributes

class SafecastRecord(RecordBase):
    @staticmethod
    def _coordsFloat(coord, ne):
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

    @property
    def point(self):
        """Get point coordinates.

        :return tuple: point coordinates (x, y)
        """
        return (
            self._coordsFloat(self['long_deg'], self['east_west']),
            self._coordsFloat(self['lat_deg'], self['hemisphere'])
        )
class SafecastReader(ReaderBase):
    """Reader class for reading Safecast format (LOG files).
    """
    _scan_attributes = False

    def __init__(self, filepath, computed_attributes=ComputedAttributes.No):
        """Constructor.

        Check format, version and deadtime.

        Computed attributes levels:

        - ComputedAttributes.No do not compute any attributes
        - ComputedAttributes.PerRecordOnly compute attributes only per record
        - ComputedAttributes.All compute all attributes
        
        :param str filepath: file name to be imported
        :param bool compute_attributes: level of computed attributes
        """
        self.format_version = None
        self.deadtime = None
        self.nlines = 0
        # default for safecast
        self.callibration_coefficient = 0.0029940119760479

        try:
            super().__init__(filepath, computed_attributes=computed_attributes)
            self.nlines = self._count('$')
        except (IOError, ReaderError) as e:
            raise ReaderError("{}".format(e))

        self._records = None
        self._record_idx = -1

    @property
    def metadata(self):
        return {
            'table': 'safecast_metadata',
            'columns': {
                'filename': self._filepath.name,
                'format': self.format_version,
                'deadtime': self.deadtime,
                'callibration_coefficient': self.callibration_coefficient
            }
        }

    def _next_data_item_(self):
        """Read next data record.
        """
        while True:
            line = self._fd.readline().strip()
            if not line:
                # EOF
                return None

            record = SafecastRecord()
            if line.startswith('#'):
                continue

            data = list(csv.reader([line]))[0]
            if len(data)+1 != self._num_attributes_read:
                ReaderLogger.warning(f"Invalid record skipped (file {self._filepath.name}): {line}")
                continue
            last_item = data[-1].split('*')
            data[-1] = last_item[0]
            data.append('*' + last_item[1])
            attrs = list(self._attributes.keys())
            for idx in range(len(data)):
                k = attrs[idx]
                record[k] = self._attributes[k]['type'](data[idx]) if self._attributes else data[idx]

            if self.computed_attributes.value >= ComputedAttributes.PerRecordOnly.value:
                for k, v in self._attributes.items():
                    if v['computed'] == ComputedAttributes.PerRecordOnly: # may be computed per record
                        record[k] = self._computeAttribute(k, record)

            return record

    def _next_data_item(self):
        """Read next data record.
        """
        if self.computed_attributes == ComputedAttributes.All:
            # all records must be loaded into memory because of attributes
            # that can only be calculated at the end
            if self._records is None:
                self._records = []
                while True:
                    record = self._next_data_item_()
                    if record is None:
                        break # EOF
                    self._records.append(record)

                self.computeAttributes(self._records)

            self._record_idx += 1
            return self._records[self._record_idx] if self._record_idx < len(self._records) else None
        else:
            return self._next_data_item_()

    def _readHeader(self):
        """Read LOG header and store metadata records.
        """
        # TODO: be less pedantic
        def _read_header_line(line, header_line):
            line = line[1:].strip()
            if header_line == 0 and line != "NEW LOG":
                raise ReaderError("Unable to read '{}': "
                                  "Invalid format".format(self._filepath))
            elif header_line == 1 : # -> version
                if not line.startswith('format'):
                    raise ReaderError("Unable to read '{}': "
                                      "Unknown version".format(self._filepath))
                else:
                    self.format_version = line.split('=')[1]
            elif header_line == 2: # -> deadtime
                if not line.startswith('deadtime'):
                    raise ReaderError("Unable to read '{}': "
                                      "Unknown deadtime".format(self._filepath))
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
            line = line.strip()
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

    def reset(self):
        """Reset reading.
        """
        # self._records = None
        self._record_idx = -1
        super().reset()

    def count(self):
        """Get data record count.
        """
        return self.nlines

    def _computeAttribute(self, attribute, record):
        """Compute attribute for single record.

        :param str attribute: attribute name to be computed
        :param SafecastRecord record: record item

        :return computed value
        """
        value = None
        if attribute == "ader_microsvh":
            try:
                if record['pulses5s'] > 0:
                    value = record['pulses5s'] * 12
                else:
                    value = record['cpm']
                value *= self.callibration_coefficient
            except ValueError:
                value = -1
        elif attribute == "time_local":
            try:
                value = self._datetime2localtime(record['date_time'])
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

    def _checkDate(self, fdate):
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

    def _validateDate(self, curr_datetime, prev_datetime, first_valid_date):
        """Validate date.

        :param curr_datetime: date to be validated
        :param prev_datetime: previous date or None
        :param first_valid_date: first valid date (if prev_datetime is None)

        :return: validate date, update flag
        """
        if self._checkDate(curr_datetime):
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

    def computeAttributes(self, records):
        """Compute attributes.

        :param list records: list of SafecastRecords
        """
        # get first valid datetime
        first_valid_date = None
        for record in records:
            if self._checkDate(record["date_time"]):
                first_valid_date = datetime.strptime(record["date_time"], "%Y-%m-%dT%H:%M:%SZ").date()
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
        prev = None  # previous record
        dose_inc = 0
        start = time.perf_counter()
        for record in records:
            # fix date if invalid
            date_time, newdt = self._validateDate(record["date_time"], prev_date_time, first_valid_date)

            # compute ader stats
            if ader_max is None or ader_max < record["ader_microsvh"]:
                ader_max = record["ader_microsvh"]
            ader_cum += record["ader_microsvh"]

            # compute local time (from datetime)
            try:
                time_local = self._datetime2localtime(date_time)
            except ValueError:
                time_local = "unknown"

            # compute coordinates
            point = record.point
            if prev is not None:
                timediff = self._datetimediff(
                    prev_date_time,
                    date_time
                ).total_seconds() / (60 * 60)

                dose_inc = record["ader_microsvh"] * timediff

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
            prev = record
            prev_date_time = date_time
            prev_point = point

            attrs = OrderedDict([
                ("speed_kmph", speed),
                ("dose_increment", dose_inc),
                ("time_cumulative", self._td2str(timedelta(hours=time_cum))),
                ("dose_cumulative", dose_cum),
                ("dist_cumulative", dist_cum),
            ])
            if newdt:
                attrs["date_time"] = date_time

            # update records
            record.update(attrs)

            for k, v in self._attributes.items():
                if v['computed'].value > ComputedAttributes.PerRecordOnly.value and k not in attrs:
                    raise ReaderError(f"Attribute {k} not computed")

            count += 1

        # update statistics
        self._stats = {
            'count' : count,
            'radiation': {
                'max' : ader_max,
                'avg' : ader_cum / count,
                'total': dose_cum,
            },
            'route': {
                'speed' : speed_cum / count,
                'time': self._td2str(timedelta(hours=time_cum)),
                'distance' : dist_cum,
            }
        }
