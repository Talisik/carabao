import dataclasses
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, List

from generic_consumer import PassiveConsumer

from carabao import POD_NAME


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
        exceptions: List[str]
        date_created: datetime

    name: str = POD_NAME
    storage: Any = None
    document_selector: Callable[
        ["LogToDB.Document"],
        dict,
    ] = dataclasses.asdict

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
        document: "LogToDB.Document",
    ):
        try:
            from pymongo.collection import Collection

            if not isinstance(storage, Collection):
                return False

            storage.insert_one(
                self.__class__.document_selector(document),
            )

        except ImportError:
            return False

        except Exception as e:
            print("An error occurred.", e)
            return True

        return False

    def process(self, payloads: list):
        if self.__class__.storage == None:
            return

        document = LogToDB.Document(
            name=self.__class__.name,
            exceptions=[
                str(error)
                for error in self.kwargs.get(
                    "__errors",
                    [],
                )
            ],
            date_created=datetime.now(timezone.utc),
        )

        if self.__process_mongo(
            self.__class__.storage,
            document,
        ):
            return
