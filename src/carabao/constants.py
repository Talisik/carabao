import os

from dotenv import load_dotenv
from fun_things.environment import env

load_dotenv()


def __environment(value):
    if value == "staging":
        return "staging"

    if value == "production":
        return "production"

    raise Exception(f"Invalid environment '{value}'!")


def __core_startup(value):
    value = value.upper()

    if value not in ["ENABLED", "DISABLED", "AUTO_START"]:
        raise Exception(f"Invalid core startup '{value}'!")

    return value


# ROOT_FOLDER_NAME = pathlib.Path(os.getcwd()).name
# """
# The name of the current working directory.
# """

FRAMEWORK_NAME = "CARABAO"
FRAMEWORK_AUTO_INITIALIZE = env(
    f"{FRAMEWORK_NAME}_AUTO_INITIALIZE",
    cast=bool,
    default=True,
)
"""
If the framework should be initialized upon import.
"""
FRAMEWORK_STARTUP = env(
    f"{FRAMEWORK_NAME}_STARTUP",
    cast=__core_startup,
    default="AUTO_START",
)
"""
The behaviour of the framework on how it should start.

`ENABLED` =
The framework can be started.

`DISABLED` =
The framework cannot be started.
This does not throw an error.

`AUTO_START` =
The framework starts automatically.
It can still be started manually.
Happens when the process is about to exit.
"""
FRAMEWORK_MAIN_FILE = env(
    f"{FRAMEWORK_NAME}_MAIN_FILE",
    cast=str,
    default=".",
)
"""
The location of the main file to be executed.

This is used by the CLI.
"""
FRAMEWORK_START_WITH_ERROR = env(
    f"{FRAMEWORK_NAME}_START_WITH_ERROR",
    cast=bool,
    default=False,
)
"""
If the framework should still auto-start regardless
if there was an error.
"""
FRAMEWORK_CONFIG = env(
    f"{FRAMEWORK_NAME}_CONFIG",
    cast=str,
    default="ENABLED",
)
"""
If the framework should write a `.cfg` file.

`ENABLED` =
The framework will write the entire `.cfg` file.

`DISCRETE` =
The framework will write the list of consumers only.

`DISABLED` =
The framework will not write the `.cfg` file.
"""
FRAMEWORK_DEPLOY_SAFELY = env(
    f"{FRAMEWORK_NAME}_DEPLOY_SAFELY",
    cast=bool,
    default=True,
)
"""
If `True`,
things that might be bad in a proper deployment will be adjusted,
such as testing-related stuff.
"""

CONFIG_NAME = ".ignore.carabao.cfg"
CONFIG_LAST_RUN = "last_run"
CONFIG_CONSUMERS = "consumers"

POD_NAME = env(
    "POD_NAME",
    cast=str,
    default="",
)

try:
    POD_INDEX = int(POD_NAME.split("-")[-1])
except:
    POD_INDEX = 0

IN_KUBERNETES = any(
    map(
        # Prevent testing mode in Kubernetes.
        lambda key: "kubernetes" in key.lower(),
        os.environ.keys(),
    )
)
"""
If this process is running inside Kubernetes.
"""
ENVIRONMENT = env(
    "ENVIRONMENT",
    cast=__environment,
    default="staging",
)
"""
Values: `staging`, `production`
"""
IS_PRODUCTION = ENVIRONMENT == "production"
IS_STAGING = ENVIRONMENT == "staging"
TESTING = (
    False
    if FRAMEWORK_DEPLOY_SAFELY and IN_KUBERNETES
    else (
        env(
            "TESTING",
            cast=bool,
            default=False,
        )
    )
)
"""
For testing purposes.

Always `False` inside Kubernetes.
"""
SINGLE_RUN = env(
    "SINGLE_RUN",
    cast=bool,
    default=True,
)

QUEUE_NAME = env(
    "QUEUE_NAME",
    cast=str,
    default=None,
)
BATCH_SIZE = env(
    "BATCH_SIZE",
    cast=int,
    default=1,
)

SLEEP_MIN = env(
    "SLEEP_MIN",
    cast=float,
    default=3,
)
SLEEP_MAX = env(
    "SLEEP_MAX",
    cast=float,
    default=5,
)

EXIT_ON_FINISH = env(
    "EXIT_ON_FINISH",
    cast=bool,
    default=True,
)
EXIT_DELAY = env(
    "EXIT_DELAY",
    cast=float,
    default=3,
)


try:
    from fun_things.singleton_hub.mongo_hub import MongoHub

    class mongo(MongoHub):
        pass

except:
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

except:
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

except:
    pass
