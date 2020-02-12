from __future__ import print_function
from __future__ import division
from __future__ import absolute_import
from builtins import *
from builtins import object
import sys
import os
import glob
import shutil
import datetime

assert 'pymel' not in sys.modules or 'PYMEL_DOCSTRINGS_MODE' in os.environ, "to generate docs PYMEL_DOCSTRINGS_MODE=html env var must be set before pymel is imported"

# remember, the processed command examples are not version specific. you must
# run cmdcache.fixCodeExamples() to bring processed examples in from the raw
# version-specific example caches
os.environ['PYMEL_DOCSTRINGS_MODE'] = 'html'

pymel_root = os.path.dirname(os.path.dirname(sys.modules[__name__].__file__))
docsdir = os.path.join(pymel_root, 'docs')
stubdir = os.path.join(pymel_root, 'extras', 'completion', 'py')

useStubs = False

if useStubs:
    sys.path.insert(0, stubdir)
    import pymel
    print(pymel.__file__)
else:
    import pymel
    # make sure dynamic modules are fully loaded
    from pymel.core.uitypes import *
    from pymel.core.nodetypes import *

version = pymel.__version__
SOURCE = 'source'
BUILD_ROOT = 'build'
BUILD = os.path.join(BUILD_ROOT, version)
sourcedir = os.path.join(docsdir, SOURCE)
gendir = os.path.join(sourcedir, 'generated')
buildrootdir = os.path.join(docsdir, BUILD_ROOT)
builddir = os.path.join(docsdir, BUILD)

from pymel.internal.cmdcache import fixCodeExamples

def get_internal_cmds():
    cmds = []
    # they first provided them as 'internalCmds.txt', then as
    # internalCommandList.txt
    notfound = []
    for filename in ('internalCmds.txt', 'internalCommandList.txt'):
        cmdlistPath = os.path.join(docsdir, filename)
        if os.path.isfile(cmdlistPath):
            break
        else:
            notfound.append(cmdlistPath)
    else:
        filepaths = ', '.join(notfound)
        raise RuntimeError("could not find list of internal commands - tried: {}"
                           .format(filepaths))
    with open(os.path.join(docsdir, 'internalCmds.txt')) as f:
        for line in f:
            line = line.strip()
            if line:
                cmds.append(line)
    return set(cmds)

def monkeypatch_autosummary():
    """
    Monkeypatch sphinx to remove autodesk internal commands from the docs. 

    This request comes from Autodesk.

    Instead we do something unbelievably hacky and simply make it appear as
    if these objects don't exist.

    Other solutions investigated:
    - adding a jinja filter for use inside the template: you can provide your
      own template loader, but there's no callback or easily monkey-patchable
      function to setup the template environment, which is where the filters 
      need to be added.  I guess you could monkey-patch 
      jinja2.sandbox.SandboxedEnvironment...
    - adding a 'autodoc-skip-member' callback: our module template does not use
      the :members: directive (because it does some extra fanciness to group 
      objects into sections by type) and as a result 'autodoc-skip-member'
      never fires for module members.
    """
    # this function should get an award for most roundabout solution to a problem
    import sphinx.util.inspect
    import sphinx.ext.autosummary
    import inspect
    if sphinx.util.inspect.safe_getattr.__module__ != 'sphinx.util.inspect':
        print("already patched")
        return

    _orig_safe_getattr = sphinx.util.inspect.safe_getattr

    internal_cmds = get_internal_cmds()

    def safe_getattr(obj, name, *defargs):
        if name not in {'__get__', '__set__', '__delete__'}:
            if hasattr(obj, '__name__') and \
                    obj.__name__ in {'pymel.core.other'} and \
                    name in internal_cmds:
                print("SKIP %s.%s" % (obj.__name__, name))
                # raising an AttributeError silently skips the object
                raise AttributeError
        return _orig_safe_getattr(obj, name, *defargs)

    # autosummary does `from sphinx.util.inspect import safe_getattr` so we 
    # need to override it there
    sphinx.ext.autosummary.safe_getattr = safe_getattr
    # this is not strictly necessar, but I'm paranoid about future changes to 
    # sphinx breaking this hack
    sphinx.util.inspect.safe_getattr = safe_getattr

