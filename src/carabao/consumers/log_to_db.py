import dataclasses
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, List, Optional

from generic_consumer import PassiveConsumer

from ..constants import POD_NAME


class LogToDB(PassiveConsumer):
    """
    A passive consumer that logs exceptions to a database.

    This consumer monitors for exceptions and stores them in a MongoDB collection
    when the storage attribute is properly configured. It uses a Document dataclass
    to structure the data before saving it to the database.

    Attributes:
        name (str): The name identifier for the logs, defaults to POD_NAME
        storage (Any): The database storage object, typically a MongoDB collection
        document_selector (Callable): Function to convert Document to dict format
    """

    @dataclass
    class Document:
        name: str
        error: str
        date_created: datetime
        date_expiration: datetime

    name: str = POD_NAME
    """
    The name identifier for the logs.
    """
    storage: Any = None
    """
    The database storage object.
    """
    document_selector: Callable[
        ["LogToDB.Document"],
        dict,
    ] = dataclasses.asdict
    """
    Function to convert Document to dict format.
    """
    log_without_errors: bool = False
    """
    If True, the consumer will log the payloads even if there are no errors.
    """
    expiration_time: timedelta = timedelta(
        hours=1,
    )
    """
    The expiration time for log documents in the database.
    """
    use_stacktrace: bool = True
    """
    If True, the consumer will log the stack trace of the error.
    """

    @classmethod
    def hidden(cls):
        return False

    @classmethod
    def priority_number(cls):
        return -100

    @classmethod
    def condition(cls, queue_name: str):
        return cls.storage != None

    def __process_mongo(
        self,
        storage,
        documents: List["LogToDB.Document"],
    ):
        try:
            from pymongo import InsertOne
            from pymongo.collection import Collection

            if not isinstance(storage, Collection):
                return

            storage.bulk_write(
                [
                    InsertOne(
                        self.__class__.document_selector(document),
                    )
                    for document in documents
                ],
                ordered=False,
            )

        except ImportError:
            return False

        except Exception as e:
            print("An error occurred.", e)
            return True

        return False

    def process(self, payloads: list):
        storage = self.__class__.storage

        if isinstance(storage, Callable):
            storage = storage()

        if storage == None:
            return

        __errors_str = (
            self.kwargs.get("__errors_stacktrace", [])
            if self.__class__.use_stacktrace
            else self.kwargs.get("__errors_str", [])
        )

        if not __errors_str:
            return

        now = datetime.now(timezone.utc)
        documents = [
            LogToDB.Document(
                name=self.__class__.name,
                error=error,
                date_created=now,
                date_expiration=now + self.__class__.expiration_time,
            )
            for error in __errors_str
        ]

        if self.__process_mongo(
            storage,
            documents,
        ):
            return
