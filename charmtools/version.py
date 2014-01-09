
import pkg_resources


def main():
    version = pkg_resources.get_distribution("charm-tools").version
    print "%s %s" % ('charm-tools', version)


if __name__ == '__main__':
    main()
