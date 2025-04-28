import os
from importlib import import_module
from typing import Any, Iterable, Optional, final

from fun_things import lazy

from .cfg.cfg import CFG
from .constants import C


class Settings:
    PROCESSES: Optional[int]
    """
    The number of processes to use for the framework.
    """

    LANE_DIRECTORIES: Iterable[str]
    """
    A collection of directory paths where lane modules are located.
    These directories will be scanned for lane definitions.
    """

    DEPLOY_SAFELY: bool
    """
    If True, adjusts settings that might be problematic in production environments,
    such as disabling testing-related features.
    """

    SINGLE_RUN: bool
    """
    If True, the framework will execute each lane only once and then exit.
    Otherwise, lanes will continue to run according to their schedules.
    """

    SLEEP_MIN: float
    """
    Minimum sleep time (in seconds) between lane executions when no work is available.
    This helps prevent excessive CPU usage during idle periods.
    """

    SLEEP_MAX: float
    """
    Maximum sleep time (in seconds) between lane executions when no work is available.
    The framework will not sleep longer than this duration between checks.
    """

    EXIT_ON_FINISH: bool
    """
    If True, the framework will exit after all lanes have completed execution.
    This is typically used in conjunction with run_once=True.
    """

    EXIT_DELAY: float
    """
    Time delay (in seconds) before exiting when exit_on_finish is True.
    Provides a grace period for any final operations to complete.
    """

    @classmethod
    def get_all_fields(cls):
        """
        Gets all field names defined in this class and its parent classes.

        Yields:
            str: Names of all fields defined in class annotations.
        """
        yield from (
            key
            for sub_cls in cls.__mro__
            if hasattr(sub_cls, "__annotations__")
            for key in sub_cls.__annotations__.keys()
        )

    @classmethod
    def value_of(cls, key: str):
        """
        Gets the value of a setting by key name.

        This method checks for the setting in the following order:
        1. Environment variables (if also defined in C)
        2. This class's attributes
        3. C module attributes

        Args:
            key (str): The name of the setting to retrieve.

        Returns:
            The value of the requested setting.

        Raises:
            ValueError: If the setting key is not found in any of the checked locations.
        """
        if key in os.environ and hasattr(C, key):
            value = getattr(C, key)

            if callable(value):
                return value()

            return value

        if hasattr(cls, key):
            return getattr(cls, key)

        if hasattr(C, key):
            value = getattr(C, key)

            if callable(value):
                return value()

            return value

        raise ValueError(f"Invalid setting key: {key}")

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
