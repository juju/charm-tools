# Juju Charms

This is a collection of Juju charms for use as a reference and in
deploying real services using juju. See Juju's home page for
more information.

https://juju.ubuntu.com
https://launchpad.net/charm

# Quick Start

First, you'll need juju. If its not available in your version of Ubuntu
you can use the PPA:

    sudo add-apt-repository ppa:juju/stable
    sudo apt-get update
    sudo apt-get install juju-core

You can install charm-tools from the distro, stable ppa, or daily-builds
PPA.

    sudo apt-get install charm-tools

Alternatively you can branch the project and run the tip of the code.

    bzr branch lp:charm-tools
    cd charm-tools

If you've branched locally, you'll need to add the `charm-tools/bin`
directory to your `$PATH`

    export PATH="$(pwd):${PATH}"

# Directory structure

## bin

tools to help in building charms

## templates

templates for usage in building new charms

# Tools

In order to use any of these charms, once you have juju setup and
working in your path

## create

To generate a new charm from a debian package available on your system

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
