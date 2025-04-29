from abc import ABC
from configparser import ConfigParser
from typing import Optional


class BaseCFG(ABC):
    """
    Base class for handling configuration files in .cfg format.

    This class provides functionality to read, modify and save configuration files.
    """

    filepath: str
    __parser: Optional[ConfigParser] = None

    @property
    def parser(self):
        """
        Gets the configuration parser.

        Lazily initializes the parser if it hasn't been initialized yet.

        Returns:
            ConfigParser: The configuration parser instance.
        """
        if self.__parser is None:
            self.__parser = self.__get_config()

        return self.__parser

    def __get_config(self):
        """
        Creates and initializes a new ConfigParser.

        Returns:
            ConfigParser: The initialized configuration parser.
        """
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
        """
        Gets a configuration section, creating it if it doesn't exist.

        Args:
            text: The name of the section.

        Returns:
            SectionProxy: The section proxy object.
        """
        if text not in self.parser:
            self.parser.add_section(text)

        return self.parser[text]

    def write(
        self,
        section: str,
        key: str,
        value: str,
    ):
        """
        Writes a value to a section.
        """
        self.get_section(section)[key] = value

    def save(self):
        """
        Saves the `.cfg` file.
        """
        with open(self.filepath, "w") as f:
            self.parser.write(f)
