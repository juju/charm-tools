#!/usr/bin/python3

import amulet

d = amulet.Deployment()

$deploy
$relate
# Don't forget to expose using d.expose(service)

try:
    d.setup(timeout=900)
    d.sentry.wait()
except amulet.helpers.TimeoutError:
    amulet.raise_status(amulet.SKIP, msg="Environment wasn't stood up in time")
except:
    raise

# Now you can use d.sentry.unit[UNIT] to address each of the units and perform
# more in-depth steps. There are three test statuses: amulet.PASS, amulet.FAIL,
# and amulet.SKIP - these can be triggered with amulet.raise_status(). Each
# d.sentry.unit[] has the following methods:
# - .info - An array of the information of that unit from Juju
# - .file(PATH) - Get the details of a file on that unit
# - .file_contents(PATH) - Get plain text output of PATH file from that unit
# - .directory(PATH) - Get details of directory
# - .directory_contents(PATH) - List files and folders in PATH on that unit
# - .relation(relation, service:rel) - Get relation data from return service

# Make sure to rename this file from something other than 00-autogen
