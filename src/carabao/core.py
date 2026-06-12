import asyncio
import sys
from typing import Optional, Type, Union, final

from l2l import AsyncLane, Lane
from l2l import logger as l2l_logger
from lazy_main import LazyMain

from .constants import C
from .errors import MissingEnvError
from .settings import Settings


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
                The UI passes False so the loop never calls exit().
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
        """Whether the registry has a matching ACTIVE primary lane for ``name``.

        Mirrors ``start``'s own guard: passive lanes (e.g. the always-on
        watchers, whose condition matches every name) don't count — otherwise a
        purely-async queue would falsely look like it has sync lanes, and
        ``Lane.start`` would then raise 'No lanes found'.
        """

        return any(
            lane.primary() and not lane.passive() and lane.condition(name)
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

                try:
                    async for result in AsyncLane.start(
                        name,
                        print_lanes=print_lanes,
                        processes=processes,
                    ):
                        collected.append(result)

                    return collected
                finally:
                    # Async clients must close inside the loop (their close is a
                    # coroutine, and the loop is gone once asyncio.run returns).
                    await Core.__aclose_clients()

            results.extend(asyncio.run(_drain()))

        return results

    @staticmethod
    async def __aclose_clients():
        """Awaitable cleanup of async DB hubs, run inside the event loop."""
        for hub_name in ("amongo", "aredis"):
            try:
                from . import constants

                hub = getattr(constants, hub_name, None)

                if hub is not None:
                    await hub.clear_all()

            except Exception:
                pass

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
        # gate its verbosity: lane lifecycle logs at TRACE, so show TRACE in dev,
        # info otherwise.
        l2l_logger.set_level("TRACE" if C.IN_DEVELOPMENT else "INFO")

        settings = Settings.get()

        cls.__started = True

        cls.load_lanes(settings)

        C.load_all_properties()

        if C.QUEUE_NAME is None:
            raise MissingEnvError("QUEUE_NAME")

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

        for loop in main:
            loop(
                C.QUEUE_NAME,
                print_lanes=False,
                processes=settings.value_of("PROCESSES"),
            )

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
