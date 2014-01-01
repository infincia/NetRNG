#NetRNG

Allows a dedicated machine with an HWRNG to provide random data to other 
machines on the network. Code should be simple and easy to understand, and
should also be portable beyond Linux to FreeBSD and other systems

##Purpose

Devices like the RaspberryPi, PC Engines ALIX, some server hardware and the occasional
desktop sometimes have a hardware based RNG built-in or attached via PCI card.

###Security notes

NetRNG does one job, moves random data around on the local network. It doesn't attempt
to validate the random data according to FIPS or any other standard, rngd or 
other tools can already do that for you if you deem it useful. 

NetRNG does attempt to split up the random data it receives from the HWRNG so that 
each client receives a unique stream with no duplicated samples going to multiple 
clients.


###Setup

There is a server, netrng-server, and a client, netrngd. The server runs on the 
machine with the HWRNG, the client runs on any machine you want to use it on. 

The client attempts to setup and maintain a local fifo so that other programs 
like rng-tools can read from it and submit the data in to the Linux kernel.


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
 
###Using NetRNG

The general idea is simple, as long as you have a working HWRNG things should
just basically work

####Run directly for testing

    source /opt/NetRNG/env/bin/activate
    cd /opt/NetRNG
    python netrng.py


####Long term use

The Upstart script included in the repo is simple, just copy it to the system 
and Upstart will keep NetRNG running for you

    cp /opt/NetRNG/netrng.conf.upstart /etc/init/netrng.conf
    service netrng start


