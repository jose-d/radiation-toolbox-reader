import tempfile

from collections import OrderedDict
from pathlib import Path

from osgeo import gdal

from reader import ComputedAttributes
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
        self._attributeDefs(Reader, self.dataFile, ref, args={"computed_attributes": ComputedAttributes.No})

        ref += ['ader_microsvh', 'time_local']
        self._attributeDefs(Reader, self.dataFile, ref, args={"computed_attributes": ComputedAttributes.PerRecordOnly})

        ref += [
            'speed_kmph', 'dose_increment',
            'time_cumulative', 'dose_cumulative', 'dist_cumulative'
        ]
        self._attributeDefs(Reader, self.dataFile, ref, args={"computed_attributes": ComputedAttributes.All})

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
        self._record(Reader, self.dataFile, ref, args={"computed_attributes": ComputedAttributes.No})
        # check first item including computed attributes
        ref.update(OrderedDict([
            ('ader_microsvh', 0.0718562874251496),
            ('time_local', '14:00:36'),
        ]))
        self._record(Reader, self.dataFile, ref, args={"computed_attributes": ComputedAttributes.PerRecordOnly})
        ref.update(OrderedDict([
            ('speed_kmph', 0),
            ('dose_increment', 0),
            ('time_cumulative', '00:00:00'),
            ('dose_cumulative', 0),
            ('dist_cumulative', 0),
        ]))
        self._record(Reader, self.dataFile, ref, args={"computed_attributes": ComputedAttributes.All})
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
        self._record(Reader, self.dataFile, ref, args={"computed_attributes": ComputedAttributes.All}, idx=self.ref_count-1)

    def test_004(self):
        """Test CSV export."""
        self._exportCSV(Reader, self.dataFile)

    def test_005(self):
        """Test GDAL-based export."""
        self._exportGDAL(Reader, self.dataFile, 'GPKG', 'gpkg')
        self._exportGDAL(Reader, self.dataFile, 'SQLite', 'db')

        # check duplication
        self._exportGDAL(Reader, self.dataFile, 'SQLite', 'db', repeat=True)

    def test_006(self):
        """Tests stats and count consistency."""
        self._stats(Reader, self.dataFile)

    def _import_multiple_files(self, single_table):
        counts = {}
        driver_name = "SQLite"
        temp_path = f"{tempfile.mktemp()}.db"
        files = list(Path(self.dataFile).parent.glob("*.log"))
        ds = None
        for fn in files:
            with Reader(fn) as r:
                counts[fn.stem] = r.count()
                ds = r.export_memory(ds, single_table=single_table)
        gdal.VectorTranslate(temp_path, ds, format=driver_name)

        # check result
        ds = self._openDS(temp_path, driver_name)
        layer_count = len(files) if single_table is None else 1
        ref_layer_count = layer_count if r.metadata is None else layer_count + 1

        assert self._layerCount(ds) == ref_layer_count
        for idx in range(ds.GetLayerCount()):
            if ds.IsLayerPrivate(idx) is True:
                continue

            lyr = ds.GetLayer(idx)
            if lyr.GetName().endswith('metadata'):
                assert lyr.GetFeatureCount() == len(files)
            else:
                if single_table is not None:
                    assert lyr.GetName() == single_table
                    assert lyr.GetFeatureCount() == sum(list(counts.values()))
                else:
                    assert lyr.GetFeatureCount() == counts[lyr.GetName()]
        ds.Close()

    def test_007(self):
        """Test export on multiple files."""
        self._import_multiple_files(single_table=None)
        self._import_multiple_files(single_table='data')

    def test_008(self):
        """Test invalid date."""
        ref = OrderedDict({
            'device': '$CZRDD',
            'device_id': '0073',
            'date_time': '2024-08-19T05:35:34Z',
            'cpm': 41,
            'pulses5s': 3,
            'pulses_total': 1329,
            'validity': 'A',
            'lat_deg': '4923.9780',
            'hemisphere': 'N',
            'long_deg': '01316.7036',
            'east_west': 'E',
            'altitude': 413.18,
            'gps_validity': 'A',
            'sat': 20,
            'hdop': 69,
            'checksum': '*54',
            'ader_microsvh': 0.1077844311377244,
            'time_local': 'unknown',
            'speed_kmph': 3.5328649782013257,
            'dose_increment': 8.9820359281437e-05,
            'time_cumulative': '00:00:03',
            'dose_cumulative': 8.9820359281437e-05,
            'dist_cumulative': 2.9440541485011047
        })
        self._record(Reader, Path(self.dataFile).parent / "sample_1.log",
                     ref, args={"computed_attributes": ComputedAttributes.All}, idx=1)
