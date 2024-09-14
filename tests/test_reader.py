class TestReader:
    @staticmethod
    def _count(reader, filename, count):
        with reader(filename) as r:
            assert r.count() == count

    @staticmethod
    def _attributeDefs(reader, filename):
        with reader(filename) as r:
            return r.attributeDefs()

    @staticmethod
    def _record(reader, filename, ref):
        with reader(filename) as r:
            assert r.__next__() == ref
