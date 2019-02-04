"""Helper for working with a MySQL database"""
import json
import socket
import re
import sys
import platform
import os
import glob

from string import upper

from charmhelpers.core.host import (
    mkdir,
    pwgen,
    write_file
)
from charmhelpers.core.hookenv import (
    config as config_get,
    relation_get,
    related_units,
    unit_get,
    log,
    DEBUG,
    INFO,
    WARNING,
)
from charmhelpers.fetch import (
    apt_install,
    apt_update,
    filter_installed_packages,
)
from charmhelpers.contrib.peerstorage import (
    peer_store,
    peer_retrieve,
)
from charmhelpers.contrib.network.ip import get_host_ip

try:
    import MySQLdb
except ImportError:
    apt_update(fatal=True)
    apt_install(filter_installed_packages(['python-mysqldb']), fatal=True)
    import MySQLdb


class MySQLHelper(object):

    def __init__(self, rpasswdf_template, upasswdf_template, host='localhost',
                 migrate_passwd_to_peer_relation=True,
                 delete_ondisk_passwd_file=True):
        self.host = host
        # Password file path templates
        self.root_passwd_file_template = rpasswdf_template
        self.user_passwd_file_template = upasswdf_template

        self.migrate_passwd_to_peer_relation = migrate_passwd_to_peer_relation
        # If we migrate we have the option to delete local copy of root passwd
        self.delete_ondisk_passwd_file = delete_ondisk_passwd_file

    def connect(self, user='root', password=None):
        log("Opening db connection for %s@%s" % (user, self.host), level=DEBUG)
        self.connection = MySQLdb.connect(user=user, host=self.host,
                                          passwd=password)

    def database_exists(self, db_name):
        cursor = self.connection.cursor()
        try:
            cursor.execute("SHOW DATABASES")
            databases = [i[0] for i in cursor.fetchall()]
        finally:
            cursor.close()

        return db_name in databases

    def create_database(self, db_name):
        cursor = self.connection.cursor()
        try:
            cursor.execute("CREATE DATABASE {} CHARACTER SET UTF8"
                           .format(db_name))
        finally:
            cursor.close()

    def grant_exists(self, db_name, db_user, remote_ip):
        cursor = self.connection.cursor()
        priv_string = "GRANT ALL PRIVILEGES ON `{}`.* " \
                      "TO '{}'@'{}'".format(db_name, db_user, remote_ip)
        try:
            cursor.execute("SHOW GRANTS for '{}'@'{}'".format(db_user,
                                                              remote_ip))
            grants = [i[0] for i in cursor.fetchall()]
        except MySQLdb.OperationalError:
            return False
        finally:
            cursor.close()

        # TODO: review for different grants
        return priv_string in grants

    def create_grant(self, db_name, db_user, remote_ip, password):
        cursor = self.connection.cursor()
        try:
            # TODO: review for different grants
            cursor.execute("GRANT ALL PRIVILEGES ON {}.* TO '{}'@'{}' "
                           "IDENTIFIED BY '{}'".format(db_name,
                                                       db_user,
                                                       remote_ip,
                                                       password))
        finally:
            cursor.close()

    def create_admin_grant(self, db_user, remote_ip, password):
        cursor = self.connection.cursor()
        try:
            cursor.execute("GRANT ALL PRIVILEGES ON *.* TO '{}'@'{}' "
                           "IDENTIFIED BY '{}'".format(db_user,
                                                       remote_ip,
                                                       password))
        finally:
            cursor.close()

    def cleanup_grant(self, db_user, remote_ip):
        cursor = self.connection.cursor()
        try:
            cursor.execute("DROP FROM mysql.user WHERE user='{}' "
                           "AND HOST='{}'".format(db_user,
                                                  remote_ip))
        finally:
            cursor.close()

    def execute(self, sql):
        """Execute arbitary SQL against the database."""
        cursor = self.connection.cursor()
        try:
            cursor.execute(sql)
        finally:
            cursor.close()

    def migrate_passwords_to_peer_relation(self, excludes=None):
        """Migrate any passwords storage on disk to cluster peer relation."""
        dirname = os.path.dirname(self.root_passwd_file_template)
        path = os.path.join(dirname, '*.passwd')
        for f in glob.glob(path):
            if excludes and f in excludes:
                log("Excluding %s from peer migration" % (f), level=DEBUG)
                continue

            _key = os.path.basename(f)
            with open(f, 'r') as passwd:
                _value = passwd.read().strip()

            try:
                peer_store(_key, _value)
                if self.delete_ondisk_passwd_file:
                    os.unlink(f)
            except ValueError:
                # NOTE cluster relation not yet ready - skip for now
                pass

    def get_mysql_password_on_disk(self, username=None, password=None):
        """Retrieve, generate or store a mysql password for the provided
        username on disk."""
        if username:
            template = self.user_passwd_file_template
            passwd_file = template.format(username)
        else:
            passwd_file = self.root_passwd_file_template

        _password = None
        if os.path.exists(passwd_file):
            log("Using existing password file '%s'" % passwd_file, level=DEBUG)
            with open(passwd_file, 'r') as passwd:
                _password = passwd.read().strip()
        else:
            log("Generating new password file '%s'" % passwd_file, level=DEBUG)
            if not os.path.isdir(os.path.dirname(passwd_file)):
                # NOTE: need to ensure this is not mysql root dir (which needs
                # to be mysql readable)
                mkdir(os.path.dirname(passwd_file), owner='root', group='root',
                      perms=0o770)
                # Force permissions - for some reason the chmod in makedirs
                # fails
                os.chmod(os.path.dirname(passwd_file), 0o770)

            _password = password or pwgen(length=32)
            write_file(passwd_file, _password, owner='root', group='root',
                       perms=0o660)

        return _password

    def get_mysql_password(self, username=None, password=None):
        """Retrieve, generate or store a mysql password for the provided
        username using peer relation cluster."""
        excludes = []

        # First check peer relation
        if username:
            _key = 'mysql-{}.passwd'.format(username)
        else:
            _key = 'mysql.passwd'

        try:
            _password = peer_retrieve(_key)
            # If root password available don't update peer relation from local
            if _password and not username:
                excludes.append(self.root_passwd_file_template)

        except ValueError:
            # cluster relation is not yet started; use on-disk
            _password = None

        # If none available, generate new one
        if not _password:
            _password = self.get_mysql_password_on_disk(username, password)

        # Put on wire if required
        if self.migrate_passwd_to_peer_relation:
            self.migrate_passwords_to_peer_relation(excludes=excludes)

        return _password

    def get_mysql_root_password(self, password=None):
        """Retrieve or generate mysql root password for service units."""
        return self.get_mysql_password(username=None, password=password)

    def normalize_address(self, hostname):
        """Ensure that address returned is an IP address (i.e. not fqdn)"""
        if config_get('prefer-ipv6'):
            # TODO: add support for ipv6 dns
            return hostname

        if hostname != unit_get('private-address'):
            return get_host_ip(hostname, fallback=hostname)

        # Otherwise assume localhost
        return '127.0.0.1'

    def get_allowed_units(self, database, username, relation_id=None):
        """Get list of units with access grants for database with username.

        This is typically used to provide shared-db relations with a list of
        which units have been granted access to the given database.
        """
        self.connect(password=self.get_mysql_root_password())
        allowed_units = set()
        for unit in related_units(relation_id):
            settings = relation_get(rid=relation_id, unit=unit)
            # First check for setting with prefix, then without
            for attr in ["%s_hostname" % (database), 'hostname']:
                hosts = settings.get(attr, None)
                if hosts:
                    break

            if hosts:
                # hostname can be json-encoded list of hostnames
                try:
                    hosts = json.loads(hosts)
                except ValueError:
                    hosts = [hosts]
            else:
                hosts = [settings['private-address']]

            if hosts:
                for host in hosts:
                    host = self.normalize_address(host)
                    if self.grant_exists(database, username, host):
                        log("Grant exists for host '%s' on db '%s'" %
                            (host, database), level=DEBUG)
                        if unit not in allowed_units:
                            allowed_units.add(unit)
                    else:
                        log("Grant does NOT exist for host '%s' on db '%s'" %
                            (host, database), level=DEBUG)
            else:
                log("No hosts found for grant check", level=INFO)

        return allowed_units

    def configure_db(self, hostname, database, username, admin=False):
        """Configure access to database for username from hostname."""
        self.connect(password=self.get_mysql_root_password())
        if not self.database_exists(database):
            self.create_database(database)

        remote_ip = self.normalize_address(hostname)
        password = self.get_mysql_password(username)
        if not self.grant_exists(database, username, remote_ip):
            if not admin:
                self.create_grant(database, username, remote_ip, password)
            else:
                self.create_admin_grant(username, remote_ip, password)

        return password


