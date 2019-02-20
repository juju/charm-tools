Build Tactics
=============

When building charms, multiple layers are brought together in an ordered,
depth-first recursive fashion.  The individual files of each layer are merged
according to a list of merge tactics.  These tactics determine whether the file
from a higher layer will replace or be merged with the copy from the lower
layer, with the details of how the merge happens being implemented by the
tactic.  Each file is tested against each tactic in a specific order (as
determined by the ``DEFAULT_TACTICS`` list), with the first one to match being
applied to the file and all other tactics disregarded.


Built-in Tactics
----------------

.. automembersummary::
    :nosignatures:

    ~charmtools.build.tactics

.. automodule:: charmtools.build.tactics
   :members:


Custom Tactics
--------------

A charm or layer can also define one or more custom tactics in its ``layer.yaml``
file.  The file can contain a top-level ``tactics`` key, whose value is a list of
dotted Python module names, relative to the layer's base directory.  For
example, a layer could include this in its ``layer.yaml``:

.. code-block:: yaml

   tactics:
     - tactics.my_layer.READMETactic

This would cause the build command to look for a module ``tactics/my_layer.py``
with a class of ``READMETactic`` in it, which must inherit from
:class:`~charmtools.build.tactics.Tactic`.

Custom tactics are tested before the built-in tactics, so they can override
the behavior of built-in tactics if desired.  Care should be taken if doing
this because changing the behavior of built-in tactics can end up breaking
other layers or charms.
