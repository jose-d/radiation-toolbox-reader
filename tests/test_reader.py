import os
import sys
import tempfile
import csv
import pytest
from pathlib import Path

from reader.exceptions import ReaderExportDuplication

class TestReader:
    @staticmethod
    def _count(reader, filename, count):
        with reader(filename) as r:
            assert r.count() == count

    @staticmethod
    def _attributeDefs(reader, filename, ref, args={}):
        with reader(filename, **args) as r:
            assert list(r.attributeDefs().keys()) == ref

    @staticmethod
    def _record(reader, filename, ref, args={}, idx=0):
        def comp_record(rec1, rec2, tol=1e12):
            for k, v in rec1.items():
                if type(v) == float:
                    if abs(v-rec2[k]) > 1e-9:
                        print(f"DIFF: {v} x {rec2[k]}", file=sys.stderr)
                        return False
                else:
                    if v != rec2[k]:
                        print(f"DIFF: {v} x {rec2[k]}", file=sys.stderr)
                        return False
            return True

        with reader(filename, **args) as r:
            if idx == 0:
                assert comp_record(next(r), ref)
            else:
                for i in range(idx+1):
                    item = next(r)
                assert comp_record(item, ref)

    @staticmethod
    def _exportCSV(reader, filename):
        def dict2str(item):
            for k in item:
                item[k] = str(item[k])

        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            with reader(filename) as r:
                r.exportCSV(tmp.name)

            for count, line in enumerate(tmp):
                pass

            # check number of lines
            assert count == r.count()

        with open(tmp.name) as fd:
            # check first item
            csv_reader = csv.DictReader(fd)
            with reader(filename) as r:
                first_item = next(r)
                dict2str(first_item)
                assert next(csv_reader) == first_item

        os.remove(tmp.name)

    def _exportGDAL(self, reader, filename, driver_name, extension, repeat=False):
        from osgeo import gdal

        with reader(filename) as r:
            temp_path = f"{tempfile.mktemp()}.{extension}"
            r.export(temp_path, driver_name=driver_name)

            # check result
            ds = self._openDS(temp_path, driver_name)
            ref_layer_count = 2 if r.metadata else 1
            assert self._layerCount(ds) == ref_layer_count
            layer = ds.GetLayerByName(Path(filename).stem)
            assert layer is not None
            assert layer.GetFeatureCount() == r.count()

            # check first item
            first_feat = layer.GetNextFeature()
            first_item = next(r)
            for k, v in first_item.items():
                field_name = k.replace("-", "_") if "-" in k else k
                assert first_feat.GetField(field_name) == v

            if repeat:
                with pytest.raises(ReaderExportDuplication):
                    r.export(temp_path, driver_name=driver_name)

    @staticmethod
    def _layerCount(ds):
        return [ds.IsLayerPrivate(i) for i in range(ds.GetLayerCount())].count(False)

    @staticmethod
    def _openDS(path, driver_name):
        from osgeo import gdal

        oo = []
        if driver_name == "SQLite":
            oo.append("LIST_ALL_TABLES=YES")
        return gdal.OpenEx(path, gdal.OF_VECTOR, open_options=oo)

    def _stats(self, reader, filename):
        with reader(filename) as r:
            stats = r.stats()
            assert stats['count'] == r.count()
