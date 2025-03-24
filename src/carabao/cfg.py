from configparser import ConfigParser
from .constants import (
    CONFIG_NAME,
    CONFIG_LAST_RUN,
    CONFIG_CONSUMERS,
    QUEUE_NAME,
)
from generic_consumer import GenericConsumer


class CFG:
    @property
    def parser(self):
        if self.__parser == None:
            self.__parser = self.__get_config()

        return self.__parser

    @property
    def last_run_queue_name(self):
        section = self.get_section(CONFIG_LAST_RUN)

        return section.get("queue_name")

    @property
    def active_consumers(self):
        section = self.get_section(CONFIG_CONSUMERS)

        active = section.get("active")

        if active == None:
            return

        active = active.splitlines()

        for queue_name in active:
            queue_name = queue_name.strip()

            if not queue_name:
                continue

            yield queue_name

    def __init__(
        self,
        name: str = CONFIG_NAME,
    ):
        self.name = name
        self.__parser = None

    def __get_config(self):
        config = ConfigParser(
            allow_no_value=True,
            comment_prefixes=[],
            strict=False,
        )

        config.read(self.name)

        return config

    def get_section(
        self,
        text: str,
    ):
        if text not in self.parser:
            self.parser.add_section(text)

        return self.parser[text]

    def write_last_run(self):
        section = self.get_section(CONFIG_LAST_RUN)

        section["queue_name"] = QUEUE_NAME

    def write_consumers(self):
        section = self.get_section(CONFIG_CONSUMERS)

        consumers = GenericConsumer.available_consumers()
        active = []
        passive = []

        for consumer in consumers:
            queue_name = consumer.queue_name()

            if consumer.passive():
                passive.append(queue_name)
            else:
                active.append(queue_name)

        section["active"] = "\r\n" + "\r\n".join(active)
        section["passive"] = "\r\n" + "\r\n".join(passive)

    def save(self):
        """
        Saves the `.cfg` file.
        """
        with open(CONFIG_NAME, "w") as f:
            self.parser.write(f)
