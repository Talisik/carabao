import logging
import os
import sys
import traceback

FORMAT = "\033[90m%(asctime)s.%(msecs)03d\033[0m {levelname} \033[90m%(name)s\033[0m.\033[90m%(funcName)s\033[0m.\033[90m%(lineno)d\033[0m {message}"


class LevelFilter(logging.Filter):
    def __init__(self, level):
        self.level = level

    def filter(self, record):
        return record.levelno == self.level


def _new_handler(
    level: int,
    format: str,
    stream=sys.stdout,
):
    handler = logging.StreamHandler(stream)
    handler.setLevel(level)

    formatter = logging.Formatter(
        format,
        datefmt="%H:%M:%S",
    )

    handler.addFilter(LevelFilter(level))
    handler.setFormatter(formatter)

    return handler


class LogMeta(type):
    cache: dict[str, logging.Logger] = {}

    def get(cls) -> logging.Logger:
        summary = traceback.extract_stack(None)[-3]

        if summary.filename.startswith("<") and summary.filename.endswith(">"):
            return  # type: ignore

        name = ".".join(
            os.path.relpath(
                summary.filename,
                os.getcwd(),
            ).split(".")[:-1]
        )

        if name in cls.cache:
            return cls.cache[name]

        logger = logging.getLogger(name)

        logger.setLevel(logging.INFO)

        logger.addHandler(
            _new_handler(
                logging.DEBUG,
                FORMAT.format(
                    levelname="\033[90m%(levelname)s\033[0m",
                    message="\033[90m%(message)s\033[0m",
                ),
            )
        )

        logger.addHandler(
            _new_handler(
                logging.INFO,
                FORMAT.format(
                    levelname="\033[94m%(levelname)s\033[0m",
                    message="%(message)s",
                ),
            )
        )

        logger.addHandler(
            _new_handler(
                logging.WARNING,
                FORMAT.format(
                    levelname="\033[33m%(levelname)s\033[0m",
                    message="\033[33m%(message)s\033[0m",
                ),
            )
        )

        logger.addHandler(
            _new_handler(
                logging.ERROR,
                FORMAT.format(
                    levelname="\033[91m%(levelname)s\033[0m",
                    message="\033[91m%(message)s\033[0m",
                ),
            )
        )

        logger.addHandler(
            _new_handler(
                logging.CRITICAL,
                FORMAT.format(
                    levelname="\033[101;30m%(levelname)s\033[0m",
                    message="\033[31;1m%(message)s\033[0m",
                ),
            )
        )

        cls.cache[name] = logger

        return logger

    def info(cls, *args, **kwargs):
        return cls.get().info(*args, **kwargs)

    def print(cls, *args, **kwargs):
        return cls.get().info(*args, **kwargs)

    def warn(cls, *args, **kwargs):
        return cls.get().warning(*args, **kwargs)

    def warning(cls, *args, **kwargs):
        return cls.get().warning(*args, **kwargs)

    def error(cls, *args, **kwargs):
        return cls.get().error(*args, **kwargs)

    def critical(cls, *args, **kwargs):
        return cls.get().critical(*args, **kwargs)


class log(metaclass=LogMeta):
    def __new__(cls):
        return cls.get()
