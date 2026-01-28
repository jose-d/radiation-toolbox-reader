import re
from collections import OrderedDict

from . import RecordBase, ReaderBase
from .exceptions import ReaderError
from .logger import ReaderLogger

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
    _encoding = 'utf-8-sig'
    _encoding_candidates = ['latin1']

    def _readHeader(self):
        """Read header file.
        """
        section = "header_data"
        metadata = {
            section: {}
        }
        while True:
            pos_before = self._fd.tell()
            line = self._fd.readline()
            if line == '\n':
                # skip empty lines
                continue
            line = line.rstrip()
            if line.startswith('/*'):
                continue
            elif line.startswith('PA '):
                # first data record
                self._fd.seek(pos_before)
                break
            elif not line:
                break
            # process metadata
            try:
                for kv in line.split(';'):
                    k, v = map(lambda x: x.strip(), kv.split(' ', 1))
                    metadata[section][k] = v
            except ValueError:
                # try Vx.y
                matched = re.search(r'V\d+\.\d+', line)
                if matched:
                    k = 'V'
                    v = line[1:].strip()
                else:
                    k = line.strip()
                    v = None
                metadata[section][k] = v

        version = None
        try:
            version = metadata['header_data']['V']
            if version.startswith('1'):
                raise ReaderError(f"Unsupported ERS version {version}")
            metadata['version'] = version
            del metadata['header_data']['V']
        except KeyError:
            pass

        if version is None:
            ReaderLogger.warning("Unable to determine ERS version")

        return metadata

    def _next_data_item(self):
        """Read next data record.
        """
        while True:
            line = self._fd.readline()
            if line == '\n':
                # skip empty line
                continue
            if line == '':
                # EOF
                return None
            line = line.rstrip()
            if line.startswith('PA '):
                record = ERSRecord()
                for it in line.split(';'):
                    try:
                        k, v = map(lambda x: x.strip(), it.strip().split(' ', 1))
                    except ValueError:
                        k = it.strip()
                        v = ''
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
