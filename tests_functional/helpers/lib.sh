output () {
    echo `date`: $*
}

start_output () {
    echo -n `date`: $*
}

start_test () {
    echo -n `date`: Testing $*
}

shell_type=`echo $0 | awk -F. '{print $NF}'`

HELPERS_HOME=${HELPERS_HOME:-"$test_home/../../helpers/$shell_type"}

LIB_SOURCED=1
