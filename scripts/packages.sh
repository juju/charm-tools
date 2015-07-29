#!/bin/bash

function apt_install() {
    packages=$@
    missing=()
    for p in $packages; do
        if ! dpkg-query -s $p &> /dev/null; then
            missing+=($p)
        fi
    done
    if [ -n "${missing}" ]; then
        sudo apt-get update
        sudo apt-get install -y ${missing}
        return 1
    fi
    return 0
}
apt_install $@
exit $?
