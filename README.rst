Juju Charm Tools
================

|build|

.. |build| image:: https://snapcraft.io/charm/badge.svg
    :target: https://snapcraft.io/charm

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
          - CHARM_INTERFACES_DIR: $CRAFT_PROJECT_DIR/interfaces/
          - CHARM_LAYERS_DIR: $CRAFT_PROJECT_DIR/layers/

    bases:
      - build-on:
          - name: ubuntu
            channel: "22.04"
            architectures: [amd64]
        run-on:
          - name: ubuntu
            channel: "22.04"
            architectures: [amd64]
      - build-on:
          - name: ubuntu
            channel: "22.04"
            architectures: [arm64]
        run-on:
          - name: ubuntu
            channel: "22.04"
            architectures: [arm64]
      - build-on:
          - name: ubuntu
            channel: "22.04"
            architectures: [ppc64el]
        run-on:
          - name: ubuntu
            channel: "22.04"
            architectures: [ppc64el]
      - build-on:
          - name: ubuntu
            channel: "22.04"
            architectures: [s390x]
        run-on:
          - name: ubuntu
            channel: "22.04"
            architectures: [s390x]

Note that this ``charmcraft.yaml`` specifies the 3.x track for charm-tools, as
it's building on the 22.04 base (jammy) which is Python 3.10.

Binary builds
-------------

To help with reducing the installation dependencies of python modules on the
runtime systems, binary wheels may be built.  These are architecture-dependent
and so the 'build-on/run-on' bases specification (as shown above) **must** be
used if the charm must support multiple architectures. An example of when a
binary wheel is preferable is for the cryptography module, which, for recent
releases, requires a rust compiler installed on the target system to build the
module if a binary wheel is not used.  Use the ``--binary-wheels`` option when
using ``charm build``.

Snap Tracks/Version
-------------------

Due to the complexity of building reactive charms across multiple Python
versions, the tool has been split into two tracks:

1. The 2.x track is hard coded to build using Python 3.6, which is the
   equivalent of using Ubuntu 18.04 (Bionic) as a base.
2. The 3.x track uses the Python version from the build environement.  This
   means that it is useful for building charms from 20.04 onwards, but does
   mean that a separate build (as indicated above) may need to be used for each
   base the the charm should run on.

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
