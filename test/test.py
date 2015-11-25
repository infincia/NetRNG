#!/usr/bin/env python

from __future__ import absolute_import

import sys

import netrng.core

def test_server():
    server = netrng.core.Server(listen_address='127.0.0.1',
                          port=8989,
                          max_clients=2,
                          sample_size_bytes=2048,
                          hwrng_device='/dev/zero',
                          use_zeroconf=False)
    
def test_client():
    client = netrng.core.Client(server_address='127.0.0.1', port=8989, use_zeroconf=False)

if __name__ == '__main__':
    test_server()
    test_client()
    sys.exit(0)
    