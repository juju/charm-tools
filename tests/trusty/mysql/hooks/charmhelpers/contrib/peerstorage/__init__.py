# Copyright 2014-2015 Canonical Limited.
#
# This file is part of charm-helpers.
#
# charm-helpers is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License version 3 as
# published by the Free Software Foundation.
#
# charm-helpers is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with charm-helpers.  If not, see <http://www.gnu.org/licenses/>.

import six
from charmhelpers.core.hookenv import relation_id as current_relation_id
from charmhelpers.core.hookenv import (
    is_relation_made,
    relation_ids,
    relation_get,
    local_unit,
    relation_set,
)


"""
This helper provides functions to support use of a peer relation
for basic key/value storage, with the added benefit that all storage
can be replicated across peer units.

Requirement to use:

To use this, the "peer_echo()" method has to be called form the peer
relation's relation-changed hook:

@hooks.hook("cluster-relation-changed") # Adapt the to your peer relation name
def cluster_relation_changed():
    peer_echo()

Once this is done, you can use peer storage from anywhere:

@hooks.hook("some-hook")
def some_hook():
    # You can store and retrieve key/values this way:
    if is_relation_made("cluster"):  # from charmhelpers.core.hookenv
        # There are peers available so we can work with peer storage
        peer_store("mykey", "myvalue")
        value = peer_retrieve("mykey")
        print value
    else:
        print "No peers joind the relation, cannot share key/values :("
"""


def peer_retrieve(key, relation_name='cluster'):
    """Retrieve a named key from peer relation `relation_name`."""
    cluster_rels = relation_ids(relation_name)
    if len(cluster_rels) > 0:
        cluster_rid = cluster_rels[0]
        return relation_get(attribute=key, rid=cluster_rid,
                            unit=local_unit())
    else:
        raise ValueError('Unable to detect'
                         'peer relation {}'.format(relation_name))


def peer_retrieve_by_prefix(prefix, relation_name='cluster', delimiter='_',
                            inc_list=None, exc_list=None):
    """ Retrieve k/v pairs given a prefix and filter using {inc,exc}_list """
    inc_list = inc_list if inc_list else []
    exc_list = exc_list if exc_list else []
    peerdb_settings = peer_retrieve('-', relation_name=relation_name)
    matched = {}
    for k, v in peerdb_settings.items():
        full_prefix = prefix + delimiter
        if k.startswith(full_prefix):
            new_key = k.replace(full_prefix, '')
            if new_key in exc_list:
                continue
            if new_key in inc_list or len(inc_list) == 0:
                matched[new_key] = v
    return matched


def peer_store(key, value, relation_name='cluster'):
    """Store the key/value pair on the named peer relation `relation_name`."""
    cluster_rels = relation_ids(relation_name)
    if len(cluster_rels) > 0:
        cluster_rid = cluster_rels[0]
        relation_set(relation_id=cluster_rid,
                     relation_settings={key: value})
    else:
        raise ValueError('Unable to detect '
                         'peer relation {}'.format(relation_name))


def peer_echo(includes=None):
    """Echo filtered attributes back onto the same relation for storage.

    This is a requirement to use the peerstorage module - it needs to be called
    from the peer relation's changed hook.
    """
    rdata = relation_get()
    echo_data = {}
    if includes is None:
        echo_data = rdata.copy()
        for ex in ['private-address', 'public-address']:
            if ex in echo_data:
                echo_data.pop(ex)
    else:
        for attribute, value in six.iteritems(rdata):
            for include in includes:
                if include in attribute:
                    echo_data[attribute] = value
    if len(echo_data) > 0:
        relation_set(relation_settings=echo_data)


def peer_store_and_set(relation_id=None, peer_relation_name='cluster',
                       peer_store_fatal=False, relation_settings=None,
                       delimiter='_', **kwargs):
    """Store passed-in arguments both in argument relation and in peer storage.

    It functions like doing relation_set() and peer_store() at the same time,
    with the same data.

    @param relation_id: the id of the relation to store the data on. Defaults
                        to the current relation.
    @param peer_store_fatal: Set to True, the function will raise an exception
                             should the peer sotrage not be avialable."""

    relation_settings = relation_settings if relation_settings else {}
    relation_set(relation_id=relation_id,
                 relation_settings=relation_settings,
                 **kwargs)
    if is_relation_made(peer_relation_name):
        for key, value in six.iteritems(dict(list(kwargs.items()) +
                                             list(relation_settings.items()))):
            key_prefix = relation_id or current_relation_id()
            peer_store(key_prefix + delimiter + key,
                       value,
                       relation_name=peer_relation_name)
    else:
        if peer_store_fatal:
            raise ValueError('Unable to detect '
                             'peer relation {}'.format(peer_relation_name))
