import os
import inspect
import csv
import copy
from pathlib import Path
from contextlib import AbstractContextManager
from types import TracebackType
from collections import OrderedDict
from enum import Enum

from .exceptions import ReaderError, ReaderExportError, ReaderExportDuplication
from .logger import ReaderLogger

__version__ = "1.0.0"

class RecordBase(OrderedDict):
    @property
    def point(self):
        """Get point coordinates.

        :return tuple: point coordinates (x, y)
        """
        raise NotImplementedError()

class ComputedAttributes(Enum):
    No = 0
    PerRecordOnly = 1
    All = 2

class ReaderBase(AbstractContextManager['ReaderBase']):
    """Base reader class.
    """
    _scan_attributes = True

    def __init__(self, filepath, rb=False, computed_attributes=ComputedAttributes.No):
        self._filepath = Path(filepath)

        # open data input file
        self._open_flag = 'rb' if rb else 'r'
        self._fd = self._open()

        # attribute names & data types
        self._attributes = None
        self.computed_attributes = computed_attributes
        self._attributes = self.attributeDefs()
        self._num_attributes_read = sum(
            1 for attr in self._attributes.values() if attr['computed'] == ComputedAttributes.No
        )

        # statistics
        self._stats = None

    def __del__(self):
        """Destructor, close input file.
        """
        self.release()

    @property
    def metadata(self):
        return {}

    def _open(self):
        """Open input file.

        :return: file descriptor
        """
        if hasattr(self, "_fd") is False or self._fd is None:
            try:
                self._fd = open(self._filepath, self._open_flag)
            except IOError as e:
                raise ReaderError("{}".format(e))

        return self._fd

    def stats(self):
        """Compute statistics.

        :return dict: stats
        """
        if self._stats is None:
            self._stats = {'count': self.count()}
        return self._stats

    def __enter__(self):
        """Enter context manager protocol.
        """
        super().__enter__()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit context manager protocol.
        """
        super().__exit__(exc_type, exc_val, exc_tb)

    def count(self):
        """Count data records.
        """
        raise NotImplementedError()

    def _next_data_item(self):
        """Read next data record.
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
        record = self._next_data_item()
        if record is None:
            raise StopIteration

        return record

    def reset(self):
        """Reset reading.
        """
        self._fd = self._open()
        self._fd.seek(0)

    def release(self):
        """Release resources.
        """
        if self._fd is not None:
            self._fd.close()
            self._fd = None

    def _count(self, counter):
        """Count data records.

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
                    "type" : eval(row['type']),
                    "alias": None,
                    "computed": ComputedAttributes.No
                }
            }
            if 'alias' in row and row['alias']:
                attrb[row['attribute']]['alias'] = row['alias'].replace('_', ' ')
            if 'computed' in row and row['computed']:
                computed = attrb[row['attribute']]['computed'] = ComputedAttributes(int(row['computed']))
                if computed.value > 0 and (self.computed_attributes == ComputedAttributes.No or
                                     computed.value > self.computed_attributes.value):
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
            record = self._next_data_item()
            self.reset()
            for name in record.keys():
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
            for record in self:
                fd.write(sep.join(map(str, record.values())) + os.linesep)

    def export(self, filename, driver_name, overwrite=False, single_table=None):
        """Export data using GDAL library.

        :param str filename: target file path
        :param str driver_name: GDAL driver to be used to export data
        :param bool overwrite: True to overwrite existing target data source
        :param str single_table: name of table where to insert data records from multiple imported files or None (create a new table for each imported file)
        """
        if driver_name not in ("GPKG", "SQLite"):
            ReaderLogger.warning(f"GDAL driver {driver_name} is not supported. "
                                 "Its functionality is not guaranteed.")

        from osgeo import gdal
        gdal.UseExceptions()

        driver = gdal.GetDriverByName(driver_name)
        if driver is None:
            raise ReaderExportError(f"Unknown GDAL driver {driver_name}")

        if overwrite is True and Path(filename).exists():
            driver.Delete(filename)
        try:
            ReaderLogger.debug(f"Creating output file: {filename}")
            if not Path(filename).exists():
                ds = driver.Create(filename, 0, 0, 0, gdal.GDT_Unknown)
            else:
                ds = gdal.OpenEx(filename, gdal.OF_VECTOR | gdal.OF_UPDATE)
        except RuntimeError as e:
            raise ReaderExportError(f"{e}")

        self._export(ds, single_table)

    def _export(self, ds, single_table=None):
        """Export data using GDAL library.

        :param GDALDataset ds: target GDAL dataset
        :param str single_table: name of table where to insert data records from multiple imported files or None (create a new table for each imported file)
        """
        from osgeo import ogr, osr

        # collect fields
        field_names = []
        field_types = []
        map_types = {
            int: ogr.OFTInteger,
            float: ogr.OFTReal,
            str: ogr.OFTString,
        }
        for k, v in self.attributeDefs().items():
            field_name = k.replace("-", "_") if "-" in k else k
            field_names.append(field_name)
            field_types.append(map_types[v['type']])

        layer_name = Path(self._filepath).stem if single_table is None else single_table
        layer = ds.GetLayerByName(layer_name)
        if layer is None:
            # create layer
            srs = osr.SpatialReference()
            srs.ImportFromEPSG(4326)
            layer = ds.CreateLayer(layer_name, srs, geom_type=ogr.wkbPoint)

            # create fields
            for field_name, field_type in zip(field_names, field_types):
                layer.CreateField(ogr.FieldDefn(field_name, field_type))
        else:
            if single_table is None:
                # layer already exists
                raise ReaderExportDuplication(layer_name)

        # write features
        layer_defn = layer.GetLayerDefn()
        for rec in self:
            feature = ogr.Feature(layer_defn)
            for idx, value in enumerate(rec.values()):
                feature.SetField(idx, value)
            geometry = ogr.Geometry(ogr.wkbPoint)
            geometry.AddPoint_2D(*rec.point)
            feature.SetGeometry(geometry)
            layer.CreateFeature(feature)
            feature = None

        # write metadata
        meta = self.metadata
        if meta:
            self._writeMetadata(ds, meta)

        ds.FlushCache()

        self.reset()
        if ds.GetDriver().ShortName != "Memory":
            ds.Close()

    def export_memory(self, ds, single_table=None):
        """Export data into memory using GDAL library.

        :param GDALDataset ds: target GDAL dataset or None to create a new dataset
        :param str single_table: name of table where to insert data records from multiple imported files or None (create a new table for each imported file)
        """
        from osgeo import gdal
        if ds is None:
            driver = gdal.GetDriverByName('Memory')
            ds = driver.Create('', 0, 0, 0, gdal.GDT_Unknown)

        self._export(ds, single_table)

        return ds

    def _writeMetadata(self, ds, metadata):
        """Write metadata table.

        :param GDALDataSource ds: target data source
        :param dict metadata: metadata dictionary
        """
        from osgeo import ogr

        layer_name = metadata['table']
        layer = ds.GetLayerByName(layer_name)
        if layer is None:
            layer = ds.CreateLayer(layer_name, geom_type=ogr.wkbNone)
            if 'columns' in metadata:
                for key in metadata['columns']:
                    field = ogr.FieldDefn(key, ogr.OFTString)
                    layer.CreateField(field)

        layer_defn = layer.GetLayerDefn()
        feat = ogr.Feature(layer_defn)
        for key, value in metadata['columns'].items():
            feat.SetField(key, value)
        layer.CreateFeature(feat)
        feat = None
