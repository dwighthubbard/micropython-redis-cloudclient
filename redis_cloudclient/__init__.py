import machine
import uos
from bootconfig.config import get
from uredis_modular.client import Client




class RedisStream(object):
    redis_key = b'RedisRepl'
    buffersize = 256  # Size of the buffer in bytes
    _read_position = 0
    _connection = None

    def __init__(self, host=None, port=6379, redis=None, redis_key=None, buffer_size=256):
        self._connection = redis
        if not redis:
            if not host:
                try:
                    host = get('redis_server')
                    if port==6379:
                        port = int(get('redis_port'))
                except ImportError:
                    pass
            self._connection = Client(host, port)
        if redis_key:
            self.redis_key = redis_key
        else:
            redis_key = self.name + '.stdout'
        self._buffer_size = buffer_size
        self.clear()

    def read(self, size=None):
        if size:
            end = self._read_position + size
        else:
            end = -1
        data = self._connection.execute_command('GETRANGE', self.redis_key + '.stdin', self._read_position, end)
        self._read_position += len(data)
        return data

    def write(self, data):
        if '\n' in data:
            self.flush()
        buffer_remaining = self._buffer_size - len(self._buffer)
        if len(data) > buffer_remaining:
            self.flush()
        if len(data) > self._buffer_size:
            self._connection.execute_command('APPEND', self.redis_key, bytes(data))
        else:
            self._buffer += bytes(data)

        return len(data)

    def flush(self):
        if not self._buffer:
            return
        self._connection.execute_command('APPEND', self.redis_key, self._buffer)
        self._buffer = bytes()

    def clear(self):
        self._buffer = bytes()
        self._connection.execute_command('DEL', self.redis_key)


def heartbeat(connection, name, state='idle', ttl=30):
    key = 'board:' + name
    connection.execute_command('SETEX', key, ttl, state)


class Logger(object):
    levels = dict(
        DEBUG = 10,
        INFO = 20
    )

    def __init__(self, redis_connection, name):
        self.redis_connection = redis_connection
        self.redis_key = name + '.logging'
        self.get_log_level()

    def get_log_level(self):
        log_level = self.redis_connection.execute_command('GET', self.redis_key)
        if not log_level:
            log_level = self.levels['INFO']
        self.log_level = int(log_level)
        return self.log_level

    def debug(self, *args, **kwargs):
        if self.log_level > self.levels['DEBUG']:
            return
        print(*args, **kwargs)

    def info(self, *args, **kwargs):
        if self.log_level > self.levels['INFO']:
            return
        print(*args, **kwargs)


def eventloop():
    # from microqueue import MicroQueue
    from bootconfig.config import get

    redis_connection = Client(get('redis_server'), get('redis_port'))
    name = get('name')

    name_in = 'repl:' + name
    in_key = name_in + '.command'
    name_stdout = name_in + '.stdout'
    name_complete = name_in + '.complete'
    # logger = Logger(redis_connection, name)
    # logger.debug('queue name', 'hotqueue:'+name_in)
    # logger.debug('stdout_key', name_stdout)
    # q_complete=MicroQueue(name_complete, redis=redis_connection)

    out_stream = RedisStream(redis_key=name_stdout, redis=redis_connection)
    uos.dupterm(out_stream)

    while True:
        heartbeat(redis_connection, name, state=b'idle')
        command = redis_connection.execute_command('BLPOP', in_key, 25)
        if command:
            # logger.get_log_level()
            command = command[1]
            # logger.debug('running command:', command)
            out_stream.clear()
            # q_complete.clear()
            heartbeat(redis_connection, name, state=b'running', ttl=120)
            rc = exec_command(command)
            out_stream.flush()
            # q_complete.put(rc)


def exec_command(command):
    try:
        exec(command)
        return 0
    except Exception as exc:
        from sys import print_exception
        print_exception(exc)
        return 1
