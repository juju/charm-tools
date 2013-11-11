DESTDIR = 
prefix = /usr
DDIR = $(DESTDIR)$(prefix)
bindir = $(DDIR)/bin
mandir = $(DDIR)/share/man/man1
datadir = $(DDIR)/share/charm-tools
helperdir = $(DDIR)/share/charm-helper
confdir = $(DESTDIR)/etc
INSTALL = install

all:

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

integration:
	tests_functional/helpers/helpers.sh || sh -x tests_functional/helpers/helpers.sh timeout
	@echo Test shell helpers with dash
	bash tests_functional/helpers/helpers.sh || bash -x tests_functional/helpers/helpers.sh timeout
	tests_functional/helpers/helpers.bash || sh -x tests_functional/helpers/helpers.bash timeout
	@echo Test shell helpers with bash
	bash tests_functional/helpers/helpers.bash || bash -x tests_functional/helpers/helpers.bash timeout
	@echo Test charm proof
	tests_functional/proof/test.sh
	tests_functional/create/test.sh
#	PYTHONPATH=helpers/python python helpers/python/charmhelpers/tests/test_charmhelpers.py

lint:
	@echo PEP8 Lint of Python files
	@pep8 charmtools && echo OK

test:
	@nosetests -s tests/test_*.py

coverage:
	@nosetests --with-coverage --cover-package=charmtools --cover-tests -s tests/test_*.py

check: integration test lint

clean:
	find . -name '*.pyc' -delete
	find . -name '*.bak' -delete
