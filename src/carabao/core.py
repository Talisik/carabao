import asyncio
import sys
from typing import Optional, Type, Union, final

from l2l import AsyncLane, Lane
from l2l import logger as l2l_logger
from lazy_main import LazyMain

from .constants import C
from .errors import MissingEnvError
from .settings import Settings
from .style import style


@final
class Core:
    """
    Core class for managing the Carabao framework lifecycle.

    This class provides static methods for initializing, starting, and managing the framework.
    It handles configuration loading, lane management, and runtime mode settings.
    The class is marked as final to prevent inheritance.
    """

    __name: Optional[str] = None
    __test_mode: Optional[bool] = None
    __dev_mode = False
    __started = False
    __exit_on_finish: Optional[bool] = None

    def __init__(self):
        raise Exception("This is not instantiable!")

    @classmethod
    def name(cls):
        """
        Returns the name of the current instance.

        Returns:
            Optional[str]: The name of the instance if set, None otherwise.
        """
        return cls.__name

    @classmethod
    def is_dev(cls):
        """
        Checks if the framework is running in development mode.

        Returns:
            bool: True if in development mode, False otherwise.
        """
        return cls.__dev_mode

    @classmethod
    def is_test(cls):
        """
        Checks if the framework is running in test mode.

        Returns:
            Optional[bool]: True if in test mode, False if not, None if not set.
        """
        return cls.__test_mode

    @classmethod
    def initialize(
        cls,
        name: Optional[str] = None,
        dev_mode: bool = False,
        test_mode: Optional[bool] = None,
    ):
        """
        Initializes the framework with the specified settings.

        This method can only be called once. Subsequent calls will be ignored.

        Args:
            name: Optional name for the instance
            dev_mode: Whether to run in development mode
            test_mode: Whether to run in test mode
        """
        if cls.__started:
            return

        cls.__name = name
        cls.__dev_mode = dev_mode
        cls.__test_mode = test_mode

    @classmethod
    def start(
        cls,
        name: Optional[str] = None,
        dev_mode: bool = False,
        test_mode: Optional[bool] = None,
        exit_on_finish: Optional[bool] = None,
    ):
        """
        Starts the framework with the specified settings.

        This method initializes the framework and begins execution of lanes.
        It can only be called once. Subsequent calls will be ignored.

        Args:
            name: Optional name for the instance
            dev_mode: Whether to run in development mode
            test_mode: Whether to run in test mode
            exit_on_finish: Overrides the EXIT_ON_FINISH setting when not None.
                The visualizer passes False so the loop never calls exit().
        """
        cls.initialize(
            name=name,
            dev_mode=dev_mode,
            test_mode=test_mode,
        )

        if cls.__started:
            return

        cls.__name = name
        cls.__dev_mode = dev_mode
        cls.__test_mode = test_mode
        cls.__exit_on_finish = exit_on_finish

        cls.__start()

    @classmethod
    def load_lanes(
        cls,
        settings: Union[Settings, Type[Settings]],
    ):
        """
        Loads all Lane classes from the specified directories.

        This method scans the configured directories for Lane classes and loads them
        into the framework. The directories are specified in the settings object.

        Args:
            settings: The settings object containing the LANE_DIRECTORIES configuration.
        """
        _ = [
            lane
            for lane_directory in settings.value_of("LANE_DIRECTORIES")
            for lane in Lane.load(lane_directory)
        ]

    @staticmethod
    def __has_primary(root, name: str) -> bool:
        """Checks (without instantiating) if a registry has a matching primary lane."""
        return any(
            lane.primary() and lane.condition(name)
            for lane in root.available_lanes()
        )

    @staticmethod
    def __run_lanes(
        name: str,
        print_lanes: bool = True,
        processes: Optional[int] = None,
    ):
        """Runs matching lanes, auto-detecting sync vs async registries.

        Sync lanes run through ``Lane.start``; async lanes are drained inside
        ``asyncio.run`` via ``AsyncLane.start``. Returns the collected results so
        ``LazyMain`` can detect whether any work was done. A queue name may match
        lanes in either registry (or both).
        """
        has_sync = Core.__has_primary(Lane, name)
        has_async = Core.__has_primary(AsyncLane, name)

        if not has_sync and not has_async:
            raise ValueError(f"No lanes found for '{name}'!")

        results = []

        if has_sync:
            results.extend(
                Lane.start(
                    name,
                    print_lanes=print_lanes,
                    processes=processes,
                )
            )

        if has_async:

            async def _drain():
                collected = []

                async for result in AsyncLane.start(
                    name,
                    print_lanes=print_lanes,
                    processes=processes,
                ):
                    collected.append(result)

                return collected

            results.extend(asyncio.run(_drain()))

        return results

    @classmethod
    def __start(cls):
        """
        Internal method that handles the actual framework startup process.

        This method:
        1. Configures logging
        2. Loads settings
        3. Loads lanes
        4. Loads all properties
        5. Validates required environment variables
        6. Sets up the main execution loop
        7. Handles cleanup of database connections

        Raises:
            MissingEnvError: If required environment variables are not set
        """
        if not C.IN_DEVELOPMENT and not C.TESTING:
            try:
                from loguru import logger

                logger.remove()
                logger.add(sys.stderr, level="INFO")
            except Exception:
                pass

        # lane2lane ships its own toggleable logger (no longer loguru-based);
        # gate its verbosity the same way: debug in dev, info otherwise.
        l2l_logger.set_level("DEBUG" if C.IN_DEVELOPMENT else "INFO")

        settings = Settings.get()

        cls.__started = True

        cls.load_lanes(settings)

        C.load_all_properties()

        if C.QUEUE_NAME is None:
            raise MissingEnvError("QUEUE_NAME")

        if C.IN_DEVELOPMENT:
            print(style.yellow("🛠️ Running in development mode."))

        else:
            print(style.green("🚀 Running in release mode."))

        if C.TESTING:
            print(style.blue("🧪 Running in testing mode."))

            if not C.IN_DEVELOPMENT:
                print(
                    style.red(
                        "🚨 You are testing in release mode! "
                        "Did you do this intentionally?"
                    )
                )

        print()

        settings.before_start()

        exit_on_finish = (
            cls.__exit_on_finish
            if cls.__exit_on_finish is not None
            else settings.value_of("EXIT_ON_FINISH")
        )

        main = LazyMain(
            main=cls.__run_lanes,
            run_once=settings.value_of("SINGLE_RUN"),
            sleep_min=lambda: settings.value_of("SLEEP_MIN"),
            sleep_max=lambda: settings.value_of("SLEEP_MAX"),
            exit_on_finish=exit_on_finish,
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

        try:
            from .constants import pg

            pg.clear_all()

        except Exception:
            pass
