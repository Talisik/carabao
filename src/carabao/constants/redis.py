from typing import Set

from fun_things.singleton_hub.redis_hub import RedisHub, RedisHubMeta
from redis import Redis
from redis.backoff import ExponentialBackoff
from redis.exceptions import ConnectionError, TimeoutError
from redis.retry import Retry

from ._constants import C


class RedisMeta(RedisHubMeta):
    __cache: Set[str] = set()

    def _value_selector(cls, name: str):
        client = super()._value_selector(name)

        if not C(
            "REDIS_KUMA",
            cast=bool,
            default=True,
        ):
            return client

        kwargs = client.connection_pool.connection_kwargs
        host = kwargs.get("host")
        port = kwargs.get("port")
        address = f"{host}:{port}"

        if not host or not port:
            return client

        if address in cls.__cache:
            return client

        url = C(
            "REDIS_KUMA_URL",
            default=None,
        )

        from carabao.helpers.kumander import kumander

        if not url and not kumander.url:
            return client

        timeout = C(
            "REDIS_KUMA_PING_TIMEOUT",
            cast=float,
            default=3,
        )

        try:
            probe = Redis(
                host=host,
                port=port,
                socket_timeout=timeout,
                socket_connect_timeout=timeout,
            )

            try:
                probe.ping()

            finally:
                probe.close()

        except Exception:
            kumander.ping(
                url,
                "Redis",
                addresses=address,
            )

            raise

        return client


class redis(RedisHub, metaclass=RedisMeta):
    _kwargs = dict(
        retry=Retry(
            ExponentialBackoff(
                cap=60,
                base=1,
            ),
            25,
        ),
        retry_on_error=[
            ConnectionError,
            TimeoutError,
            ConnectionResetError,
        ],
        health_check_interval=60,
    )
