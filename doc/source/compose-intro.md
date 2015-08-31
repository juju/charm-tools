charm compose/refresh combines various included layers to produce an output
charm. These layers can be maintained and updated separately and then the
refresh process can be used to regenerate the charm.

COMPOSER_PATH is a ':' delimited path list used to resolve local include matches. 
INTERFACE_PATH is the directory from which interfaces will be resolved.

Examples:
charm compose -o /tmp/out trusty/mycharm

Will generate /tmp/out/trusty/mycharm will all the includes specified.

WORKFLOW
========

Typically you'll make changes in the layer owning the file(s) in queustion
and then recompose the charm and deploy/upgrade-charm that. You'll not
want to edit the generated charm directly.
