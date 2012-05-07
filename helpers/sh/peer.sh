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

echo WARNING: peer functions are untested, and may provide unreliable
echo services. Their use is experimental.

. "${HELPERS_HOME:-/usr/share/charm-helper/sh}/unit.sh"

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
    local FIRST_UNIT_ID=`relation-list | cut -d/ -f2 | sort -n | head -n 1`
    if [ -z $FIRST_UNIT_ID ] ; then
      #no one else in the list, we are obviously the leader
      return 0
    fi
    if [ $REMOTE_UNIT_ID -lt $FIRST_UNIT_ID ] ; then
      #remote must be departing, lets not worry about it
      if [ $LOCAL_UNIT_ID -lt $FIRST_UNIT_ID ]; then
          return 0
      else
          return 1
      fi
    else
      if [ $LOCAL_UNIT_ID -lt $REMOTE_UNIT_ID ] && [ $LOCAL_UNIT_ID -lt $FIRST_UNIT_ID ]; then
          return 0
      else
          return 1
      fi
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
        local leader_id=`ch_unit_id $JUJU_UNIT_NAME`
        local leader_name=$JUJU_UNIT_NAME
    else
        # this is  a slave the leader is the head of the list
        local leader_id=`relation-list | cut -d/ -f2 | sort -n | head -n 1`
        local leader_name=`relation-list | grep "/$leader_id$"`
    fi
    if [ $# -gt 0 ] && [ "$1" = "--id" ]; then
        echo $leader_id
    else
        echo $leader_name
    fi
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
#  101 files were sent from the leader
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
  # $USER may not be set
  USER=${USER:-`whoami`}
  # $HOME may not be set
  if [ -z "${HOME:-}" ] ; then
    if [ "$USER" = "root" ] ; then 
      HOME="/$USER"
    else
      HOME="/home/$USER"
    fi  
  fi
  if ! echo "$HOME" | grep -q "$USER" ; then 
    if [ "$USER" = "root" ] ; then 
      HOME="/$USER"
    else
      HOME="/home/$USER"
    fi  
  fi
  local ssh_key_p="$HOME/.ssh"
  local result=100
  
  if [ $# -eq 0 ]; then
    juju-log -l ERROR "$USAGE"
    juju-log -l ERROR "ch_peer_copy: please provide at least one argument (path)"
    return 1
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
      local sourcep="$1"
      shift
      paths="$paths $sourcep $USER@X0X0X0X0:$1"
      juju-log -l DEBUG "ch_peer_copy: paths found: $sourcep -> $1"
      shift
      ;;
    esac
  done
  if [ -z "$paths" ]; then
    juju-log -l ERROR "$USAGE"
    juju-log -l ERROR "ch_peer_copy: please provide at least one path"
    exit 1
  fi
  if [ x"$copy_command" = x"rsync" ]; then
    scp_options=$rsync_options
  fi
  
  local list=""
  list=`relation-list`
  # if we are not in a relation, do ch_peer_copy_new
  if [ -z "${list:-}" ] ; then
    _ch_peer_copy_new "$copy_command $scp_options" "$paths"
    result=$?
    juju-log -l DEBUG "ch_peer_copy: returning $result"
    return $result
  fi

  ## LEADER ##
  
  if ch_peer_i_am_leader ; then
    juju-log -l INFO "ch_peer_copy: This is our leader"
    
    local remote=`relation-get scp-hostname`
    local ssh_key_saved=`relation-get scp-ssh-key-saved`
    if [ -z $remote ] || [ "$remote" = "0" ] ; then
      juju-log -l DEBUG "ch_peer_copy: We do not have a remote hostname yet"
      relation-set scp-copy-done=0
      remote=0
    fi  
    
    if [ -n $remote ]; then
      # We know where to send file to
      
      case $ssh_key_saved in
      1) # ssh keys have been saved, let's copy
        paths=`echo "$paths" | sed "s/X0X0X0X0/$remote/g"`
        local p1=""
        #we do not want globbing in the loop as it would mess with the number of passes and we work on pairs
        local globstate=`set -o | grep "noglob" | grep -q off && echo "+f" || echo "-f"`
        set -f
        for path in $paths ; do 
          if [ "$p1" != "" ] ; then
            juju-log -l INFO  "ch_peer_copy: $copy_command $scp_options $p1 $path"
            #globbing is wanted here to handle 
            set +f
            eval "$copy_command $scp_options $p1 $path"
            set -f
            p1=""
          else
            p1=$path
          fi
        done
        set $globstate
        relation-set scp-copy-done=1
        #save host and paths for later use
        _ch_peer_copy_save "$copy_command" "$scp_options" "$remote" "$paths" "$JUJU_REMOTE_UNIT"
        juju-log -l DEBUG "ch_peer_copy: save done"
        result=101
        ;;
        
      *) # we need to first distribute our ssh key files
        juju-log -l DEBUG "ch_peer_copy: distributing ssh key"
        if [ ! -f "$ssh_key_p/id_rsa" ]; then
          ssh-keygen -q -N '' -t rsa -b 2048 -f $ssh_key_p/id_rsa
        fi
        relation-set scp-ssh-key="`cat $ssh_key_p/id_rsa.pub`"
        ;;
        
      esac
    fi 
    
  ## REMOTE ##
      
  else # Not the leader
    juju-log -l INFO "ch_peer_copy: This is a slave"
 
    local scp_copy_done=`relation-get scp-copy-done`
    local scp_ssh_key="`relation-get scp-ssh-key`"
    relation-set scp-hostname=`unit-get private-address`
 
    if [ -n "$scp_copy_done" ] && [ $scp_copy_done = 1 ]; then
      juju-log -l DEBUG "ch_peer_copy: copy done, thanks"
      result=0
    else
      if [ -n "$scp_ssh_key" ]; then
        juju-log "ssh key dir: $ssh_key_p"
        mkdir -p $ssh_key_p
        chmod 700 $ssh_key_p
        if ! grep -q -F "$scp_ssh_key" $ssh_key_p/authorized_keys ; then
          if [ "$USER" = "root" ] ; then
            # if we are root, need to ensure we can login
            if ! grep -q "^PermitRootLogin yes" /etc/ssh/sshd_config ; then
              juju-log -l ERROR "PermitRootLogin is not set to yes and you are root. Please use another user or call 'ch_sshd_set_root_login 1' first"
              return 1
            fi
          fi
          juju-log -l DEBUG "ch_peer_copy: saving ssh key $scp_ssh_key"
          echo "$scp_ssh_key" >> $ssh_key_p/authorized_keys
          relation-set scp-ssh-key-saved=1
        else
          juju-log -l DEBUG "ch_peer_copy: ssh keys already saved, thanks"
          relation-set scp-ssh-key-saved=1
        fi
        chmod 600 "$ssh_key_p/authorized_keys"
      else
        juju-log -l DEBUG "ch_peer_copy: ssh_keys not set yet, later"
        relation-set scp-ssh-key-saved=0 #we can't count on this being initialized correctly
      fi 
    fi 
  fi 

  juju-log "ch_peer_copy: returning: $result"
  return $result
}

