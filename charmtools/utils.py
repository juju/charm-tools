import argparse
import copy
import collections
import hashlib
import importlib
import json
import logging
import os
import re
import six
import subprocess
import sys
import tempfile
import time
from contextlib import contextmanager

from .diff_match_patch import diff_match_patch
import blessings
import pathspec
from path import Path as path

log = logging.getLogger('utils')


@contextmanager
def cd(directory, make=False):
    cwd = os.getcwd()
    if not os.path.exists(directory) and make:
        os.makedirs(directory)
    os.chdir(directory)
    try:
        yield
    finally:
        os.chdir(cwd)


@contextmanager
def tempdir(chdir=True):
    dirname = path(tempfile.mkdtemp())
    if chdir:
        with cd(dirname):
            yield dirname
    else:
        yield dirname
    dirname.rmtree_p()


def deepmerge(dest, src):
    """
    Deep merge all the keys in src. When the value of the key is a dict,
    recursively call deepmerge. When the value of the key is a list, iterate
    the entire list and de-duplicate the list. When neither a dict or a list
    call the python copy.deepcopy method.

    This is destructive (`dest` is modified), as values from `src` may be
    passed through `copy.deepcopy`.
    """
    for k, v in src.items():
        if dest.get(k) and isinstance(v, dict):
            deepmerge(dest[k], v)
        elif dest.get(k) and isinstance(v, list):
            for item in v:
                if item not in dest[k]:
                    dest[k].append(item)
        else:
            dest[k] = copy.deepcopy(v)
    return dest


def delete_path(path, obj):
    """Delete a dotted path from object, assuming each level is a dict"""
    # TODO: Support lists
    parts = path.split('.')
    for p in parts[:-1]:
        obj = obj[p]
    if parts[-1] in obj:
        del obj[parts[-1]]


class NestedDict(dict):
    def __init__(self, dict_or_iterable=None, **kwargs):
        if dict_or_iterable:
            if isinstance(dict_or_iterable, dict):
                self.update(dict_or_iterable)
            elif isinstance(dict_or_iterable, collections.Iterable):
                for k, v in dict_or_iterable:
                    self[k] = v
        if kwargs:
            self.update(kwargs)

    def __setitem__(self, key, value):
        key = key.split('.')
        o = self
        for part in key[:-1]:
            o = o.setdefault(part, self.__class__())
        dict.__setitem__(o, key[-1], value)

    def __getitem__(self, key):
        o = self
        if '.' in key:
            parts = key.split('.')
            key = parts[-1]
            for part in parts[:-1]:
                o = o[part]

        return dict.__getitem__(o, key)

    def __getattr__(self, key):
        try:
            return self[key]
        except KeyError:
            raise AttributeError(key)

    def get(self, key, default=None):
        try:
            return self[key]
        except KeyError:
            return default

    def update(self, other):
        deepmerge(self, other)


class ProcessResult(object):
    def __init__(self, command, exit_code, stdout, stderr):
        self.command = command
        self.exit_code = exit_code
        self.stdout = stdout
        self.stderr = stderr

    def __repr__(self):
        return '<ProcessResult "%s" result %s>' % (self.cmd, self.exit_code)

    @property
    def cmd(self):
        return ' '.join(self.command)

    @property
    def output(self):
        result = ''
        if self.stdout:
            stdout = self.stdout
            if six.PY3:
                stdout = stdout.decode('UTF-8')
            result += stdout
        if self.stderr:
            stderr = self.stderr
            if six.PY3:
                stderr = stderr.decode('UTF-8')
            result += stderr
        return result.strip()

    @property
    def json(self):
        if self.stdout:
            return json.loads(self.stdout)
        return None

    def __eq__(self, other):
        return self.exit_code == other

    def __bool__(self):
        return self.exit_code == 0

    __nonzero__ = __bool__

    def exit_on_error(self):
        if not bool(self):
            sys.stderr.write(
                '{}\n\nCommand failed: {}\n'.format(self.output, self.cmd))
            sys.exit(self.exit_code)


