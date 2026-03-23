Changelog
=========

Current release
^^^^^^^^^^^^

* Add ability to specify constraints for `WheelhouseTactic` (#693)
* Fix `charm-tools` version (#692)
* Pin `setuptools` < 82 and drop archived `vergit` dependency (#689)
* Enforce `cached_charm_tools_version()` to return a dict (#688)
* Add --ignore-requires-python (#686)
* `snap`: Add `rust` to `build-packages` (#682)
* Pin `path` < 17 (#675)
* Add Python 3.12 support (#672)
* Upgrade `setuptools` (#667)

charm-tools 2.8.8
^^^^^^^^^^^^^^^^^
Thursday October 26 2023

* PR: #669 Pin ruamel.yaml < 0.18 due to #668

charm-tools 2.8.7
^^^^^^^^^^^^^^^^^
Tuesday August 22 2023

* 325b4d5 [2023-08-22] Fix issues with tox targets lint & docs (#665) [GitHub]
* c213bda [2023-08-08] setup: Update charm-tools pin set [Felipe Reyes]

charm-tools 3.0.7
^^^^^^^^^^^^^^^^^
Tuesday August 22 2023

* b7128ec [2023-08-22] Fix issues with tox targets lint & docs (#664) [GitHub]
* 8ec888b [2023-08-09] setup: Update pin PyYAML [Felipe Reyes]
* 5f51a7f [2023-07-20] setup: Update charm-tools pin set [Corey Bryant]

charm-tools 2.8.6
^^^^^^^^^^^^^^^^^
Wednesday March 29 2023

* (backport) pin pip<23.1 and setuptools<67 #654

charm-tools 2.8.5
^^^^^^^^^^^^^^^^^
Wednesday March 29 2023

* Fixes for reproducible charms (bugs #606, #605, #603) #607
* snap: Replace bhttp part with stage-snap #621
* Add option to build charm with binary wheels #620
* Change series lint from warn to info message #618
* Add warning message if series is in metadata.yaml #616

charm-tools 3.0.6
^^^^^^^^^^^^^^^^^
Wednesday March 29 2023

* Pin pin<23.1 and setuptools < 67 to allow PEP-440 non compliance #653

charm-tools 3.0.5
^^^^^^^^^^^^^^^^^
Wednesday March 29 2023

* Add option to upgrade core deps in build virtualenv #650
* Fix some pip requirements lines #651

charm-tools 3.0.4
^^^^^^^^^^^^^^^^^
Sunday October 9 2022

* Fix issues with charm-tools 3.x snap on bionic
* Deprecate `charm create` command

charm-tools 3.0.3
^^^^^^^^^^^^^^^^^
Friday October 7 2022

* Clear environment variables when running apt (#641)
* Fix typo

charm-tools 3.0.2
^^^^^^^^^^^^^^^^^
Thursday September 29 2022

* Add workaround for missing build packages (#639)

  * The bare minimum of build packages may be missing following
    commit 2482f0f and commit 725d2cb.
  * While the resolution may belong in charmcraft, we need a
    workaround.
  * Fixes #638

charm-tools 3.0.1
^^^^^^^^^^^^^^^^^
Thursday September 29 2022

* Fix version output to be compatbile with sibling projects (#637)

  * Due to how some other projects parse our version string the current
    format may break people.
  * Fixes #636

charm-tools 3.0.0
^^^^^^^^^^^^^^^^^
Monday September 26 2022

* Drop support for charm store (#626)

  * The charm store has been decommissioned and replaced by Charmhub.
  * This tool is still useful for building reactive charms, but store
    management should be done with tools such as canonical/charmcraft.

* snap: Update base to core22 (#626)

* Prune snap path when building wheelhouse (#626)

  * Previously, when running charm-tools from a snap, the default was
    to use Python and associated tools from the snap when building a
    charm's wheelhouse etc.
  * This is normally not what you would want as the Python version in
    the snap does not necessarily match the Python version of the
    target system.
  * Moving forward the build environment is expected to already
    contain build-packages such as Python, pip and git.
  * To restore the old behavior the `--use-python-from-snap` option
    may be used.

* Fixes for reproducible charms (#607)

* Add option to build charm with binary wheels (#620)

* Log info message when series is mentioned in `metadata.yaml` (#618)

charm-tools 2.8.4 + charmstore-client 2.5.0
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Monday July 18 2022

**charm-tools**

* Fixes for Python 3.10 compatibility
* Add support for relation-created hooks

charm-tools 2.8.3 + charmstore-client 2.5.0
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Monday February 8 2021

**charm-tools**

* Update pinned version of PyYAML (#600)

charm-tools 2.8.2 + charmstore-client 2.5.0
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Monday February 1 2021

**charm-tools**

* Fix reproducible charms issues (#598)

charm-tools 2.8.1 + charmstore-client 2.5.0
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Wednesday January 27 2021

**charm-tools**

* Add option to create .charm file (#592)
* Add 'docs' to known metadata fields (#591)
* Add reproducible charm build feature (#585)
* Fix exception rendering "already promulgated" error (#590)
* Align setup.py to requirements.txt (#589)
* Fix TypeError from linter on X.Y min-juju-version (#588)
* Make output_dir the same as build_dir (#564)

charm-tools 2.8.0 + charmstore-client 2.5.0
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Tuesday November 10 2020

**charm-tools**

* Fix snap build for updated charmstore-client (#587)
* Store rev when pull-source on a subdir layer (#583)
* Add revision info to output of pull-source (#582)
* Add --branch option to pull-source (#581)
* Raise more useful BuildError on missing pkg name (#579)
* Deprecate Operator charm template (#578)

**charmstore-client**

* Update dependencies
* Make charm-push support archives

charm-tools 2.7.8 + charmstore-client 2.4.0+git-13-547c6f2
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Tuesday July 21 2020

**charm-tools**

* Normalize package names when processing wheelhouse (#576)

charm-tools 2.7.7 + charmstore-client 2.4.0+git-13-547c6f2
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Monday July 20 2020

**charm-tools**

* Fix handling of comments in wheelhouse (#574)

charm-tools 2.7.6 + charmstore-client 2.4.0+git-13-547c6f2
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Thursday July 16 2020

**charm-tools**

* Switch to requirements-parser for wheelhouse (#572)

charm-tools 2.7.5 + charmstore-client 2.4.0+git-13-547c6f2
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Thursday June 25 2020

**charm-tools**

* Process wheelhouse.txt holistically rather than per-layer (#569)
* Handle invalid config file more gracefully (#567)
* Default to charming category of the Juju Discourse (#565)

charm-tools 2.7.5 + charmstore-client 2.4.0+git-13-547c6f2
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Thursday June 25 2020

**charm-tools**

* Process wheelhouse.txt holistically rather than per-layer (#569)
* Handle invalid config file more gracefully (#567)
* Default to charming category of the Juju Discourse (#565)

charm-tools 2.7.4 + charmstore-client 2.4.0+git-13-547c6f2
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Thursday March 26 2020

**charm-tools**

* Add workaround for user site package conflicts (#561)
* Add Build Snap action so PRs have snap to test easily (#562)

charm-tools 2.7.3 + charmstore-client 2.4.0+git-13-547c6f2
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Saturday Feb 29 2020

**charm-tools**

* Add Operator charm template (#557)
* Add OpenStack templates to requirements (#558)
* Fix 471 (#556)
* Add functions support; (#555)
* Allow boolean config options to have null default (#554)

**charmstore-client**

* fix dependencies
* cmd/charm: allow users with domains in ACLs
* Updated charmstore and charmrepo dependency.
* charm whoami: return an error when the user is not logged in
* Update dependencies
* Fix dependency files

charm-tools 2.7.2 + charmstore-client 2.4.0+git-3-cbbf887
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Tuesday October 8 2019

**charm-tools**

* Add opendev.org https and git fetcher (#553)

**charmstore-client**

* Disallow release in promulgated namespace

charm-tools 2.7.1 + charmstore-client 2.4.0
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Tuesday September 24 2019

**charm-tools**

* Fix maintainer validation not handling unicode (#550)
* Fix snap builds on other arches (#548)
* Change deployment.type optional (for k8s charms) (#547)
* Move daemonset to deployment.type (for k8s charms) (#546)


charm-tools 2.7.0 + charmstore-client 2.4.0
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Wednesday September 18 2019

**charm-tools**

* Fix charm-build conflict when building concurrently (#545)
* Rename README files with markdown extension (#543)
* Update charm.1 manpage (#522)
* Feature/add deployment field2metadata (#544)
* fix charm build help message (#542)
* Cleanup cached layers / interfaces after build (#540)
* edge case for setting charm_ver (#538)


charm-tools 2.6.1 + charmstore-client 2.4.0
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Thursday July 11 2019

**charm-tools**

* Remove bad URL from PR template (#537)
* Update pypi release target to work with newer tox (#530)
* requirements.txt: update version limit for requests (#535) (#536)
* Fix config key regexp to allow short config keys. (#534)


charm-tools 2.6.0 + charmstore-client 2.4.0
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Thursday June 6 2019

**charm-tools**

* Honor ignores / excludes when checking for post-build changes (#529)
* Resolve vergit runtime dependency (#527)
* Upgrade to use py3.7 on Travis (#523)
* Fix installing from git without vergit installed (#520)
* Fix installation dependency on vergit (#519)
* Gracefully handle JSON decode errors from layer index (#516)
* Add support for layer-index and fallback-layer-index (#515)
* Ensure setuptools for charmstore-client build (#509)
* Refactor version handling in snap to work with core18 (#508)
* Make series required (#499)
* Add setuptools to requirements.txt (#498)
* Fix charm-layer handling of old format build-manifest (#496)
* Fix nested build dir check in Python2 (#494)
* Improve docs for LayerYAML tactic (#493)
* Add promulgate and unpromulgate commands (#491)
* Fix and improve charm-layers (#492)
* Fix checking of build dir nested under source dir (#490)
* Add basic documentation (#489)
* Allow `build` folders in the charm (#486)
* Fix CHARM_HIDE_METRICS environment variable (#483)
* Address security alerts from GitHub (#484)
* Use shutil.copytree instead of path.rename (#482)

**charmstore-client**

* Remove the temporary file
* update charmrepo dependency
* update charm dependency
* internal/ingest: set permissions correctly
* cmd/charm-ingest: use --hardlimit not --softlimit
* cmd/charm-ingest: expose disk limits
* make tests pass
* internal/ingest: transfer resources
* cmd/charm-ingest: Add a basic ingest command
* internal/ingest: resolve resources in whitelist
* internal/ingest: expose public ingest API.
* cmd/charm-ingest: Add the basics of whitelist parsing
* restore go-cmp dependency version
* Move cmd/ingest to internal/ingest
* cmd/ingest: fix comment from previous review
* cmd/ingest: run tests against real charmstore servers
* cmd/ingest: core ingestion logic
* cmd/charm/charmcmd: add some basic tests for show command
* cmd/charm/charmcmd: improve output in `charm show` for unpublished charms
* cmd/ingest: new ingest command
* cmd/charm/charmcmd: improve incompatible registry version error
* Update usage of docker to oci-image resource type.
* Reviews.
* cmd/charmcmd: Better yaml output for resources.
* cmd/charmcmd: Allow multiple users in list.
* all: use quicktest for tests
