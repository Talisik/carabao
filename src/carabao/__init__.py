from .constants import C
from .core import Core
from .lanes import *
from .settings import Settings

try:
    from .constants import mongo

except:
    pass

try:
    from .constants import redis

except:
    pass

try:
    from .constants import es

except:
    pass


def start():
    Core.start()
