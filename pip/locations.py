"""Locations where we look for configs, install stuff, etc"""

import getpass
import os
import os.path
import site
import sys
import tempfile

from distutils import sysconfig
from distutils.command.install import install, SCHEME_KEYS

from pip import appdirs
from pip.compat import get_path_uid, WINDOWS

import pip.exceptions


# Hack for flake8
install


# CA Bundle Locations
CA_BUNDLE_PATHS = [
    # Debian/Ubuntu/Gentoo etc.
    "/etc/ssl/certs/ca-certificates.crt",

    # Fedora/RHEL
    "/etc/pki/tls/certs/ca-bundle.crt",

    # OpenSUSE
    "/etc/ssl/ca-bundle.pem",

    # OpenBSD
    "/etc/ssl/cert.pem",

    # FreeBSD/DragonFly
    "/usr/local/share/certs/ca-root-nss.crt",

    # Homebrew on OSX
    "/usr/local/etc/openssl/cert.pem",
]

# Attempt to locate a CA Bundle that we can pass into requests, we have a list
# of possible ones from various systems. If we cannot find one then we'll set
# this to None so that we default to whatever requests is setup to handle.
#
# Note to Downstream: If you wish to disable this autodetection and simply use
#                     whatever requests does (likely you've already patched
#                     requests.certs.where()) then simply edit this line so
#                     that it reads ``CA_BUNDLE_PATH = None``.
CA_BUNDLE_PATH = next((x for x in CA_BUNDLE_PATHS if os.path.exists(x)), None)


# Application Directories
USER_CACHE_DIR = appdirs.user_cache_dir("pip")


DELETE_MARKER_MESSAGE = '''\
This file is placed here by pip to indicate the source was put
here by pip.

Once this package is successfully installed this source code will be
deleted (unless you remove this file).
'''
PIP_DELETE_MARKER_FILENAME = 'pip-delete-this-directory.txt'


def write_delete_marker_file(directory):
    """
    Write the pip delete marker file into this directory.
    """
    filepath = os.path.join(directory, PIP_DELETE_MARKER_FILENAME)
    marker_fp = open(filepath, 'w')
    marker_fp.write(DELETE_MARKER_MESSAGE)
    marker_fp.close()


def running_under_virtualenv():
    """
    Return True if we're running inside a virtualenv, False otherwise.

    """
    if hasattr(sys, 'real_prefix'):
        return True
    elif sys.prefix != getattr(sys, "base_prefix", sys.prefix):
        return True

    return False


def virtualenv_no_global():
    """
    Return True if in a venv and no system site packages.
    """
    # this mirrors the logic in virtualenv.py for locating the
    # no-global-site-packages.txt file
    site_mod_dir = os.path.dirname(os.path.abspath(site.__file__))
    no_global_file = os.path.join(site_mod_dir, 'no-global-site-packages.txt')
    if running_under_virtualenv() and os.path.isfile(no_global_file):
        return True


def __get_username():
    """ Returns the effective username of the current process. """
    if WINDOWS:
        return getpass.getuser()
    import pwd
    return pwd.getpwuid(os.geteuid()).pw_name


def _get_build_prefix():
    """ Returns a safe build_prefix """
    path = os.path.join(
        tempfile.gettempdir(),
        'pip_build_%s' % __get_username().replace(' ', '_')
    )
    if WINDOWS:
        """ on windows(tested on 7) temp dirs are isolated """
        return path
    try:
        os.mkdir(path)
        write_delete_marker_file(path)
    except OSError:
        file_uid = None
        try:
            # raises OSError for symlinks
            # https://github.com/pypa/pip/pull/935#discussion_r5307003
            file_uid = get_path_uid(path)
        except OSError:
            file_uid = None

        if file_uid != os.geteuid():
            msg = (
                "The temporary folder for building (%s) is either not owned by"
                " you, or is a symlink." % path
            )
            print(msg)
            print(
                "pip will not work until the temporary folder is either "
                "deleted or is a real directory owned by your user account."
            )
            raise pip.exceptions.InstallationError(msg)
    return path

