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
# ch_peer_copy [-r|--rsync][-p <port>][-o "<opt>"] sourcepath1 destpath1 [... sourcepathN destpathN]
# ch_peer_scp [-r][-p <port>][-o "<opt>"] sourcepath1 destpath1 [... sourcepathN destpathN]
# ch_peer_rsync [-p <port>] sourcepath1 destpath1 [... sourcepathN destpathN]
#
# distribute a list of file to all slave of the peer relation
#
# param
#  -r            recursive scp copy (scp only, always on with rsync)
#  -p <port>     destination port to connect to
#  -o "<opt>"    any pathttrough options to the copy util
#  --rsync       use rsync instead of scp
#  sourcepath    path from which to copy (do not specify host, it will always
#                be coming from the leader of the peer relation)
#  destpath      path to which to copy (do not specify host, it will always
#                be the slaves of the peer relation)
#
# returns
#  0 when the file is copied
#  1 when there was an error
#  100 when the file is not copied
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
  local USAGE="ERROR in $*
USAGE: ch_peer_scp [-r][-p <port>][-o \"<opt>\"] sourcepath1 destpath1 [... sourcepathN destpathN]
USAGE: ch_peer_rsync [-p <port>][-o \"<opt>\"] sourcepath1 destpath1 [... sourcepathN destpathN]"
  if [ x"$USER" = x"root" ] ; then
    #juju sets $HOME to /home/ubuntu while user is root :(
    local ssh_key_p="/root/.ssh"
  else
    local ssh_key_p="$HOME/.ssh"
  fi
  local result=100
  
  if [ $# -eq 0 ]; then
    juju-log "$USAGE"
    juju-log "ch_peer_copy: please provide at least one argument (path)"
    return 1
  fi

  ## LEADER ##
  
  if ch_peer_i_am_leader ; then
    juju-log "ch_peer_copy: This is our leader"
    
    local remote=`relation-get scp-hostname`
    local ssh_key_saved=`relation-get scp-ssh-key-saved`
    if [ -z $remote ]; then
      juju-log "ch_peer_copy: We do not have a remote hostname yet"
      remote=0
    fi  
  
    local scp_options="-o StrictHostKeyChecking=no -B"
    local rsync_options=""
    local paths=""
    local copy_command="scp"
    
    while [ "$#" -gt 0 ]; 
    do
      case "$1" in
      "-r") # scp recure
        scp_options="$scp_options -r"
        shift
        ;;
      "-p") # port number
        shift
        scp_options="$scp_options -P $1"
        rsync_options="$rsync_options -e 'ssh -p $1 -o StrictHostKeyChecking=no'"
        shift
        ;;
      "-o") # passthrough option
        shift
        scp_options="$scp_options $1"
        rsync_options="$rsync_options $1"
        shift
        ;;
      "--rsync") # rsync secure (-e ssh)
        copy_command="rsync"
        shift
        ;;
      "$0")
        shift
        ;;
      *) # should be a pair of file
        if [ -e `echo "$1" | sed 's/\*$//'` ]; then
          local sourcep="$1"
          shift
          paths="$paths $sourcep $USER@$remote:$1"
          juju-log "ch_peer_copy: paths found: $sourcep -> $1"
        else
          juju-log "ch_peer_copy: unknown option, skipping: $1"
        fi
        shift
        ;;
      esac
    done
    if [ ! -n "$paths" ]; then
      juju-log "$USAGE"
      juju-log "ch_peer_copy: please provide at least one path"
      return 1
    fi
    
    if [ -n $remote ]; then
      # We know where to send file to
      
      case $ssh_key_saved in
      1) # ssh keys have been save, let's copy
        if [ x"$copy_command" = x"rsync" ]; then
          scp_options="$rsync_options"
        fi
        juju-log "ch_peer_copy: $copy_command $scp_options $paths"
        eval "$copy_command $scp_options $paths"
        relation-set scp-copy-done=1
        ;;
        
      *) # we need to first distribute our ssh key files
        juju-log "ch_peer_copy: distributing ssh key"
        if [ ! -f "$ssh_key_p/id_rsa" ]; then
          ssh-keygen -q -N '' -t rsa -b 2048 -f $ssh_key_p/id_rsa
        fi
        relation-set scp-ssh-key="`cat $ssh_key_p/id_rsa.pub`"
        ;;
        
      esac
    fi 
    
  ## REMOTE ##
      
  else # Not the leader
    juju-log "ch_peer_copy: This is a slave"
 
    local scp_copy_done=`relation-get scp-copy-done`
    local scp_ssh_key="`relation-get scp-ssh-key`"
 
    if [ -n "$scp_copy_done" ] && [ $scp_copy_done = 1 ]; then
      juju-log "ch_peer_copy: copy done, thanks"
      result=0
    else
      if [ -n "$scp_ssh_key" ]; then
        juju-log "ssh key dir: $ssh_key_p"
        mkdir -p $ssh_key_p
        chmod 700 $ssh_key_p
        if ! grep -q -F "$scp_ssh_key" $ssh_key_p/authorized_keys ; then
          juju-log "ch_peer_copy: saving ssh key $scp_ssh_key"
          echo "$scp_ssh_key" >> $ssh_key_p/authorized_keys
          relation-set scp-ssh-key-saved=1
        else
          juju-log "ch_peer_copy: ssh keys already saved, thanks"
          relation-set scp-ssh-key-saved=1
        fi
        chmod 600 "$ssh_key_p/authorized_keys"
      else
        juju-log "ch_peer_copy: ssh_keys not set yet, later"
        relation-set scp-hostname=`unit-get private-address`
      fi 
    fi 
  fi 
  juju-log "ch_peer_copy: returning: $result"
  return $result
}

