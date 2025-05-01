import dataclasses
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, List, Optional

from l2l import Lane

from ..constants import C


class LogToDB(Lane):
    @dataclass
    class Document:
        label: str
        type: str
        error: str
        date_created: datetime
        date_expiration: datetime

    label: Optional[str] = None
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
    If True, the lane will log the payloads even if there are no errors.
    """
    expiration_time: timedelta = timedelta(
        hours=1,
    )
    """
    The expiration time for log documents in the database.
    """
    use_stacktrace: bool = True
    """
    If True, the lane will log the stack trace of the error.
    """

    @classmethod
    def passive(cls) -> bool:
        return True

    @classmethod
    def primary(cls) -> bool:
        return True

    @classmethod
    def priority_number(cls):
        return -1900

    @classmethod
    def condition(cls, name: str):
        return cls.storage is not None

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

    def process(self, value):
        __errors_str = (
            list(self.global_errors_stacktrace())
            if self.__class__.use_stacktrace
            else list(self.global_errors_str())
        )

        if not __errors_str:
            return

        storage = self.__class__.storage

        if isinstance(storage, Callable):
            storage = storage()

        if storage is None:
            return

        now = datetime.now(timezone.utc)
        documents = [
            LogToDB.Document(
                label=self.__class__.label or C.POD_NAME,
                type="error",
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
