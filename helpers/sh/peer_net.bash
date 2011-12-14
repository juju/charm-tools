#!/bin/bash

#Copyright: Copyright 2011, Canonical Ltd., All Rights Reserved.
#License: GPL-3
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# .
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# .
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.


##
# ch_peer_scp [-r] path1 [...pathN]
# distribute a list of file (or paths with -r) to all slave of the peer
# relation
#
# param
#  -r     recursive scp copy
#  path   file or directory path
#
# returns
#  "done" when copy is complete on the slave side
#  FALSE  if an error was encountered

function ch_peer_scp {
  $USAGE="USAGE: ch_peer_scp [-r] path1 [...pathN]"
  
  ssh_key_p="/root/.ssh/"
  
  if [ $# -eq 0 ]; then
    juju-log "$USAGE"
    juju-log "$0: please provide at least one path"
    exit 1
  fi

  
  if  [[ `ch_peer_am_I_leader` > /dev/null ]] ; then
    juju-log "$0: This is our leader"

    for arg in $*
    do
      scp_options="-o StrictHostKeyChecking=no -B -q"
      paths=""
      case $arg in
      "-r") # scp recure
        scp_options="$scp_options -r"
        ;;
      "$0")
        ;;
      *) # should be a file
        if [ -e $arg ]; then
          paths="$paths $arg root@$remote:$arg"
        else
          juju-log "$0: Path does not exist, cannot distribute: $arg"
          exit 1
        ;;
    done
    if [ ! -n $paths ]; then
      juju-log "$USAGE"
      juju-log "$0: please provide at least one path"
      exit 1
    fi
    
    remote=$(relation-get scp-hostname)
    ssh_key_saved=$(relation-get scp-ssh-key-saved)
    
    if [ -n $remote ]; then
      # We know where to send file to
      
      case $ssh_key_saved in
      1) # ssh keys have been save, let's copy
        juju-log "$0: scp $scp_options $paths"
        scp $scp_options $paths
        relation-set scp-copy-done=1
        ;;
        
      *) # we need to first distribute our ssh key files
        juju-log "$0: distubuting ssh key"
        if [[ ! -f "$ssh_key_p/id_rsa" ]]; then
          ssh-keygen -q -N '' -t rsa -b 2048 -f /root/.ssh/id_rsa
        fi
        relation-set scp-ssh-key="`cat /root/.ssh/id_rsa.pub`"
        ;;
        
      esac
      
  else # Not the leader
    juju-log "$0: This is a slave"
 
    scp_copy_done=$(relation-get scp_copy_done)
    scp_ssh_key=$(relation-get scp-ssh-key)
 
    if [ -n scp_copy_done ] then
      juju-log "$0: copy done, thanks"
      echo "done"
      exit 0
    else
      if [ -n $scp_ssh_key ]; then
        mkdir -p $ssh_key_p
        grep -q -F "$scp_ssh_key" $ssh_key_p/authorized_keys
        if [[ $? != 0 ]]; then
          juju-log "$0: saving ssh key $scp_ssh_key"
          echo "$scp_ssh_key" >> $ssh_key_p/authorized_keys
          relation-set scp-ssh-key-saved=1
        else
          juju-log "$0: ssh keys already saved, thanks"
        fi
      else
        juju-log "$0: ssh_keys not set yet, later"
        relation-set scp-hostname=`unit-get private-address`
      fi # if [ -n $scp_ssh_key ]; then
    fi # if [ -n scp_copy_done ] then
  fi # if  [[ `ch_peer_am_I_leader` > /dev/null ]] ; then

}


