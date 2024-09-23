import tempfile
import csv
import os

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
                    if abs(v-rec2[k]) > 1e-12:
                        return False
                else:
                    if v != rec2[k]:
                        return False
            return True

        with reader(filename, **args) as r:
            if idx == 0:
                assert comp_record(next(r), ref)
            else:
                for i in range(idx+1):
                    item = r.__next__()
                assert comp_record(item, ref)

    @staticmethod
    def _exportCSV(reader, filename):
        def dict2str(item):
            for k in item:
                item[k] = str(item[k])

        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            with reader(filename) as r:
                r.toCSV(tmp.name)

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
