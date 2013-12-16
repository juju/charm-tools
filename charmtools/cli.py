import os
import sys
import glob


def parser_defaults(parser):
    parser.add_argument('-b', '--bundle', action='store_true',
                        help='Process as a bundle')
    parser.add_argument('--debug', action='store_true',
                        help='Provide additional debug information')

    return parser


def usage(exit_code=0, bundle=False):
    sys.stderr.write('usage: %s subcommand\n' % os.path.basename(sys.argv[0]))
    subs = subcommands(os.path.dirname(os.path.realpath(__file__)))
    sys.stderr.write('\n  Available subcommands are:\n    ')
    sys.stderr.write('\n    '.join(subs))
    sys.stderr.write('\n')
    sys.exit(exit_code)


def subcommands(scripts_dir):
    subs = []
    for path in os.environ['PATH'].split(os.pathsep):
        path = path.strip('"')
        for cmd in glob.glob(os.path.join(path, 'charm-*%s' % ext())):
            sub = os.path.basename(cmd)
            sub = sub.split('charm-')[1].replace(ext(), '')
            subs.append(sub)

    subs = sorted(set(subs))
    # Removes blacklisted items from the subcommands list.
    return filter(lambda s: s not in ['mr', 'charms'], subs)


def ext():
    return '.exe' if os.name == 'nt' else ''
