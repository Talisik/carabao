from dataclasses import dataclass
from importlib import import_module
from typing import Any, Callable, final

from fun_things import lazy

from .cfg.cfg import CFG


@dataclass(frozen=True)
class Field:
    default: Any = None
    cast: Callable[[Any], Any] = str
    required: bool = False


class Form:
    @final
    def __init__(self):
        raise Exception("This is not instantiable!")

    @classmethod
    def get_annotations(cls):
        annotations = {}
        defaults = {}

        for base in reversed(cls.__mro__):
            if hasattr(base, "__annotations__"):
                annotations.update(base.__annotations__)

                for key, value in base.__dict__.items():
                    if key in base.__annotations__:
                        defaults[key] = value

        return annotations, defaults

    @staticmethod
    @lazy.fn
    def get():
        """Get the Form class from the configured module path.

        Returns:
            The Form class that inherits from Form, or the base Form class if no
            custom form is found.
        """
        module_path = CFG().form

        try:
            # Try direct import
            module = import_module(module_path)

        except ModuleNotFoundError:
            # If the module can't be found, return the base class
            return Form

        # Find the class that inherits from Settings
        for attr_name in dir(module):
            attr = getattr(module, attr_name)
            if isinstance(attr, type) and issubclass(attr, Form) and attr is not Form:
                return attr

        return Form


class FOrm1(Form):
    a = Field(
        default="True",
        cast=bool,
    )
