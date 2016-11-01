# Micropython Redis Cloud Client

Provides a client that allows one a network capable micropython board to 
interface with a central redis server.

# Quickstart

## Configure the redis server settings to point to the redis server

The Redis Cloud Client uses the bootconfig.config module to get/set the 
configuration.

If the board is not configured, the settings can be done manually using 
the bootconfig.config module.  In the example below replace [server]
with the redis server ip address and [serverport] with the port that
redis is running on.

These values will be saved so this step only has to be run once.

    from bootconfig.config import set
    set('redis_server', '[server]')
    set('redis_port', '[serverport]')
    set('name', '[boardname]')

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

### Added redis_cloudclient to automatically start

The following command will add the cloudclient to the main.py.  This
only needs to be run once.

    import redis_cloudclient.service
    redis_cloudclient.service.autostart()
    