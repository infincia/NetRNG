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
import sys
import os
import logging
import time

log = logging.getLogger('netrng')
log.setLevel(logging.INFO)
mainHandler = logging.StreamHandler()
mainHandler.setFormatter(logging.Formatter('%(levelname)s %(asctime)s - %(module)s - %(funcName)s: %(message)s'))
log.addHandler(mainHandler)


FS_DEV_RANDOM = '/dev/random'
PROC_ENTROPY_AVAIL = '/proc/sys/kernel/random/entropy_avail'

def print_entropy_avail():
    with open(PROC_ENTROPY_AVAIL, 'r') as entropy_avail:
        log.info('Entropy in pool: %s' % entropy_avail.readline())


# main program loop
def main():
    try:
        while True:
            print_entropy_avail()
            time.sleep(1)
    except KeyboardInterrupt as e:
        log.debug('Exiting due to keyboard interrupt')
        sys.exit(0)


if __name__ == '__main__':
    main()