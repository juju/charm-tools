Changelog
=========

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
