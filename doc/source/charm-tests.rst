==============
Charm Testing
==============

Intro
=====

**DRAFT**

Juju has been designed from the start to foster a large collection of
"charms". Charms are expected to number in the thousands, and be self
contained, with well defined interfaces for defining their relationships
to one another.

Because this is a large complex system, not unlike a Linux software
distribution, there is a need to test the charms and how they interact
with one another. This specification  defines a plan for implementing
a simple framework to help this happen.

Static tests have already been implemented in the ``charm proof`` command
as part of ``charm-tools``. Any static testing of charms is beyond the
scope of this specification.

Phase 1 - Generic tests
=======================

All charms share some of the same characteristics. They all have a
yaml file called ``metadata.yaml``, and when deployed, juju will always
attempt to progress the state of the service from install to config to
started. Because of this, all charms can be tested using the following
algorithm::

 deploy charm
 while state != started
   if timeout is reached, FAIL
   if state == install_error, config_error, or start_error, FAIL
   if state == started, PASS

Other generic tests may be identified, so a collection of generic tests should be the focus of an implementation.

Note that this requirement is already satisfied by Mark Mims' jenkins tester:
http://charmtests.markmims.com/

Phase 2 - Charm Specific tests
==============================

Charm authors will have the best insight into whether or not a charm is
working properly.

To facilitate tests attached to charms, a simple structure will be
utilized to attach tests to charms. Under the charm root directory,
a sub-directory named 'tests' will be scanned by a test runner for
executable files matching the glob ``*.test``. These will be run in
lexical order by the test runner, with a predictible environment. The
tests can make the following assumptions:

* A minimal install of the release of Ubuntu which the charm is targetted
  at will be available.
* A version of juju is installed and available in the system path.
* the default environment is bootstrapped
* The CWD is the charm root directory
* Full network access to deployed nodes will be allowed.
* the bare name of any charm in arguments to juju will be resolved to a
  charm url and/or repository arguments of the test runner's choice. This
  means that if you need mysql, you do not do ``juju deploy cs:mysql`` or
  ``juju deploy --repository ~/charms local:mysql``, but just ``juju deploy
  mysql``. A wrapper will resolve this according to the circumstances of
  the test.
* a special sub-command of juju, ``deploy-previous``, will deploy the
  last successfully tested charm instead of the one from the current
  delta. This will allow testing upgrade-charm.

The following restrictions will be enforced:

* bootstrap and destroy-environment will be unavailable
* ``~/.juju`` will not be accessible to the tests

The following restrictions may be enforced:

* Internet access will be restricted from the testing host.

If present, tests/requirements.yaml will be read to determine packages
that need to be installed in order to facilitate the tests. The packages
can *only* be installed from the official, default Ubuntu archive for the
release which the charm is intended for. The format of requirements.yaml
is as such::

    packages: [ package1, package2, package3 ]

If a tool is needed to perform a test and not available in the Ubuntu
archive, it can also be included in the ``tests/`` directory, as long
as the file which contains it does not end in ``.test``. Note that build
tools cannot be assumed to be available on the testing system.

Test Runner
===========

A test runner will periodically poll the collection of charms for changes
since the last test run. If there have been changes, the entire set of
changes will be tested as one delta. This delta will be recorded in the
test results in such a way where a developer can repeat the exact set
of changes for debugging purposes.

All of the charms will be scanned for tests in lexical order by
series, charm name, branch name. Non official charms which have not
been reviewed by charmers will not have their tests run until the test
runner's restrictions have been vetted for security, since we will be
running potentially malicious code. It is left to the implementor to
determine what mix of juju, client platform, and environment settings
are appropriate, as all of these are variables that will affect the
running charms, and so may affect the outcome.

Example
=======

Deploy requirements and Poll
----------------------------

The following example test script uses a tool that is not widely available
yet, ``get-unit-info``. In the future enhancements should be made to
juju core to allow such things to be made into plugins. Until then,
it can be included in each test dir that uses it, or we can build a
package of tools that are common to tests.::

    #!/bin/sh

    set -e

    teardown() {
        juju destroy-service memcached
        juju destroy-service mysql
        juju destroy-service mediawiki
        if [ -n "$datadir" ] ; then
            if [ -f $datadir/passed ]; then
                rm -r $datadir
            else
                echo $datadir preserved
            fi
        fi
    }
    trap teardown EXIT


    juju deploy mediawiki
    juju deploy mysql
    juju deploy memcached
    juju add-relation mediawiki:db mysql:db
    juju add-relation memcached mediawiki
    juju expose mediawiki

    for try in `seq 1 600` ; do
        host=`juju status | tests/get-unit-info mediawiki public-address`
        if [ -z "$host" ] ; then
            sleep 1 
        else
            break
        fi
    done

    if [ -z "$host" ] ; then
        echo ERROR: status timed out 
        exit 1
    fi

    datadir=`mktemp -d ${TMPDIR:-/tmp}/wget.test.XXXXXXX`
    echo INFO: datadir=$datadir

    wget --tries=100 --timeout=6 http://$host/ -O - -a $datadir/wget.log | grep -q '<title>'

    if [ $try -eq 600 ] ; then
        echo ERROR: Timed out waiting.
        exit 1
    fi

    touch $datadir/passed

    trap - EXIT
    teardown

    echo INFO: PASS
    exit 0

