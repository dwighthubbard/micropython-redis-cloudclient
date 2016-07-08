"""
Eventloop functionality
"""
import sys
from uredis_modular.client import Client


class EventLoop(object):
    """
    Main eventloop object to handle various events on the device
    """
    handlers = {
        'command': 'exec_command',
        'copy': 'copy_file',
        'print': 'print_message',
        'rename': 'rename_board'
    }
    def __init__(self, name=None, redis_server=None, redis_port=18266, enable_logging=False):
        self.enable_logging = enable_logging
        self.name = name
        self.redis_server = redis_server
        self.redis_port = redis_port

        self._get_redis_host_and_port()
        print('Connecting to Redis server at %s:%d' % (self.redis_server, self.redis_port))
        self.redis_connection = Client(self.redis_server, self.redis_port)

        self._determine_keys()
        self._enable_logging()
        self._find_handlers()
        self._initialize_console()

    ################################################################
    # Init operations
    ################################################################
    def clear_keys(self):
        """
        Clear the redis keys for this eventloop
        """
        for key in [self.complete_key, self.console_key]:
            self.redis_connection.execute_command('DEL', key)

    def _determine_keys(self):
        """
        Calculate the redis key names to use for different operations.
        """
        if not self.name:
            from bootconfig.config import get
            self.name = get('name')
        self.base_key = 'repl:' + self.name
        self.command_key = self.base_key + '.command'
        self.console_key = self.base_key + '.console'
        self.complete_key = self.base_key + '.complete'

    def _enable_logging(self):
        """
        Create a Logger object to send logs to redis if logging is enabled.
        """
        if self.enable_logging:
            from .logging import Logger
            self.logger = Logger(self.redis_connection, self.name)

    def _find_handlers(self):
        """
        Iterate the handlers dictionary and replace string handler names with
        the method
        """
        for key, value in self.handlers.items():
            if isinstance(self.handlers[key], str):
                try:
                    operation = getattr(self, self.handlers[key])
                except AttributeError:
                    # No method with the specified name
                    print('No method %r found' % self.handlers[key])
                    continue
                del self.handlers[key]
                new_key = self.base_key + '.' + key
                self.handlers[new_key.encode()] = operation

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
        if sys.platform not in ['WiPy']:
            # Dupterm is currently broken on wipy
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
        key = 'board:' + self.name
        key_info = 'boardinfo:' + self.name
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
        if key.startswith(self.base_key + '.'):
            handler = key[len(self.base_key)+1:]
            if handler in self.handlers.keys():
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
                self.logger.get_log_level()
                self.logger.debug('running handler %r', handler)
            rc = handler(value)

    def run(self):
        """
        Start the eventloop
        """
        while True:
            self.heartbeat(state=b'idle')
            self.handle_queues()


    # Operations handlers
    def not_implemented(self, queuekey):
        """
        Handler that gets called if no handler is defined
        """
        print('Recieved an event for a non-existant operation %r' % queuekey)

    def copy_file(self, filename, buffer_size=256):
        self.heartbeat(state=b'copying', ttl=30)
        file_key = b'file:' + self.name + b':' + filename
        file_size = int(self.redis_connection.execute_command('STRLEN', file_key))
        position = 0
        while True:
            with open(filename, 'w') as file_handle:
                end = position + buffer_size
                data = self.redis_connection.execute_command('GETRANGE', file_key, position, end)
                if data:
                    file_handle.write(data)
                if len(data) < buffer_size:
                    break
                position += len(data)

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
        name = name.decode()
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
    eventloop = EventLoop()
    eventloop.run()
