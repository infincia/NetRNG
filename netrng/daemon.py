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
import time
import sys
import os
import logging
from six.moves import configparser

# local modules
import netrng.core

'''
    Config

'''
config_defaults = dict()

global_defaults = {'mode': 'server',
                   'port': 8989,
                   'debug': 'no',
                   'zeroconf': 'no'}

server_defaults = {'sample_size_bytes': 2048,
                   'listen_address': '0.0.0.0',
                   'hwrng_device': '/dev/hwrng',
                   'max_clients': 2}

client_defaults = {'server_address': '192.168.1.2'}

config_defaults.update(global_defaults)
config_defaults.update(server_defaults)
config_defaults.update(client_defaults)

netrng_config = configparser.ConfigParser(defaults=config_defaults)
netrng_config.read('/etc/netrng.conf')

# logging level
DEBUG = netrng_config.getboolean('Global', 'debug')



''' 
    Logging setup
    
'''

log = logging.getLogger('netrng')
if DEBUG:
    log.setLevel(logging.DEBUG)
else:
    log.setLevel(logging.INFO)
mainHandler = logging.StreamHandler()
mainHandler.setFormatter(logging.Formatter('%(asctime)s - %(message)s'))
log.addHandler(mainHandler)




'''
    Select correct mode based on configuration and start
    
'''

def main():
    mode = netrng_config.get('Global', 'mode')
    port = netrng_config.getint('Global', 'port')
    use_zeroconf = netrng_config.getboolean('Global', 'zeroconf')

    if mode == 'server':
        listen_address    = netrng_config.get('Server', 'listen_address')
        max_clients       = netrng_config.getint('Server', 'max_clients')
        sample_size_bytes = netrng_config.getint('Server', 'sample_size_bytes')
        hwrng_device      = netrng_config.get('Server', 'hwrng_device')

        server = netrng.core.Server(listen_address=listen_address,
                              port=port,
                              max_clients=max_clients,
                              sample_size_bytes=sample_size_bytes,
                              hwrng_device=hwrng_device,
                              use_zeroconf=use_zeroconf)

        try:
            server.start()
        finally:
            server.stop()

    elif mode == 'client':
        server_address = netrng_config.get('Client', 'server_address')

        client = netrng.core.Client(server_address=server_address, port=port, use_zeroconf=use_zeroconf)
        client.start()

    else:
        log.error('NetRNG: no mode selected, quitting')
        sys.exit(1)

if __name__ == '__main__':
    main()

