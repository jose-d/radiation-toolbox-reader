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
