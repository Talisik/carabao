from carabao.constants import C
from carabao.lanes.uptime_kuma import UptimeKuma

try:
    from elasticsearch import Elasticsearch

    from carabao.constants import es

except Exception:
    es = None
    Elasticsearch = None

try:
    from loguru import logger

    LOGGER_ERROR = logger.error

except Exception:
    LOGGER_ERROR = print


class ESKuma(UptimeKuma):
    kind = "Elasticsearch"

    @classmethod
    def condition(cls, name: str):
        if not C(
            "ES_KUMA",
            cast=bool,
            default=True,
        ):
            return False

        url = C(
            "ES_KUMA_URL",
            default=None,
        ) or C(
            "UPTIME_KUMA_URL",
            default=None,
        )

        if url:
            return True

        return False

    def check(self, format: str, url: str) -> bool:
        if not es:
            return True

        if not Elasticsearch:
            return True

        url = (
            C(
                "ES_KUMA_URL",
                default=None,
            )
            or url
        )

        cache = set()
        ok = True

        timeout = C(
            "ES_KUMA_PING_TIMEOUT",
            cast=float,
            default=5.0,
        )

        for client in es.get_all():
            try:
                nodes = list(client.transport.node_pool.all())

            except Exception:
                nodes = []

            address = ",".join(sorted(f"{node.host}:{node.port}" for node in nodes))

            if not address:
                continue

            if address in cache:
                continue

            cache.add(address)

            try:
                response = client.options(
                    request_timeout=timeout,
                ).ping()

                if response:
                    continue

            except Exception:
                ...

            ok = False

            self.ping(
                format,
                url,
                address,
            )

        return ok
