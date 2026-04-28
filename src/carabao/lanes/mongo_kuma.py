from carabao.constants import C
from carabao.lanes.uptime_kuma import UptimeKuma

try:
    import pymongo

    from carabao.constants import mongo

except Exception:
    mongo = None
    pymongo = None

try:
    from loguru import logger

    LOGGER_ERROR = logger.error

except Exception:
    LOGGER_ERROR = print


class MongoKuma(UptimeKuma):
    kind = "MongoDB"

    @classmethod
    def condition(cls, name: str):
        if not C(
            "MONGO_KUMA",
            cast=bool,
            default=True,
        ):
            return False

        url = C(
            "MONGO_KUMA_URL",
            default=None,
        ) or C(
            "UPTIME_KUMA_URL",
            default=None,
        )

        if url:
            return True

        return False

    def check(self, format: str, url: str) -> bool:
        if not mongo:
            return True

        if not pymongo:
            return True

        url = (
            C(
                "MONGO_KUMA_URL",
                default=None,
            )
            or url
        )

        cache = set()
        ok = True

        for client in mongo.get_all():
            addresses = ",".join(
                sorted(
                    f"{hostname}:{port}"
                    for hostname, port in client.topology_description.server_descriptions().keys()
                )
            )

            if not addresses:
                continue

            if addresses in cache:
                continue

            cache.add(addresses)

            try:
                with pymongo.timeout(
                    C(
                        "MONGO_KUMA_PING_TIMEOUT",
                        cast=float,
                        default=5.0,
                    )
                ):
                    client.admin.command("ping")

                continue

            except Exception:
                ok = False

                self.ping(
                    format,
                    url,
                    addresses,
                )

        return ok
