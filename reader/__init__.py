import os
import inspect
import csv
import copy

from pathlib import Path
from contextlib import AbstractContextManager
from types import TracebackType
from collections import OrderedDict

from .exceptions import ReaderError, ReaderExportError
from .logger import ReaderLogger

__version__ = "1.0.0"

class ReaderBase(AbstractContextManager['ReaderBase']):
    """Base reader class.
    """
    _scan_attributes = True

    def __init__(self, filepath, rb=False, computed_attributes=False):
        self._filepath = filepath

        try:
            flag = 'rb' if rb else 'r'
            self._fd = open(self._filepath, flag)
        except IOError as e:
            raise ReaderError("{}".format(e))

        # attribute names & data types
        self._attributes = None
        self.computed_attributes = computed_attributes
        self._attributes = self.attributeDefs()

    def __del__(self):
        """Destructor, close input file.
        """
        if self._fd:
            self._fd.close()

    def __enter__(self):
        """Enter context manager protocol.
        """
        super().__enter__()
        return self

    def __exit__(self,
                 exc_type: None | type[BaseException],
                 exc_val: None | BaseException,
                 exc_tb: None | TracebackType,
                 /):
        """Exit context manager protocol.
        """
        super().__exit__(exc_type, exc_val, exc_tb)

    def count(self):
        """Count data items.
        """
        raise NotImplementedError()

    def _getPoint(self, item):
        """Get point coordinates.

        :param OrderedDict: item

        :return tuple: point coordinates (x, y)
        """
        raise NotImplementedError()

    def _next_data_item(self):
        """Read next data item.
        """
        raise NotImplementedError()

    def __iter__(self):
        """Loop through features.
        """
        self.reset()
        return self

    def __next__(self):
        """Return next record.
        """
        item = self._next_data_item()
        if item is None:
            raise StopIteration

        return item

    def reset(self):
        """Reset reading.
        """
        self._fd.seek(0)

    def _count(self, counter):
        """Count data items.

        Inspired by http://stackoverflow.com/questions/845058/how-to-get-line-count-cheaply-in-python.

        :param counter: counter string
        """
        self.reset()

        lines = 0
        buf_size = 1024 * 1024
        read_f = self._fd.read # loop optimization

        buf = read_f(buf_size)
        while buf:
            lines += buf.count(counter)
            buf = read_f(buf_size)

        self.reset()
        return lines

    def _readAttributeDefs(self, def_file):
        """Read attribute definitions.

        :param str def_file: CSV defintion file
        """
        def addAttribute(row):
            attrb = {
                row['attribute']: {
                    "type" : eval(row['type'])
                }
            }
            if 'alias' in row and row['alias']:
                attrb[row['attribute']]['alias'] = row['alias'].replace('_', ' ')
            if 'computed' in row and row['computed']:
                computed = attrb[row['attribute']]['computed'] = int(row['computed'])
                if self.computed_attributes is False and computed > 0:
                    return {}

            return attrb

        if os.path.exists(def_file):
            with open(def_file) as fd:
                def_attrbs = list(csv.DictReader(fd, delimiter=';'))
        else:
            raise ReaderError(f"Definition file {def_file} not found")

        self._attributes = OrderedDict()
        if self._scan_attributes:
            # limit attributes based on input file (first feature) - ERS/PEI format specific
            self.reset()
            item = self._next_data_item()
            self.reset()
            for name in item.keys():
                # first try full name match
                found = False
                for row in def_attrbs:
                    if row['attribute'] == name:
                        self._attributes.update(addAttribute(row))
                        found = True
                        break
                if found:
                    continue
                for row in def_attrbs:
                    # full name match is not required see
                    # https://gitlab.com/opengeolabs/qgis-radiation-toolbox-plugin/issues/41#note_136183930
                    if row['attribute'] == name[:len(row['attribute'])] or name == row['attribute'][:len(name)]:
                        row_modified = copy.copy(row)
                        row_modified['attribute'] = name # force (full) attribute name from input file
                        if row_modified['alias']:
                            row_modified['alias'] = '{} ({})'.format(name, row_modified['alias'])
                        self._attributes.update(addAttribute(row_modified))
                        break
        else:
            # add all attributes
            for row in def_attrbs:
                self._attributes.update(addAttribute(row))

    def attributeDefs(self):
        """Get attribute definitions from file.
        """
        if self._attributes is None:
            self._readAttributeDefs(self._definitionCSVFile)

        return self._attributes

    @property
    def _definitionCSVFile(self):
        return os.path.join(
            os.path.dirname(__file__),
            os.path.splitext(inspect.getfile(self.__class__))[0] + '.csv'
        )

    def exportCSV(self, filename, sep=','):
        """Export data into CSV file.

        :param str filename: target CSV file path
        :param str sep: separator
        """
        with open(filename, "w") as fd:
            # header
            fd.write(sep.join(self.attributeDefs().keys()) + os.linesep)
            # body
            for item in self:
                fd.write(sep.join(map(str, item.values())) + os.linesep)

    def export(self, filename, driver_name, append=False):
        """Export data using GDAL library.

        :param str filename: target file path
        :param str driver_name: GDAL driver to be used to export data
        :param bool append: True to append new data to existing datasource otherwise overwrite data source if exists
        """
        if driver_name not in ("GPKG", "SQLite"):
            ReaderLogger.warning(f"GDAL driver {driver_name} is not supported. "
                                 "Its functionality is not guaranteed.")

        from osgeo import gdal, ogr, osr
        gdal.UseExceptions()

        driver = ogr.GetDriverByName(driver_name)
        if driver is None:
            raise ReaderExportError(f"Unknown GDAL driver {driver_name}")
        try:
            ReaderLogger.debug(f"Creating output file: {filename}")
            if append is True:
                if not Path(filename).exists():
                    ds = driver.CreateDataSource(filename)
                else:
                    ds = gdal.OpenEx(filename, gdal.OF_VECTOR | gdal.OF_UPDATE)
            else:
                if Path(filename).exists():
                    driver.DeleteDataSource(filename)
                ds = driver.CreateDataSource(filename)
        except RuntimeError as e:
            raise ReaderExportError(f"{e}")

        # create layer
        layer_name = Path(self._filepath).stem
        srs = osr.SpatialReference()
        srs.ImportFromEPSG(4326)
        layer = ds.CreateLayer(layer_name, srs, geom_type=ogr.wkbPoint)

        # create fields
        field_types = {
            int: ogr.OFTInteger,
            float: ogr.OFTReal,
            str: ogr.OFTString,
        }
        field_names = []
        for k, v in self.attributeDefs().items():
            field_name = k.replace("-", "_") if "-" in k else k
            layer.CreateField(ogr.FieldDefn(field_name, field_types[v['type']]))
            field_names.append(field_name)

        # write features
        layer_defn = layer.GetLayerDefn()
        for rec in self:
            feature = ogr.Feature(layer_defn)
            for idx, value in enumerate(rec.values()):
                feature.SetField(field_names[idx], value)
            geometry = ogr.Geometry(ogr.wkbPoint)
            geometry.AddPoint_2D(*self._getPoint(rec))
            feature.SetGeometry(geometry)
            layer.CreateFeature(feature)
            feature = None

        self.reset()
        ds.Close()
