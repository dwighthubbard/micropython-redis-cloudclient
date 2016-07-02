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
