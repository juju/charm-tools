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

STATUS
======

charm-tools is now largely in *maintenance mode*, as the charms.reactive method
of building charms is deprecated in favour of using the `operator
framework <https://juju.is/docs/sdk>`_.  This means that, generally, only bug
fixes or features required to make charm-tools work better with charmcraft will
be considered.

charm-tools should only be used to maintain existing charms.reactive charms,
and not to start *new* charms.  The `operator framework
<https://juju.is/docs/sdk>`_ should be used for new charms.

Also, it is increasingly more difficult to get a single Python code base to
build source charms that will work across Xenial to Jammy+ (e.g. Python 3.5 to
Python 3.10) due to Python versions < 3.7 being EOL. There are a number of
strategies to deal with that, and it generally involves pinning python modules
for various different versions of Python when building the charm.  As the
`charmhub <https://charmhub.io/>`_ supports architecture-specific builds of
charms, charm-tools also offers binary charms, which are charms with
pre-compiled binary wheels that do not need build environments on the target
system.  See ``charm build --help`` for more details.

charm-tools is available as a snap and can be used within a ``charmcraft.yaml``
to build a reactive charm suitable for uploading to the
`charmhub <https://charmhub.io/>`_:

.. code-block:: yaml

    type: charm

    parts:
      charm:
        source: src/
        plugin: reactive
        build-snaps:
          - charm/3.x/stable
        build-environment:
          - CHARM_INTERFACES_DIR: /root/project/interfaces/
          - CHARM_LAYERS_DIR: /root/project/layers/

    bases:
      - build-on:
          - name: ubuntu
            channel: "22.04"
            architectures:
              - amd64
        run-on:
          - name: ubuntu
            channel: "22.04"
            architectures: [amd64, s390x, ppc64el, arm64]
          - name: ubuntu
            channel: "22.10"
            architectures: [amd64, s390x, ppc64el, arm64]

Note that this ``charmcraft.yaml`` specifies the 3.x track for charm-tools, as
it's building on the 22.04 base (jammy) which is Python 3.10.

Snap Tracks/Version
-------------------

Due to the complexity of building reactive charms across multiple Python
versions, the tool has been split into two tracks:

1. For charms targetting Ubuntu focal (20.04) or earlier: 2.x
2. For charms targetting Ubuntu jammy (22.04) or later: 3.x

Other charms.reactive projects
------------------------------

* `layer-basic <https://github.com/juju-solutions/layer-basic>`_ - the base layer in all ``charms.reactive`` charms.
* `charms.reactive <https://github.com/juju-solutions/charms.reactive>`_ - core libraries used in building reactive charms.
* `layer-index <https://github.com/juju/layer-index>`_ - formal layer index.

Installation
============

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
