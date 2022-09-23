.. Charm Tools documentation master file, created by
   sphinx-quickstart on Tue Feb 19 14:28:07 2019.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Charm Tools documentation
=========================

The `charm` command includes several subcommands used to build and maintain,
`Juju Charms`_ written in the `reactive framework`_, which are Open Source
encapsulated operations logic for managing software in the cloud or bare-metal
servers using cloud-like APIs.

To ensure charms are built in a clean environment and with Python wheels
compatible with the target series for the cherm, we recommend the use of the
`charmcraft`_ tool and the `reactive plugin`_.

**NOTE** For new charms the preferred approach is to use the `ops framework`_.

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
.. _reactive framework: https://charmsreactive.readthedocs.io/en/latest/
.. _charmcraft: https://juju.is/docs/sdk/charmcraft
.. _reactive plugin:
   https://juju.is/docs/sdk/pack-your-reactive-based-charm-with-charmcraft
.. _ops framework: https://juju.is/docs/sdk/ops
