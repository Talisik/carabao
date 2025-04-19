import logging
from typing import Type, Union, final

from l2l import LOGGER, Lane
from lazy_main import LazyMain

from .constants import C
from .settings import Settings


@final
class Core:
    __started = False

    def __init__(self):
        raise Exception("This is not instantiable!")

    @classmethod
    def start(cls):
        """
        Starts the module.

        This module can only start once.
        """
        if cls.__started:
            return

        cls.__start()

    @classmethod
    def load_lanes(
        cls,
        settings: Union[Settings, Type[Settings]],
    ):
        _ = [
            lane
            for lane_directory in settings.value_of("LANE_DIRECTORIES")
            for lane in Lane.load(lane_directory)
        ]

    @classmethod
    def __start(cls):
        LOGGER().setLevel(logging.DEBUG if C.TESTING else logging.INFO)

        settings = Settings.get()
        cls.__started = True

        cls.load_lanes(settings)

        if C.QUEUE_NAME is None:
            raise Exception("'QUEUE_NAME' is not in the environment!")

        main = LazyMain(
            main=Lane.start,
            run_once=settings.value_of("SINGLE_RUN"),
            sleep_min=settings.value_of("SLEEP_MIN"),
            sleep_max=settings.value_of("SLEEP_MAX"),
            exit_on_finish=settings.value_of("EXIT_ON_FINISH"),
            exit_delay=settings.value_of("EXIT_DELAY"),
            error_handler=settings.error_handler,
        )
        print_lanes = True

        for loop in main:
            loop(
                C.QUEUE_NAME,
                print_lanes=print_lanes,
                processes=settings.value_of("PROCESSES"),
            )

            print_lanes = False

        try:
            from .constants import mongo

            mongo.clear_all()

        except Exception:
            pass

        try:
            from .constants import redis

            redis.clear_all()

        except Exception:
            pass

        try:
            from .constants import es

            es.clear_all()

        except Exception:
            pass
