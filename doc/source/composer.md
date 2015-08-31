Juju Charm Composition
======================

Status | *Alpha*
------- -------

This is a Prototype designed to flush out requirements around Charm
Composition. Today its very common to fork charms for minor changes or to have
to use subordinate charms to take advantages of frameworks where you need to
deploy a custom workload to an existing runtime. With charm composition you
should be able to include from a charm that provides the runtime (or just some
well contained feature set) and maintain you're delta as a 'layer' that gets
composed with its base to produce a new charm.

This process should be runnable repeatedly allowing charms to be regenerated.


This work is currently feature incomplete but does allow the generation of
simple charms and useful basic composition. It is my hope that this will
encourage discussion of the feature set needed to one day have charm
composition supported natively in juju-core.


Today the system can be run as follows:

    ./juju_compose.py -o <output_repo> <charm to build from>

So you might use the included (very unrealistic) test case as like:

    ./juju_compose -o out -n foo tests/trusty/tester

Running this should produce a charm in out/trusty/foo which is composed
according to the composer.yaml file in tests/trusty/tester. While this isn't
documented yet it shows some of the basic features of diverting hooks (for
pre/post hooks support), replacing files, merging metadata.yaml changes, etc.

It should be enough to give you an idea how it works. In order for this example
to run you'll need to pip install bundletester as it shares some code with that
project.

Theory
======

A generated charm is composed of layers. The generator acts almost like a
compiler taking the input from each layer and producing an output file in the
resultant charm.

The generator keeps track of which layer owns each file and allows layers to
update files they own should the charm be refreshed later.

The generated charm itself should be treated as immutable. The top layer that
was used to generate it is where user level modifications should live.


Setting Up your Repo
====================
This currently allows for two new ENV variables when run
    COMPOSER_PATH:  a ':' separated list of JUJU_REPOSITORY that should be searched for includes
    INTERFACE_PATH: a ':' separated list of paths to resolve interface:_name_ includes from.

JUJU_REPOSITORY entries take the usual format *series*/*charm*
INTERFACE repos take the format of *interface_name*. Where interface_name is
the name as it appears in the metadata.yaml

Composition Types
=================

Each file in each layer gets matched by a single Tactic. Tactics implement how
the data in a file moves from one layer to the next (and finally to the target
charm). By default this will be a simple copy but in the cases of certain files
(mostly known YAML files like metadata.yaml and config.yaml) each layer is
combined with the previous layers before being written.

Normally the default tactics are fine but you have the ability in the
composer.yaml to list a set of Tactics objects that will be checked before the
default and control how data moves from one layer to the next.


composer.yaml
=============
Each layer used to build a charm can have a composer.yaml file. The top layer
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


Includes is a list of one or more layers and interfaces that should be
composited. Those layers may themselves have other includes and/or
interfaces.

Tactics is a list of Tactics to be loaded. See juju_compose.tactics.Tactics for
the default interface. You'll typically need to implement at least a trigger() method
and a __call__() method.

config and metadata take optional lists of keys to remove from config.yaml and
metadata.yaml when generating their data. This allows for charms to, for
example, narrow what they expose to clients.


Inspect
=======

If you've already generated a charm you can see which layers own which files by
using the include **juju inspect [charmdir]*** command. This should render a
tree of the files in the color of each layer. Each layers assigned color is
presented in a legend at the top of the output.

TODO:
- lint about methods in base layer not provided/extended in lower
layers



