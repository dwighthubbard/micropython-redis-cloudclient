from .eventloop import start


__version__ = '0.0.8'


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
