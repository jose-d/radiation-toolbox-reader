from collections import OrderedDict

from . import RecordBase, ReaderBase
from .exceptions import ReaderError

class ERSRecord(RecordBase):
    @property
    def point(self):
        """Get point coordinates.

        :return tuple: point coordinates (x, y)
        """
        return (float(self['PE']), float(self['PN']))

class ERSReader(ReaderBase):
    """ERS reader class.
    """
    def _next_data_item(self):
        """Read next data record.
        """
        while True:
            line = self._fd.readline().rstrip()
            if not line:
                # EOF
                return None
            if line.startswith('PA '):
                record = ERSRecord()
                for it in line.split(';'):
                    k, v = map(lambda x: x.strip(), it.strip().split(' ', 1))
                    if k == '#S':
                        # see https://gitlab.com/opengeolabs/qgis-radiation-toolbox-plugin/issues/41#note_137813150
                        idx = 1
                        for s_v in v.strip().split(' '):
                            record['{}{}'.format(k, idx)] = s_v
                            idx += 1
                    else:
                        # https://gitlab.com/opengeolabs/qgis-radiation-toolbox-plugin/issues/38#note_153255013
                        if ',' in v and k == 'DHSR':
                            v = v.replace(',', '.')
                        record[k] = self._attributes[k]['type'](v) if self._attributes else v

                if hasattr(self, "_num_attributes_read") and len(record.keys()) != self._num_attributes_read:
                    ReaderLogger.warning(f"Invalid record skipped (file {self._filepath.name}): {line}")
                    continue

                return record

    def count(self):
        """Count data records.
        """
        return self._count('PA ')

    def _getPoint(self, item):
        """Get point coordinates.

        :param OrderedDict: item

        :return tuple: point coordinates (x, y)
        """
