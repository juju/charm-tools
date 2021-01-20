Reproducible Charms
===================

When building charms, multiple layers are brought together in an ordered,
depth-first recursive fashion.  The individual files of each layer are merged,
and then python modules are brought in according to ``wheelhouse.txt`` files
that may exist in each layer.

Layers (and Interfaces) are typically Git repositories, and by default the
default branch (usually called ``master``) of the repository is fetched and
used.

Also, although the top level Python modules can be pinned in the
``wheelhouse.txt`` files, any dependent modules are fetched as their latest
versions.  This makes re-building a charm with the same layers and modules
tricky, which may be required for stable charms.  It is possible, by populating
layer and interface directories directly, and by pinning every Python module in
a ``wheelhouse.txt`` override file that is passed using the
``--wheelhouse-overrides`` option to the ``charm build`` command.

An alternative strategy is to use a new feature of the ``charm build`` command
which can generate a lock file that contains all of the layers and Python
modules, and their versions.  This can then, for subsequent builds, be used to
fetch the same layer versions and Python modules to re-create the charm.

As the lock file is a ``JSON`` file, it can be manually edited to change a
layer version if a new version of a stable charm is needed, or a python module
can be changed.

Additionally, it is possible to track a branch in the repository for a layer so
that a stable (or feature) branch can be maintained and then charms rebuilt
from that branch.

The new options for this feature are:

 * ``--write-lock-file``
 * ``--use-lock-file-branches``
 * ``--ignore-lock-file``


Creating the lock file
----------------------

To create a lock file, the option ``--write-lock-file`` is passed to the
``charm build`` command.  This option *automatically* ignores the existing lock
file, and rebuilds the charm using the latest versions of the layers and the
versions of the modules as determined in the various ``wheelhouse.txt`` files.

Python module versions are also recorded.  If a VCS repository is used for the
python module, then any branch specified is also recorded, along with the
commit.

At the end of the build, the lock file is written with all of the layer and
Python module information.

The lock file is installed *in* the base layer directory so that it can be
committed into the VCS and used for subsequent builds.

The name of the lock file is ``build.lock``.

Rebuilding the charm from the lock file
---------------------------------------

If a lock file (``build.lock``) is available in the top layer, then it will be
used to control the versions of the layers and modules *by default*.  i.e. the
presence of the lock file controls the build.

Three options are available which can influence the build when a lock file is
present:

 * ``--ignore-lock-file``
 * ``--use-lock-file-branches``
 * ``--wheelhouse-overrides``

If the ``--ignore-lock-file`` option is used, then the charm is built as though
there is no lock file.

If the ``--use-lock-file-branches`` is used, then, for VCS items (layers,
interfaces, and Python modules specified using a VCS string), then the branch
(if there was one) will be used, rather than the commit version.  This can be
used to track a branch in a layer or Python module.

Note: if ``--wheelhouse-overrides`` is used, then that wheelhouse will override
the lock file.  i.e. the lock file overrides the layers' ``wheelhouse.txt``
file, and then the ``--wheelhouse-overrides`` then can override the lock-file.
This is intentional to allow the build to perform specific overrides as
needed.

Other useful information
------------------------

This is the first iteration of 'reproducible charms'.  As such, only Git is
supported as the VCS for the layers, and Git and Bazaar for Python modules.  A
future iteration may support more VCS systems.

Only the top layer is inspected for a ``build.lock`` file.  Any other layers
are considered inputs and their ``build.lock`` files are ignored (if they are
present).

Also, regardless of the ``wheelhouse.txt`` layers, the lock file will override
any changes that may be introduced in stable branches, if they are bing tracked
using ``--use-lock-file-branches``.  This may lead to unexpected behaviour.
