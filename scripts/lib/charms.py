import os
import sys
from launchpadlib.launchpad import Launchpad


def remote():
    lp = Launchpad.login_anonymously('charm-tools', 'production',
                                     version='devel')
    charm = lp.distributions['charms']
    current_series = str(charm.current_series).split('/').pop()
    branches = charm.getBranchTips()
    charms = []

    for branch in branches:
        try:
            branch_series = str(branch[2][0]).split('/')[0]
            charm_name = str(branch[0]).split('/')[3]
        except IndexError:
            branch_series = ''
        if branch_series == current_series:
            charms.append("lp:charms/%s" % charm_name)
        else:
            charms.append("lp:%s" % branch[0])
    return charms


def local(directory):
    '''Show charms that actually exist locally. Different than Mr.list'''
    local_charms = []
    for charm in os.listdir(directory):
        if os.path.exists(os.join(directory, charm, '.bzr')):
            local_charms.append(charm)
    return local_charms