if running_under_virtualenv():
    build_prefix = os.path.join(sys.prefix, 'build')
    src_prefix = os.path.join(sys.prefix, 'src')
else:
    # Note: intentionally NOT using mkdtemp
    # See https://github.com/pypa/pip/issues/906 for plan to move to mkdtemp
    build_prefix = _get_build_prefix()

    # FIXME: keep src in cwd for now (it is not a temporary folder)
    try:
        src_prefix = os.path.join(os.getcwd(), 'src')
    except OSError:
        # In case the current working directory has been renamed or deleted
        sys.exit(
            "The folder you are executing pip from can no longer be found."
        )

# under Mac OS X + virtualenv sys.prefix is not properly resolved
# it is something like /path/to/python/bin/..
# Note: using realpath due to tmp dirs on OSX being symlinks
build_prefix = os.path.abspath(os.path.realpath(build_prefix))
src_prefix = os.path.abspath(src_prefix)

# FIXME doesn't account for venv linked to global site-packages

site_packages = sysconfig.get_python_lib()
user_site = site.USER_SITE
user_dir = os.path.expanduser('~')
if WINDOWS:
    bin_py = os.path.join(sys.prefix, 'Scripts')
    bin_user = os.path.join(user_site, 'Scripts')
    # buildout uses 'bin' on Windows too?
    if not os.path.exists(bin_py):
        bin_py = os.path.join(sys.prefix, 'bin')
        bin_user = os.path.join(user_site, 'bin')
    default_storage_dir = os.path.join(user_dir, 'pip')
    default_config_basename = 'pip.ini'
    default_config_file = os.path.join(
        default_storage_dir,
        default_config_basename,
    )
    default_log_file = os.path.join(default_storage_dir, 'pip.log')
else:
    bin_py = os.path.join(sys.prefix, 'bin')
    bin_user = os.path.join(user_site, 'bin')
    default_storage_dir = os.path.join(user_dir, '.pip')
    default_config_basename = 'pip.conf'
    default_config_file = os.path.join(
        default_storage_dir,
        default_config_basename,
    )
    default_log_file = os.path.join(default_storage_dir, 'pip.log')

    # Forcing to use /usr/local/bin for standard Mac OS X framework installs
    # Also log to ~/Library/Logs/ for use with the Console.app log viewer
    if sys.platform[:6] == 'darwin' and sys.prefix[:16] == '/System/Library/':
        bin_py = '/usr/local/bin'
        default_log_file = os.path.join(user_dir, 'Library/Logs/pip.log')

site_config_files = [
    os.path.join(path, default_config_basename)
    for path in appdirs.site_config_dirs('pip')
]


def distutils_scheme(dist_name, user=False, home=None, root=None):
    """
    Return a distutils install scheme
    """
    from distutils.dist import Distribution

    scheme = {}
    d = Distribution({'name': dist_name})
    d.parse_config_files()
    i = d.get_command_obj('install', create=True)
    # NOTE: setting user or home has the side-effect of creating the home dir
    # or user base for installations during finalize_options()
    # ideally, we'd prefer a scheme class that has no side-effects.
    i.user = user or i.user
    i.home = home or i.home
    i.root = root or i.root
    i.finalize_options()
    for key in SCHEME_KEYS:
        scheme[key] = getattr(i, 'install_' + key)

    if i.install_lib is not None:
        # install_lib takes precedence over purelib and platlib
        scheme.update(dict(purelib=i.install_lib, platlib=i.install_lib))

    if running_under_virtualenv():
        scheme['headers'] = os.path.join(
            sys.prefix,
            'include',
            'site',
            'python' + sys.version[:3],
            dist_name,
        )

        if root is not None:
            scheme["headers"] = os.path.join(
                root,
                os.path.abspath(scheme["headers"])[1:],
            )

    return scheme