##
# ch_sshd_set_root_login [0|1]
#
# modify /etc/ssh/sshd_config to set PermitRootLogin and reload ssh server
#
# param
#  0 disable
#  1 enable (default)
#
# returns nothing

ch_sshd_set_root_login() {
  local on=${1:-1}
  if [ $on = 1 ] ; then
    if ! grep -q "^PermitRootLogin yes" /etc/ssh/sshd_config ; then
      sed -i 's/PermitRootLogin no/PermitRootLogin yes/' /etc/ssh/sshd_config
      service ssh reload
    fi
  else  
    if ! grep -q "^PermitRootLogin no" /etc/ssh/sshd_config ; then
      sed -i 's/PermitRootLogin yes/PermitRootLogin no/' /etc/ssh/sshd_config
      service ssh reload
    fi
  fi
  return 0
}

_ch_peer_copy_set_paths() {
  juju-log -l DEBUG "_ch_peer_copy_set_paths"
  local unitname=""
  unitname=`echo $JUJU_UNIT_NAME | sed 's/\//-/g'`
  CH_PEER_COPY_P="/var/lib/juju/$unitname"
  if [ ! `mkdir -p $CH_PEER_COPY_P 2>/dev/null` ] ; then
    if [ ! -e $CH_PEER_COPY_P ]; then
      CH_PEER_COPY_P="${HOME:-/root}/ch_test/$unitname"
      mkdir -p $CH_PEER_COPY_P
    fi
  fi
  CH_PEER_COPY_HOST_F="$CH_PEER_COPY_P/ch_peer_copy_hosts"
  CH_PEER_COPY_PATHS_F="$CH_PEER_COPY_P/ch_peer_copy_paths"
}

# Save copy commands and host for later replay
_ch_peer_copy_save() {
  # $1 copy_command
  # $2 options
  # $3 remote host
  # $4 paths
  # $5 remote unit name
  
  juju-log -l DEBUG "_ch_peer_copy_save: $*"
  
  _ch_peer_copy_set_paths
  
  #save paths
  local suffix=`echo "$1%$2" | base64 -w 0 `
  local paths=`echo "$4" | base64 -w 0`
  local do_save=1
  
  juju-log -l DEBUG "_ch_peer_copy_save: $* in ${CH_PEER_COPY_PATHS_F}-$suffix"
  
  if [ -e "${CH_PEER_COPY_PATHS_F}-$suffix" ]; then
    if grep -q -F "$paths" "${CH_PEER_COPY_PATHS_F}-$suffix"  ; then
      do_save=0
    fi
  fi
  if [ $do_save = 1 ] ; then
    juju-log -l DEBUG "_ch_peer_copy_save: saving $paths in ${CH_PEER_COPY_PATHS_F}-$suffix"
    echo "$paths" >> ${CH_PEER_COPY_PATHS_F}-$suffix
    juju-log -l DEBUG "_ch_peer_copy_save: paths: saved"
  fi
  do_save=1
  
  
  #save hosts
  if [ -e "${CH_PEER_COPY_HOST_F}" ]; then
    if grep -q -F "$3" "${CH_PEER_COPY_HOST_F}" ; then
      do_save=0
    fi
  fi
  [ $do_save = 1 ] && echo "$5 $3" >> $CH_PEER_COPY_HOST_F
  juju-log -l DEBUG "_ch_peer_copy_save: host: $5 $3"
}

