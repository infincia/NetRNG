#NetRNG

**Note: The master branch of this code is alpha quality but usable**.

NetRNG is effectively a network connected hardware random number generator. 

It allows devices like the RaspberryPi, Beaglebone, or any machine with a TPM, 
Entropy Key, or other hardware random number generator onboard to act as a NetRNG 
server, providing high quality random data to other machines on the network. 

Virtual machines can potentially benefit the most from NetRNG, as they typically 
suffer from poor quality local entropy sources due to their running environment.

No application or kernel changes are required on NetRNG Client machines; any
application using ``/dev/random`` and ``/dev/urandom`` will automatically and 
transparently receive entropy from the NetRNG server.

##Why it exists

EntropyBroker is the closest similar project I know of, but it didn't build when I
tried to use it, and the code seems quite large and complicated for a task that,
conceptually, is very simple.

So I wrote NetRNG. It's simple code, easy to maintain, easy to deploy, and with 
the exception of some network protocol issues before v0.1, it works quite 
well.

##Current state of the code at v0.1:  

Reconnection seems to be working when either the server or client restarts, or 
fails to properly close the socket connection. 

It relies on a simple activity timeout on both sides, which will cause a disconnection 
even if the other side hasn't actually disappeared but is simply idle. 

If the server is configured to allow only two clients to connect, and two are 
connected but one of them isn't actively requesting entropy, that client will be 
disconnected after 5 seconds, and another waiting client will be able to connect. 

That cycle will repeat endlessly, which may be a desirable behavior in order to 
prevent idle clients from monopolizing the NetRNG server.

##How it works

As a complete system, NetRNG links ``/dev/hwrng`` on one machine, to ``/dev/random``
on many others, carefully ensuring that each machine receives unique entropy samples,
while allowing the entropy to be validated for quality and ensuring that entropy
is fairly distributed among connected clients.

It is essentially a persistent pipeline from one machine to many others, with
some minor restrictions on how the pipeline functions to make it suitable for the 
task.

However, netrng.py itself does one job and only one job: it moves random data 
around on the local network. Other tasks like validating the samples and providing
them to the kernel entropy pool are left to ``rngd`` from rng-tools, which is
automatically started and managed by NetRNG.


###Server

The NetRNG server reads from ``/dev/hwrng`` (configurable), dividing up the stream 
in to non-repeating, non-overlapping samples of a size defined in the configuration
file, then sends each one to clients on the local network.

The maximum number of clients that will be accepted can be configured on the server,
this allows you to prevent a slow HWRNG from being spread too thin among too many
clients. 

I'm working on a QoS style load management system that will allow you to guarantee
that each connected client can receive entropy samples at a specific rate, 10KB/s
for example. Clients would be allowed to connect until the server could no longer
guarantee that entropy rate to each of them.


###Client

The client starts ``rngd`` from rng-tools as a subprocess, then connects to the 
server and starts requesting entropy samples from it. Then each sample is forwarded
to ``rngd`` for processing.

Then, ``rngd`` validates the quality of the entropy sample before submitting it to 
the Linux or FreeBSD kernel for other programs to use via ``/dev/random``.


###Common devices to use as the NetRNG server

* RaspberryPi
* Beaglebone
* PC Engines ALIX
* Various server mainboards
* Any machine with a TPM chip onboard
* Any machine with an Entropy Key


###Setup

There is very little actual setup required. 

No paths in the code are hardcoded, feel free to put the code wherever you
like, but ``/opt/NetRNG``is the default so make sure to change the init/upstart 
script to match if you put the code somewhere else.

In the near future NetRNG will probably be provided via native deb/rpm packages
and uploaded to PyPi making it available for installation with pip.

For now, you'll need to manually install it.

####Clone the repo

    cd /opt/
    git clone https://github.com/infincia/NetRNG.git

####Install Python libraries

Create and activate a virtualenv, then install the python libraries into it:

    virtualenv /opt/NetRNG/env
    source /opt/NetRNG/env/bin/activate
    pip install -r /opt/NetRNG/requirements.txt

####Install rng-tools

On some Linux distributions, rng-tools is installed by default. For others you
will need to install it yourself.

On Ubuntu or Debian you can install it like this:

    sudo apt-get install rng-tools
    
I have not tested NetRNG on FreeBSD, but rng-tools seems to support FreeBSD so
it should work. You'll need to install rng-tools from the ports collection.
    
####Configuration

Copy and rename the sample config file on all machines before use:

    cp /opt/NetRNG/netrng.conf.sample /etc/netrng.conf

The NetRNG server requires very little configuration on most systems, but the 
client requires setting the right server address and setting the mode to 'client'. 

The rest of the configuration should be fine unless you have a very slow HWRNG and 
need to tweak the data flow settings. The defaults send 2KB chunks of random data 
to each connected client as fast as possible. You can tweak sample_size_bytes if 
needed. This process may be automated in the future.


###Run directly for testing

    source /opt/NetRNG/env/bin/activate
    cd /opt/NetRNG
    python netrng.py


###Long term use

I have written an Upstart script as an example, I will write a systemd script
soon as well. If someone would like to contribute other types of init scripts
I will gladly accept a pull request.

If you need the Upstart script, just copy it to the system location and start it.

    cp /opt/NetRNG/netrng.conf.upstart /etc/init/netrng.conf
    service netrng start
    
Then Upstart will keep it running for you all the time.
