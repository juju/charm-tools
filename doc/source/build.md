Juju Charm Building
===================

Today its very common to fork charms for minor changes or to have to use
subordinate charms to take advantages of frameworks where you need to deploy a
custom workload to an existing runtime. With charm build you should be
able to include from a charm that provides the runtime (or just some well
contained feature set) and maintain you're delta as a 'layer' that gets
built with its base to produce a new charm.

This process should be runnable repeatedly allowing charms to be regenerated.


Today the system can be run as follows:

    charm build -o <output_repo> <charm to build from>

So you might use the included (very unrealistic) test case as like:

    charm build -o out -n foo tests/trusty/tester

Running this should produce a charm in out/trusty/foo which is built
according to the layer.yaml file in tests/trusty/tester. 

Theory
======

A built charm is composed of layers. The generator acts almost like a compiler
taking the input from each layer and producing an output file in the
resultant charm.

The generator keeps track of which layer owns each file and allows layers to
update files they own should the charm be refreshed later.

The generated charm itself should be treated as immutable. The top layer that
was used to generate it is where user level modifications should live.


Setting Up your Repo
====================
This currently allows for two new ENV variables when run
    LAYER_PATH:  a ':' separated list of JUJU_REPOSITORY that should be searched for includes
    INTERFACE_PATH: a ':' separated list of paths to resolve interface:_name_ includes from.

JUJU_REPOSITORY entries take the usual format *series*/*charm*
INTERFACE repos take the format of *interface_name*. Where interface_name is
the name as it appears in the metadata.yaml

Build Tactics
=============

Each file in each layer gets matched by a single Tactic. Tactics implement how
the data in a file moves from one layer to the next (and finally to the target
charm). By default this will be a simple copy but in the cases of certain files
(mostly known YAML files like metadata.yaml and config.yaml) each layer is
combined with the previous layers before being written.

Normally the default tactics are fine but you have the ability in the
layer.yaml to list a set of Tactics objects that will be checked before the
default and control how data moves from one layer to the next.


layer.yaml
==========
Each layer used to build a charm can have a layer.yaml file. The top layer
(the one actually invoked from the command line) must. These tell the generator what do,
ranging from which base layers to include, to which interfaces. They also allow for 
the inclusion of specialized directives for processing some types of files.

    Keys:
        includes: ["trusty/mysql", "interface:mysql"]
        tactics: [ dottedpath.toTacticClass, ]
        config:
            deletes: 
                - key names
        metadata:
            deletes:
                - key names
        ignore:
            - tests
        exclude:
            - unit_tests
            - README.md


Includes is a list of one or more layers and interfaces that should be
built Those layers may themselves have other includes and/or
interfaces.

Tactics is a list of Tactics to be loaded. See charmtools.build.tactics.Tactics
for the default interface. You'll typically need to implement at least a
trigger() method and a __call__() method.

`config` and `metadata` take lists of keys to remove from `config.yaml` and
`metadata.yaml` when generating their data. This allows for charms to, for
example, narrow what they expose to clients.

`ignore` is a list of files or directories to ignore from a lower layer,
using the same format as a `.gitignore` or `.bzrignore` file.  Thus, if any
lower layer provides, in the example above, a `tests` directory, it will not
be included in the built charm, although any `tests` directory in this or a
higher level layer *will* be included.

`exclude` is a list of files or directories to exclude from this layer,
using the same format as a `.gitignore` or `.bzrignore` file.  Thus, if the
current layer provides, in the example above, a `unit_tests` directory and a
`README.md` file, it will not be included in the built charm, although any
`unit_tests` directory or `README.md` file in either a lower or higher level
layer *will* be included, using the same compositing rules as normal.


charm layers
============

If you've already generated a charm you can see which layers own which files by
using the include **charm layers [charmdir]*** command. This should render a
tree of the files in the color of each layer. Each layers assigned color is
presented in a legend at the top of the output.
