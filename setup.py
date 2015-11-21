#!/usr/bin/env python

import sys
import os
import codecs
from os.path import join, abspath, basename, dirname
try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup



py = sys.version_info
if py < (2,7) and py < (3,0):
    raise NotImplementedError("NetRNG requires Python 2.7, Python 3.2+ support will be available when gevent supports Python 3")

def read_file(name, *args):
    try:
        return codecs.open(join(dirname(__file__), name),  encoding='utf-8').read(*args)
    except OSError:
        return ''


setup(name='netrng',
    version='0.2a0',
    description='A network entropy distribution system',
    long_description=read_file('README.rst'),
    author='Stephen Oliver',
    author_email='steve@infincia.com',
    url='http://infincia.github.io/netrng/',
    entry_points={
        'console_scripts': [
            'netrngd = netrng.daemon:main',
            'netrng-entropycheck = netrng.entropycheck:main',
            'netrng-perftest = netrng.perftest:main',
        ]
    },
    data_files=[('conf',  ['conf/netrng.conf.sample', 'conf/netrng.conf.upstart', 'conf/netrng.service'])],
    packages=['netrng'],
    license='MIT',
    keywords='rng hwrng entropy random',
    platforms = 'any',
    install_requires = ['gevent==1.0.1', 'msgpack-python==0.4.2', 'zeroconf==0.15.1'],
    classifiers=['Development Status :: 3 - Alpha',
        'License :: OSI Approved :: MIT License',
        'Natural Language :: English',
        'Operating System :: POSIX',
        'Programming Language :: Python :: 2.7',
        'Topic :: Software Development :: Libraries',
        'Topic :: Software Development :: Libraries :: Python Modules',
    ],
)


