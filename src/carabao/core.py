import logging
from typing import final

from l2l import LOGGER, Lane
from lazy_main import LazyMain

from .constants import QUEUE_NAME, TESTING
from .settings import Settings


@final
class Core:
    def __init__(self):
        raise Exception("This is not instantiable!")

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
        if cls.__started:
            return

        cls.__start()

    @classmethod
    def __start(cls):
        LOGGER().setLevel(logging.DEBUG if TESTING else logging.INFO)

        settings = Settings.get()
        cls.__started = True

        _ = [
            lane
            for lane_directory in settings.lane_directories
            for lane in Lane.load(lane_directory)
        ]

        if QUEUE_NAME == None:
            raise Exception("'QUEUE_NAME' is not in the environment!")

        main = LazyMain(
            main=Lane.start,
            run_once=settings.run_once,
            sleep_min=settings.sleep_min,
            sleep_max=settings.sleep_max,
            exit_on_finish=settings.exit_on_finish,
            exit_delay=settings.exit_delay,
            error_handler=settings.error_handler,
        )
        print_lanes = True

        for loop in main:
            loop(
                QUEUE_NAME,
                print_lanes=print_lanes,
            )

            print_lanes = False

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
