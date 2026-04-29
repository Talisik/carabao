import os
from typing import Set

import psycopg2
from fun_things.singleton_hub.environment_hub import EnvironmentHubMeta
from psycopg2._psycopg import connection
from psycopg2.extensions import parse_dsn

from ._constants import C


class PGMeta(EnvironmentHubMeta[connection]):
    _formats = EnvironmentHubMeta._bake_basic_uri_formats(
        "PG",
        "POSTGRESQL",
        "POSTGRES",
    )
    _kwargs: dict = {}
    _log: bool = True
    __cache: Set[str] = set()

    def _value_selector(cls, name: str):
        dsn = os.environ.get(name)
        client = psycopg2.connect(
            dsn,
            **cls._kwargs,
        )

        if cls._log:
            print(f"PostgreSQL `{name}` instantiated.")

        cls._kuma_check(dsn)

        return client

    def _kuma_check(cls, dsn):
        if not C(
            "PG_KUMA",
            cast=bool,
            default=True,
        ):
            return

        if not dsn:
            return

        try:
            parts = parse_dsn(dsn)

        except Exception:
            return

        host = parts.get("host")
        port = parts.get("port") or 5432
        address = f"{host}:{port}"

        if not host:
            return

        if address in cls.__cache:
            return

        url = C(
            "PG_KUMA_URL",
            default=None,
        )

        from carabao.helpers.kumander import kumander

        if not url and not kumander.url:
            return

        timeout = C(
            "PG_KUMA_PING_TIMEOUT",
            cast=float,
            default=3,
        )

        try:
            probe = psycopg2.connect(
                dsn,
                connect_timeout=max(int(timeout), 1),
            )

            try:
                cur = probe.cursor()
                cur.execute("SELECT 1")
                cur.close()

            finally:
                probe.close()

        except Exception:
            kumander.ping(
                url,
                "PostgreSQL",
                addresses=address,
            )

            raise

    def _on_clear(cls, key: str, value: connection) -> None:
        value.close()

        if cls._log:
            print(f"PostgreSQL `{key}` closed.")


class pg(metaclass=PGMeta):
    def __new__(cls, name: str = ""):
        return cls.get(name)
