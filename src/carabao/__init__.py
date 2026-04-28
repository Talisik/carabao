from .constants import C
from .core import Core
from .form import F, Field, Form
from .lanes import (
    ESKuma,
    LogToDB,
    MongoKuma,
    NetworkHealth,
    NetworkWatcher,
    PrettyEnv,
    RedisKuma,
    ResourceWatcher,
)
from .settings import Settings

try:
    from .constants import mongo

except Exception:
    pass

try:
    from .constants import redis

except Exception:
    pass

try:
    from .constants import es

except Exception:
    pass

try:
    from .constants import pg

except Exception:
    pass


def start():
    """
    Starts the Carabao framework.

    This is the main entry point to initialize and run the application.
    """
    Core.start()


__all__ = [
    "C",
    "Core",
    "LogToDB",
    "NetworkHealth",
    "NetworkWatcher",
    "PrettyEnv",
    "ResourceWatcher",
    "MongoKuma",
    "RedisKuma",
    "ESKuma",
    "Settings",
    "start",
    "mongo",
    "redis",
    "es",
    "pg",
    "Field",
    "F",
    "Form",
]
