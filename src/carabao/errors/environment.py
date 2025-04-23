"""Environment-related errors."""


class MissingEnvError(Exception):
    """
    Raised when a required environment variable is missing.
    """

    def __init__(self, name: str):
        """
        Initialize the error with the name of the missing variable.

        Args:
            name: The name of the missing environment variable.
        """
        self.name = name

        super().__init__(
            f"'{name}' is not in the environment!",
        )
