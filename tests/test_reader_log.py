from reader.safecast import SafecastReader as Reader
from tests.test_reader import TestReader

class TestReaderLog(TestReader):
    dataFile = "./tests/data/sample.log"
    def test_001(self):
        """Check number of records."""
        self._count(Reader, self.dataFile, 941)

    def test_002(self):
        """Check first record."""
        ref = ['$BNRDD',
               '2849',
               '2019-01-01T13:00:41Z',
               '29',
               '0',
               '1049',
               'A',
               '5038.5193',
               'N',
               '01351.3901',
               'E',
               '256.10',
               'A',
               '7',
               '110*42']
        rec = self._record(Reader, self.dataFile, ref)

