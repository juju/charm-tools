#!/usr/bin/env python

from launchpadlib.launchpad import Launchpad
from operator import itemgetter
import datetime
import itertools
import argparse


def calculate_age(from_date=None):
    if not from_date:
        return None


def format_as_table(data,
                    keys,
                    header=None,
                    sort_by_key=None,
                    sort_order_reverse=False):
    """Takes a list of dictionaries, formats the data, and returns
    the formatted data as a text table.

    Required Parameters:
        data - Data to process (list of dictionaries). (Type: List)
        keys - List of keys in the dictionary. (Type: List)

    Optional Parameters:
        header - The table header. (Type: List)
        sort_by_key - The key to sort by. (Type: String)
        sort_order_reverse - Default sort order is ascending, if
            True sort order will change to descending. (Type: Boolean)
    """
    # Sort the data if a sort key is specified (default sort order
    # is ascending)
    if sort_by_key:
        data = sorted(data,
                      key=itemgetter(sort_by_key),
                      reverse=sort_order_reverse)

    # If header is not empty, add header to data
    if header:
        # Get the length of each header and create a divider based
        # on that length
        header_divider = []
        for name in header:
            header_divider.append('-' * len(name))

        # Create a list of dictionary from the keys and the header and
        # insert it at the beginning of the list. Do the same for the
        # divider and insert below the header.
        header_divider = dict(zip(keys, header_divider))
        data.insert(0, header_divider)
        header = dict(zip(keys, header))
        data.insert(0, header)

    column_widths = []
    for key in keys:
        column_widths.append(max(len(str(column[key])) for column in data))

    # Create a tuple pair of key and the associated column width for it
    key_width_pair = zip(keys, column_widths)

    format = ('%-*s ' * len(keys)).strip() + '\n'
    formatted_data = ''
    for element in data:
        data_to_format = []
        # Create a tuple that will be used for the formatting in
        # width, value format
        for pair in key_width_pair:
            data_to_format.append(pair[1])
            data_to_format.append(element[pair[0]])
        formatted_data += format % tuple(data_to_format)
    return formatted_data


def charm_review_queue():
    print "Connecting to launchpad..."
    lp = Launchpad.login_anonymously('charm-tools', 'production',
                                     version='devel',
                                     launchpadlib_dir='~/.cache/launchpadlib')
    charm = lp.distributions['charms']
    charmers = lp.people['charmers']
    charm_contributors = lp.people['charm-contributors']

    print "Querying launchpad for bugs ..."
    bugs = charm.searchTasks(tags=['new-formula', 'new-charm'],
                             status=['New', 'Confirmed', 'Triaged',
                                     'In Progress', 'Fix Committed'],
                             tags_combinator="Any")
    charmers_bugs = charmers.searchTasks(
        status=['New', 'Confirmed', 'Triaged', 'In Progress',
                'Fix Committed'])

    print "Querying launchpad for proposals ..."
    proposals = charmers.getRequestedReviews(status="Needs review")
    charm_contributors_proposals = charm_contributors.getRequestedReviews(
        status="Needs review")

    print "Building review_queue ..."
    queue = list()
    max_summary_length = 50

    # Bugs in charms distribution and charmers group
    for bug in itertools.chain(bugs.entries, charmers_bugs.entries):
        entry_summary = bug['title'].split('"')[1].strip()
        bug_created = datetime.datetime.strptime(
            bug['date_created'].split('+')[0], "%Y-%m-%dT%H:%M:%S.%f")
        entry_age = datetime.datetime.utcnow() - bug_created
        entry = {'date_created': bug['date_created'].split("T")[0],
                 'age': str(entry_age).split('.')[0],
                 'summary': (entry_summary[:max_summary_length] + '...')
                 if len(entry_summary) > max_summary_length else entry_summary,
                 'item': bug['web_link'],
                 'status': bug['status'],
                 }
        queue.append(entry)

    # Merge proposals in charmers group
    for proposal in itertools.chain(proposals.entries,
                                    charm_contributors_proposals.entries):
        proposal_summary = proposal['description']
        proposal_date_created = datetime.datetime.strptime(
            proposal['date_created'].split('+')[0], "%Y-%m-%dT%H:%M:%S.%f")
        proposal_age = datetime.datetime.utcnow() - proposal_date_created
        if proposal_summary is None:
            proposal_summary = "Proposal"
        entry = {'date_created': proposal['date_created'].split("T")[0],
                 'age': str(proposal_age).split('.')[0],
                 'summary': (proposal_summary[:max_summary_length] + '...')
                 if len(proposal_summary) > max_summary_length
                 else proposal_summary,
                 'item': proposal['web_link'],
                 'status': proposal['queue_status'],
                 }
        queue.append(entry)

    return(sorted(queue, key=lambda k: k['date_created']))


def main():
    parser = argparse.ArgumentParser(
        description="Shows items needing the attention of ~charmers")
    parser.parse_args()
    review_queue = charm_review_queue()
    keys = ['date_created', 'age', 'summary', 'item', 'status']
    headers = ['Date Created', 'Age', 'Summary', 'Item', 'Status']
    print "Queue length: %d" % len(review_queue)
    if isinstance(review_queue, list) and len(review_queue) > 0:
        print format_as_table(review_queue,
                              keys,
                              header=headers,
                              sort_by_key='date_created',
                              sort_order_reverse=False)

if __name__ == "__main__":
    main()
