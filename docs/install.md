# Installation Instructions

### Installing on micropython on the esp8266

To install on esp8266 modules:

#### Step 1. Change into the esp8266 build directory

    $ cd esp8266

#### Step 2. Use upip to install the module into the scripts directory.

Set the MICROPYPATH environment variable to point to the scripts 
directory.  

    $ MICROPYPATH=scripts;micropython -m upip install micropython-redis-cloudclient

#### Step 3. Deploy the module to the esp8266.  

    $ make deploy