class Process(object):
    def __init__(self, command=None, exit=False, log=log, **kwargs):
        if isinstance(command, str):
            command = (command, )
        self.command = command
        self._exit_on_error = exit
        self.log = log
        self._kw = kwargs

    def __repr__(self):
        return "<Command %s>" % (self.command, )

    def exit_on_error(self, exit=True):
        self._exit_on_error = exit
        return self

    def __call__(self, *args, **kw):
        kwargs = dict(stdout=subprocess.PIPE,
                      stderr=subprocess.STDOUT)
        if self._kw:
            kwargs.update(self._kw)
        kwargs.update(kw)
        if self.command:
            all_args = self.command + args
        else:
            all_args = args
        if 'env' not in kwargs:
            kwargs['env'] = os.environ

        p = subprocess.Popen(all_args, **kwargs)
        stdout, stderr = p.communicate()
        self.log.debug(stdout)
        stdout = stdout.strip()
        if stderr is not None:
            stderr = stderr.strip()
            self.log.debug(stderr)
        exit_code = p.poll()
        result = ProcessResult(all_args, exit_code, stdout, stderr)
        self.log.debug("process: %s (%d)", result.cmd, result.exit_code)
        if self._exit_on_error:
            result.exit_on_error()
        return result


command = Process


class Commander(object):
    def __init__(self, log=log):
        self.log = log

    def set_log(self, logger):
        self.log = logger

    def __getattr__(self, key):
        return command((key,), log=self.log)

    def check(self, *args, **kwargs):
        kwargs.update({'log': self.log})
        return command(command=args, **kwargs).exit_on_error()

    def __call__(self, *args, **kwargs):
        kwargs.update({'log': self.log})
        return command(command=args, shell=True, **kwargs)


sh = Commander()
dig = Process(('dig', '+short'))
api_endpoints = Process(('juju', 'api-endpoints'))


def wait_for(timeout, interval, *callbacks, **kwargs):
    """
    Repeatedly try callbacks until all return True

    This will wait interval seconds between attempts and will error out
    after timeout has been exceeded.

    Callbacks will be called with the container as their argument.

    Setting timeout to zero will loop until cancelled, power runs outs,
    hardware fails, or the heat death of the universe.
    """
    start = time.time()
    if timeout:
        end = start + timeout
    else:
        end = 0

    bar = kwargs.get('bar', None)
    message = kwargs.get('message', None)
    once = 1
    while True:
        passes = True
        if end > 0 and time.time() > end:
            raise OSError("Timeout exceeded in wait_for")
        if bar:
            bar.next(once, message=message)
            if once == 1:
                once = 0
        if int(time.time()) % interval == 0:
            for callback in callbacks:
                result = callback()
                passes = passes & bool(result)
                if passes is False:
                    break
            if passes is True:
                break
        time.sleep(1)


def until(*callbacks, **kwargs):
    return wait_for(0, 20, *callbacks, **kwargs)


def retry(attempts, *callbacks, **kwargs):
    """
    Repeatedly try callbacks a fixed number of times or until all return True
    """
    for attempt in range(attempts):
        if 'bar' in kwargs:
            kwargs['bar'].next(attempt == 0, message=kwargs.get('message'))
        for callback in callbacks:
            if not callback():
                break
        else:
            break
    else:
        raise OSError("Retry attempts exceeded")
    return True


def which(program):
    def is_exe(fpath):
        return os.path.isfile(fpath) and os.access(fpath, os.X_OK)

    fpath, fname = os.path.split(program)
    if fpath:
        if is_exe(program):
            return program
    else:
        for fpath in os.environ["PATH"].split(os.pathsep):
            fpath = fpath.strip('"')
            exe_file = os.path.join(fpath, program)
            if is_exe(exe_file):
                return exe_file
    return None


def load_class(full_class_string, workingdir=None):
    """
    dynamically load a class from a string
    """

    module_path, class_str = full_class_string.rsplit(".", 1)
    if not workingdir:
        workingdir = os.getcwd()
    sys.path.insert(0, workingdir)
    try:
        module = importlib.import_module(module_path)
        return getattr(module, class_str)
    finally:
        sys.path.pop(0)


