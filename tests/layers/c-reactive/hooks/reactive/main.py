from charmhelpers.core.reactive import when
from charmhelpers.core import hookenv

@when('db.database.available')
def pretend_we_have_db(pgsql):
    hookenv.log("Got db: %s:%s" %(pgsql.host(), pgsql.database()))
