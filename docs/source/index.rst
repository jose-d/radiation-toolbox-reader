Radiation Toolbox Reader
========================

Python package designed for reading data formats used by radiation
monitoring devices.

Currently supported formats (reading only):

* Safecast LOG
* ERS

Usage
-----

Import a reader class:

.. code-block:: python

   from reader.safecast import SafecastReader as Reader

Input data file is read by:

.. code-block:: python

   r = Reader("./tests/data/sample.log")


Number of records is returned by the ``count()`` method:

.. code-block:: python

   r.count()


Records may be read in a for loop:

.. code-block:: python

   for rec in r:
       print(rec)

In the example above the reading of the Safecast LOG format is
presented. Similarly, the ERS format can be read using:

.. code-block:: python

   from reader.ers import ERSReader as Reader

Funding
-------

`SURO <https://www.suro.cz/en>`__, Czech Republic

Developed by `OpenGeoLabs <https://opengeolabs.cz/en/home>`__
