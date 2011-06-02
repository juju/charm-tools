DESTDIR = /usr
bindir = $(DESTDIR)/bin
mandir = $(DESTDIR)/share/man/man1
datadir = $(DESTDIR)/share/principia-tools
INSTALL = install

all:

install:
	$(INSTALL) -d $(mandir)
	$(INSTALL) -t $(mandir) principia.1
	$(INSTALL) -d $(bindir)
	$(INSTALL) -t $(datadir) principia
	ln -sf $(datadir)/principia $(bindir)
	gzip $(mandir)/principia.1
	$(INSTALL) -d $(datadir)
	cp -rf scripts templates $(datadir)
