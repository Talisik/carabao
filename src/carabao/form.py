from dataclasses import dataclass
from typing import Any, Callable, Generic, Set, Type, TypeVar, final

from l2l import Lane

T = TypeVar("T")


def _str2bool(value: Any):
    if isinstance(value, bool):
        return value

    if isinstance(value, str):
        return value.lower() in ("true", "1", "yes", "on")

    return bool(value)


@dataclass(frozen=True)
class _Field(Generic[T]):
    default: Any
    cast: Callable[[Any], T]
    raw_cast: Any
    name: str = None  # type: ignore


def _make_field(
    name: str,
    default: Any,
    cast: Callable[[Any], T],
):
    raw_cast = cast

    if cast is bool:
        cast = _str2bool  # type: ignore

    return _Field(
        name=name,
        default=default,
        cast=cast,
        raw_cast=raw_cast,
    )


def Field(
    default: Any = None,
    cast: Callable[[str], T] = str,
    name: str = None,  # type: ignore
) -> T:
    return _make_field(
        name=name,
        default=default,
        cast=cast,
    )  # type: ignore


class Form:
    @final
    def __init__(self):
        raise Exception("This is not instantiable!")

    @staticmethod
    def get_fields(lane: Type[Lane]):
        names: Set[str] = set()

        for form in Form.get_forms_from_lane(lane):
            annotations, defaults = Form.get_annotations(form)

            for name, value in defaults.items():
                if name in names:
                    continue

                names.add(name)

                if isinstance(value, _Field):
                    yield value

                elif name in annotations:
                    yield _make_field(
                        name=name,
                        default=value,
                        cast=annotations[name],
                    )

                else:
                    yield _make_field(
                        name=name,
                        default=value,
                        cast=str,
                    )

            for name, cast in annotations.items():
                if name in names:
                    continue

                names.add(name)

                yield _make_field(
                    name=name,
                    default=None,
                    cast=cast,
                )

    @staticmethod
    def get_forms_from_lane(lane: Type[Lane]):
        """Get all Form classes defined within a Lane class.

        Args:
            lane: The Lane class to search for Form classes.

        Yields:
            Form classes defined within the Lane class.
        """
        for base_class in lane.__mro__:
            for inner_class in base_class.__dict__.values():
                if not isinstance(inner_class, type):
                    continue

                if inner_class.__name__ == "Form" or issubclass(inner_class, Form):
                    yield inner_class

    @staticmethod
    def get_annotations(type: Type):
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
                        value, (classmethod, staticmethod)
                    ):
                        continue

                    # if key in base.__annotations__:
                    defaults[key] = value

        return annotations, defaults
