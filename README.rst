============================
NetRNG
============================

.. image:: https://travis-ci.org/infincia/NetRNG.svg?branch=master
    :target: https://travis-ci.org/infincia/NetRNG

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

Why it exists
-------------

EntropyBroker is the closest similar project I know of, but it didn't build when I
tried to use it, and the code seems quite large and complicated for a task that,
conceptually, is very simple.

So I wrote NetRNG. It's simple code, easy to maintain, easy to deploy, and with 
the exception of some network protocol issues before v0.1, it works quite 
well.

How it works
------------

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


Server
------

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


Client
------

The client starts ``rngd`` from rng-tools as a subprocess, then connects to the 
server and starts requesting entropy samples from it. Then each sample is forwarded
to ``rngd`` for processing.

Then, ``rngd`` validates the quality of the entropy sample before submitting it to 
the Linux or FreeBSD kernel for other programs to use via ``/dev/random``.


Common devices to use as the NetRNG server
------------------------------------------

* RaspberryPi
* Beaglebone
* PC Engines ALIX
* Various server mainboards
* Any machine with a TPM chip onboard
* Any machine with an Entropy Key


Setup
-----

There is very little actual configuration required for NetRNG, but until it is
packaged and uploaded to PyPi you'll need to manually clone the repository and
package it for installation.

Feel free to install the generated package wherever you like, but ``/opt/NetRNG``
is the default where the bundled init/upstart script are pointed, so if you
install the module somewhere else make sure to change them once they're copied
to /etc/.

I don't advise installing the package in the main system python package directory,
use a virtualenv to make things easier :)

Note: these instructions are written for Debian/Ubuntu and derivatives, you'll
need to determine the equivalent native package names for build-essential and
python-dev.

The virtualenv activation is repeated on purpose in certain steps to ensure that
someone who isn't following the steps sequentially won't accidentally install
python modules in the global system (not being root helps here, but just in
case...).

Clone the repo
--------------

.. code-block:: shell

    cd ~/
    git clone https://github.com/infincia/NetRNG.git

Create virtualenv
-----------------

Create a virtualenv for NetRNG:

.. code-block:: shell

    virtualenv /opt/NetRNG

Setup build environment
-----------------------

Some NetRNG dependencies require building python C extensions, so we need to
install a compiler and python development headers so they'll build properly
during installation of the NetRNG package:

.. code-block:: shell

    apt-get install build-essential
    apt-get install python-dev

The `wheel` module is also needed to build NetRNG, so we install it in to the
virtualenv:

.. code-block:: shell

    source /opt/NetRNG/bin/activate
    pip install wheel

Build and install NetRNG
-----------------------------

.. code-block:: shell

    cd ~/NetRNG
    source /opt/NetRNG/bin/activate
    python setup.py bdist_wheel
    pip install dist/netrng*.whl


Install rng-tools
-----------------

On some Linux distributions, rng-tools is installed by default. For others you
will need to install it yourself.

On Ubuntu or Debian you can install it like this:

.. code-block:: shell

    sudo apt-get install rng-tools
    
I have not tested NetRNG on FreeBSD, but rng-tools seems to support FreeBSD so
it should work. You'll need to install rng-tools from the ports collection.
    
Configuration
-------------

Copy and rename the sample config file on all machines before use:

.. code-block:: shell

    cp /opt/NetRNG/conf/netrng.conf.sample /etc/netrng.conf

The NetRNG server requires very little configuration on most systems, but the 
client requires setting the right server address and setting the mode to 'client'. 

The rest of the configuration should be fine unless you have a very slow HWRNG and 
need to tweak the data flow settings. The defaults send 2KB chunks of random data 
to each connected client as fast as possible. You can tweak sample_size_bytes if 
needed. This process may be automated in the future.


Run for testing
---------------

Since the compiled daemon script is available on your path while the virtualenv
is activated, you can run it directly after the config file is determined to be
correct:

.. code-block:: shell

    source /opt/NetRNG/bin/activate
    netrngd


Long term use
-------------

I have written both Upstart and systemd scripts for netrngd.

If someone would like to contribute other types of init scripts I will gladly 
accept a pull request.

To use the the systemd script:

.. code-block:: shell

    cp /opt/NetRNG/conf/netrng.service /etc/systemd/system/
    systemctl daemon-reload
    systemctl start netrng
    
To use the Upstart script:

.. code-block:: shell

    cp /opt/NetRNG/conf/netrng.conf.upstart /etc/init/netrng.conf
    service netrng start
