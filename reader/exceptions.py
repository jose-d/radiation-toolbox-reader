"""Safecast Reader Library

(C) 2015-2016 by OpenGeoLabs s.r.o.

Read the file LICENCE.md for details.

.. sectionauthor:: Martin Landa <martin.landa opengeolabs.cz>
"""
                                        
class ReaderError(Exception):
    """Reader error class.
    """
    pass

class ReaderExportError(Exception):
    """Reader error class when exporting data.
    """
    pass

class ReaderExportDuplication(Exception):
    """Reader error class on duplicated layer when exporting data.
    """
    def __init__(self, layer_name):
        self.msg = f"Duplicated layer '{layer_name}'. Export skiped."

    def __str__(self):
        return self.msg
