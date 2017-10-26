Juju Charm Tools
================

.. image:: https://travis-ci.org/juju/charm-tools.svg
    :target: https://travis-ci.org/juju/charm-tools

This is a collection of tools to make writing Juju charms easier. See Juju's
home page for more information.

https://jujucharms.com/


Installation
------------

To run the latest stable release, use::

    sudo snap install charm

You'll also almost certainly want to install Juju as well::

    sudo snap install juju --classic

If you want to run the latest pre-release versions, you can use the
other snap channels: candidate, beta, and edge.  For example::

    sudo snap install charm --channel=edge


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
