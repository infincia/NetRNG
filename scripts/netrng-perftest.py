#!/bin/python

import logging
from netrng import NetRNGServer


log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)
mainHandler = logging.StreamHandler()
mainHandler.setFormatter(logging.Formatter('%(asctime)s - %(message)s'))
log.addHandler(mainHandler)


server = NetRNGServer()
server.calibrate()
