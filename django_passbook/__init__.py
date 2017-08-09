VERSION = ('0', '2', '1dev')


def get_version(*args, **kwargs):
    return '.'.join(VERSION)

__version__ = get_version()
