import atexit
import logging
import sys
from types import TracebackType
from typing import Callable, List, Literal, Optional, Type, final

from generic_consumer import GenericConsumer, logger
from lazy_main import LazyMain

from .cfg import CFG
from .constants import (
    EXIT_DELAY,
    EXIT_ON_FINISH,
    FRAMEWORK_AUTO_INITIALIZE,
    FRAMEWORK_CONFIG,
    FRAMEWORK_START_WITH_ERROR,
    FRAMEWORK_STARTUP,
    QUEUE_NAME,
    SINGLE_RUN,
    SLEEP_MAX,
    SLEEP_MIN,
    TESTING,
)


@final
class Core:
    startup: Literal[
        "AUTO_START",
        "ENABLED",
        "DISABLED",
    ] = FRAMEWORK_STARTUP  # type: ignore
    config: Literal[
        "ENABLED",
        "DISCRETE",
        "DISABLED",
    ] = FRAMEWORK_CONFIG  # type: ignore
    __started = False
    __initialized = False
    __excepthook = sys.excepthook
    __exception: BaseException = None  # type: ignore
    __error_handlers: List[Callable[[Exception], None]] = []
    __exit_handlers: List[Callable] = []

    def __init__(self):
        raise Exception("This is not instantiable!")

    @classmethod
    def initialize(cls):
        """
        Initializes the module.

        This is automatically called if the environment
        `CARABAO_AUTO_INITIALIZE` is `True`.

        This module can only initialize once.
        """
        if cls.__initialized:
            return

        logger.setLevel(logging.DEBUG if TESTING else logging.INFO)

        sys.excepthook = Core.__excepthook_wrapper

        cls.__initialized = True

    @classmethod
    def add_error_handler(
        cls,
        fn: Callable[[Exception], None],
    ):
        cls.__error_handlers.append(fn)

    @classmethod
    def add_exit_handler(
        cls,
        fn: Callable,
    ):
        cls.__exit_handlers.append(fn)

    @classmethod
    def __error_handler(cls, e: Exception):
        for handler in cls.__error_handlers:
            try:
                handler(e)
            except:
                pass

    @classmethod
    def __exit_handler(cls):
        for handler in cls.__exit_handlers:
            try:
                handler()
            except:
                pass

    @classmethod
    def __excepthook_wrapper(
        cls,
        type: Type[BaseException],
        value: BaseException,
        traceback: Optional[TracebackType],
    ):
        cls.__excepthook(type, value, traceback)
        cls.__exception = value

    @classmethod
    def start(cls):
        """
        Starts the module.

        This is automatically called
        before exiting if the environment
        `CARABAO_AUTO_START` is `True`.

        You may call this at any time even if
        `CARABAO_AUTO_START` is `True`,
        unless `Core.enabled` is `DISABLED`.

        Does not automatically start if an error occurs,
        unless if the environment
        `CARABAO_START_WITH_ERROR` is `True`.

        This module can only start once.
        """
        if Core.startup == "DISABLED":
            return

        if cls.__started:
            return

        cls.__start()

    @classmethod
    def __start(cls):
        cls.__started = True

        if QUEUE_NAME == None:
            raise Exception("'QUEUE_NAME' is not in the environment!")

        main = LazyMain(
            main=GenericConsumer.start,
            run_once=SINGLE_RUN,
            sleep_min=SLEEP_MIN,
            sleep_max=SLEEP_MAX,
            exit_on_finish=EXIT_ON_FINISH,
            exit_delay=EXIT_DELAY,
            error_handler=cls.__error_handler,
        )
        print_consumers = True

        for loop in main:
            loop(
                QUEUE_NAME,
                print_consumers=print_consumers,
            )

            print_consumers = False

        try:
            from .constants import mongo

            mongo.clear_all()

        except:
            pass

        try:
            from .constants import redis

            redis.clear_all()

        except:
            pass

        try:
            from .constants import es

            es.clear_all()

        except:
            pass

        cls.__exit_handler()

    @staticmethod
    @atexit.register
    def __atexit():
        if Core.config != "DISABLED":
            cfg = CFG()

            if Core.config != "DISCRETE":
                cfg.write_last_run()

            cfg.write_consumers()

            cfg.save()

        if Core.startup != "AUTO_START":
            return

        if Core.__started:
            return

        start_with_error = FRAMEWORK_START_WITH_ERROR

        if not start_with_error and Core.__exception != None:
            return

        Core.__start()


if FRAMEWORK_AUTO_INITIALIZE:
    Core.initialize()
