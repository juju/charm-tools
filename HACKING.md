# HACKING

Herein lay instructions on how to contribute to this project.


# Developer install

First install the dependencies of the dependencies

```bash
sudo apt install libssl-dev
```

This codebase requires a few system-wide dependencies be installed.  The
"sysdeps" make target will install them::

```bash
make deps
```

Next the build needs to be run::

```bash
make
```

Tests can be run my make or as a script (which allows for command-line options
to be passed).

```bash
make test
bin/test
```

# Filing Bugs

Please file bugs here: https://github.com/juju/charm-tools/issues
