from importlib import import_module
from typing import Any, Iterable, final

from fun_things import lazy

from .cfg.cfg import CFG
from .constants import C


class Settings:
    lane_directories: Iterable[str] = [
        "lanes",
    ]
    """
    A collection of directory paths where lane modules are located.
    These directories will be scanned for lane definitions.
    """

    deploy_safely = C.FRAMEWORK_DEPLOY_SAFELY
    """
    If True, adjusts settings that might be problematic in production environments,
    such as disabling testing-related features.
    """

    run_once = C.SINGLE_RUN
    """
    If True, the framework will execute each lane only once and then exit.
    Otherwise, lanes will continue to run according to their schedules.
    """

    sleep_min = C.SLEEP_MIN
    """
    Minimum sleep time (in seconds) between lane executions when no work is available.
    This helps prevent excessive CPU usage during idle periods.
    """

    sleep_max = C.SLEEP_MAX
    """
    Maximum sleep time (in seconds) between lane executions when no work is available.
    The framework will not sleep longer than this duration between checks.
    """

    exit_on_finish = C.EXIT_ON_FINISH
    """
    If True, the framework will exit after all lanes have completed execution.
    This is typically used in conjunction with run_once=True.
    """

    exit_delay = C.EXIT_DELAY
    """
    Time delay (in seconds) before exiting when exit_on_finish is True.
    Provides a grace period for any final operations to complete.
    """

    @classmethod
    def error_handler(cls, e: Exception) -> Any:
        """
        Default error handler for exceptions raised during lane execution.

        Args:
            e: The exception that was raised.

        Returns:
            Any: The result to be used in place of the failed operation.
        """
        pass

    @final
    def __init__(self):
        raise Exception("This is not instantiable!")

    @staticmethod
    @lazy.fn
    def get():
        """
        Returns the user-defined Settings class.

        Loads the settings module specified in the carabao.cfg file
        and returns the first class that inherits from Settings.
        If no such class is found, returns the base Settings class.

        Returns:
            Type[Settings]: The user-defined Settings class or the base Settings class.
        """
        settings_module = CFG().settings
        try:
            # Try direct import
            settings = import_module(settings_module)
        except ModuleNotFoundError:
            # If the module can't be found, return the base class
            return Settings

        # Find the class that inherits from Settings
        for attr_name in dir(settings):
            attr = getattr(settings, attr_name)
            if (
                isinstance(attr, type)
                and issubclass(attr, Settings)
                and attr is not Settings
            ):
                return attr

        return Settings
