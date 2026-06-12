"""Async Redis hub (``aredis``) for use inside ``AsyncLane`` lanes.

Thin re-export of fun_things' ``AsyncRedisHub`` (``redis.asyncio``). The accessor
is sync — only the operations are awaited::

    await aredis("cache").get("key")

Clients are closed via ``aredis.aclose_all()`` (an awaitable); the framework
calls it inside the event loop when async lanes finish.
"""

from fun_things.singleton_hub.async_redis_hub import (  # noqa: F401
    AsyncRedisHub as aredis,
)
from fun_things.singleton_hub.async_redis_hub import (  # noqa: F401
    AsyncRedisHubMeta,
)
