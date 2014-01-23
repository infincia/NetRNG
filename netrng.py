# pip packages

from gevent import monkey; monkey.patch_all()

# standard libraries

import time
import sys
import os
import logging
import ConfigParser
import msgpack
import socket
import errno
import gevent
import gevent.subprocess
from gevent.server import StreamServer
from gevent.pool import Pool
from gevent.coros import RLock




'''
    Config

'''

netrng_config = ConfigParser.ConfigParser()
netrng_config.read('/etc/netrng.conf')

# whether we're in client or server mode
NETRNG_MODE = netrng_config.get('Global', 'mode')

# logging level
DEBUG = netrng_config.getboolean('Global', 'debug')

# delimiter for end of socket messages
SOCKET_DELIMITER = '--NETRNG-SOCKET-DELIMITER'




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

        # TCP port to listen on
        self.port = netrng_config.getint('Global', 'port')

        # How much random data to request from the device for each client push
        self.sample_size_bytes = netrng_config.getint('Server', 'sample_size_bytes')

        # Listen address used by the server
        self.listen_address = netrng_config.get('Server', 'listen_address')

        # Source device to use for random data, should be something fast and
        # high quality, DON'T set this to /dev/random
        self.hwrng_device = netrng_config.get('Server', 'hwrng_device')

        # Maximum number of clients to accept, this prevents your HWRNG from being
        # overloaded, starving clients. This requires testing and depends entirely on
        # how fast your HWRNG can be read. A device that can spit out 1mbps (100KB/s) could
        # give 100 clients 1KB/s, but a device that can only generate 128bps may only
        # be able to serve 1 client slowly
        self.max_clients = netrng_config.getint('Server', 'max_clients')

        # open the hwrng for reading later during client requests
        self.hwrng = open(self.hwrng_device, 'r')
        
        # lock to prevent multiple clients from getting the same random samples
        self.lock = RLock()





    def serve(self, sock, address):
        '''
            Serves client connections providing random samples to them in a one-to-many 
            request response architecture, with locking to ensure each client gets unique
            samples
    
        '''
        log.debug('NetRNG server: client connected %s', address)
        while True:
            try:
                requestmsg = ""
                while True:
                    data = sock.recv(1024)
                    requestmsg = requestmsg + data
                    log.debug('NetRNG server: receive cycle: %s', requestmsg)
                    if SOCKET_DELIMITER in requestmsg:
                        requestmsg = requestmsg.replace(SOCKET_DELIMITER, '')
                        break
                log.debug('NetRNG server: receive cycle done: %s', requestmsg)
                request = msgpack.unpackb(requestmsg)
                log.debug('NetRNG server: request %s', request)
                if request['get'] == 'config':
                    log.debug('NetRNG server: sending configuration to %s', address)
                    response = {'push': 'config', 'config': {'max_clients': self.max_clients, 'sample_size_bytes': self.sample_size_bytes}}
                    log.debug('NetRNG server: sending response %s', response)
                    responsemsg = msgpack.packb(response)
                    sock.sendall(responsemsg + SOCKET_DELIMITER)
                    log.debug('NetRNG server: response sent')
                elif request['get'] == 'sample':
                    with self.lock:
                        log.debug('NetRNG server: lock acquired %s', self.lock)
                        sample = self.hwrng.read(self.sample_size_bytes)
                    log.debug('NetRNG server: lock release')
                    response = {'push': 'sample', 'sample': sample}
                    log.debug('NetRNG server: sending response')
                    responsemsg = msgpack.packb(response)
                    sock.sendall(responsemsg + SOCKET_DELIMITER)
            except socket.error as e:
                if isinstance(e.args, tuple):
                    if e[0] == errno.EPIPE:
                        log.debug('NetRNG server: client disconnected %s', address)
                else:
                    log.exception('NetRNG server: socket error %s', e)
                sock.close()
                break
            except Exception as e:
                log.exception('NetRNG server: %s', e)
                sock.close()
                break


    def start(self):
        '''
            Server starts listening on a TCP socket and spawns a greenlet for each
            new connection. Blocks caller.

        '''
        self.pool = Pool(self.max_clients)
        self.server = StreamServer((self.listen_address, self.port), self.serve, spawn=self.pool)
        log.debug('NetRNG server: serving up to %d connections on ("%s", %d)', self.max_clients, self.listen_address, self.port)
        try:
            self.server.serve_forever()
        except KeyboardInterrupt as e:
            log.debug('NetRNG server: exiting due to keyboard interrupt')
            sys.exit(0)