def walk(pathobj, fn, matcher=None, kind=None, **kwargs):
    """walk pathobj calling fn on each matched entry yielding each
    result. If kind is 'file' or 'dir' only that type ofd entry will
    be walked. matcher is an optional function returning bool indicating
    if the entry should be processed.
    """
    p = path(pathobj)
    walker = p.walk
    if kind == "files":
        walker = p.walkfiles
    elif kind == "dir":
        walker = p.walkdir

    for entry in walker():
        relpath = entry.relpath(pathobj)
        if matcher and not matcher(relpath):
            continue
        yield (entry, fn(entry, **kwargs))


def ignore_matcher(ignores=[]):
    spec = pathspec.PathSpec.from_lines(pathspec.GitIgnorePattern, ignores)

    def matcher(entity):
        return entity not in spec.match_files((entity,))
    return matcher


def sign(pathobj):
    p = path(pathobj)
    if not p.isfile():
        return None
    return hashlib.sha256(p.bytes()).hexdigest()


def delta_signatures(manifest_filename, ignore=None):
    md = path(manifest_filename)
    repo = md.normpath().dirname()

    expected = json.load(md.open())
    current = {}
    for rel, sig in walk(repo, sign, ignore_matcher(ignore or [])):
        rel = rel.relpath(repo)
        current[rel] = sig
    add, change, delete = set(), set(), set()

    for p, s in current.items():
        fp = repo / p
        if not fp.isfile():
            continue

        if p not in expected["signatures"]:
            add.add(p)
            continue
        # layer, kind, sig
        # don't include items generated only for the last layer
        if expected["signatures"][p][0] == "build":
            continue
        if expected["signatures"][p][2] != s:
            change.add(p)

    for p, d in expected["signatures"].items():
        if p not in current:
            delete.add(path(p))
    return add, change, delete


class ColoredFormatter(logging.Formatter):

    def __init__(self, terminal, *args, **kwargs):
        super(ColoredFormatter, self).__init__(*args, **kwargs)
        self._terminal = terminal

    def format(self, record):
        output = super(ColoredFormatter, self).format(record)
        if record.levelno >= logging.CRITICAL:
            line_color = self._terminal.bold_yellow_on_red
        elif record.levelno >= logging.ERROR:
            line_color = self._terminal.red
        elif record.levelno >= logging.WARNING:
            line_color = self._terminal.yellow
        elif record.levelno >= logging.INFO:
            line_color = self._terminal.green
        else:
            line_color = self._terminal.cyan
        return line_color(output)


class TermWriter(object):
    def __init__(self, fp=None, term=None, force_styling=False):
        if fp is None:
            fp = sys.stdout
        self.fp = fp
        if term is None:
            term = blessings.Terminal(force_styling=force_styling)
        self.term = term

    def __getattr__(self, key):
        return getattr(self.term, key)

    def write(self, msg, *args, **kwargs):
        if 't' in kwargs:
            raise ValueError("Using reserved token 't' in TermWriter.write")
        kwargs['t'] = self.term
        self.fp.write(msg.format(*args, **kwargs))


class _O(dict):
    def __getattr__(self, k):
        return self[k]


REACTIVE_PATTERNS = [
    re.compile(r"\s*@when"),
    re.compile(r".set_state\(")
]


def delta_python(orig, dest, patterns=REACTIVE_PATTERNS, context=2):
    """Delta two python files looking for certain patterns"""
    try:
        if isinstance(orig, path):
            od = orig.text()
        elif hasattr(orig, 'read'):
            od = orig.read()
        else:
            raise TypeError("Expected path() or file(), got %s" % type(orig))
    except Exception:
        log.error('Error reading {}'.format(orig))
        raise
    try:
        if isinstance(dest, path):
            dd = dest.text()
        elif hasattr(orig, 'read'):
            dd = dest.read()
        else:
            raise TypeError("Expected path() or file(), got %s" % type(dest))
    except Exception:
        log.error('Error reading {}'.format(dest))
        raise

    differ = diff_match_patch()
    linect = 0
    lastMatch = None
    for res in differ.diff_main(od, dd):
        if res[0] == diff_match_patch.DIFF_EQUAL:
            linect += res[1].count('\n')
            lastMatch = res[:]
            continue
        elif res[0] == diff_match_patch.DIFF_INSERT:
            linect += res[1].count('\n')
        else:
            linect -= res[1].count('\n')

        for p in patterns:
            if p.search(lastMatch[1]):
                yield [linect, lastMatch, res]
                break


