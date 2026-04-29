from typing import Set

import pymongo
from fun_things.singleton_hub.mongo_hub import MongoHub, MongoHubMeta

from ._constants import C


class MongoMeta(MongoHubMeta):
    __cache: Set[str] = set()

    def _value_selector(cls, name: str):
        client = super()._value_selector(name)

        if not C(
            "MONGO_KUMA",
            cast=bool,
            default=True,
        ):
            return client

        addresses = addresses = ",".join(
            sorted(
                f"{hostname}:{port}"
                for hostname, port in client.topology_description.server_descriptions().keys()
            )
        )

        if addresses in cls.__cache:
            return client

        url = C(
            "MONGO_KUMA_URL",
            default=None,
        )

        from carabao.helpers.kumander import kumander

        if not url and not kumander.url:
            return client

        try:
            with pymongo.timeout(
                C(
                    "MONGO_KUMA_PING_TIMEOUT",
                    cast=float,
                    default=3,
                )
            ):
                client.admin.command("ping")

        except Exception:
            kumander.ping(
                url,
                "MongoDB",
                addresses=addresses,
            )

            raise

        return client


class mongo(MongoHub, metaclass=MongoMeta): ...
