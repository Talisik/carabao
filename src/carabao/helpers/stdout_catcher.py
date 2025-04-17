import sys
from io import StringIO
from typing import Iterable


class StdOutCatcher(StringIO):
    def write(self, s: str):
        result = super().write(s)

        self.__stdout.write(s)

        return result

    def writelines(self, lines: Iterable[str]):
        result = super().writelines(lines)

        self.__stdout.writelines(lines)

        return result

    def open(self):
        self.__stdout = sys.stdout
        sys.stdout = self

    def close(self):
        sys.stdout = self.__stdout
        del self.__stdout
