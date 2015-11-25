#!/usr/bin/env python

""" NetRNG Daemon

    A network connected random number generator daemon

    Copyright 2014 Infincia LLC
    
    See LICENSE file for license information

"""

from __future__ import absolute_import, print_function, division

__author__ = 'Stephen Oliver'
__maintainer__ = 'Stephen Oliver <steve@infincia.com>'
__version__ = '0.2b1'
__license__ = 'MIT'

# standard libraries
import logging

# local modules
import netrng.core


log = logging.getLogger('netrng')
log.setLevel(logging.DEBUG)
mainHandler = logging.StreamHandler()
mainHandler.setFormatter(logging.Formatter('%(asctime)s - %(message)s'))
log.addHandler(mainHandler)

def main():
    server = netrng.core.Server()
    server.calibrate()
