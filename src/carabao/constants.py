import os
import re

from dotenv import load_dotenv
from fun_things import lazy
from fun_things.environment import env
from psycopg2._psycopg import connection


@lazy
class Constants:
    __env = False

    @classmethod
    def load_env(cls):
        if cls.__env:
            return

        cls.__env = True

        __environment = os.getenv(
            "ENVIRONMENT",
            "staging",
        )
        __env_file = f".env.{__environment}" if __environment else ".env"

        if os.path.exists(__env_file):
            load_dotenv(__env_file)
            print(
                f"\033[43m\033[33m{__env_file}\033[0m\033[33m loaded.\033[0m",
            )
        else:
            load_dotenv()
            print(
                "\033[43m\033[33m.env\033[0m\033[33m loaded.\033[0m",
            )

    def load_all_properties(self):
        """
        Loads all property functions to ensure that all environment variables
        are initialized and loaded.
        """
        for name in dir(self):
            attr = getattr(self, name)

            if isinstance(attr, property):
                # Access the property to trigger its loading
                if not attr.fget:
                    continue

                _ = attr.fget(self)

    @property
    @lazy.fn
    def PROCESSES(self):
        self.load_env()

        return env(
            "PROCESSES",
            cast=int,
            default=None,
        )

    @property
    @lazy.fn
    def DEPLOY_SAFELY(self):
        """
        If `True`,
        things that might be bad in a proper deployment will be adjusted,
        such as testing-related stuff.
        """
        self.load_env()

        return env(
            "DEPLOY_SAFELY",
            cast=bool,
            default=True,
        )

    @property
    @lazy.fn
    def POD_NAME(self):
        self.load_env()

        return env(
            "POD_NAME",
            cast=str,
            default="",
        )

    @property
    @lazy.fn
    def POD_INDEX(self):
        self.load_env()

        try:
            return int(self.POD_NAME.split("-")[-1])
        except Exception:
            return 0

    @property
    @lazy.fn
    def IN_KUBERNETES(self):
        """
        If this process is running inside Kubernetes.
        """
        self.load_env()

        return any(
            map(
                # Prevent testing mode in Kubernetes.
                lambda key: "kubernetes" in key.lower(),
                os.environ.keys(),
            )
        )

    @property
    @lazy.fn
    def ENVIRONMENT(self):
        self.load_env()

        return env(
            "ENVIRONMENT",
            cast=str,
            default="staging",
        )

    @property
    @lazy.fn
    def IN_DEVELOPMENT(self):
        pass

    @property
    @lazy.fn
    def ENV_IS_PRODUCTION(self):
        self.load_env()

        return self.ENVIRONMENT == "production"

    @property
    @lazy.fn
    def ENV_IS_STAGING(self):
        self.load_env()

        return self.ENVIRONMENT == "staging"

    @property
    @lazy.fn
    def TESTING(self):
        """
        For testing purposes.

        Always `False` inside Kubernetes.
        """
        self.load_env()

        return (
            False
            if C.DEPLOY_SAFELY and self.IN_KUBERNETES
            else (
                env(
                    "TESTING",
                    cast=bool,
                    default=False,
                )
            )
        )

    @property
    @lazy.fn
    def SINGLE_RUN(self):
        self.load_env()
        return env(
            "SINGLE_RUN",
            cast=bool,
            default=True,
        )

    @property
    @lazy.fn
    def QUEUE_NAME(self):
        self.load_env()
        return env(
            "QUEUE_NAME",
            cast=str,
            default=None,
        )

    @property
    @lazy.fn
    def BATCH_SIZE(self):
        self.load_env()
        return env(
            "BATCH_SIZE",
            cast=int,
            default=1,
        )

    @property
    @lazy.fn
    def SLEEP_MIN(self):
        self.load_env()

        return env(
            "SLEEP_MIN",
            cast=float,
            default=3,
        )

    @property
    @lazy.fn
    def SLEEP_MAX(self):
        self.load_env()

        return env(
            "SLEEP_MAX",
            cast=float,
            default=5,
        )

    @property
    @lazy.fn
    def EXIT_ON_FINISH(self):
        self.load_env()

        return env(
            "EXIT_ON_FINISH",
            cast=bool,
            default=True,
        )

    @property
    @lazy.fn
    def EXIT_DELAY(self):
        self.load_env()

        return env(
            "EXIT_DELAY",
            cast=float,
            default=3,
        )

    @property
    @lazy.fn
    def LANE_DIRECTORIES(self):
        """
        A list of directories where lane modules are located.
        """
        self.load_env()

        return env(
            "LANE_DIRECTORIES",
            cast=lambda value: [
                item.strip()
                for item in re.split(
                    r"[^,\n]+",
                    value,
                )
            ],
            default=["lanes"],
        )


C = Constants()

if os.getenv(
    "CARABAO_ENV_AUTOLOAD",
    "1",
).lower() in (
    "true",
    "1",
    "t",
    "y",
    "yes",
):
    C.load_env()

try:
    from fun_things.singleton_hub.mongo_hub import MongoHub

    class mongo(MongoHub):
        pass

except Exception:
    pass


try:
    from fun_things.singleton_hub.redis_hub import RedisHub
    from redis.backoff import ExponentialBackoff
    from redis.exceptions import ConnectionError, TimeoutError
    from redis.retry import Retry

    class redis(RedisHub):
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

except Exception:
    pass


try:
    from fun_things.singleton_hub.elasticsearch_hub import ElasticsearchHub

    class es(ElasticsearchHub):
        _kwargs = dict(
            request_timeout=30,
            sniff_on_start=True,
            sniff_on_connection_fail=True,
            min_delay_between_sniffing=60,
            max_retries=5,
            retry_on_timeout=True,
            connections_per_node=25,
        )

except Exception:
    pass

try:
    import psycopg2
    from fun_things.singleton_hub.environment_hub import EnvironmentHubMeta
    from psycopg2._psycopg import connection

    admin = psycopg2.connect()

    class PGMeta(EnvironmentHubMeta[connection]):
        _formats = EnvironmentHubMeta._bake_basic_uri_formats(
            "PG",
            "POSTGRESQL",
            "POSTGRES",
        )
        _kwargs: dict = {}
        _log: bool = True

        def _value_selector(cls, name: str):
            client = psycopg2.connect(
                os.environ.get(name),
                **cls._kwargs,
            )

            if cls._log:
                print(f"PostgreSQL `{name}` instantiated.")

            return client

        def _on_clear(cls, key: str, value: connection) -> None:
            value.close()

            if cls._log:
                print(f"PostgreSQL `{key}` closed.")

    class pg(metaclass=PGMeta):
        def __new__(cls, name: str = ""):
            return cls.get(name)

except Exception:
    pass
