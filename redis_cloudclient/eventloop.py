"""
Eventloop functionality
"""
import sys
import time

from uredis_modular.client import Client
from .exceptions import RedisNotRunning


class EventLoop(object):
    """
    Main eventloop object to handle various events on the device
    """
    handlers = {
        b'command': b'exec_command',
        b'copy': b'copy_file',
        b'print': b'print_message',
        b'rename': b'rename_board'
    }
    def __init__(self, name=None, redis_server=None, redis_port=18266, enable_logging=False):
        self.enable_logging = enable_logging
        self.name = name
        self.redis_server = redis_server
        self.redis_port = redis_port

        self._get_redis_host_and_port()
        self._determine_keys()
        self._find_handlers()

    ################################################################
    # Init operations
    ################################################################
    def clear_keys(self):
        """
        Clear the redis keys for this eventloop
        """
        for key in [self.command_key, self.complete_key, self.console_key]:
            self.redis_connection.execute_command('DEL', key)

    def _determine_keys(self):
        """
        Calculate the redis key names to use for different operations.
        """
        if not self.name:
            from bootconfig.config import get
            self.name = get('name').encode()
            if not self.name:
                from bootconfig.config import set
                import time
                self.name = self.platform.encode() + bytes(int(time.time()))
                set('name', self.name)
        self.base_key = b'repl:' + self.name
        self.command_key = self.base_key + b'.command'
        self.console_key = self.base_key + b'.console'
        self.complete_key = self.base_key + b'.complete'

    def _find_handlers(self):
        """
        Iterate the handlers dictionary and replace string handler names with
        the method
        """
        for key, value in self.handlers.items():
            if isinstance(self.handlers[key], bytes):
                try:
                    operation = getattr(self, self.handlers[key].decode())
                except AttributeError:
                    # No method with the specified name
                    print('No method %r found' % self.handlers[key])
                    continue
                del self.handlers[key]
                new_key = self.base_key + b'.' + key
                self.handlers[new_key] = operation

    def _get_redis_host_and_port(self):
        """
        Determine the redis server host and port values, getting them from the
        bootconfig configuration if they aren't set.
        """
        if not self.redis_server:
            from bootconfig.config import get
            self.redis_server = get('redis_server')
            redis_port = get('redis_port')
            if redis_port:
                self.redis_port = int(redis_port)

    def _initialize_console(self):
        """
        Initialize the console redirection for the event loop
        """
        from .console import RedisStream
        self.console = RedisStream(redis=self.redis_connection, redis_key=self.console_key)
        if sys.platform not in ['WiPy', 'linux']:
            # Dupterm is currently broken on wipy and unix
            from uos import dupterm
            dupterm(self.console)
        self.clear_keys()
        self.console.clear()

    def clear_completion_queue(self):
        self.redis_connection.execute_command('DEL', self.complete_key)

    def signal_completion(self, rc):
        """
        Put the return code in the completion queue
        """
        self.redis_connection.execute_command('RPUSH', self.complete_key, rc)

    def heartbeat(self, state=b'idle', ttl=300):
        """
        Update the board heartbeat key (and it's time to live)

        Parameters
        ----------
        state : bytes, optional
            The state the board is in

        ttl : int, optional
            The time to live in seconds for the key.  After
            the ttl expires the key is removed from the redis
            server.  Default: 30 seconds
        """
        key = b'board:' + self.name
        key_info = b'boardinfo:' + self.name
        self.redis_connection.execute_command('SETEX', key, ttl, state)
        self.redis_connection.execute_command('SETEX', key_info, ttl, sys.platform)

    def keyname_to_handler(self, key):
        """
        Convert a keyname to a handler name

        Parameters
        ----------
        key : bytes
            The redis keyname

        Returns
        -------
        bytes
            The handler name or None if no such handler
        """
        if key.startswith(self.base_key + b'.'):
            handler = key[len(self.base_key)+1:]
            print(handler, self.handlers.keys())
            if self.handlers.get(handler, None):
                return handler

    def handle_queues(self, timeout=1):
        """
        Check for and execute commands from the command queue

        This willl listen to all the handler queues and call the handler
        with the value from the associated queue.
        """
        command = ['BLPOP'] + list(self.handlers.keys()) + [timeout]
        response = self.redis_connection.execute_command(*command)
        if response:
            queuekey, value = response
            handler = self.handlers.get(queuekey, self.not_implemented)
            if self.enable_logging:
                print('running handler %r', self.keyname_to_handler(handler))
            rc = handler(value)

    def run(self):
        """
        Start the eventloop
        """
        print('Connecting to cloudmanager server at %s:%d' % (self.redis_server, self.redis_port))
        try:
            self.redis_connection = Client(self.redis_server, self.redis_port)
        except OSError:
            raise RedisNotRunning(
                'The Cloudmanager service is not running at %s:%s' % (self.redis_server, self.redis_port)
            )
        self._initialize_console()
        print('Registering with the server as %r' % self.name.decode())


        while True:
            self.heartbeat(state=b'idle')
            self.handle_queues()


    # Operations handlers
    def not_implemented(self, queuekey):
        """
        Handler that gets called if no handler is defined
        """
        print('Recieved an event for a non-existant operation %r' % queuekey)

    def copy_file(self, transaction_key, buffer_size=256):
        self.heartbeat(state=b'copying', ttl=30)
        file_key = self.redis_connection.execute_command('HGET', transaction_key, 'source')
        filename = self.redis_connection.execute_command('HGET', transaction_key, 'dest')
        print('Copying file %r' % filename)
        # file_size = int(self.redis_connection.execute_command('STRLEN', file_key))
        position = 0
        with open(filename, 'wb') as file_handle:
            while True:
                end = position + buffer_size
                data = self.redis_connection.execute_command('GETRANGE', file_key, position, end)
                if data:
                    file_handle.write(data)
                if len(data) < buffer_size:
                    break
                position += len(data)
        self.redis_connection.execute_command('DEL', transaction_key)
        self.signal_completion(0)
        self.heartbeat(state=b'idle')

    def exec_command(self, command):
        """
        Execute a single command.

        Parameters
        ----------
        command: bytes
            The command to execute

        Returns
        -------
        int
            The return code of the command, will be 0 if the command completed
            sucessfully and 1 if it generated an exception.
        """
        self.console.clear()
        self.clear_completion_queue()
        self.heartbeat(state=b'running', ttl=30)

        try:
            exec(command)
            rc = 0
        except Exception as exc:
            from sys import print_exception
            print_exception(exc)
            rc = 1

        self.console.flush()
        self.signal_completion(rc)
        self.heartbeat(state=b'idle')
        return rc

    def print_message(self, message):
        print(message.decode())

    def rename_board(self, name):
        name = name
        from bootconfig.config import set
        self.heartbeat(state=b'renaming', ttl=1)
        self.name = name
        set('name', name)
        self.heartbeat(state=b'idle')


def start():
    """
    Start the event loop
    """
    print('Redis CloudClient starting')
    retry_time = 5
    eventloop = EventLoop()
    while True:
        try:
            eventloop.run()
        except RedisNotRunning:
            print(
                'Could not connect to the cloudmanager server at %s:%s, retrying in %d seconds' % (
                    eventloop.redis_server, eventloop.redis_port, retry_time
                )
            )
            time.sleep(retry_time)
            retry_time *= 2
            if retry_time > 900:
                print('Giving up')
                break

