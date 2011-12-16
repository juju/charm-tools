output () {
    echo `date`: $*
}

start_output () {
    echo -n `date`: $*
}

start_test () {
    echo -n `date`: Testing $*
}

HELPERS_HOME=${HELPERS_HOME:-"$test_home/../../helpers/sh"}

LIB_SOURCED=1
