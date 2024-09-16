from collections import OrderedDict

from reader.safecast import SafecastReader as Reader
from tests.test_reader import TestReader

class TestReaderLog(TestReader):
    dataFile = "./tests/data/sample.log"
    def test_001(self):
        """Check number of records."""
        self._count(Reader, self.dataFile, 941)

    def test_002(self):
        """Check attribute definitions."""
        ref = ['device', 'device_id', 'date_time', 'cpm', 'pulses5s',
               'pulses_total', 'validity', 'lat_deg', 'hemisphere',
               'long_deg', 'east_west', 'altitude', 'gps_validity',
               'sat', 'hdop', 'checksum']
        self._attributeDefs(Reader, self.dataFile, ref)

    def test_003(self):
        """Check first record."""
        ref = OrderedDict({
            'device': '$BNRDD',
            'device_id': '2849',
            'date_time': '2019-01-01T13:00:41Z',
            'cpm': 29,
            'pulses5s': 0,
            'pulses_total': 1049,
            'validity': 'A',
            'lat_deg': '5038.5193',
            'hemisphere': 'N',
            'long_deg': '01351.3901',
            'east_west': 'E',
            'altitude': 256.1,
            'gps_validity': 'A',
            'sat': 7,
            'hdop': 110,
            'checksum': '*42'
        })
        self._record(Reader, self.dataFile, ref)

