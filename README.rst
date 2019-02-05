Juju Charm Tools
================

|travis| |build|

.. |travis| image:: https://travis-ci.org/juju/charm-tools.svg
    :target: https://travis-ci.org/juju/charm-tools
.. |build| image:: https://build.snapcraft.io/badge/juju/charm-tools.svg
    :target: https://build.snapcraft.io/user/juju/charm-tools

This is a collection of tools to make writing Juju charms easier. See Juju's
home page for more information.

https://jujucharms.com/


Installation
------------

To run the latest stable release, use::

    sudo snap install charm --classic

You'll also almost certainly want to install Juju as well::

    sudo snap install juju --classic

If you want to run the latest pre-release versions, you can use the
other snap channels.  For example::

    sudo snap install charm --channel=edge

The available channels are: stable, candidate, beta, and edge.

  Note: While charm-tools is also available on PyPI (for use as a Python
  dependency) and is generally kept up to date there with stable releases,
  the snap should always be used instead, if at all possible.


Usage
-----

To see a list of available commands, use::

    charm help

The most commonly used commands are the charm life-cycle commands::

    charm create    # create a new charm
    charm build     # build a charm using layers
    charm proof     # validate a charm via the linter
    charm login     # login to the charm store
    charm push      # push a charm to the store
    charm release   # release a pushed charm to the public
    charm show      # show information about a charm in the store
