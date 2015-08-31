#!/bin/bash
#
#    "             "
#  mmm   m   m   mmm   m   m
#    #   #   #     #   #   #
#    #   #   #     #   #   #
#    #   "mm"#     #   "mm"#
#    #             #
#  ""            ""
# This file is managed by Juju. Do not make local changes.

set -eu

BACKUP_DIR=${1}
RETENTION=${2}

if [ ! -d "${BACKUP_DIR}" ] ; then
    echo "Backup directory ${BACKUP_DIR} does not exitst!"
    exit 1
fi
if [ -z "${RETENTION}" ] ; then
    echo "Please specify backup retention count!"
    exit 1
fi

cd ${BACKUP_DIR}
PASSWORD=$(cat /var/lib/mysql/mysql.passwd)

mysqldump -p${PASSWORD} --all-databases --ignore-table=mysql.event | gzip > backup.sql.gz
savelog -q -c ${RETENTION} -l backup.sql.gz
