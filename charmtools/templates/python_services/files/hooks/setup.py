def pre_install():
    install_charmhelpers()


def install_charmhelpers():
    try:
        import charmhelpers  # noqa
    except ImportError:
        import os
        import sys
        import subprocess
        subprocess.check_call(['apt-get', 'install', '-y', 'python-pip'])
        subprocess.check_call(['pip', 'install', 'charmhelpers'])
        os.execv(sys.executable, sys.argv)
