"""
Eventloop functionality
"""
import sys
from .console import RedisStream
from uredis_modular.client import Client


class EventLoop(object):
    """
    Main eventloop object to handle various events on the device
    """

    def __init__(self, redis_server=None, redis_port=18266, enable_logging=False):
        self.enable_logging = enable_logging

        if not redis_server:
            from bootconfig.config import get, set
            redis_server = get('redis_server')
            redis_port = get('redis_port')
            if redis_port:
                redis_port = int(redis_port)
        print('Connecting to Redis server at %s:%d' % (redis_server, redis_port))
        self.redis_connection = Client(redis_server, redis_port)

        self.name = get('name')
        self.base_key = 'repl:' + self.name
        self.command_key = self.base_key + '.command'
        self.console_key = self.base_key + '.console'
        self.complete_key = self.base_key + '.complete'
        if self.enable_logging:
            from .logging import Logger
            self.logger = Logger(self.redis_connection, self.name)

        self.console = RedisStream(redis=self.redis_connection, redis_key=self.console_key)
        from uos import dupterm
        self.clear_keys()
        self.console.clear()
        dupterm(self.console)

    def clear_keys(self):
        """
        Clear the redis keys for this eventloop
        """
        for key in [self.complete_key, self.console_key]:
            self.redis_connection.execute_command('DEL', key)

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
        self.heartbeat(state=b'running', ttl=300)
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

    def clear_completion_queue(self):
        self.redis_connection.execute_command('DEL', self.complete_key)

    def signal_completion(self, rc):
        """
        Put the return code in the completion queue
        """
        self.redis_connection.execute_command('RPUSH', self.complete_key, rc)

    def heartbeat(self, state=b'idle', ttl=30):
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

    # Operations handlers
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

def start():
    """
    Start the event loop
    """
    print('Redis CloudClient starting')
    eventloop = EventLoop()
    eventloop.run()
