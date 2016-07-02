#!/usr/bin/env python
import os
import subprocess


def git_revision_count():
    try:
        result = subprocess.check_output(['git', 'rev-list', '--all']).decode().split(os.linesep)
    except subprocess.CalledProcessError:
        result = 0
    return len(result)


def infer_version():
    version = '0.0.%s' % os.environ.get('TRAVIS_BUILD_NUMBER', str(git_revision_count()))
    return version


def update_dunder_init_version(filename, version=None):
    if not version:
        version = infer_version()
    if os.path.exists(filename):
        print('In filename %r, setting __version__ = %r' % (filename, version))
        infile = None
        with open(filename) as read_handle:
            infile = read_handle.readlines()
        if infile:
            with open(filename, 'w') as write_handle:
                for line in infile:
                    if '__version__' in line:
                        temp = line.split('=')
                        temp[-1] = ' ' + repr(version) + '\n'
                        line = '='.join(temp)
                    write_handle.write(line)


def update_setup_version(filename=None, version=None):
    if not filename:
        filename = 'setup.py'
    if not version:
        version = infer_version()
    infile = None
    with open(filename) as setup_handle:
        infile = setup_handle.readlines()
    if infile:
        with open(filename, 'w') as setup_handle:
            for line in infile:
                if 'version=' in line:
                    temp = line.split('=')
                    temp[-1] = repr(version) + ',\n'
                    line = '='.join(temp)
                setup_handle.write(line)


if __name__ == '__main__':
    update_setup_version('setup.py')
    update_dunder_init_version('redis_cloudclient/__init__.py')
