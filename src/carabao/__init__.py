from .constants import C
from .core import Core
from .lanes import LogToDB, NetworkHealth, PrettyEnv
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


def start():
    Core.start()


__all__ = [
    "C",
    "Core",
    "LogToDB",
    "NetworkHealth",
    "PrettyEnv",
    "Settings",
    "start",
    "mongo",
    "redis",
    "es",
]
