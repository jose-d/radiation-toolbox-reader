from collections import OrderedDict

from reader.ers import ERSReader as Reader
from tests.test_reader import TestReader

class TestReaderLog(TestReader):
    dataFile = "./tests/data/sample.ers"
    def test_001(self):
        """Check number of records."""
        self._count(Reader, self.dataFile, 2692)

    def test_002(self):
        """Check attribute definitions."""
        ref = ['PA', 'CD', 'CT', 'PE', 'PN', 'PH',
               'AD_K-40', 'AD_U-238', 'AD_Th-232',
               'AA_Cs-137', 'DHSR']
        self._attributeDefs(Reader, self.dataFile, ref)

    def test_003(self):
        """Check first record."""
        ref = OrderedDict({
            'PA': 'demo_point-0001',
            'CD': '2015-04-01',
            'CT': '12:12:12',
            'PE': 14.960050,
            'PN': 38.383420,
            'PH': 49,
            'AD_K-40': 251.2445,
            'AD_U-238': 95.57773,
            'AD_Th-232': 11.81432,
            'AA_Cs-137': 1219.730,
            'DHSR': 0.05766440
        })
        self._record(Reader, self.dataFile, ref)

