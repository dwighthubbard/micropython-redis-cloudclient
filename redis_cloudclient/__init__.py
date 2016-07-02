import sys
from uredis_modular.client import Client


__version__ = '0.0.6'


class RedisStream(object):
    redis_key = b'RedisRepl'
    buffersize = 80  # Size of the buffer in bytes
    _read_position = 0
    _connection = None

    def __init__(self, redis, redis_key, buffer_size=256):
        self._connection = redis
        self.redis = redis
        self.redis_key = redis_key
        self.redis_stdout_key = redis_key + '.stdout'
        self.redis_stdin_key = redis_key + '.stdin'
        self._buffer_size = buffer_size
        self.clear()

    def read(self, size=None):
        """
        Read from the input key stored in the redis server

        Parameters
        ----------
        size: int, optional
            How many bytes to read, if not specified reads everyting

        Returns
        -------
        bytes:
            Data read
        """
        if size:
            end = self._read_position + size
        else:
            end = -1
        data = self._connection.execute_command('GETRANGE', self.redis_stdin_key, self._read_position, end)
        self._read_position += len(data)
        return data

    def write(self, data):
        """
        Write data bytestring to a string in the output redis key

        Parameters
        ----------
        data : bytes
            The bytestring to write

        Returns
        -------
        The number of bytes written
        """
        if '\n' in data:
            self.flush()

        buffer_remaining = self._buffer_size - len(self._buffer)
        if len(data) > buffer_remaining:
            self.flush()
        if len(data) > self._buffer_size:
            self._connection.execute_command('APPEND', self.redis_stdout_key, bytes(data))
        else:
            self._buffer += bytes(data)

        return len(data)

    def flush(self):
        """
        Write buffered data to the output key on the redis server and reset the buffer.
        """
        if not self._buffer:
            return
        self._connection.execute_command('APPEND', self.redis_stdout_key, self._buffer)
        self._buffer = bytes()

    def clear(self):
        """
        Clear all data from the redis output key on the redis server
        """
        self._buffer = bytes()
        self._connection.execute_command('DEL', self.redis_stdout_key)
        self._connection.execute_command('DEL', self.redis_stdin_key)


class EventLoop(object):
    """
    Main eventloop object to handle various events on the device
    """

    def __init__(self, redis_server=None, redis_port=18266, enable_logging=False):
        self.enable_logging = enable_logging
        if self.enable_logging:
            from .logging import Logger
            self.logger = Logger(self.redis_connection, self.name)

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
        command = self.redis_connection.execute_command('BLPOP', self.command_key, 25)
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
    print('Redis CloudClient version %r starting' % __version__)
    eventloop = EventLoop()
    eventloop.run()


def autostart():
    """
    Add startup code to main.py
    """
    code = """
# Added by redis_cloudclient
import redis_cloudclient
redis_cloudclient.start()
"""
    with open('main.py', 'a') as fh:
        fh.write(code)
