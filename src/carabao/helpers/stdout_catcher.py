import sys
from io import StringIO
from typing import Iterable


class StdOutCatcher(StringIO):
    """
    A class for capturing stdout output while still allowing it to be printed.

    This class intercepts writes to stdout, stores them in an internal buffer,
    and also forwards them to the original stdout.
    """

    def write(self, s: str):
        """
        Write a string to the buffer and to the original stdout.

        Args:
            s: The string to write.

        Returns:
            int: The number of characters written.
        """
        result = super().write(s)

        self.__stdout.write(s)

        return result

    def writelines(self, lines: Iterable[str]):
        """
        Write multiple lines to the buffer and to the original stdout.

        Args:
            lines: An iterable of strings to write.

        Returns:
            None
        """
        result = super().writelines(lines)

        self.__stdout.writelines(lines)

        return result

    def open(self):
        """
        Start capturing stdout by replacing sys.stdout with this instance.

        Stores the original stdout for later restoration.
        """
        self.__stdout = sys.stdout
        sys.stdout = self

    def close(self):
        """
        Stop capturing stdout and restore the original stdout.
        """
        sys.stdout = self.__stdout
        del self.__stdout
