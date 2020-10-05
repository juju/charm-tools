.. Charm Tools documentation master file, created by
   sphinx-quickstart on Tue Feb 19 14:28:07 2019.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Charm Tools documentation
=========================

The `charm` command includes several subcommands used to build, maintain,
and release `Juju Charms`_, which are Open Source encapsulated operations
logic for managing software in the cloud or bare-metal servers using
cloud-like APIs.

Installation is easy with snaps:

.. code-block:: bash

    snap install --classic charm

Reference for the various available commands can be found below, or via
the command-line with:

.. code-block:: bash

    charm help


.. toctree::
   :maxdepth: 2
   :caption: Reference

   commands
   tactics
   reproducible-charms


.. toctree::
   :caption: Project
   :glob:
   :maxdepth: 3

   contributing
   changelog



Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`


.. _Juju Charms: https://docs.jujucharms.com/
