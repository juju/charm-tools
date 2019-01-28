#
# Copyright 2014 Canonical Ltd.
#
# Authors:
#  Edward Hope-Morley <opentastic@gmail.com>
#

import time

from charmhelpers.core.hookenv import (
    log,
    INFO,
)


def retry_on_exception(num_retries, base_delay=0, exc_type=Exception):
    """If the decorated function raises exception exc_type, allow num_retries
    retry attempts before raise the exception.
    """
    def _retry_on_exception_inner_1(f):
        def _retry_on_exception_inner_2(*args, **kwargs):
            retries = num_retries
            multiplier = 1
            while True:
                try:
                    return f(*args, **kwargs)
                except exc_type:
                    if not retries:
                        raise

                delay = base_delay * multiplier
                multiplier += 1
                log("Retrying '%s' %d more times (delay=%s)" %
                    (f.__name__, retries, delay), level=INFO)
                retries -= 1
                if delay:
                    time.sleep(delay)

        return _retry_on_exception_inner_2

    return _retry_on_exception_inner_1
