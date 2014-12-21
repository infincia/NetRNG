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
import signal

# pip packages


import gevent
import gevent.subprocess
from gevent.server import StreamServer
from gevent.pool import Pool
from gevent.coros import RLock
from gevent import Timeout



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
        self.rng_lock = RLock()





    def serve(self, sock, address):
        '''
            Serves client connections providing random samples to them in a one-to-many 
            request response architecture, with locking to ensure each client gets unique
            samples
    
        '''
        log.debug('NetRNG server: client connected %s', address)

        try:
            while True:
                log.debug('NetRNG server: receive cycle start')
                requestmsg = ""
                with Timeout(5, gevent.Timeout):
                    while True:
                        data = sock.recv(1024)
                        requestmsg = requestmsg + data
                        log.debug('NetRNG server: receive cycle: %s', requestmsg)
                        if SOCKET_DELIMITER in requestmsg:
                            break
                        gevent.sleep()
                requestmsg = requestmsg.replace(SOCKET_DELIMITER, '')
                request = msgpack.unpackb(requestmsg)
                log.debug('NetRNG server: receive cycle done')
                log.debug('NetRNG server: request received %s', request)
                if request['get'] == 'sample':
                    with self.rng_lock:
                        log.debug('NetRNG server: rng lock acquired')
                        sample = self.hwrng.read(self.sample_size_bytes)
                    log.debug('NetRNG server: rng lock released')
                    log.debug('NetRNG server: sending response')
                    responsemsg = msgpack.packb({'push': 'sample', 'sample': sample})
                    sock.sendall(responsemsg + SOCKET_DELIMITER)
        except socket.error as e:
            if isinstance(e.args, tuple):
                if e[0] == errno.EPIPE:
                    log.debug('NetRNG server: client disconnected %s', address)
            else:
                log.exception('NetRNG server: socket error %s', e)
        except gevent.Timeout as timeout:
            log.debug('NetRNG server: client socket timeout')
        except Exception as e:
            log.exception('NetRNG server: %s', e)
        finally:
            sock.close()


    def calibrate(self):
        '''
            Naive implementation of auto-calibration for entropy source, should
            check how much entropy can be received in a given number of seconds
            and use that information to decide how much entropy can be distributed
            per second. With that information, it should be possible to decide
            how many clients can be promised `sample_size_bytes` per second

        '''
        log.debug('NetRNG server: starting entropy source performance calibration')
        calibration_period = 15 # seconds
        received_entropy = ""
        stop_time = time.time() + calibration_period
        while time.time() < stop_time:
            received_entropy += self.hwrng.read(self.sample_size_bytes)
        received_entropy_size = len(received_entropy)
        received_entropy_per_second = received_entropy_size / calibration_period
        log.debug('NetRNG server: completed entropy source performance calibration')
        log.debug('NetRNG server: entropy source can provide %d bytes per second')

    def start(self):
        '''
            Server starts listening on a TCP socket and spawns a greenlet for each
            new connection. Blocks caller.

        '''
        self.pool = Pool(self.max_clients)
        self.server = StreamServer((self.listen_address, self.port), self.serve, spawn=self.pool)
        log.debug('NetRNG server: serving up to %d connections on %s:%d)', self.max_clients, self.listen_address, self.port)
        try:
            self.server.start()
            gevent.wait()
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

        # Connection state
        self.connected = False

        # client socket for connecting to server
        self.rngd = gevent.subprocess.Popen(['rngd','-f','-r','/dev/stdin'],
                                               stdin=gevent.subprocess.PIPE,
                                               stdout=open(os.devnull, 'w'),
                                               stderr=open(os.devnull, 'w'),
                                               close_fds=True)

        # client socket for connecting to server
        self.sock = None
    
    
    def stream(self):
        '''
            Opens a connection to the server, configures the sample size to
            match the server configuration, then starts feeding received samples to rngd 
            running in a subprocess. 
            
            Running rngd in a subprocess allows runtime control over
            starting/stopping/configuring it at the right times

        '''
        log.debug('NetRNG client: initializing')
        while True:
            try:
                if not self.connected:
                    self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    self.sock.connect((self.server_address, self.port))
                    log.debug('NetRNG client: connected to %s:%d)', self.server_address, self.port)
                    self.connected = True


                # request a new sample
                log.debug('NetRNG client: requesting sample')
                requestmsg = msgpack.packb({'get': 'sample'})
                self.sock.sendall(requestmsg + SOCKET_DELIMITER)
                log.debug('NetRNG client: sample request sent')


                # wait for response
                log.debug('NetRNG client: receive cycle start')
                responsemsg = ""
                with Timeout(5, gevent.Timeout):
                    while True:
                        data = self.sock.recv(1024)
                        responsemsg = responsemsg + data
                        log.debug('NetRNG client: receive cycle: %s', responsemsg)
                        if SOCKET_DELIMITER in responsemsg:
                            break
                        gevent.sleep()
                responsemsg = responsemsg.replace(SOCKET_DELIMITER, '')
                response = msgpack.unpackb(responsemsg)
                log.debug('NetRNG client: receive cycle done')


                if response['push'] == 'sample':
                    sample = response['sample']
                    log.debug('NetRNG client: received %d byte sample', len(sample))
                    self.rngd.stdin.write(sample)
                    self.rngd.stdin.flush()
                else:
                    log.debug('NetRNG client: received unknown response from server')

            except socket.error as socket_exception:
                log.debug('NetRNG client: server unavailable, reconnecting in 10 seconds')
                self.connected = False
                self.sock.close()
                time.sleep(10)
            except gevent.Timeout as timeout:
                log.debug('NetRNG client: server socket timeout')
                self.connected = False
                self.sock.close()
                time.sleep(10)
            except KeyboardInterrupt as keyboard_exception:
                log.debug('NetRNG client: exiting due to keyboard interrupt')
                self.connected = False
                self.sock.close()
                break
            except Exception as unknown_exception:
                log.exception('NetRNG client: unknown exception %s', unknown_exception)
                self.connected = False
                self.sock.close()
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

