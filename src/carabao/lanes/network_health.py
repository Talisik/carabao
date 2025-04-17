from datetime import datetime, timezone
from typing import Any

from fun_things import ping
from l2l import Lane

from ..helpers.stdout_catcher import StdOutCatcher


class NetworkHealth(Lane):
    label: str = "unknown"
    storage: Any = None
    catcher = StdOutCatcher()

    @classmethod
    def hidden(cls):
        return True

    @classmethod
    def priority_number(cls):
        return 200

    @classmethod
    def condition(cls, name: str):
        return cls.storage is not None

    def __process_mongo(
        self,
        ping_s,
        storage,
    ):
        try:
            from pymongo.collection import Collection

            if isinstance(storage, Collection):
                storage.update_one(
                    filter={
                        "label": self.__class__.name,
                    },
                    update={
                        "$set": {
                            "label": self.__class__.name,
                            "ping_s": ping_s if ping_s is not None else -1,
                            "date_created": datetime.now(timezone.utc),
                        },
                        "$setOnInsert": {
                            "date_updated": datetime.now(timezone.utc),
                        },
                    },
                    upsert=True,
                )

        except ImportError:
            return False

        except Exception as e:
            print("An error occurred.", e)
            return True

        return True

    def process(self, value):
        if self.__class__.storage is None:
            return

        self.__class__.catcher.open()
