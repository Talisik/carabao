"""Async MongoDB hub (``amongo``) for use inside ``AsyncLane`` lanes.

Thin re-export of fun_things' ``AsyncMongoHub`` (pymongo's native
``AsyncMongoClient``, no motor). The accessor is sync — only the operations are
awaited::

    doc = await amongo("main").db.articles.find_one({"id": 1})

Clients are closed via ``amongo.aclose_all()`` (an awaitable); the framework
calls it inside the event loop when async lanes finish.
"""

from fun_things.singleton_hub.async_mongo_hub import (  # noqa: F401
    AsyncMongoHub as amongo,
)
from fun_things.singleton_hub.async_mongo_hub import (  # noqa: F401
    AsyncMongoHubMeta,
)
