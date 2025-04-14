from .constants import (  # ROOT_FOLDER_NAME,
    BATCH_SIZE,
    ENVIRONMENT,
    IS_PRODUCTION,
    IS_STAGING,
    POD_INDEX,
    POD_NAME,
    QUEUE_NAME,
    SINGLE_RUN,
    TESTING,
)
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
