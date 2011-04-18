# vim: syntax=python

import os
import MySQLdb

change_unit = os.environ.get("ENSEMBLE_REMOTE_UNIT")
# We'll name the database the same as the service.
database_name, _ = change_unit.split("/")
# A user per service unit so we can deny access quickly
user = change_unit.replace("/","-")
connection = None

def get_db_cursor():
    # Connect to mysql
    passwd = open("/var/lib/ensemble/mysql.passwd").read().strip()
    print passwd
    connection = MySQLdb.connect(user="root", host="localhost", passwd=passwd)

    return connection.cursor()