# do a new copy when not called within a relation
# returns
#  1 when there was an error
#  100 when the file is not copied
#  101 when the file is sent from server

_ch_peer_copy_new() {
  # $1 "$copy_command $scp_options" 
  # $2 "$paths"
  
  _ch_peer_copy_set_paths
  local result=100
  local hosts=""
  local paths=""
  
  if [ -e "$CH_PEER_COPY_HOST_F" ] ; then
    hosts=`cat $CH_PEER_COPY_HOST_F | cut -d" " -f2`
    
    for h in $hosts ;
    do
      paths=`echo "$2" | sed "s/X0X0X0X0/$h/"`
      local p1=""
      #we do not want globbing in the loop as it would mess with the number of passes and we work on pairs
      local globstate=`set -o | grep "noglob" | grep -q off && echo "+f" || echo "-f"`
      set -f
      for path in $paths ; do 
        if [ "$p1" != "" ] ; then
          juju-log -l INFO "_ch_peer_copy_new: $1 $p1 $path"
          set +f
          eval "$1 $p1 $path"
          set -f
          p1=""
        else
          p1=$path
        fi
      done
      set $globstate
      result=101
    done
  else
    juju-log -l DEBUG "ch_peer_copy_new: no host cache yet"
  fi
  juju-log -l DEBUG "_ch_peer_copy_new: returning $result"
  return $result
}

##
# ch_peer_copy_replay
#
# do a replay of all previous cached copies 
# would typically be used within a config changed to resync
# files that might have been modified to all peers in the relation
#
# param none
#
# returns
#  0 when the file is copied
#  1 when there was an error
#  100 when the file is not copied

ch_peer_copy_replay() {
  _ch_peer_copy_set_paths
  local result=100
  local hosts=""
  local copies=""
  local h=""
  local c=""
  local commandopt=""
  local list_paths=""
  local encp=""
  local mpath=""
  
  if [ ! -e "$CH_PEER_COPY_HOST_F" ] ; then
    juju-log -l DEBUG "ch_peer_copy_replay: no host cache yet"
    result=1
  fi
  
  if [ $result = 100 ];  then
   hosts=`cat $CH_PEER_COPY_HOST_F`
   copies=`ls ${CH_PEER_COPY_PATHS_F}-* | xargs -n1 basename`
   
   if [ -z "$copies" ] ; then
     juju-log -l DEBUG "ch_peer_copy_replay: no command cache yet"
     result=1
   fi
  fi
  
  if [ $result = 100 ];  then
   for h in $hosts ;
   do
     
     for c in $copies ; 
     do
       commandopt=`echo $c | cut -d- -f2 | base64 -d | sed 's/%/ /'`  
       list_paths=`cat $CH_PEER_COPY_P/$c`
      
       for encp in $list_paths ;
       do
         mpath=`echo $encp | base64 -d`
         local p1=""
         #we do not want globbing in the loop as it would mess with the number of passes and we work on pairs
         local globstate=`set -o | grep "noglob" | grep -q off && echo "+f" || echo "-f"`
         set -f
         for path in $mpath ; do 
           if [ "$p1" != "" ] ; then
             juju-log -l INFO "ch_peer_copy_replay: $commandopt $p1 $path"
             set +f
             eval "$commandopt $p1 $path"
             set -f
             p1=""
           else
             p1=$path
           fi
         done
         set $globstate
         result=0
       done
       
     done
     
   done
  fi
  return $result
}

##
# ch_peer_copy_cleanup <remote-unit>
#
# Removes a parting remote unit fron the host cache
# Should be called for each peer-relation-departed
#
# param
#  <remote-unit>    name of the remote unit
#
# returns nothing

ch_peer_copy_cleanup() {
   juju-log -l DEBUG "ch_peer_copy_cleanup: $1"
   _ch_peer_copy_set_paths
   if [ ! -e "$CH_PEER_COPY_HOST_F" ] ; then
    juju-log -l DEBUG "ch_peer_copy_cleanup: no host cache yet"
    return
   fi
   local unitname=""
   unitname=`echo $1 | sed -e 's/\(\.\|\/\|\*\|\[\|\]\)/\\&/g'`
   sed -i "/^$unitname.*$/d" $CH_PEER_COPY_HOST_F
   return 0
}

