import os
import inspect
import csv
import copy

from contextlib import AbstractContextManager
from types import TracebackType
from collections import OrderedDict

from .exceptions import ReaderError

__version__ = "1.0.0"

class ReaderBase(AbstractContextManager['ReaderBase']):
    """Base reader class.
    """
    _scan_attributes = True

    def __init__(self, filepath, rb=False):
        self._filepath = filepath

        try:
            flag = 'rb' if rb else 'r'
            self._fd = open(self._filepath, flag)
        except IOError as e:
            raise ReaderError("{}".format(e))

        # attribute names & data types
        self._attributes = None
        self._attributes = self.attributeDefs()

    def __del__(self):
        """Destructor, close input file.
        """
        if self._fd:
            self._fd.close()

    def __enter__(self):
        """Enter context manager protocol.
        """
        super().__enter__()
        return self

    def __exit__(self,
                 exc_type: None | type[BaseException],
                 exc_val: None | BaseException,
                 exc_tb: None | TracebackType,
                 /):
        """Exit context manager protocol.
        """
        super().__exit__(exc_type, exc_val, exc_tb)

    def count(self):
        """Count data items.
        """
        raise NotImplementedError()

    def _next_data_item(self):
        """Read next data item.
        """
        raise NotImplementedError()

    def __iter__(self):
        """Loop through features.
        """
        self._reset()
        return self

    def __next__(self):
        """Return next record.
        """
        item = self._next_data_item()
        if not item:
            raise StopIteration

        return item

    def _reset(self):
        """Reset reading.
        """
        self._fd.seek(0, 0)

    def _count(self, counter):
        """Count data items.

        Inspired by http://stackoverflow.com/questions/845058/how-to-get-line-count-cheaply-in-python.

        :param counter: counter string
        """
        self._reset()

        lines = 0
        buf_size = 1024 * 1024
        read_f = self._fd.read # loop optimization

        buf = read_f(buf_size)
        while buf:
            lines += buf.count(counter)
            buf = read_f(buf_size)

        return lines

    def _readAttributeDefs(self, def_file):
        """Read attribute definitions.

        :param str def_file: CSV defintion file
        """
        def addAttribute(row):
            attrbs = {
                row['attribute']: {
                    "type" : eval(row['type'])
                }
            }
            if 'alias' in row and row['alias']:
                attrbs[row['attribute']]['alias'] = row['alias'].replace('_', ' ')

            return attrbs

        if os.path.exists(def_file):
            with open(def_file) as fd:
                def_attrbs = list(csv.DictReader(fd, delimiter=';'))
        else:
            raise ReaderError(f"Definition file {def_file} not found")

        self._attributes = OrderedDict()
        if self._scan_attributes:
            # limit attributes based on input file (first feature) - ERS/PEI format specific
            self._reset()
            item = self._next_data_item()
            self._reset()
            for name in item.keys():
                # first try full name match
                found = False
                for row in def_attrbs:
                    if row['attribute'] == name:
                        self._attributes.update(addAttribute(row))
                        found = True
                        break
                if found:
                    continue
                for row in def_attrbs:
                    # full name match is not required see
                    # https://gitlab.com/opengeolabs/qgis-radiation-toolbox-plugin/issues/41#note_136183930
                    if row['attribute'] == name[:len(row['attribute'])] or name == row['attribute'][:len(name)]:
                        row_modified = copy.copy(row)
                        row_modified['attribute'] = name # force (full) attribute name from input file
                        if row_modified['alias']:
                            row_modified['alias'] = '{} ({})'.format(name, row_modified['alias'])
                        self._attributes.update(addAttribute(row_modified))
                        break
        else:
            # add all attributes
            for row in def_attrbs:
                self._attributes.update(addAttribute(row))

    def attributeDefs(self):
        """Get attribute definitions from file.
        """
        if self._attributes is None:
            self._readAttributeDefs(self._definitionCSVFile)

        return self._attributes

    @property
    def _definitionCSVFile(self):
        return os.path.join(
            os.path.dirname(__file__),
            os.path.splitext(inspect.getfile(self.__class__))[0] + '.csv'
        )
