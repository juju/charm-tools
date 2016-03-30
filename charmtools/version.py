
import pkg_resources

def charm_version():
    try:
        from apt.cache import Cache
        charm_vers = Cache()['charm'].versions
        for v in charm_vers:
            if v.is_installed:
                charm_ver = v.version
                break
    except ImportError:
        charm_ver = 'unavailable'
    except:
        charm_ver = 'error'

    return charm_ver


def main():
    version = pkg_resources.get_distribution("charm-tools").version

    print "charm %s" % charm_version()
    print "charm-tools %s" % version


if __name__ == '__main__':
    main()
