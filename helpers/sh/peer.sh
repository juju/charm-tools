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
# ch_peer_i_am_leader
# Returns 1 if the current unit is the leader
#
# no params
#
# return 0|1
ch_peer_i_am_leader()
{
    local REMOTE_UNIT_ID=`ch_unit_id $JUJU_REMOTE_UNIT`
    local LOCAL_UNIT_ID=`ch_my_unit_id`
    local FIRST_UNIT=`relation-list | head -n 1`
    local FIRST_UNIT_ID=`ch_unit_id $FIRST_UNIT`

    if [ $LOCAL_UNIT_ID -lt $REMOTE_UNIT_ID ] && [ $LOCAL_UNIT_ID -lt $FIRST_UNIT_ID ]; then
        return 0
    else
        return 1
    fi
} 

##
# ch_peer_leader [--id]
#
# Return the name [or id] of the leader unit
#
# Option --id will have the function return the unit id instead
#
# Returns leader-unit-name[or ID]
ch_peer_leader()
{
    if ch_peer_i_am_leader; then
        # this is the leader, return our own unit name
        local leader="$JUJU_UNIT_NAME"
    else
        # this is  a slave the leader is the head of the list
        local leader="`relation-list | head -n 1`"
    fi
    if [ $# -gt 0 ] && [ "$1" = "--id" ]; then
        echo "`ch_unit_id $leader`"
    else
        echo "$leader"
    fi
}

##
# ch_unit_id <unit-name>
# Returns the unit id
#
# Param <unit-name> is the name of the unit
#
# returns <unit-d> | FALSE
ch_unit_id()
{
    echo "${1##*/}"
}

##
# ch_my_unit_id
# Returns the unit id of the current unit
#
# param none
#
# returns <unit-id> | FALSE
ch_my_unit_id()
{
    echo "`ch_unit_id $JUJU_UNIT_NAME`"
}


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
ch_peer_copy() {
  CH_USAGE="ERROR in $*
USAGE: ch_peer_scp [-r] path1 [...pathN]
USAGE: ch_peer_rsync path1 [...pathN]"
  CH_ssh_key_p="$HOME/.ssh"
  if [ $# -eq 0 ]; then
    juju-log "$CH_USAGE"
    juju-log "ch_peer_copy: please provide at least one argument (path)"
    exit 1
  fi

  ## LEADER ##
  
  if  [ `ch_peer_am_I_leader` = 1 ] ; then
    juju-log "ch_peer_copy: This is our leader"
    
    CH_remote=`relation-get scp-hostname`
    CH_ssh_key_saved=`relation-get scp-ssh-key-saved`
    if [ -z $CH_remote ]; then
      juju-log "ch_peer_copy: We do not have a remote hostname yet"
      CH_remote=0
    fi  
  
    CH_scp_options="-o StrictHostKeyChecking=no -B -v"
    CH_rsync_options="-avz -e ssh"
    CH_paths=""
    CH_copy_command="scp"
    
    while [ "$#" -gt 0 ]; 
    do
      case "$1" in
      "-r") # scp recure
        CH_scp_options="$CH_scp_options -r"
        shift
        ;;
      "-p") # port number
        shift
        CH_scp_options="$CH_scp_options -P $1"
        CH_rsync_options="-avz -e 'ssh -p $1'"
        shift
        ;;
      "--rsync") # rsync secure (-e ssh)
        CH_copy_command="rsync"
        shift
        ;;
      "$0")
        shift
        ;;
      *) # should be a file
        if [ -e "$1" ]; then
          CH_paths="$CH_paths $1 $USER@$CH_remote:$1"
          juju-log "ch_peer_copy: path found: $1"
        else
          juju-log "ch_peer_copy: Path does not exist, skipping distribution of: $1"
        fi
        shift
        ;;
      esac
    done
    if [ ! -n "$CH_paths" ]; then
      juju-log "$CH_USAGE"
      juju-log "ch_peer_copy: please provide at least one path"
      exit 1
    fi
    
    if [ -n $CH_remote ]; then
      # We know where to send file to
      
      case $CH_ssh_key_saved in
      1) # ssh keys have been save, let's copy
        juju-log "ch_peer_copy: $CH_copy_command $CH_scp_options $CH_paths"
        $CH_copy_command $CH_scp_options $CH_paths ||
        relation-set scp-copy-done=1
        ;;
        
      *) # we need to first distribute our ssh key files
        juju-log "ch_peer_copy: distributing ssh key"
        if [ ! -f "$CH_ssh_key_p/id_rsa" ]; then
          ssh-keygen -q -N '' -t rsa -b 2048 -f $CH_ssh_key_p/id_rsa
        fi
        relation-set scp-ssh-key="`cat $CH_ssh_key_p/id_rsa.pub`"
        ;;
        
      esac
    fi 
    
  ## REMOTE ##
      
  else # Not the leader
    juju-log "ch_peer_copy: This is a slave"
 
    CH_scp_copy_done=`relation-get scp-copy-done`
    CH_scp_ssh_key=`relation-get scp-ssh-key`
 
    if [ -n "$CH_scp_copy_done" ] && [ $CH_scp_copy_done = 1 ]; then
      juju-log "ch_peer_copy: copy done, thanks"
      echo "done"
    else
      if [ -n "$CH_scp_ssh_key" ]; then
        mkdir -p $CH_ssh_key_p
        grep -q -F "$CH_scp_ssh_key" $CH_ssh_key_p/authorized_keys
        if [ $? != 0 ]; then
          juju-log "ch_peer_copy: saving ssh key $CH_scp_ssh_key"
          echo "CH_$scp_ssh_key" >> $CH_ssh_key_p/authorized_keys
          relation-set scp-ssh-key-saved=1
        else
          juju-log "ch_peer_copy: ssh keys already saved, thanks"
          relation-set scp-ssh-key-saved=1
        fi
      else
        juju-log "ch_peer_copy: ssh_keys not set yet, later"
        relation-set scp-hostname=`unit-get private-address`
      fi 
    fi 
  fi 

}