def generate(clean=True):
    """delete build and auto-generated source directories and re-generate a 
    top-level documentation source file for each module."""
    print("generating %s - %s" % (docsdir, datetime.datetime.now()))
    monkeypatch_autosummary()
    from sphinx.ext.autosummary.generate import main as sphinx_autogen

    if clean:
        clean_build()
        clean_generated()
    os.chdir(sourcedir)

    sphinx_autogen( [''] + '--templates ../templates modules.rst'.split() )
    sphinx_autogen( [''] + '--templates ../templates'.split() + glob.glob('generated/pymel.*.rst') )
    print("...done generating %s - %s" % (docsdir, datetime.datetime.now()))

def clean_build():
    "delete existing build directory"
    if os.path.exists(buildrootdir):
        print("removing %s - %s" % (buildrootdir, datetime.datetime.now()))
        shutil.rmtree(buildrootdir)

def clean_generated():
    "delete existing generated directory"
    if os.path.exists(gendir):
        print("removing %s - %s" % (gendir, datetime.datetime.now()))
        shutil.rmtree(gendir)

def find_dot():
    if os.name == 'posix':
        dot_bin = 'dot'
    else:
        dot_bin = 'dot.exe'

    for p in os.environ['PATH'].split(os.pathsep):
        d = os.path.join(p, dot_bin)
        if os.path.exists(d):
            return d
    raise TypeError('cannot find graphiz dot executable in the path (%s)' % os.environ['PATH'])

def copy_changelog():
    changelog = os.path.join(pymel_root, 'CHANGELOG.rst')
    whatsnew = os.path.join(pymel_root, 'docs', 'source', 'whats_new.rst')
    shutil.copy2(changelog, whatsnew)

class NoSubprocessWindow(object):
    '''Context manager to make subprocess not open a new window by default, on
    windows.

    On windows, whenever a subprocess launches, it opens a window by default.
    Since our sphinx build will be launch a LOT of "dot.exe" subprocess,
    this effectively hijacks the computer while we are building the docs,
    since each new window steals focus. It also slows down doc generation.
    We monkey-patch subprocess to not open a window by default on windows.
    '''
    def __enter__(self):
        import inspect
        import subprocess
        if os.name == 'nt':
            origInit = subprocess.Popen.__init__.__func__
            self.origInit = origInit

            argspec = inspect.getargspec(self.origInit)
            creationflags_index = argspec.args.index('creationflags')
            CREATE_NO_WINDOW_FLAG = 0x08000000

            def __init__(self, *args, **kwargs):
                if (len(args) <= creationflags_index
                        and 'creationflags' not in kwargs):
                    kwargs['creationflags'] = CREATE_NO_WINDOW_FLAG
                    return origInit(self, *args, **kwargs)

            subprocess.Popen.__init__ = __init__
        else:
            self.origInit = None

    def __exit__(self, exc_type, exc_val, exc_tb):
        import subprocess
        if self.origInit is not None:
            subprocess.Popen.__init__ = self.origInit


def build(clean=True, opts=None, filenames=None, **kwargs):
    from sphinx import main as sphinx_build
    print("building %s - %s" % (docsdir, datetime.datetime.now()))

    if clean or not os.path.isdir(gendir):
        generate(clean=clean)

    os.chdir( docsdir )
    if clean:
        clean_build()

    copy_changelog()

    #mkdir -p build/html build/doctrees

    #import pymel.internal.cmdcache as cmdcache
    #cmdcache.fixCodeExamples()
    if opts is None:
        opts = ['']
    else:
        opts = [''] + lists(opts)
    opts += '-b html -d build/doctrees'.split()

    # set some defaults
    dot = kwargs.get('graphviz_dot')
    if dot is None:
        kwargs['graphviz_dot'] = find_dot()
    else:
        if not os.path.isfile(dot):
            raise RuntimeError("passed in graphviz_dot binary did not exist:"
                               " {}".format(dot))

    for key, value in kwargs.items():
        opts.append('-D')
        opts.append( key.strip() + '=' + value.strip() )
    opts.append('-P')
    opts.append(SOURCE)
    opts.append(BUILD)
    if filenames is not None:
        opts.extend(filenames)
    print("sphinx_build({!r})".format(opts))

    with NoSubprocessWindow():
        sphinx_build(opts)
    print("...done building %s - %s" % (docsdir, datetime.datetime.now()))

