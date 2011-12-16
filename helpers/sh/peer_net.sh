#!/bin/sh

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
# ch_peer_copy [-r|--rsync] path1 [...pathN]
# ch_peer_scp [-r] path1 [...pathN]
# ch_peer_rsync path1 [...pathN]
#
# distribute a list of file to all slave of the peer relation
#
# param
#  -r      recursive scp copy
#  --rsync use rsync instead of scp
#  path    file or directory path
#
# returns
#  "done" when copy is complete on the slave side
#  FALSE  if an error was encountered
#
# This executes in multiple passes between the leader and each peer
#
#    LEADER                      SLAVE
#       <------------------- set scp-hostname
# set scp-ssh-key -----------------> 
#                            save shh-keys
#       <------------------- set scp-ssh-key-saved
# do file copy
# set scp-copy-done --------------->
#
# This function is idempotent and should be called for each JOINED or 
# CHANGED event for slave or leader in the peer relation exactly the same way

alias ch_peer_scp=ch_peer_copy
alias ch_peer_rsync='ch_peer_copy --rsync'
function ch_peer_copy {
  $CH_USAGE="ERROR in $*
USAGE: ch_peer_scp [-r] path1 [...pathN]
USAGE: ch_peer_rsync path1 [...pathN]"
  CH_ssh_key_p="/root/.ssh/"
  
  if [ $# -eq 0 ]; then
    juju-log "$CH_USAGE"
    juju-log "$0: please provide at least one path"
    exit 1
  fi

  ## LEADER ##
  
  if  [[ `ch_peer_am_I_leader` > /dev/null ]] ; then
    juju-log "$0: This is our leader"
    
    CH_remote=$(relation-get scp-hostname)
    CH_ssh_key_saved=$(relation-get scp-ssh-key-saved)
    if [ -z $CH_remote ]; then
      juju-log "$0: We do not have a remote hostname yet"
      $CH_remote=0
    fi  
  
    CH_scp_options=" -o StrictHostKeyChecking=no -B -q "
    CH_rsync_options=" -avz -e ssh "
    unset CH_paths
    CH_copy_command="scp "
    
    for arg in $*
    do
      case $CH_arg in
      "-r") # scp recure
        CH_scp_options="$CH_scp_options -r"
        ;;
      "--rsync") # rsync secure (-e ssh)
        CH_copy_command="rsync"
        ;;
      "$0")
        ;;
      *) # should be a file
        if [ -e $CH_arg ]; then
          CH_paths="$CH_paths $CH_arg root@$CH_remote:$CH_arg"
        else
          juju-log "$0: Path does not exist, skipping distribution of: $arg"
        fi
        ;;
    done
    if [ -z $CH_paths ]; then
      juju-log "$CH_USAGE"
      juju-log "$0: please provide at least one path"
      exit 1
    fi
    
    if [ -n $CH_remote ]; then
      # We know where to send file to
      
      case $CH_ssh_key_saved in
      1) # ssh keys have been save, let's copy
        juju-log "$0: $CH_copy_command $CH_scp_options $CH_paths"
        $CH_copy_command $CH_scp_options $CH_paths
        relation-set scp-copy-done=1
        ;;
        
      *) # we need to first distribute our ssh key files
        juju-log "$0: distubuting ssh key"
        if [[ ! -f "$CH_ssh_key_p/id_rsa" ]]; then
          ssh-keygen -q -N '' -t rsa -b 2048 -f /root/.ssh/id_rsa
        fi
        relation-set scp-ssh-key="`cat /root/.ssh/id_rsa.pub`"
        ;;
        
      esac
    fi # if [ -n $remote ]; then
    
  ## REMOTE ##
      
  else # Not the leader
    juju-log "$0: This is a slave"
 
    CH_scp_copy_done=$(relation-get scp_copy_done)
    CH_scp_ssh_key=$(relation-get scp-ssh-key)
 
    if [ -n scp_copy_done ] then
      juju-log "$0: copy done, thanks"
      echo "done"
      exit 0
    else
      if [ -n $CH_scp_ssh_key ]; then
        mkdir -p $CH_ssh_key_p
        grep -q -F "$CH_scp_ssh_key" $CH_ssh_key_p/authorized_keys
        if [[ $? != 0 ]]; then
          juju-log "$0: saving ssh key $CH_scp_ssh_key"
          echo "CH_$scp_ssh_key" >> $CH_ssh_key_p/authorized_keys
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


