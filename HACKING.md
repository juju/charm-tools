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

Tests can be run by make or as a script (which allows for command-line options
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

# Release Instructions

The edge channel of the snap is automatically built from master. The version is
derived from the tags in the git repo; a release should be tagged with the form:
`v{major}.{minor}.{point}`, e.g. `v2.2.0`.

After a full release has been promoted to the stable channel of the snap, a dev
or pre-release tag should be added to master, e.g. `v2.2.1-dev` or `v2.2.1-pre`.
Dev and pre-release versions will have git info appended to the version reported
in the snap, to more easily track exactly what is included in the snap. You can
also always get the full version information with:

```bash
charm version --format=long
```

PyPI should be kept up to date with full releases, but the authoritative source
is always the snap.  Note: for the version to work on PyPI, it needs to be cached
in the `charmtools/VERSION` file, in JSON format.  This is updated automatically
by `setup.py`, so to release to PyPI, you should just do the following:

```bash
python setup.py sdist upload
```


# Filing Bugs

Please file bugs here: https://github.com/juju/charm-tools/issues
