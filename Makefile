# Makefile debugging hack: uncomment the two lines below and make will tell you
# more about what is happening.  The output generated is of the form
# "FILE:LINE [TARGET (DEPENDENCIES) (NEWER)]" where DEPENDENCIES are all the
# things TARGET depends on and NEWER are all the files that are newer than
# TARGET.  DEPENDENCIES will be colored green and NEWER will be blue.
#OLD_SHELL := $(SHELL)
#SHELL = $(warning [$@ [32m($^) [34m($?)[m ])$(OLD_SHELL)

WD := $(shell pwd)
DESTDIR = 
prefix = /usr
DDIR = $(DESTDIR)$(prefix)
bindir = $(DDIR)/bin
mandir = $(DDIR)/share/man/man1
datadir = $(DDIR)/share/charm-tools
helperdir = $(DDIR)/share/charm-helper
confdir = $(DESTDIR)/etc
INSTALL = install

# We use a "canary" file to tell us if the package has been installed in
# "develop" mode.
DEVELOP_CANARY := lib/__develop_canary
develop: $(DEVELOP_CANARY)
$(DEVELOP_CANARY): | python-deps
	bin/python setup.py develop
	touch $(DEVELOP_CANARY)

build: deps develop bin/test

dependencies:
	bzr checkout lp:~juju-jitsu/charm-tools/dependencies

# We use a "canary" file to tell us if the Python packages have been installed.
PYTHON_PACKAGE_CANARY := lib/python2.7/site-packages/___canary
python-deps: $(PYTHON_PACKAGE_CANARY)
$(PYTHON_PACKAGE_CANARY): requirements.txt | dependencies
	sudo apt-get update
	sudo apt-get install -y build-essential bzr python-dev \
	    python-virtualenv python-tox
	virtualenv .
	bin/pip install --no-index --no-dependencies --find-links \
	    file:///$(WD)/dependencies/python -r requirements.txt
	touch $(PYTHON_PACKAGE_CANARY)

deps: python-deps | dependencies

bin/nosetests: python-deps

bin/test: | bin/nosetests
	ln scripts/test bin/test

test: build 
	tox

lint: sources = setup.py charmtools
lint: build
	@find $(sources) -name '*.py' -print0 | xargs -r0 bin/flake8

tags:
	ctags --tag-relative --python-kinds=-iv -Rf tags --sort=yes \
	    --exclude=.bzr --languages=python

clean:
	find . -name '*.py[co]' -delete
	find . -type f -name '*~' -delete
	find . -name '*.bak' -delete
	rm -rf bin include lib local man dependencies

install:
	$(INSTALL) -d $(mandir)
	$(INSTALL) -t $(mandir) charm.1
	$(INSTALL) -d $(datadir)
	$(INSTALL) -t $(datadir) charm
	$(INSTALL) -d $(bindir)
	$(INSTALL) -d $(helperdir)
	$(INSTALL) -d $(confdir)/bash_completion.d
	$(INSTALL) misc/bash-completion $(confdir)/bash_completion.d/charm
	ln -sf $(datadir)/charm $(bindir)
	gzip $(mandir)/charm.1
	cp -rf scripts templates $(datadir)
	cp -rf helpers/* $(helperdir)

integration: build
	tests_functional/helpers/helpers.sh || sh -x tests_functional/helpers/helpers.sh timeout
	@echo Test shell helpers with bash
	bash tests_functional/helpers/helpers.sh \
	    || bash -x tests_functional/helpers/helpers.sh timeout
	tests_functional/helpers/helpers.bash || sh -x tests_functional/helpers/helpers.bash timeout
	@echo Test shell helpers with bash
	bash tests_functional/helpers/helpers.bash \
	    || bash -x tests_functional/helpers/helpers.bash timeout
	@echo Test charm proof
	tests_functional/proof/test.sh
	tests_functional/create/test.sh
	tests_functional/add/test.sh
#	PYTHONPATH=helpers/python python helpers/python/charmhelpers/tests/test_charmhelpers.py

coverage: build bin/test
	bin/test --with-coverage --cover-package=charmtools --cover-tests

check: build integration test lint

define phony
  build
  check
  clean
  deps
  install
  lint
  tags
  test
endef

.PHONY: $(phony)

.DEFAULT_GOAL := build
