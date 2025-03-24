from datetime import datetime, timezone
from typing import Any

from fun_things import ping
from generic_consumer import PassiveConsumer

from ..helpers.stdout_catcher import StdOutCatcher


class NetworkHealth(PassiveConsumer):
    name: str = "unknown"
    storage: Any = None
    catcher = StdOutCatcher()

    @classmethod
    def hidden(cls):
        return False

    @classmethod
    def priority_number(cls):
        return 200

    @classmethod
    def condition(cls, queue_name: str):
        return cls.storage != None

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
                            "ping_s": ping_s if ping_s != None else -1,
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

    def process(self, payloads: list):
        if self.__class__.storage == None:
            return

        self.__class__.catcher.open()
