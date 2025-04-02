import os
from typing import Literal

from dotenv import load_dotenv
from fun_things.environment import env

load_dotenv()


def __environment(value):
    if value == "staging":
        return "staging"

    if value == "production":
        return "production"

    raise ValueError(f"Invalid environment '{value}'!")


# ROOT_FOLDER_NAME = pathlib.Path(os.getcwd()).name
# """
# The name of the current working directory.
# """

FRAMEWORK_NAME = "CARABAO"
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
