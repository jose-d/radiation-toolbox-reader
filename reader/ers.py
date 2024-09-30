from collections import OrderedDict

from . import ReaderBase
from .exceptions import ReaderError

class ERSReader(ReaderBase):
    """ERS reader class.
    """
    def _next_data_item(self):
        """Read next data item.
        """
        while True:
            line = self._fd.readline().rstrip()
            if not line:
                # EOF
                return None
            if line.startswith('PA '):
                item = OrderedDict()
                for it in line.split(';'):
                    k, v = map(lambda x: x.strip(), it.strip().split(' ', 1))
                    if k == '#S':
                        # see https://gitlab.com/opengeolabs/qgis-radiation-toolbox-plugin/issues/41#note_137813150
                        idx = 1
                        for s_v in v.strip().split(' '):
                            item['{}{}'.format(k, idx)] = s_v
                            idx += 1
                    else:
                        # https://gitlab.com/opengeolabs/qgis-radiation-toolbox-plugin/issues/38#note_153255013
                        if ',' in v and k == 'DHSR':
                            v = v.replace(',', '.')
                        item[k] = self._attributes[k]['type'](v) if self._attributes else v

                return item

    def count(self):
        """Count data items.
        """
        return self._count('PA ')

    def _get_point(self, item):
        """Get point coordinates.

        :param OrderedDict: item

        :return tuple: point coordinates (x, y)
        """
        return (float(item['PE']), float(item['PN']))
