DESTDIR = 
prefix = /usr
DDIR = $(DESTDIR)$(prefix)
bindir = $(DDIR)/bin
mandir = $(DDIR)/share/man/man1
datadir = $(DDIR)/share/charm-tools
INSTALL = install

all:

install:
	$(INSTALL) -d $(mandir)
	$(INSTALL) -t $(mandir) charm.1
	$(INSTALL) -d $(datadir)
	$(INSTALL) -t $(datadir) charm
	$(INSTALL) -d $(bindir)
	ln -sf $(datadir)/charm $(bindir)
	gzip $(mandir)/charm.1
	cp -rf scripts templates $(datadir)
