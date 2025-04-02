from abc import ABC
from configparser import ConfigParser
from typing import Optional


class BaseCFG(ABC):
    filepath: str
    __parser: Optional[ConfigParser] = None

    @property
    def parser(self):
        if self.__parser == None:
            self.__parser = self.__get_config()

        return self.__parser

    def __get_config(self):
        config = ConfigParser(
            allow_no_value=True,
            comment_prefixes=[],
            strict=False,
        )

        config.read(self.filepath)

        return config

    def get_section(
        self,
        text: str,
    ):
        if text not in self.parser:
            self.parser.add_section(text)

        return self.parser[text]

    def save(self):
        """
        Saves the `.cfg` file.
        """
        with open(self.filepath, "w") as f:
            self.parser.write(f)
