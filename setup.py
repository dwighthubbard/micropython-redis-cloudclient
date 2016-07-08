import sys
# Remove current dir from sys.path, otherwise setuptools will peek up our
# module instead of system.
sys.path.pop(0)
from setuptools import setup


setup(
    name='micropython-redis-cloudclient',
    description='Micropython client that allows network attached boards to be controlled from a central redis server',
    long_description="""Provides a client that allows one a network capable micropython board to
interface with a central redis server.""",
    url='https://github.com/dhubbard/micropython-redis-cloudclient',
    author='Dwight Hubbard',
    author_email="dwight@dwighthubbard.com",
    install_requires=['micropython-redis.client', 'micropython-bootconfig'],
    license='MIT',
    maintainer='Dwight Hubbard',
    maintainer_email='dwight@dwighthubbard.com',
    packages=['redis_cloudclient'],
    version='0.0.16',
    zip_safe=True,
)
