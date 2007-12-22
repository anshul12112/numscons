#! /usr/bin/env python
# Last Change: Tue Dec 04 02:00 PM 2007 J

# This module defines some helper functions, to be used by high level checkers

import os
from copy import deepcopy

from numscons.core.libinfo import get_config_from_section, get_config

# Tools to save and restore environments construction variables (the ones often
# altered for configuration tests)
_arg2env = {'cpppath' : 'CPPPATH',
            'cflags' : 'CFLAGS',
            'libpath' : 'LIBPATH',
            'libs' : 'LIBS',
            'linkflags' : 'LINKFLAGS',
            'rpath' : 'RPATH',
            'frameworks' : 'FRAMEWORKS'}

def save_and_set(env, opts):
    """keys given as config opts args."""
    saved_keys = {}
    keys = opts.data.keys()
    for k in keys:
        saved_keys[k] = (env.has_key(_arg2env[k]) and\
                         deepcopy(env[_arg2env[k]])) or\
                        []
    kw = zip([_arg2env[k] for k in keys], [opts.data[k] for k in keys])
    kw = dict(kw)
    env.AppendUnique(**kw)
    return saved_keys

def restore(env, saved_keys):
    keys = saved_keys.keys()
    kw = zip([_arg2env[k] for k in keys], 
             [saved_keys[k] for k in keys])
    kw = dict(kw)
    env.Replace(**kw)

class ConfigOpts:
    # Any added key should be added as an argument to __init__ 
    _keys = ['cpppath', 'cflags', 'libpath', 'libs', 'linkflags', 'rpath',
             'frameworks']
    def __init__(self, cpppath = None, cflags = None, libpath = None, libs = None, 
                 linkflags = None, rpath = None, frameworks = None):
        data = {}

        if not cpppath:
            data['cpppath'] = []
        else:
            data['cpppath'] = cpppath

        if not cflags:
            data['cflags'] = []
        else:
            data['cflags'] = cflags

        if not libpath:
            data['libpath'] = []
        else:
            data['libpath'] = libpath

        if not libs:
            data['libs'] = []
        else:
            data['libs'] = libs

        if not linkflags:
            data['linkflags'] = []
        else:
            data['linkflags'] = linkflags

        if not rpath:
            data['rpath'] = []
        else:
            data['rpath'] = rpath

        if not frameworks:
            data['frameworks'] = []
        else:
            data['frameworks'] = frameworks

        self.data = data

    def __getitem__(self, key):
        return self.data[key]

    def __setitem__(self, key, item):
        self.data[key] = item

    def __repr__(self):
        msg = [r'%s : %s' % (k, i) for k, i in self.data.items()]
        return '\n'.join(msg)

# Implementation function to check symbol in a library
def check_symbol(context, headers, sym, extra = r''):
    # XXX: add dep vars in code
    #code = [r'#include <%s>' %h for h in headers]
    code = []
    code.append(r'''
#undef %(func)s
#ifdef __cplusplus
extern "C" 
#endif
char %(func)s();

int main()
{
return %(func)s();
return 0;
}
''' % {'func' : sym})
    code.append(extra)
    return context.TryLink('\n'.join(code), '.c')

class ConfigRes:
    def __init__(self, name, cfgopts, origin, version = None):
        self.name = name
        self.cfgopts = cfgopts
        self.origin = origin
        self.version = version

    def __getitem__(self, key):
        return self.cfgopts.data[key]

    def __setitem__(self, key, item):
        self.cfgopts.data[key] = item

    def is_customized(self):
        return bool(self.origin)

    def __repr__(self):
        msg = ['Using %s' % self.name]
        if self.is_customized():
            msg += [  'Customized items site.cfg:']
        else:
            msg += ['  Using default configuration:']

        msg += ['  %s : %s' % (k, i) for k, i in self.cfgopts.data.items() if len(i) > 0]
        msg += ['  Version is : %s' % self.version]
        return '\n'.join(msg)

    def __str__(self):
        return self.__repr__()

def _check_headers(context, cpppath, cflags, headers, autoadd):          
    """Try to compile code including the given headers."""       
    env = context.env        
         
    #----------------------------        
    # Check headers are available        
    #----------------------------        
    oldCPPPATH = (env.has_key('CPPPATH') and deepcopy(env['CPPPATH'])) or []         
    oldCFLAGS = (env.has_key('CFLAGS') and deepcopy(env['CFLAGS'])) or []        
    env.AppendUnique(CPPPATH = cpppath)          
    env.AppendUnique(CFLAGS = cflags)        
    # XXX: handle context        
    hcode = ['#include <%s>' % h for h in headers]       
         
    # HACK: we add cpppath in the command of the source, to add dependency of        
    # the check on the cpppath.          
    hcode.extend(['#if 0', '%s' % cpppath, '#endif\n'])          
    src = '\n'.join(hcode)       
         
    ret = context.TryCompile(src, '.c')          
    if ret == 0 or autoadd == 0:         
        env.Replace(CPPPATH = oldCPPPATH)        
        env.Replace(CFLAGS = oldCFLAGS)          
        
    return ret 

