from typing import Set

from fun_things.singleton_hub.elasticsearch_hub import (
    ElasticsearchHub,
    ElasticsearchHubMeta,
)

from ._constants import C


class ESMeta(ElasticsearchHubMeta):
    __cache: Set[str] = set()

    def _value_selector(cls, name: str):
        client = super()._value_selector(name)

        if not C(
            "ES_KUMA",
            cast=bool,
            default=True,
        ):
            return client

        try:
            nodes = list(client.transport.node_pool.all())

        except Exception:
            nodes = []

        address = ",".join(sorted(f"{node.host}:{node.port}" for node in nodes))

        if not address:
            return client

        if address in cls.__cache:
            return client

        url = C(
            "ES_KUMA_URL",
            default=None,
        )

        from carabao.helpers.kumander import kumander

        if not url and not kumander.url:
            return client

        timeout = C(
            "ES_KUMA_PING_TIMEOUT",
            cast=float,
            default=3,
        )

        try:
            response = client.options(
                request_timeout=timeout,
            ).ping()

            if not response:
                raise Exception("ping returned False")

        except Exception:
            kumander.ping(
                url,
                "Elasticsearch",
                addresses=address,
            )

            raise

        return client


class es(ElasticsearchHub, metaclass=ESMeta):
    _kwargs = dict(
        request_timeout=30,
        # sniff_on_start=True,
        sniff_on_connection_fail=True,
        min_delay_between_sniffing=60,
        max_retries=5,
        retry_on_timeout=True,
        connections_per_node=25,
    )
