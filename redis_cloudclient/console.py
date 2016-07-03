"""
Console functionality
"""

class RedisStream(object):
    """
    File I/O object that streams data to/from redis keys (strings)

    """
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
