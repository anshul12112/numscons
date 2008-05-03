# This module cannot be imported directly, because it needs scons module.
from os.path import join as pjoin

from SCons.Environment import Environment

from numscons.core.misc import get_additional_toolpaths

class NumpyEnvironment(Environment):
    """An SCons Environment subclass which knows how to deal with distutils
    idiosyncraties."""
    def __init__(self, *args, **kw):
        Environment.__init__(self, *args, **kw)

    def Configure(self, *args, **kw):
        if kw.has_key('conf_dir') or kw.has_key('log_file'):
            # XXX handle this gracefully
            assert 0 == 1
        else:
            kw['conf_dir'] = pjoin(self['build_dir'], '.sconf')
            kw['log_file'] = pjoin(self['build_dir'], 'config.log')
        return Environment.Configure(self, *args, **kw)

    def Tool(self, toolname, path = None):
        """Like SCons.Tool, but knows about numscons specific toolpaths."""
        if path:
            return Environment.Tool(self, toolname, 
                    path + get_additional_toolpaths(self))
        else:
            return Environment.Tool(self, toolname, get_additional_toolpaths(self))

