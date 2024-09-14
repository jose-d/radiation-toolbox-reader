class TestReader:
    @staticmethod
    def _count(reader, filename, count):
        r = reader(filename)
        assert r.count() == count

    @staticmethod
    def _attributeDefs(reader, filename):
        r = reader(filename)
        return r.attributeDefs()

    @staticmethod
    def _record(reader, filename, ref):
        r = reader(filename)
        assert r.__next__() == ref