class NetRNGClient(object):
    '''
        NetRNG client
    
    '''
    def __init__(self):
    
        # TCP port to connect to on the server
        self.port = netrng_config.getint('Global', 'port')

        # Address of the server to connect to
        self.server_address = netrng_config.get('Client', 'server_address')

        # Size of each incoming sample, retrieved from the server at runtime
        self.sample_size_bytes = 0

        # Retrieved from server at runtime
        self.server_max_clients = 0

        # Configuration state
        self.configured = False

        # Connection state
        self.connected = False


    def stream(self):
        '''
            Opens a connection to the server, configures the sample size to
            match the server configuration, then starts feeding received samples to rngd 
            running in a subprocess. 
            
            Running rngd in a subprocess allows runtime control over
            starting/stopping/configuring it at the right times

        '''
        log.debug('NetRNG client: initializing')
        sock = None
        rngd = None
        while True:
            try:
                if not self.connected:
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.connect((self.server_address, self.port))
                    log.debug('NetRNG client: connected to ("%s", %d)', self.server_address, self.port)
                    self.connected = True
                if not self.configured:
                    log.debug('NetRNG client: requesting configuration from server')
                    request = {'get': 'config'}
                    log.debug('NetRNG client: request %s', request)
                    requestmsg = msgpack.packb(request)
                    sock.sendall(requestmsg + SOCKET_DELIMITER)
                    responsemsg = ""
                    while True:
                        data = sock.recv(1024)
                        responsemsg = responsemsg + data
                        log.debug('NetRNG client: receive cycle: %s', responsemsg)
                        if SOCKET_DELIMITER in responsemsg:
                            responsemsg = responsemsg.replace(SOCKET_DELIMITER, '')
                            break
                    log.debug('NetRNG client: receive cycle done: %s', responsemsg)
                    response = msgpack.unpackb(responsemsg)
                    log.debug('NetRNG client: response %s', response)
                    if response['push'] == 'config':
                        log.debug('NetRNG client: config received %s', response)
                        server_config = response['config']
                        self.server_max_clients = server_config['max_clients']
                        self.sample_size_bytes = server_config['sample_size_bytes']
                        self.configured = True
                        rngd = gevent.subprocess.Popen(['rngd','-f','-r','/dev/stdin'],
                                            stdin=gevent.subprocess.PIPE,
                                            stdout=open(os.devnull, 'w'),
                                            stderr=open(os.devnull, 'w'),
                                            close_fds=True)
                        log.debug('NetRNG client: started rngd configured for %d byte samples', self.sample_size_bytes)
                log.debug('NetRNG client: requesting sample')
                request = {'get': 'sample'}
                requestmsg = msgpack.packb(request)
                sock.sendall(requestmsg + SOCKET_DELIMITER)
                log.debug('NetRNG server: request sent %s', request)
                responsemsg = ""
                while True:
                    data = sock.recv(1024)
                    responsemsg = responsemsg + data
                    log.debug('NetRNG client: receive cycle: %s', responsemsg)
                    if SOCKET_DELIMITER in responsemsg:
                        responsemsg = responsemsg.replace(SOCKET_DELIMITER, '')
                        break
                log.debug('NetRNG client: receive cycle done: %s', responsemsg)
                response = msgpack.unpackb(responsemsg)
                log.debug('NetRNG client: response %s', response)
                if response['push'] == 'sample':
                    sample = response['sample']
                    log.debug('NetRNG client: received %d byte sample', len(sample))
                    rngd.stdin.write(sample)
                    rngd.stdin.flush()
            except socket.error, msg:
                sock.close()
                self.connected = False
                log.debug('NetRNG client: server unavailable, reconnecting in 10 seconds')
                gevent.sleep(10)
            except KeyboardInterrupt as e:
                log.debug('NetRNG client: exiting due to keyboard interrupt')
                sock.close()
                sys.exit(0)
            except Exception as e:
                log.exception('NetRNG client: exception %s', e)
                sock.close()
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
        client.stream()
    else:
        log.error('NetRNG: no mode selected, quitting')
        sys.exit(1)

