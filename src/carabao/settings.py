import os
from importlib import import_module
from typing import Any, Iterable, Optional, final

from fun_things import lazy

from .cfg.public_cfg import PUBLIC_CFG
from .constants import C


class Settings:
    """
    Base class for framework settings and configuration management.

    This class provides a centralized way to manage framework configuration through
    class attributes and environment variables. It supports inheritance for custom
    settings classes and provides methods for accessing and validating settings.

    The class is designed to be inherited by user-defined settings classes that can
    override default values and add custom settings.
    """

    PROCESSES: Optional[int]
    """
    The number of processes to use for the framework.
    
    This setting controls the level of parallelism in lane execution.
    A value of None or 1 will run lanes sequentially.
    """

    LANE_DIRECTORIES: Iterable[str]
    """
    A collection of directory paths where lane modules are located.
    
    These directories will be scanned for lane definitions during framework startup.
    Each directory should contain Python modules that define Lane classes.
    """

    DEPLOY_SAFELY: bool
    """
    Controls production safety settings.
    
    If True, adjusts settings that might be problematic in production environments,
    such as disabling testing-related features and enforcing stricter validation.
    """

    SINGLE_RUN: bool
    """
    Controls the execution mode of the framework.
    
    If True, the framework will execute each lane only once and then exit.
    Otherwise, lanes will continue to run according to their schedules.
    """

    SLEEP_MIN: float
    """
    Minimum sleep time between lane executions.
    
    When no work is available, the framework will sleep for at least this duration
    (in seconds) before checking for new work. This helps prevent excessive CPU usage.
    """

    SLEEP_MAX: float
    """
    Maximum sleep time between lane executions.
    
    The framework will not sleep longer than this duration (in seconds) between checks
    for new work, even if no work is available.
    """

    EXIT_ON_FINISH: bool
    """
    Controls framework termination behavior.
    
    If True, the framework will exit after all lanes have completed execution.
    This is typically used in conjunction with SINGLE_RUN=True.
    """

    EXIT_DELAY: float
    """
    Grace period before framework termination.
    
    When EXIT_ON_FINISH is True, the framework will wait this many seconds
    before exiting, allowing any final operations to complete.
    """

    @classmethod
    def get_all_fields(cls):
        """
        Gets all field names defined in this class and its parent classes.

        This method traverses the class hierarchy to find all defined settings fields,
        including those inherited from parent classes.

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
    def value_of(cls, key: str) -> Any:
        """
        Gets the value of a setting by key name.

        This method implements a priority-based lookup system for settings:
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
    def before_start(cls) -> Any:
        """
        Hook method called before framework startup.

        This method can be overridden by subclasses to perform any necessary
        initialization or validation before the framework starts.

        Returns:
            Any: The result of the initialization process.
        """
        pass

    @classmethod
    def error_handler(cls, e: Exception) -> Any:
        """
        Default error handler for exceptions raised during lane execution.

        This method can be overridden by subclasses to implement custom error
        handling logic. The default implementation does nothing.

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

        This method loads the settings module specified in the carabao.cfg file
        and returns the first class that inherits from Settings. If no such class
        is found, returns the base Settings class.

        The method is decorated with @lazy.fn to ensure the settings are loaded
        only when needed and cached for subsequent calls.

        Returns:
            Type[Settings]: The user-defined Settings class or the base Settings class.
        """
        settings_module = PUBLIC_CFG.settings

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
