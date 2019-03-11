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

develop:
	tox --develop --notest

build: deps develop

PYTHON_DEPS=build-essential bzr python-dev python-tox
python-deps: scripts/packages.sh
	$(if $(shell ./scripts/packages.sh $(PYTHON_DEPS)), \
	tox -r --notest)

deps: python-deps

test: build
	tox

tags:
	ctags --tag-relative --python-kinds=-iv -Rf tags --sort=yes \
	    --exclude=.bzr --languages=python

clean:
	find . -name '*.py[co]' -delete
	find . -type f -name '*~' -delete
	find . -name '*.bak' -delete
	rm -rf bin include lib local man dependencies dist
	rm -f charmtools/VERSION

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

pypi: clean
	tox -e pypi

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

coverage: build
	tox

check: build integration test

define phony
  build
  check
  clean
  deps
  install
  pypi
  tags
  test
endef

.PHONY: $(phony)

.DEFAULT_GOAL := build
