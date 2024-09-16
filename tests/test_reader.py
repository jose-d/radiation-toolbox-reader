class TestReader:
    @staticmethod
    def _count(reader, filename, count):
        with reader(filename) as r:
            assert r.count() == count

    @staticmethod
    def _attributeDefs(reader, filename, ref):
        with reader(filename) as r:
            assert list(r.attributeDefs().keys()) == ref

    @staticmethod
    def _record(reader, filename, ref):
        with reader(filename) as r:
            assert r.__next__() == ref
