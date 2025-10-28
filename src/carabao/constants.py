import os
import re
from typing import Any, Callable, TypeVar

from dotenv import load_dotenv
from fun_things import lazy, undefined
from fun_things.environment import env

T = TypeVar("T")


@lazy
class Constants:
    __env = False
    __values = {}
    __custom = {}

    def __call__(
        self,
        *keys,
        cast: Callable[[Any], T] = str,
        default: Any = undefined,
        write_to_env=False,
    ):
        self.load_env()

        return env(
            *keys,
            cast=cast,
            default=default,
            write_to_env=write_to_env,
        )

    def __getitem__(self, key: str) -> Any:
        if key in self.__custom:
            return self.__custom[key]

        if key in self.__values:
            return self.__values[key]

        return self(key)

    def __setitem__(self, key: str, value: Any):
        self.__custom[key] = value

    def __delitem__(self, key: str):
        del self.__custom[key]

    def field(
        self,
        *keys,
        cast: Callable[[Any], T] = str,
        default: Any = undefined,
        write_to_env=False,
    ):
        def field() -> T:
            for key in keys:
                if key in self.__custom:
                    return self.__custom[key]

                if key in self.__values:
                    return self.__values[key]

            return self(
                *keys,
                cast=cast,
                default=default,
                write_to_env=write_to_env,
            )

        return field

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

        template = "\033[{0}m{1}\033[0m"
        result = []

        from .core import Core

        is_dev = Core.is_dev()

        for filepath, template in {
            ".env.development" if is_dev else ".env.release": "\033[43;30m{0}\033[0m"
            if is_dev
            else "\033[42;30m{0}\033[0m",
            ".env": "\033[47;30m{0}\033[0m",
        }.items():
            if not os.path.exists(filepath):
                continue

            load_dotenv(filepath)

            result.append(template.format(filepath))

        print(
            "Environment:",
            " + ".join(result) + "\n",
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
    def PROCESSES(self):
        """
        The number of processes to use in the application.

        Returns:
            int or None: Number of processes to use, or None for default.
        """
        key = "PROCESSES"

        if key in self.__custom:
            return self.__custom[key]

        if key in self.__values:
            return self.__values[key]

        self.load_env()

        self.__values[key] = value = env(
            key,
            cast=int,
            default=None,
        )

        return value

    @property
    def DEPLOY_SAFELY(self):
        """
        If `True`,
        things that might be bad in a proper deployment will be adjusted,
        such as testing-related stuff.
        """
        key = "DEPLOY_SAFELY"

        if key in self.__custom:
            return self.__custom[key]

        if key in self.__values:
            return self.__values[key]

        self.load_env()

        self.__values[key] = value = env(
            key,
            cast=bool,
            default=True,
        )

        return value

    @property
    def POD_NAME(self):
        """
        The name of the Kubernetes pod running this application.

        Returns:
            str: The pod name, or empty string if not in Kubernetes.
        """
        key = "POD_NAME"

        if key in self.__custom:
            return self.__custom[key]

        if key in self.__values:
            return self.__values[key]

        self.load_env()

        self.__values[key] = value = env(
            key,
            cast=str,
            default="",
        )

        return value

    @property
    def POD_INDEX(self):
        """
        The index of the pod in a stateful set, extracted from POD_NAME.

        Returns:
            int: The pod index, or 0 if not determinable.
        """
        key = "POD_INDEX"

        if key in self.__custom:
            return self.__custom[key]

        if key in self.__values:
            return self.__values[key]

        self.load_env()

        try:
            self.__values[key] = value = int(self.POD_NAME.split("-")[-1])
        except Exception:
            self.__values[key] = value = 0

        return value

    @property
    def IN_KUBERNETES(self):
        """
        If this process is running inside Kubernetes.
        """
        key = "IN_KUBERNETES"

        if key in self.__custom:
            return self.__custom[key]

        if key in self.__values:
            return self.__values[key]

        self.load_env()

        self.__values[key] = value = any(
            map(
                # Prevent testing mode in Kubernetes.
                lambda key: "kubernetes" in key.lower(),
                os.environ.keys(),
            )
        )

        return value

    @property
    def ENVIRONMENT(self):
        """
        The current environment the application is running in.

        Returns:
            str: The environment name (e.g., 'production', 'staging', 'development').
        """
        key = "ENVIRONMENT"

        if key in self.__custom:
            return self.__custom[key]

        if key in self.__values:
            return self.__values[key]

        self.load_env()

        self.__values[key] = value = env(
            key,
            cast=str,
            default="staging",
        )

        return value

    @property
    def IN_DEVELOPMENT(self):
        """
        Indicates if the application is ran via `carabao dev` or `moo dev`.

        Returns:
            bool: True if in development mode, False otherwise.
        """
        from .core import Core

        return Core.is_dev()

    @property
    def IS_PRODUCTION(self):
        """
        Indicates if the application is running in a production environment.

        Returns:
            bool: True if ENVIRONMENT equals 'production', False otherwise.
        """
        self.load_env()

        return self.ENVIRONMENT == "production"

    @property
    def IS_STAGING(self):
        """
        Indicates if the application is running in a staging environment.

        Returns:
            bool: True if ENVIRONMENT equals 'staging', False otherwise.
        """
        self.load_env()

        return self.ENVIRONMENT == "staging"

    @property
    def TESTING(self):
        """
        For testing purposes.

        Always `False` inside Kubernetes.
        """
        key = "TESTING"

        if key in self.__custom:
            return self.__custom[key]

        if key in self.__values:
            return self.__values[key]

        self.load_env()

        from .core import Core

        is_test = Core.is_test()

        self.__values[key] = value = (
            is_test
            if is_test is not None
            else (
                False
                if self.DEPLOY_SAFELY and self.IN_KUBERNETES
                else env(key, cast=bool, default=False)
            )
        )

        return value

    @property
    def SINGLE_RUN(self):
        """
        Determines if the application should run only once.

        Returns:
            bool: True if application should exit after one run, False for continuous execution.
        """
        key = "SINGLE_RUN"

        if key in self.__custom:
            return self.__custom[key]

        if key in self.__values:
            return self.__values[key]

        self.load_env()

        self.__values[key] = value = env(
            key,
            cast=bool,
            default=True,
        )

        return value

    @property
    def QUEUE_NAME(self):
        """
        The name of the queue to process.

        Returns:
            str or None: The queue name or None if not specified.
        """
        key = "QUEUE_NAME"

        if key in self.__custom:
            return self.__custom[key]

        if key in self.__values:
            return self.__values[key]

        from .core import Core

        custom_name = Core.name()

        if custom_name is not None:
            self.__values[key] = value = custom_name

        else:
            self.__values[key] = value = env(
                key,
                cast=str,
                default=None,
            )

        return value

    @property
    def BATCH_SIZE(self):
        """
        The number of items to process in a batch.

        Returns:
            int: Batch size, defaults to 1 if not specified.
        """
        key = "BATCH_SIZE"

        if key in self.__custom:
            return self.__custom[key]

        if key in self.__values:
            return self.__values[key]

        self.load_env()

        self.__values[key] = value = env(
            key,
            cast=int,
            default=1,
        )

        return value

    @property
    def SLEEP_MIN(self):
        """
        The minimum sleep time between loop iterations when no work is available.

        Returns:
            float: Minimum sleep time in seconds, defaults to 3.
        """
        key = "SLEEP_MIN"

        if key in self.__custom:
            return self.__custom[key]

        if key in self.__values:
            return self.__values[key]

        self.load_env()

        self.__values[key] = value = env(
            key,
            cast=float,
            default=3,
        )

        return value

    @property
    def SLEEP_MAX(self):
        """
        The maximum sleep time between loop iterations when no work is available.

        Returns:
            float: Maximum sleep time in seconds, defaults to 5.
        """
        key = "SLEEP_MAX"

        if key in self.__custom:
            return self.__custom[key]

        if key in self.__values:
            return self.__values[key]

        self.load_env()

        self.__values[key] = value = env(
            key,
            cast=float,
            default=5,
        )

        return value

    @property
    def EXIT_ON_FINISH(self):
        """
        Determines if the application should exit after all work is finished.

        Returns:
            bool: True if the application should exit when finished, False otherwise.
        """
        key = "EXIT_ON_FINISH"

        if key in self.__custom:
            return self.__custom[key]

        if key in self.__values:
            return self.__values[key]

        self.load_env()

        self.__values[key] = value = env(
            key,
            cast=bool,
            default=True,
        )

        return value

    @property
    def EXIT_DELAY(self):
        """
        The delay before exiting after all work is finished, when EXIT_ON_FINISH is True.

        Returns:
            float: Exit delay in seconds, defaults to 3.
        """
        key = "EXIT_DELAY"

        if key in self.__custom:
            return self.__custom[key]

        if key in self.__values:
            return self.__values[key]

        self.load_env()

        self.__values[key] = value = env(
            key,
            cast=float,
            default=3,
        )

        return value

    @property
    def LANE_DIRECTORIES(self):
        """
        A list of directories where lane modules are located.
        """
        key = "LANE_DIRECTORIES"

        if key in self.__custom:
            return self.__custom[key]

        if key in self.__values:
            return self.__values[key]

        self.load_env()

        self.__values[key] = value = env(
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

        return value


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
            # sniff_on_start=True,
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
