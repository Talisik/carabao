from carabao.constants import C
from carabao.lanes.uptime_kuma import UptimeKuma

try:
    from redis import Redis

    from carabao.constants import redis

except Exception:
    redis = None
    Redis = None

try:
    from loguru import logger

    LOGGER_ERROR = logger.error

except Exception:
    LOGGER_ERROR = print


class RedisKuma(UptimeKuma):
    kind = "Redis"

    @classmethod
    def condition(cls, name: str):
        if not C(
            "REDIS_KUMA",
            cast=bool,
            default=True,
        ):
            return False

        url = C(
            "REDIS_KUMA_URL",
            default=None,
        ) or C(
            "UPTIME_KUMA_URL",
            default=None,
        )

        if url:
            return True

        return False

    def check(self, format: str, url: str) -> bool:
        if not redis:
            return True

        if not Redis:
            return True

        url = (
            C(
                "REDIS_KUMA_URL",
                default=None,
            )
            or url
        )

        cache = set()
        ok = True

        timeout = C(
            "REDIS_KUMA_PING_TIMEOUT",
            cast=float,
            default=3,
        )

        for client in redis.get_all():
            kwargs = client.connection_pool.connection_kwargs
            address = f"{kwargs.get('host')}:{kwargs.get('port')}"

            if not address:
                continue

            if address in cache:
                continue

            cache.add(address)

            probe_kwargs = {
                **kwargs,
                "socket_timeout": timeout,
                "socket_connect_timeout": timeout,
                "retry_on_timeout": False,
                "retry_on_error": [],
            }

            probe_kwargs.pop("retry", None)

            try:
                probe = Redis(**probe_kwargs)

                try:
                    response = probe.ping()

                finally:
                    probe.close()

                if response:
                    continue

            except Exception:
                continue

            ok = False

            self.ping(
                format,
                url,
                address,
            )

        return ok
