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
# Run tests using make
make test
# Run tests as a script
bin/test
```

You can out the code on your machine by building the project and going into the
virtualenv that tox made.

```bash
# Build the project
make build
# Activate the virtualenv tox made
source .tox/py27/bin/activate
```

Now you're inside the virtualenv. You should see `(py27)` in front of your bash
prompt. If you run `charm-build` inside the virtualenv, you'll be running the
charmtools from your development directory instead of the one installed on your
system.

# Filing Bugs

Please file bugs here: https://github.com/juju/charm-tools/issues
