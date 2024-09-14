from collections import OrderedDict

from reader.ers import ERSReader as Reader
from tests.test_reader import TestReader

class TestReaderLog(TestReader):
    dataFile = "./tests/data/sample.ers"
    def test_001(self):
        """Check number of records."""
        self._count(Reader, self.dataFile, 2692)

    def test_002(self):
        """Check first record."""
        ref = OrderedDict({
            'PA': 'demo_point-0001',
            'CD': '2015-04-01',
            'CT': '12:12:12',
            'PE': '14.960050',
            'PN': '38.383420',
            'PH': '49',
            '': 'AD_K-40 2.512445e+02',
            'AD_U-238': '9.557773e+01',
            'AD_Th-232': '1.181432e+01',
            'AA_Cs-137': '1.219730e+03',
            'DHSR': '5.766440e-02'
        })
        rec = self._record(Reader, self.dataFile, ref)