def check_include_and_run(context, name, opts, headers, run_src, autoadd = 1):
    """This is a basic implementation for generic "test include and run"
    testers.
    
    For example, for library foo, which implements function do_foo, and with
    include header foo.h, this will:
        - test that foo.h is found and compilable by the compiler
        - test that the given source code can be compiled. The source code
          should contain a simple program with the function.
          
    Arguments:
        - name: name of the library
        - cpppath: list of directories
        - headers: list of headers
        - run_src: the code for the run test
        - libs: list of libraries to link
        - libpath: list of library path.
        - linkflags: list of link flags to add."""

    context.Message('Checking for %s ... ' % name)
    env = context.env

    ret = _check_headers(context, opts['cpppath'], opts['cflags'], headers, 
                         autoadd)
    if not ret:
        context.Result('Failed: %s include not found' % name)
        return 0

    #------------------------------
    # Check a simple example works
    #------------------------------
    saved = save_and_set(env, opts)
    try:
        # HACK: we add libpath and libs at the end of the source as a comment, to
        # add dependency of the check on those.
        src = '\n'.join([r'#include <%s>' % h for h in headers] +\
                        [run_src, r'#if  0', r'%s' % str(opts), r'#endif', '\n'])
        ret, out = context.TryRun(src, '.c')
    finally:
        if (not ret or not autoadd):
            # If test failed or autoadd is disabled, restore everything
            restore(env, saved)

    if not ret:
        context.Result('Failed: %s test could not be linked and run' % name)
        return 0

    context.Result(ret)
    return ret

def check_run_f77(context, name, opts, run_src, autoadd = 1):
    """This is a basic implementation for generic "run" testers.
    
    For example, for library foo, which implements function do_foo
        - test that the given source code can be compiled. The source code
          should contain a simple program with the function.
          
    Arguments:
        - name: name of the library."""

    context.Message('Checking for %s ... ' % name)
    env = context.env

    #------------------------------
    # Check a simple example works
    #------------------------------
    saved = save_and_set(env, opts)
    try:
        # HACK: we add libpath and libs at the end of the source as a comment, to
        # add dependency of the check on those.
        src = '\n'.join([run_src] + [r'* %s' % s for s in str(opts).split('\n')])
        ret, out = context.TryRun(src, '.f')
    finally:
        if (not ret or not autoadd):
            # If test failed or autoadd is disabled, restore everything
            restore(env, saved)

    if not ret:
        context.Result('Failed: %s test could not be linked and run' % name)
        return 0

    context.Result(ret)
    return ret

def check_code(context, name, section, defopts, headers_to_check, funcs_to_check, 
           check_version, version_checker, autoadd, rpath_is_libpath = True):
    """Generic implementation for perflib check.

    This checks for header (by compiling code including them) and symbols in
    libraries (by linking code calling for given symbols). Optionnaly, it can
    get the version using some specific function.
    
    See CheckATLAS or CheckMKL for examples."""
    context.Message("Checking %s ... " % name)

    try:
        value = os.environ[name]
        if value == 'None':
            return context.Result('Disabled from env through var %s !' % name), {}
    except KeyError:
        pass

    # Get site.cfg customization if any
    siteconfig, cfgfiles = get_config()
    (cpppath, libs, libpath), found = get_config_from_section(siteconfig, section)
    if found:
        opts = ConfigOpts(cpppath = cpppath, libpath = libpath, libs = libs)
        if len(libs) == 1 and len(libs[0]) == 0:
            opts['libs'] = defopts['libs']
    else:
        opts = defopts

    if rpath_is_libpath:
	opts['rpath'] = deepcopy(opts['libpath'])

    env = context.env

    # Check whether the header is available (CheckHeader-like checker)
    saved = save_and_set(env, opts)
    try:
        src_code = [r'#include <%s>' % h for h in headers_to_check]
        src_code.extend([r'#if 0', str(opts), r'#endif', '\n'])
        src = '\n'.join(src_code)
        st = context.TryCompile(src, '.c')
    finally:
        restore(env, saved)

    if not st:
        context.Result('Failed (could not check header(s) : check config.log '\
                       'in %s for more details)' % env['build_dir'])
        return st, ConfigRes(name, opts, found)

    # Check whether the library is available (CheckLib-like checker)
    saved = save_and_set(env, opts)
    try:
        for sym in funcs_to_check:
            extra = [r'#if 0', str(opts), r'#endif', '\n']
            st = check_symbol(context, headers_to_check, sym, '\n'.join(extra))
            if not st:
                break
    finally:
        if st == 0 or autoadd == 0:
            restore(env, saved)
        
    if not st:
        context.Result('Failed (could not check symbol %s : check config.log '\
                       'in %s for more details))' % (sym, env['build_dir']))
        return st, ConfigRes(name, opts, found)
        
    context.Result(st)

    # Check version if requested
    if check_version:
        if version_checker:
            vst, v = version_checker(context, opts)
            if vst:
                version = v
            else:
                version = 'Unknown (checking version failed)'
        else:
            version = 'Unkown (not implemented)'
        cfgres = ConfigRes(name, opts, found, version)
    else:
        cfgres = ConfigRes(name, opts, found, version = 'Not checked')

    return st, cfgres