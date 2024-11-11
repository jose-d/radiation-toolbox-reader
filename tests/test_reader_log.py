import tempfile

from collections import OrderedDict
from pathlib import Path

from osgeo import gdal

from reader.safecast import SafecastReader as Reader
from tests.test_reader import TestReader

class TestReaderLog(TestReader):
    dataFile = "./tests/data/sample.log"
    ref_count = 941
    def test_001(self):
        """Check number of records."""
        self._count(Reader, self.dataFile, self.ref_count)

    def test_002(self):
        """Check attribute definitions."""
        ref = ['device', 'device_id', 'date_time', 'cpm', 'pulses5s',
               'pulses_total', 'validity', 'lat_deg', 'hemisphere',
               'long_deg', 'east_west', 'altitude', 'gps_validity',
               'sat', 'hdop', 'checksum']
        self._attributeDefs(Reader, self.dataFile, ref, args={"computed_attributes": False})
        ref += [
            'ader_microsvh', 'time_local', 'speed_kmph', 'dose_increment',
            'time_cumulative', 'dose_cumulative', 'dist_cumulative'
        ]

        self._attributeDefs(Reader, self.dataFile, ref, args={"computed_attributes": True})

    def test_003(self):
        """Check selected records."""
        # check first item
        ref = OrderedDict({
            'device': '$BNRDD',
            'device_id': '2849',
            'date_time': '2019-01-01T13:00:36Z',
            'cpm': 31,
            'pulses5s': 2,
            'pulses_total': 1049,
            'validity': 'A',
            'lat_deg': '5038.5187',
            'hemisphere': 'N',
            'long_deg': '01351.3902',
            'east_west': 'E',
            'altitude': 256.2,
            'gps_validity': 'A',
            'sat': 6,
            'hdop': 151,
            'checksum': '*48'
        })
        self._record(Reader, self.dataFile, ref, args={"computed_attributes": False})
        # check first item including computed attributes
        ref.update(OrderedDict([
            ('ader_microsvh', 0.0718562874251496),
            ('time_local', '14:00:36'),
            ('speed_kmph', 0),
            ('dose_increment', 0),
            ('time_cumulative', '00:00:00'),
            ('dose_cumulative', 0),
            ('dist_cumulative', 0),
        ]))
        self._record(Reader, self.dataFile, ref, args={"computed_attributes": True})
        # check last item including computed attributes
        ref = OrderedDict({
            'device': '$BNRDD',
            'device_id': '2849',
            'date_time': '2019-01-01T14:19:10Z',
            'cpm': 41,
            'pulses5s': 5,
            'pulses_total': 8051,
            'validity': 'A',
            'lat_deg': '5038.5231',
            'hemisphere': 'N',
            'long_deg': '01351.3827',
            'east_west': 'E',
            'altitude': 287.7,
            'gps_validity': 'A',
            'sat': 8,
            'hdop': 103,
            'checksum': '*4B',
            'ader_microsvh': 0.179640718562874,
            'time_local': '15:19:10',
            'speed_kmph': 0.863856214386694,
            'dose_increment': 0.00024950099800399167,
            'time_cumulative': '01:18:34',
            'dose_cumulative': 0.35262890884896525,
            'dist_cumulative': 3051.8665013830273,
        })
        self._record(Reader, self.dataFile, ref, args={"computed_attributes": True}, idx=self.ref_count-1)

    def test_004(self):
        """Test CSV export."""
        self._exportCSV(Reader, self.dataFile)

    def test_005(self):
        """Test GDAL-based export."""
        self._exportGDAL(Reader, self.dataFile, 'GPKG', 'gpkg')
        self._exportGDAL(Reader, self.dataFile, 'SQLite', 'db')

    def test_006(self):
        """Tests stats and count consistency."""
        self._stats(Reader, self.dataFile)

    def test_007(self):
        """Test export on multiple files."""
        counts = {}
        driver_name = "SQLite"
        temp_path = f"{tempfile.mktemp()}.db"
        files = list(Path(self.dataFile).parent.glob("*.log"))
        for fn in files:
            with Reader(fn) as r:
                counts[fn.stem] = r.count()
                r.export(temp_path, driver_name, append=True)

        # check result
        ds = self._openDS(temp_path, driver_name)
        ref_layer_count = len(files) if r.metadata is None else len(files) + 1

        assert self._layerCount(ds) == ref_layer_count
        for idx in range(ds.GetLayerCount()):
            if ds.IsLayerPrivate(idx) is True:
                continue

            lyr = ds.GetLayer(idx)
            if lyr.GetName() == 'safecast_metadata':
                assert lyr.GetFeatureCount() == len(files)
            else:
                assert lyr.GetFeatureCount() == counts[lyr.GetName()]
        ds.Close()
