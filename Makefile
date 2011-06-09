DESTDIR = 
prefix = /usr
DDIR = $(DESTDIR)$(prefix)
bindir = $(DDIR)/bin
mandir = $(DDIR)/share/man/man1
datadir = $(DDIR)/share/principia-tools
INSTALL = install

all:

install:
	$(INSTALL) -d $(mandir)
	$(INSTALL) -t $(mandir) principia.1
	$(INSTALL) -d $(datadir)
	$(INSTALL) -t $(datadir) principia
	$(INSTALL) -d $(bindir)
	ln -sf $(datadir)/principia $(bindir)
	gzip $(mandir)/principia.1
	cp -rf scripts templates $(datadir)
