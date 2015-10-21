# Juju Charm Tools

[![Build Status](https://travis-ci.org/juju/charm-tools.svg?branch=master)](https://travis-ci.org/juju/charm-tools)

This is a collection of tools to make writing Juju charms easier. See Juju's
home page for more information.

https://jujucharms.com/

## Quick Start

### Get Juju

First, you'll need Juju. If its not available in your version of Ubuntu
you can use the PPA:

    sudo add-apt-repository ppa:juju/stable
    sudo apt-get update
    sudo apt-get install juju-core

### Get Charm Tools

Most people will want to install charm-tools from the Juju PPA.

    sudo apt-get install charm-tools

Alternatively you can download the project and run the tip of the code.

    git clone http://github.com/juju/charm-tools
    cd charm-tools


# Tools

In order to use any of these tools you need to have Juju setup and
working in your path

## create

To generate a new charm from a Debian package available on your system

    juju charm create foo

This should add a directory to charms with the name foo, and some of the
metadata.yml and hooks filled in. It will create these in $CHARM_HOME
or under the current working directory.

## proof

To perform basic static analysis on a charm, run

    juju charm proof foo

It will analyze the charm for any obvious mistakes.

## getall

Retrieves all of the charms in the charm distribution via bzr.

## subscribers

This is used to check the quality of maintainer<->bug subscriptions in
launchpad since we do not have this relationship automatically setup.

As a maintainer, if you would like to ensure that you are subscribed to
all of your charms you can run this command:

    juju charm subscribers --fix-unsubscribed --maintainer you@youremail.com --repository path/to/your/charms
