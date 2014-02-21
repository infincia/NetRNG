#NOTE: The master branch of this code is still unstable, but the zeromq branch seems to work fairly well, it's what I use at home right now. The only thing it lacks is the ability to limit connected clients automatically.

#NetRNG

NetRNG allows a dedicated machine with a hardware based random number generator
to provide random data to other machines on the network that don't have an RNG of
their own, similar to entropy broker. It allows those machines to benefit from a
high speed, (hopefully) high quality entropy source.

##Why it exists

EntropyBroker is the closest similar project I know of, but it didn't build when I
tried to use it and the code seems quite large and complicated for a task that,
conceptually, is very simple.

So I wrote NetRNG. It's incredibly simple code, easy to read and understand, easy
to deploy, and it works perfectly in all my testing.

##How it works

As a complete system, NetRNG links ``/dev/hwrng`` on one machine, to ``/dev/random``
on many others, carefully ensuring that each machine receives unique entropy samples,
while allowing the entropy to be validated for quality and ensuring that each
machine can receive a specific amount of entropy per second, preventing starvation.

It is essentially a persistent pipeline from one machine to many others, with
some minor additional restrictions on how the pipeline functions to make it
suitable for the task.

However, netrng.py itself does one job and only one job: it moves random data 
around on the local network. Other tasks like validating the samples and doing
something with them are left to other programs that are good at them.


###Server

The NetRNG server reads from ``/dev/hwrng`` (configurable), dividing up the stream 
in to non-repeating, non-overlapping samples of a size defined in the configuration
file, then sends each one to clients on the local network.

The maximum number of clients that will be accepted can be configured on the server,
this allows you to prevent a slow HWRNG from being spread too thin among too many
clients. 

At some point I want to add dynamic load management instead of a client limit.
So for example, you would configure the server to guarantee 10KB/s of random data
to each client, and the server would decide how many clients it could guarantee
that rate for based on the speed of the HWRNG being used. You can do this now 
by testing it yourself, but I would like to automate it.


###Client

The client starts ``rngd`` as a subprocess, then connects to the server and starts
receiving entropy samples from it, forwarding each one to ``rngd`` for processing.

Then, ``rngd`` validates the quality of the entropy before submitting samples to 
the Linux kernel for other programs to use via ``/dev/random``.


###Common devices to use as the RNG server

* RaspberryPi
* Beaglebone
* PC Engines ALIX
* Various server mainboards
* Entropy Key (installed in any Linux machine)


###Setup

There is very little actual setup required, and all code is in ``netrng.py``.

The configuration file determines whether the service will run in client or server
mode, review it to ensure the client and server settings are correct for your
network.

No paths in the code are hardcoded, so feel free to put the code wherever you
like, but make sure to change the init/upstart script to match.


####Clone the repo

    cd /opt/
    git clone https://github.com/infincia/NetRNG.git

####Install Python libraries

Create and activate a virtualenv, then install the python libraries into it:

    virtualenv /opt/NetRNG/env
    source /opt/NetRNG/env/bin/activate
    pip install -r /opt/NetRNG/requirements.txt
    
####Configuration

There's a simple configuration file included in the root of the project, copy 
and rename it on all machines before use

    cp /opt/NetRNG/netrng.conf.sample /etc/netrng.conf

The NetRNG server requires very little configuration on most systems, but the 
client requires setting the right server address and setting the mode to 'client'. 

The rest of the configuration should be fine unless you have a very slow HWRNG and need
to tweak the data flow settings. Some of this may be automated in the future.

The defaults send 1KB/s of random data to each connected client, if your HWRNG 
can support faster rates, change sample_size_bytes to something larger. I want 
to automate this soon by measuring the HWRNG performance at runtime and adjust 
the sample setting to divide it by the number of connected clients so
there is always an even split.


###Run directly for testing

    source /opt/NetRNG/env/bin/activate
    cd /opt/NetRNG
    python netrng.py


###Long term use

The Upstart script included in the repo is simple, just copy it to the system 
and Upstart will keep NetRNG running for you

    cp /opt/NetRNG/netrng.conf.upstart /etc/init/netrng.conf
    service netrng start