def delta_python_dump(orig, dest, patterns=REACTIVE_PATTERNS,
                      context=2, term=None,
                      from_name=None, to_name=None):
    if term is None:
        term = TermWriter()

    def norm_sources(orig, dest):
        if from_name:
            oname = from_name
        else:
            oname = orig
        if to_name:
            dname = to_name
        else:
            dname = dest
        return _O({'orig_name': oname, 'dest_name': dname})

    def prefix_lines(lines, lineno):
        if isinstance(lines, str):
            lines = lines.splitlines()
        for i, l in enumerate(lines):
            lines[i] = "%-5d| %s" % (lineno + i, l)
        return "\n".join(lines)

    i = 0
    for lineno, last, current in delta_python(orig, dest, patterns, context):
        # pull enough context
        if last:
            context_lines = last[1].splitlines()[-context:]
        message = norm_sources(orig, dest)
        message['context'] = prefix_lines(context_lines, lineno - context)
        message['lineno'] = lineno
        message['delta'] = current[1]
        s = {diff_match_patch.DIFF_EQUAL: term.normal,
             diff_match_patch.DIFF_INSERT: term.green,
             diff_match_patch.DIFF_DELETE: term.red}[current[0]]
        message['status_color'] = s
        # output message
        term.write("{t.bold}{m.orig_name}{t.normal} --> "
                   "{t.bold}{m.dest_name}{t.normal}:\n",
                   m=message)
        term.write("{m.context}{m.status_color}{m.delta}{t.normal}\n",
                   m=message)
        i += 1
    return i == 0


class Description(argparse._StoreTrueAction):
    """A argparse action that prints parent parser's description & exits."""
    def __call__(self, parser, namespace, values, option_string=None):
        print(parser.description.split('\n')[0].strip('. '))
        raise SystemExit()


def add_plugin_description(parser):
    parser.add_argument('--description', action=Description)


class OrderedSet(collections.MutableSet):
    def __init__(self, iterable=None):
        self.end = end = []
        end += [None, end, end]
        self.map = {}
        if iterable is not None:
            self |= iterable

    def __len__(self):
        return len(self.map)

    def __contains__(self, key):
        return key in self.map

    def add(self, key):
        if key not in self.map:
            end = self.end
            curr = end[1]
            curr[2] = end[1] = self.map[key] = [key, curr, end]

    def discard(self, key):
        if key in self.map:
            key, prev, next = self.map.pop(key)
            prev[2] = next
            next[1] = prev

    def __iter__(self):
        end = self.end
        curr = end[2]
        while curr is not end:
            yield curr[0]
            curr = curr[2]

    def __reversed__(self):
        end = self.end
        curr = end[1]
        while curr is not end:
            yield curr[0]
            curr = curr[1]

    def pop(self, last=True):
        if not self:
            raise KeyError('set is empty')
        key = self.end[1][0] if last else self.end[2][0]
        self.discard(key)
        return key

    def __repr__(self):
        if not self:
            return '%s()' % (self.__class__.__name__,)
        return '%s(%r)' % (self.__class__.__name__, list(self))

    def __eq__(self, other):
        if isinstance(other, OrderedSet):
            return len(self) == len(other) and list(self) == list(other)
        return set(self) == set(other)


def validate_display_name(entity, linter):
    """Validate the display name info in entity metadata.

    :param entity: dict of entity metadata parsed from metadata.yaml
    :param linter: :class:`CharmLinter` or :class: `BundleLinter` object to
        which info/warning/error messages will be written
    """
    if 'display-name' not in entity:
        linter.info('`display-name` not provided, '
                    'add for custom naming in the UI')
        return

    # Keep display name in sync with the juju/names package.
    # https://github.com/juju/names/blob/master/charm.go#L33
    match = re.match(
        r'^[A-Za-z0-9]+( [-A-Za-z0-9_]|[-A-Za-z0-9_])*$',
        entity['display-name'])
    if not match:
        linter.err('display-name: not in valid format. '
                   'Only letters, numbers, dashes, and hyphens are permitted.')
        return
