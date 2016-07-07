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
        'exec': 'exec_command',
        'copy': 'copy_file'
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
        for key in self.handlers.keys():
            if isinstance(self.handlers[key], str):
                try:
                    operation = getattr(self, key)
                except AttributeError:
                    # No method with the specified name
                    continue
                self.handlers[key] = operation

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

    def read_command(self, timeout=25):
        """
        Read a command from the command list

        Parameters
        ----------
        timeout : int optionall
            How long to wait for a command to become available before timing out.  A value of
            0 will never timeout.  Default: 25 seconds

        Returns
        -------
        bytes
            The command read from the queue, or None if it timed out.
        """
        command = self.redis_connection.execute_command('BLPOP', self.command_key, 1)
        if command:
            return command[1]

    def handle_command(self):
        """
        Check for and execute commands from the command queue
        """
        command = self.read_command()
        if command:
            if self.enable_logging:
                self.logger.get_log_level()
                self.logger.debug('running command:', command)

            rc = self.exec_command(command)

    def run(self):
        """
        Start the eventloop
        """
        while True:
            self.heartbeat(state=b'idle')
            self.handle_command()

    # Operations handlers
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


def start():
    """
    Start the event loop
    """
    print('Redis CloudClient starting')
    eventloop = EventLoop()
    eventloop.run()
