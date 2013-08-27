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

check:
	tests/helpers/helpers.sh || sh -x tests/helpers/helpers.sh timeout
	@echo Test shell helpers with dash
	bash tests/helpers/helpers.sh || bash -x tests/helpers/helpers.sh timeout
	tests/helpers/helpers.bash || sh -x tests/helpers/helpers.bash timeout
	@echo Test shell helpers with bash
	bash tests/helpers/helpers.bash || bash -x tests/helpers/helpers.bash timeout
	@echo Test charm proof
	tests/proof/test.sh
	tests/create/test.sh
	PYTHONPATH=helpers/python python helpers/python/charmhelpers/tests/test_charmhelpers.py
#	@echo PEP8 Lint of Python files
#	@echo `grep -rl '^#!/.*python' .` | xargs -r -n1 pep8

clean:
	find . -name '*.pyc' -delete
	find . -name '*.bak' -delete
