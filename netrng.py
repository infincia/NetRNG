# pip packages

#from gevent import monkey; monkey.patch_all()
#import gevent_subprocess as subprocess

# standard libraries

import time
import sys
import os
import logging
import ConfigParser
import socket
import binascii
import errno
import json
import subprocess

'''
    Config

'''

netrng_config = ConfigParser.ConfigParser()
netrng_config.read('/etc/netrng.conf')

# whether we're in client or server mode
NETRNG_MODE = netrng_config.get('Global', 'mode')

# logging level
DEBUG = netrng_config.getboolean('Global', 'debug')


''' 
    Logging setup
    
'''

log = logging.getLogger(__name__)
if DEBUG:
    log.setLevel(logging.DEBUG)
else:
    log.setLevel(logging.INFO)
mainHandler = logging.StreamHandler()
mainHandler.setFormatter(logging.Formatter('%(asctime)s - %(message)s'))
log.addHandler(mainHandler)



class NetRNGServer(object):
    '''
        NetRNG server
    
    '''
    def __init__(self):
        from gevent.coros import RLock

        self.port = netrng_config.getint('Global', 'port')

        # How much random data to request from the device for each client push
        self.sample_size_bytes = netrng_config.getint('Server', 'sample_size_bytes')

        # listen address used by the server
        self.listen_address = netrng_config.get('Server', 'listen_address')

        # which device to use on server side
        self.hwrng_device = netrng_config.get('Server', 'hwrng_device')

        # Maximum number of clients to accept, this prevents your HWRNG from being
        # overloaded, starving clients. This requires testing and depends entirely on
        # how fast your HWRNG can be read. A device that can spit out 1mbps (100KB/s) could
        # give 100 clients 1KB/s, but a device that can only generate 128bps may only
        # be able to serve 1 client slowly
        self.max_clients = netrng_config.getint('Server', 'max_clients')

        self.hwrng = open(self.hwrng_device, 'r')
        self.lock = RLock()

    def handler(self, sock, address):
        '''
            Handler for individual server connections, sends configuration data to new
            clients, then starts streaming random samples to them in a one-to-many push
            architecture with locking to ensure each client gets unique samples
    
        '''
        import gevent
        fileobj = sock.makefile()
        log.info('NetRNG Server: client connected %s', address)
        while True:
            try:
                command = fileobj.readline().rstrip('\r\n')
                if not command: break
                log.debug('NetRNG Server: got command: %s', command)
                if command == 'get:config':
                    log.debug('NetRNG Server: sending configuration to %s', address)
                    config = json.dumps({'max_clients': self.max_clients, 'sample_size_bytes': self.sample_size_bytes})
                    log.debug('NetRNG Server: config: %s', config)
                    fileobj.write(config + '\r\n')
                    fileobj.flush()
                elif command == 'get:sample':
                    with self.lock:
                        log.debug('NetRNG Server: lock acquired %s', self.lock)
                        sample = self.hwrng.read(self.sample_size_bytes)
                    log.debug('NetRNG Server: lock release')
                    fileobj.write(sample)
                    fileobj.flush()
            except socket.error, e:
                if isinstance(e.args, tuple):
                    if e[0] == errno.EPIPE:
                        log.info('NetRNG Server: client disconnected %s', address)
                else:
                    log.error('NetRNG Server: ', e)
                sock.close()
                break
            except Exception, e:
                log.exception('NetRNG Server: %s', e)
                sock.close()
                break
            gevent.sleep(0.1)


    def start(self):
        '''
            Server starts listening on a TCP socket and spawns a greenlet for each
            new connection. Blocks caller

        '''
        from gevent.server import StreamServer
        from gevent.pool import Pool
        log.info('NetRNG Server: initializing')
        pool = Pool(self.max_clients)
        log.info('NetRNG Server: setting up handler pool for %d clients', self.max_clients)
        server = StreamServer((self.listen_address, self.port), self.handler, spawn=pool)
        log.info('NetRNG Server: listening for connections on ("%s", %d)' % (self.listen_address,self.port))
        try:
            server.serve_forever()
        except KeyboardInterrupt, e:
            log.warn('NetRNG Server: exiting due to keyboard interrupt')
            sys.exit(0)

class NetRNGClient(object):
    '''
        NetRNG client
    
    '''
    def __init__(self):
        self.port = netrng_config.getint('Global', 'port')

        # Address of the server to connect to
        self.server_address = netrng_config.get('Client', 'server_address')

        # Size of each incoming sample, retrieved from the server at runtime
        self.sample_size_bytes = 0

        # Retrieved from server at runtime
        self.server_max_clients = 0

        # configuration state
        self.configured = False

        # Connection state
        self.connected = False


    def start(self):
        '''
            Opens a connection to the server, configures the sample size to
            match the server configuration, then starts feeding received samples to rngd 
            running in a subprocess. 
            
            Running rngd in a subprocess allows runtime control over
            starting/stopping/configuring it at the right times

        '''
        log.info('NetRNG client: initializing')
        sock = None
        rngd = None
        fileobj = None
        while True:
            try:
                if not self.connected:
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.connect((self.server_address, self.port))
                    log.info('NetRNG client: connected to ("%s", %d)' % (self.server_address, self.port))
                    fileobj = sock.makefile()
                    self.connected = True
                if not self.configured:
                    fileobj.write('get:config\r\n')
                    fileobj.flush()
                    server_config_string = fileobj.readline().rstrip('\r\n')
                    log.debug('NetRNG client: config received: %s', server_config_string)
                    server_config = json.loads(server_config_string)
                    self.server_max_clients = server_config['max_clients']
                    self.sample_size_bytes = server_config['sample_size_bytes']
                    self.configured = True
                    rngd = subprocess.Popen(['rngd','-f','-r','/dev/stdin'],
                                            stdin=subprocess.PIPE,
                                            stdout=open(os.devnull, 'w'),
                                            stderr=open(os.devnull, 'w'),
                                            close_fds=True)
                    log.debug('NetRNG client: started rngd configured for %d byte samples', self.sample_size_bytes)
                else:
                    fileobj.write('get:sample\r\n')
                    fileobj.flush()
                    received = fileobj.read(self.sample_size_bytes)
                    rand_hex = binascii.hexlify(received)
                    log.debug('NetRNG client: received %d bytes', len(received))
                    rngd.stdin.write(received)
                    rngd.stdin.flush()
            except socket.error, msg:
                sock.close()
                self.connected = False
                fileobj = None
                log.warn('NetRNG client: server unavailable, reconnecting in 10 seconds')
                time.sleep(10)
            except KeyboardInterrupt, e:
                log.warn('NetRNG client: exiting due to keyboard interrupt')
                sock.close()
                sys.exit(0)
            except Exception, e:
                log.exception('NetRNG Client: %s', e)
                sys.exit(0)

'''
    Select correct mode based on configuration and start
    
'''

if __name__ == '__main__':
    if NETRNG_MODE == 'server':
        server = NetRNGServer()
        server.start()
    elif NETRNG_MODE == 'client':
        client = NetRNGClient()
        client.start()
    else:
        log.error('NetRNG: no mode selected, quitting')
        sys.exit(1)