class PerconaClusterHelper(object):

    # Going for the biggest page size to avoid wasted bytes.
    # InnoDB page size is 16MB

    DEFAULT_PAGE_SIZE = 16 * 1024 * 1024
    DEFAULT_INNODB_BUFFER_FACTOR = 0.50

    def human_to_bytes(self, human):
        """Convert human readable configuration options to bytes."""
        num_re = re.compile('^[0-9]+$')
        if num_re.match(human):
            return human

        factors = {
            'K': 1024,
            'M': 1048576,
            'G': 1073741824,
            'T': 1099511627776
        }
        modifier = human[-1]
        if modifier in factors:
            return int(human[:-1]) * factors[modifier]

        if modifier == '%':
            total_ram = self.human_to_bytes(self.get_mem_total())
            if self.is_32bit_system() and total_ram > self.sys_mem_limit():
                total_ram = self.sys_mem_limit()
            factor = int(human[:-1]) * 0.01
            pctram = total_ram * factor
            return int(pctram - (pctram % self.DEFAULT_PAGE_SIZE))

        raise ValueError("Can only convert K,M,G, or T")

    def is_32bit_system(self):
        """Determine whether system is 32 or 64 bit."""
        try:
            return sys.maxsize < 2 ** 32
        except OverflowError:
            return False

    def sys_mem_limit(self):
        """Determine the default memory limit for the current service unit."""
        if platform.machine() in ['armv7l']:
            _mem_limit = self.human_to_bytes('2700M')  # experimentally determined
        else:
            # Limit for x86 based 32bit systems
            _mem_limit = self.human_to_bytes('4G')

        return _mem_limit

    def get_mem_total(self):
        """Calculate the total memory in the current service unit."""
        with open('/proc/meminfo') as meminfo_file:
            for line in meminfo_file:
                key, mem = line.split(':', 2)
                if key == 'MemTotal':
                    mtot, modifier = mem.strip().split(' ')
                    return '%s%s' % (mtot, upper(modifier[0]))

    def parse_config(self):
        """Parse charm configuration and calculate values for config files."""
        config = config_get()
        mysql_config = {}
        if 'max-connections' in config:
            mysql_config['max_connections'] = config['max-connections']

        # Set a sane default key_buffer size
        mysql_config['key_buffer'] = self.human_to_bytes('32M')
        total_memory = self.human_to_bytes(self.get_mem_total())

        log("Option 'dataset-size' has been deprecated, instead by default %d%% of system \
        available RAM will be used for innodb_buffer_pool_size allocation" %
            (self.DEFAULT_INNODB_BUFFER_FACTOR * 100), level="WARN")

        innodb_buffer_pool_size = config.get('innodb-buffer-pool-size', None)

        if innodb_buffer_pool_size:
            innodb_buffer_pool_size = self.human_to_bytes(
                innodb_buffer_pool_size)

            if innodb_buffer_pool_size > total_memory:
                log("innodb_buffer_pool_size; {} is greater than system available memory:{}".format(
                    innodb_buffer_pool_size,
                    total_memory), level='WARN')
        else:
            innodb_buffer_pool_size = int(
                total_memory * self.DEFAULT_INNODB_BUFFER_FACTOR)

        mysql_config['innodb_buffer_pool_size'] = innodb_buffer_pool_size
        return mysql_config
