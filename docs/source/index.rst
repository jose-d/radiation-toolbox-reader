Radiation Toolbox Reader
========================

Python package designed for reading data formats used by radiation
monitoring devices.

Currently supported formats (reading only):

* Safecast LOG
* ERS

.. code-block:: python

   from radiation_toolbox_reader.safecast import SafecastReader as Reader
   
   with Reader("sample.log") as r:
       print(r.count())

.. toctree::
    :maxdepth: 2

    usage.ipynb
  
Funding
-------

`SURO <https://www.suro.cz/en>`__, Czech Republic

Developed by `OpenGeoLabs <https://opengeolabs.cz/en/home>`__
