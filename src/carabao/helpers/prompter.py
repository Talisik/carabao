from abc import ABC
from typing import Any, Dict, Generic, TypeVar, Union, final

T = TypeVar("T")


class Prompter:
    """
    A class that manages a collection of components that can be queried and executed.

    The Prompter class provides a framework for organizing components with different
    priorities, allowing them to be queried for values and executed in a specific order.
    """

    class Component(Generic[T], ABC):
        """
        An abstract base class for components that can be added to a Prompter.

        Components have a priority number that determines their execution order,
        can store and retrieve values, and can be queried or executed.

        Attributes:
            priority_number (int): Determines the order of execution (higher numbers execute first)
        """

        priority_number: int = 0
        __value: T

        def __init__(
            self,
            initial_value: Union[T, None] = None,
        ):
            """
            Initialize a Component with an optional initial value.

            Args:
                initial_value: The initial value for this component
            """
            self.__initialized = False
            self.__initial_value = initial_value

        @property
        def value(self) -> T:
            """
            Get the current value of the component.

            Returns:
                The initial value if not yet initialized, otherwise the queried value
            """
            if not self.__initialized:
                return self.__initial_value  # type: ignore

            return self.__value

        @property
        def this(self):
            """
            Get the Prompter instance this component is registered with.

            Returns:
                The parent Prompter instance
            """
            return self.__this

        def _query(self) -> T:  # type: ignore
            """
            Abstract method to be implemented by subclasses to query for a value.

            Returns:
                The queried value
            """
            pass

        def _do(self) -> Any:
            """
            Abstract method to be implemented by subclasses to perform an action.

            Returns:
                Any result from the action
            """
            pass

        @final
        def _register(self, prompter: "Prompter"):
            """
            Register this component with a Prompter instance.

            Args:
                prompter: The Prompter instance to register with
            """
            self.__this = prompter

        @final
        def query(self) -> T:
            """
            Query for a value using the component's _query method.

            Returns:
                The queried value
            """
            self.__initialized = True
            self.__value = self._query()

            return self.__value

        @final
        def do(self):
            """
            Execute the component's _do method.
            """
            self._do()

        @final
        def flush(self) -> None:
            """
            Reset the component's initialization state.
            """
            self.__initialized = False

        def __getitem__(
            self,
            name: str,
        ) -> Any:
            """
            Access values from the parent Prompter.

            Args:
                name: The name of the value to retrieve

            Returns:
                The value associated with the given name
            """
            return self.this[name]

    def __init__(self):
        """
        Initialize a new Prompter instance.
        """
        self.__components: Dict[str, Prompter.Component] = {}
        self.__values: dict = {}

    def query(self):
        """
        Query all components in priority order (highest to lowest).
        """
        for component in sorted(
            self.__components.values(),
            key=lambda component: component.priority_number,
            reverse=True,
        ):
            component.query()

    def do(self):
        """
        Execute all components in priority order (highest to lowest).
        """
        for component in sorted(
            self.__components.values(),
            key=lambda component: component.priority_number,
            reverse=True,
        ):
            component.do()

    def add(self, name: str, component: "Prompter.Component"):
        """
        Add a component to this Prompter.

        Args:
            name: The name to associate with the component
            component: The component to add
        """
        self.__components[name] = component
        component._register(self)

    def set(self, name: str, value: Any):
        """
        Set a named value in this Prompter.

        Args:
            name: The name to associate with the value
            value: The value to store
        """
        self.__values[name] = value

    def __getitem__(
        self,
        name: str,
    ) -> Any:  # type: ignore
        """
        Retrieve a component's value or a stored value by name.

        Args:
            name: The name of the component or value to retrieve

        Returns:
            The value associated with the given name
        """
        if name in self.__components:
            return self.__components[name].value

        if name in self.__values:
            return self.__values[name]
