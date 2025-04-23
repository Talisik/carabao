import os
import re

from dotenv import load_dotenv
from fun_things import lazy
from fun_things.environment import env


@lazy
class Constants:
    __env = False
    __dev_mode = False

    @classmethod
    def _dev_mode(cls, name: str):
        cls.__dev_mode = True
        cls.__dev_name = name

    @classmethod
    def load_env(cls):
        """
        Loads environment variables from a file. The method first checks if the
        environment variables have already been loaded. If not, it determines
        the appropriate file to load based on the development mode. It attempts
        to load from '.env.development' or '.env.release' first, and if neither
        exists, it defaults to loading from '.env'.

        The method prints a message indicating which file was loaded.
        """
        if cls.__env:
            return

        cls.__env = True

        filepath = ".env.development" if cls.__dev_mode else ".env.release"
        color_code = "43" if cls.__dev_mode else "42"
        template = "Environment File: \033[{0}m{1}\033[0m\n"

        if os.path.exists(filepath):
            load_dotenv(filepath)

            print(
                template.format(
                    color_code,
                    filepath,
                ),
            )
            return

        filepath = ".env"

        if os.path.exists(filepath):
            load_dotenv(filepath)
            print(
                template.format(
                    color_code,
                    filepath,
                ),
            )
            return

        load_dotenv()

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
        """
        The number of processes to use in the application.

        Returns:
            int or None: Number of processes to use, or None for default.
        """
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
        """
        The name of the Kubernetes pod running this application.

        Returns:
            str: The pod name, or empty string if not in Kubernetes.
        """
        self.load_env()

        return env(
            "POD_NAME",
            cast=str,
            default="",
        )

    @property
    @lazy.fn
    def POD_INDEX(self):
        """
        The index of the pod in a stateful set, extracted from POD_NAME.

        Returns:
            int: The pod index, or 0 if not determinable.
        """
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
        """
        The current environment the application is running in.

        Returns:
            str: The environment name (e.g., 'production', 'staging', 'development').
        """
        self.load_env()

        return env(
            "ENVIRONMENT",
            cast=str,
            default="staging",
        )

    @property
    @lazy.fn
    def IN_DEVELOPMENT(self):
        """
        Indicates if the application is ran via `carabao dev` or `moo dev`.

        Returns:
            bool: True if in development mode, False otherwise.
        """
        return self.__class__.__dev_mode

    @property
    @lazy.fn
    def IS_PRODUCTION(self):
        """
        Indicates if the application is running in a production environment.

        Returns:
            bool: True if ENVIRONMENT equals 'production', False otherwise.
        """
        self.load_env()

        return self.ENVIRONMENT == "production"

    @property
    @lazy.fn
    def IS_STAGING(self):
        """
        Indicates if the application is running in a staging environment.

        Returns:
            bool: True if ENVIRONMENT equals 'staging', False otherwise.
        """
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
            if self.DEPLOY_SAFELY and self.IN_KUBERNETES
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
        """
        Determines if the application should run only once.

        Returns:
            bool: True if application should exit after one run, False for continuous execution.
        """
        self.load_env()
        return env(
            "SINGLE_RUN",
            cast=bool,
            default=True,
        )

    @property
    @lazy.fn
    def QUEUE_NAME(self):
        """
        The name of the queue to process.

        Returns:
            str or None: The queue name or None if not specified.
        """
        if self.__dev_mode:
            return self.__dev_name

        self.load_env()

        return env(
            "QUEUE_NAME",
            cast=str,
            default=None,
        )

    @property
    @lazy.fn
    def BATCH_SIZE(self):
        """
        The number of items to process in a batch.

        Returns:
            int: Batch size, defaults to 1 if not specified.
        """
        self.load_env()
        return env(
            "BATCH_SIZE",
            cast=int,
            default=1,
        )

    @property
    @lazy.fn
    def SLEEP_MIN(self):
        """
        The minimum sleep time between loop iterations when no work is available.

        Returns:
            float: Minimum sleep time in seconds, defaults to 3.
        """
        self.load_env()

        return env(
            "SLEEP_MIN",
            cast=float,
            default=3,
        )

    @property
    @lazy.fn
    def SLEEP_MAX(self):
        """
        The maximum sleep time between loop iterations when no work is available.

        Returns:
            float: Maximum sleep time in seconds, defaults to 5.
        """
        self.load_env()

        return env(
            "SLEEP_MAX",
            cast=float,
            default=5,
        )

    @property
    @lazy.fn
    def EXIT_ON_FINISH(self):
        """
        Determines if the application should exit after all work is finished.

        Returns:
            bool: True if the application should exit when finished, False otherwise.
        """
        self.load_env()

        return env(
            "EXIT_ON_FINISH",
            cast=bool,
            default=True,
        )

    @property
    @lazy.fn
    def EXIT_DELAY(self):
        """
        The delay before exiting after all work is finished, when EXIT_ON_FINISH is True.

        Returns:
            float: Exit delay in seconds, defaults to 3.
        """
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
