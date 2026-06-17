import asyncio
import sys
from typing import Optional, Type, Union, final

from l2l import AsyncLane, Lane
from l2l import logger as l2l_logger
from lazy_main import LazyMain

from .constants import C
from .errors import MissingEnvError
from .settings import Settings

# Set once we've wrapped logging.Logger.handle, so repeated Core.start()
# calls don't stack the wrapper.
_stdlib_logging_gated = False


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
    __single_run: Optional[bool] = None
    __sleep_min: Optional[float] = None
    __sleep_max: Optional[float] = None
    __processes: Optional[int] = None

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
        single_run: Optional[bool] = None,
        sleep_min: Optional[float] = None,
        sleep_max: Optional[float] = None,
        processes: Optional[int] = None,
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
            single_run: Overrides the SINGLE_RUN setting when not None (the dev
                selector's toggle passes it).
            sleep_min: Overrides the SLEEP_MIN setting when not None.
            sleep_max: Overrides the SLEEP_MAX setting when not None.
            processes: Overrides the PROCESSES setting when not None.
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
        cls.__single_run = single_run
        cls.__sleep_min = sleep_min
        cls.__sleep_max = sleep_max
        cls.__processes = processes

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
    def __has_active_primary(root, name: str) -> bool:
        """Whether the registry has a matching ACTIVE (non-passive) primary.

        Used to decide if the queue name is valid — passive lanes (always-on
        watchers, condition matches every name) don't count, else a typo'd queue
        would silently "match" a watcher.
        """

        return any(
            lane.primary() and not lane.passive() and lane.condition(name)
            for lane in root.available_lanes()
        )

    @staticmethod
    def __has_any_primary(root, name: str) -> bool:
        """Whether the registry has any matching primary — active or passive."""

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

        # A queue is valid if an ACTIVE primary matches in either registry.
        if not (
            Core.__has_active_primary(Lane, name)
            or Core.__has_active_primary(AsyncLane, name)
        ):
            raise ValueError(f"No lanes found for '{name}'!")

        # Run whichever registry has ANY match (active or passive) so passive
        # lanes (e.g. watchers) still run even when the active work is in the
        # other registry. require_active=False — validity already checked above.
        has_sync = Core.__has_any_primary(Lane, name)
        has_async = Core.__has_any_primary(AsyncLane, name)

        results = []

        if has_sync:
            results.extend(
                Lane.start(
                    name,
                    print_lanes=print_lanes,
                    processes=processes,
                    require_active=False,
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
                        require_active=False,
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

            def _level_name_allowed(name: str) -> bool:
                """Apply LOG_INCLUDE (allowlist) then LOG_EXCLUDE (denylist)."""
                name = name.upper()

                include = C.LOG_INCLUDE
                if include and name not in include:
                    return False

                return name not in C.LOG_EXCLUDE

            try:
                from loguru import logger

                logger.remove()
                # Sink at TRACE so LOG_INCLUDE/LOG_EXCLUDE fully control which
                # levels show; the env defaults (exclude DEBUG/TRACE) reproduce
                # the previous INFO floor.
                logger.add(
                    sys.stderr,
                    level="TRACE",
                    filter=lambda record: _level_name_allowed(
                        record["level"].name
                    ),
                )
            except Exception:
                pass

            # Gate ALL stdlib logging (pymongo, elasticsearch, urllib3, the
            # fun-things OTLPHelper, ...) by the same LOG_INCLUDE/LOG_EXCLUDE
            # level rules. Those loggers commonly set their own level/handlers
            # and disable propagation, so a root-logger filter won't reach
            # them; Logger.handle is the one chokepoint every logger calls
            # before dispatching to its handlers, regardless of propagate.
            try:
                global _stdlib_logging_gated

                if not _stdlib_logging_gated:
                    import logging

                    _orig_handle = logging.Logger.handle

                    def _gated_handle(self, record):
                        if not _level_name_allowed(record.levelname):
                            return
                        return _orig_handle(self, record)

                    logging.Logger.handle = _gated_handle  # type: ignore[method-assign]
                    _stdlib_logging_gated = True
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

        run_once = (
            cls.__single_run
            if cls.__single_run is not None
            else settings.value_of("SINGLE_RUN")
        )

        processes = (
            cls.__processes
            if cls.__processes is not None
            else settings.value_of("PROCESSES")
        )

        main = LazyMain(
            main=cls.__run_lanes,
            run_once=run_once,
            sleep_min=lambda: (
                cls.__sleep_min
                if cls.__sleep_min is not None
                else settings.value_of("SLEEP_MIN")
            ),
            sleep_max=lambda: (
                cls.__sleep_max
                if cls.__sleep_max is not None
                else settings.value_of("SLEEP_MAX")
            ),
            exit_on_finish=exit_on_finish,
            exit_delay=settings.value_of("EXIT_DELAY"),
            error_handler=settings.error_handler,
        )

        for loop in main:
            loop(
                C.QUEUE_NAME,
                print_lanes=False,
                processes=processes,
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
