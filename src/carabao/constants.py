import os
import re

from dotenv import load_dotenv
from fun_things import lazy
from fun_things.environment import env


@lazy
class Constants:
    __env = False

    def __load_env(self):
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

    def _ensure_env_loaded(self):
        if not self.__env:
            self.__load_env()

            self.__env = True

    @property
    @lazy.fn
    def PROCESSES(self):
        self._ensure_env_loaded()

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
        self._ensure_env_loaded()

        return env(
            "DEPLOY_SAFELY",
            cast=bool,
            default=True,
        )

    @property
    @lazy.fn
    def POD_NAME(self):
        self._ensure_env_loaded()

        return env(
            "POD_NAME",
            cast=str,
            default="",
        )

    @property
    @lazy.fn
    def POD_INDEX(self):
        self._ensure_env_loaded()

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
        self._ensure_env_loaded()

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
        self._ensure_env_loaded()

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
        self._ensure_env_loaded()

        return self.ENVIRONMENT == "production"

    @property
    @lazy.fn
    def ENV_IS_STAGING(self):
        self._ensure_env_loaded()

        return self.ENVIRONMENT == "staging"

    @property
    @lazy.fn
    def TESTING(self):
        """
        For testing purposes.

        Always `False` inside Kubernetes.
        """
        self._ensure_env_loaded()

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
        self._ensure_env_loaded()
        return env(
            "SINGLE_RUN",
            cast=bool,
            default=True,
        )

    @property
    @lazy.fn
    def QUEUE_NAME(self):
        self._ensure_env_loaded()
        return env(
            "QUEUE_NAME",
            cast=str,
            default=None,
        )

    @property
    @lazy.fn
    def BATCH_SIZE(self):
        self._ensure_env_loaded()
        return env(
            "BATCH_SIZE",
            cast=int,
            default=1,
        )

    @property
    @lazy.fn
    def SLEEP_MIN(self):
        self._ensure_env_loaded()
        return env(
            "SLEEP_MIN",
            cast=float,
            default=3,
        )

    @property
    @lazy.fn
    def SLEEP_MAX(self):
        self._ensure_env_loaded()
        return env(
            "SLEEP_MAX",
            cast=float,
            default=5,
        )

    @property
    @lazy.fn
    def EXIT_ON_FINISH(self):
        self._ensure_env_loaded()
        return env(
            "EXIT_ON_FINISH",
            cast=bool,
            default=True,
        )

    @property
    @lazy.fn
    def EXIT_DELAY(self):
        self._ensure_env_loaded()

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
        self._ensure_env_loaded()

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
