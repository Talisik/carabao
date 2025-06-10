from dataclasses import dataclass
from typing import Any, Callable, Generic, Optional, Set, Type, TypeVar

from l2l import Lane

from .helpers.utils import _str2bool

T = TypeVar("T")


@dataclass(frozen=True)
class _Field(Generic[T]):
    """
    Internal representation of a form field.

    Attributes:
        default: The default value for the field.
        cast: Function to cast input values to the appropriate type.
        raw_cast: The original cast function before any modifications.
        name: The name of the field.
    """

    default: Any
    cast: Callable[[Any], T]
    raw_cast: Any
    name: str
    min_value: int
    max_value: int
    step: int


def _make_field(
    name: str,
    default: Any,
    cast: Callable[[Any], T],
    min_value: Optional[int],
    max_value: Optional[int],
    step: int,
):
    """
    Create a new field instance with the given parameters.

    Args:
        name: The name of the field.
        default: The default value for the field.
        cast: Function to cast input values to the appropriate type.

    Returns:
        A new _Field instance.
    """
    raw_cast = cast

    if cast is bool:
        cast = _str2bool  # type: ignore

    return _Field(
        name=name,
        default=default,
        cast=cast,
        raw_cast=raw_cast,
        min_value=min_value,  # type: ignore
        max_value=max_value,  # type: ignore
        step=step,
    )


def Field(
    default: Any = None,
    cast: Callable[[str], T] = str,
    name: str = None,  # type: ignore
    min_value: int = None,  # type: ignore
    max_value: int = None,  # type: ignore
    step: int = 1,
) -> T:
    """
    Create a field for use in a Form class.

    Args:
        default: The default value for the field.
        cast: Function to cast input values to the appropriate type.
        name: Optional custom name for the field.

    Returns:
        A field instance that can be used in a Form class.
    """
    return _make_field(
        name=name,
        default=default,
        cast=cast,
        min_value=min_value,
        max_value=max_value,
        step=step,
    )  # type: ignore


def _get_fields(lane: Type[Lane]):
    """
    Extract all fields from a lane's Form classes.

    Args:
        lane: The lane class to extract fields from.

    Yields:
        Field instances from the lane's Form classes.
    """
    names: Set[str] = set()

    for form in _get_forms_from_lane(lane):
        annotations, defaults = _get_annotations(form)

        for name, value in defaults.items():
            if name in names:
                continue

            names.add(name)

            if isinstance(value, _Field):
                if value.name is None:
                    yield _make_field(
                        name=name,
                        default=value.default,
                        cast=value.cast,
                        min_value=value.min_value,
                        max_value=value.max_value,
                        step=value.step,
                    )

                else:
                    yield value

            elif name in annotations:
                yield _make_field(
                    name=name,
                    default=value,
                    cast=annotations[name],
                    min_value=None,
                    max_value=None,
                    step=1,
                )

            else:
                yield _make_field(
                    name=name,
                    default=value,
                    cast=str,
                    min_value=None,
                    max_value=None,
                    step=1,
                )

        for name, cast in annotations.items():
            if name in names:
                continue

            names.add(name)

            yield _make_field(
                name=name,
                default=None,
                cast=cast,
                min_value=None,
                max_value=None,
                step=1,
            )


def _get_forms_from_lane(lane: Type[Lane]):
    """
    Get all Form classes defined within the given lane class hierarchy.

    Args:
        lane: The lane class to search for Form classes in.

    Yields:
        Form classes found in the lane's class hierarchy.
    """
    for base_class in lane.__mro__:
        for inner_class in base_class.__dict__.values():
            if not isinstance(inner_class, type):
                continue

            if inner_class.__name__.lower() == "form":
                yield inner_class
                continue


def _get_annotations(type: Type):
    """
    Extract type annotations and default values from a class.

    Args:
        type: The class to extract annotations and defaults from.

    Returns:
        A tuple of (annotations, defaults) dictionaries.
    """
    annotations = {}
    defaults = {}

    for base in type.__mro__:
        if hasattr(base, "__annotations__"):
            annotations.update(base.__annotations__)

            for key, value in base.__dict__.items():
                if key.startswith("__") and key.endswith("__"):
                    continue

                # Skip methods and classmethods
                if callable(value) or isinstance(
                    value,
                    (
                        classmethod,
                        staticmethod,
                    ),
                ):
                    continue

                # if key in base.__annotations__:
                defaults[key] = value

    return annotations, defaults


def _get_form(lane: Type[Lane]):
    """
    Get the first Form class from a lane.

    Args:
        lane: The lane class to get the Form from.

    Returns:
        The first Form class found or None if no Form class exists.
    """
    return next(_get_forms_from_lane(lane), None)


class FormType(type):
    """
    Metaclass for Form to provide dictionary-like access to form fields.
    """

    def __getitem__(cls, name: str):
        return super().__getattribute__(name)

    def __getattr__(cls, name):
        return super().__getattribute__(name)


class Form(metaclass=FormType):
    """
    This class serves as a container for user-defined variables that can be used as
    input parameters for lanes. Users can define their own form fields by subclassing
    this class and adding typed attributes.

    Form fields can be accessed either as attributes (Form.field_name) or using
    dictionary-like syntax (Form['field_name']).
    """


F = Form
