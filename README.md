# Micropython Redis Cloud Client

Provides a client that allows one a network capable micropython board to 
interface with a central redis server.

# Quickstart

## Installing on micropython on the esp8266

To install on esp8266 modules:

### Step 1. Change into the esp8266 build directory

    $ cd esp8266

### Step 2. Use upip to install the module into the scripts directory.

Set the MICROPYPATH environment variable to point to the scripts directory.

    $ export MICROPYPATH=scripts;micropython -m upip install micropython-redis-cloudclient

### Step 3. Deploy the module to the esp8266.

    $ make deploy

## Configure the redis server settings to point to the redis server

The Redis Cloud Client uses the bootconfig.config module to get/set the 
configuration.

If the board is not configured, the settings can be done manually via
the repl using the bootconfig.config module.  In the example below replace [server]
with the redis server ip address and [serverport] with the port that
redis is running on.

These values will be saved so this step only has to be run once.

    set('redis_server', '[server]')
    set('redis_port', '[serverport]')
    set('name', '[boardname]')

##### Example of setting the client manually at the repl.

    MicroPython v1.8.1-156-gf3636a7-dirty on 2016-07-01; ESP module with ESP8266
    Type "help()" for more information.
    >>> from bootconfig.config import set
    >>> set('redis_server', '192.168.1.127')
    >>> set('redis_port', '18255')
    >>> set('name', 'esp001')

## Run the start function to start the client.

The redis_cloudclient can be started manually from the repl or added
to main.py to execute at start.

### Starting the redis_cloudclient manually

The following 2 lines will start the client.  They can be added to the
end of the main.py to make the board run the client at start.

    import redis_cloudclient
    redis_cloudclient.start()
    
##### Example of starting the client manually at the repl.

    MicroPython v1.8.1-156-gf3636a7-dirty on 2016-07-01; ESP module with ESP8266
    Type "help()" for more information.
    >>> import redis_cloudclient
    >>> redis_cloudclient.start()
    Redis CloudClient starting
    Connecting to cloudmanager server at 192.168.1.127:18266
    Registering with the server as 'esp001'


### Added redis_cloudclient to automatically start

The following command will add the cloudclient to the main.py.  This
only needs to be run once.

    import redis_cloudclient.service
    redis_cloudclient.service.autostart()

##### Example of autostarting the client manually at the repl.

    MicroPython v1.8.1-156-gf3636a7-dirty on 2016-07-01; ESP module with ESP8266
    Type "help()" for more information.
    >>> import redis_cloudclient.service
    >>> redis_cloudclient.service.autostart()
    >>>
