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
    def passive(cls):
        return True

    @classmethod
    def priority_number(cls):
        """
        Defines the priority of this lane in the execution order.

        Lower numbers have higher priority.

        Returns:
            int: The priority number.
        """
        return -1900

    @classmethod
    def condition(cls, name: str):
        """
        Checks if this lane should be enabled.

        Args:
            name: The queue name to check.

        Returns:
            bool: True if storage is configured, False otherwise.
        """
        return cls.storage is not None

    def __process_mongo(
        self,
        ping_s,
        storage,
    ):
        """
        Process ping results and store them in MongoDB.

        Args:
            ping_s: Ping time in seconds, or None if ping failed.
            storage: MongoDB collection to store the results.

        Returns:
            bool: True if processing was successful, False otherwise.
        """
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
        """
        Process the network health check.

        This method pings various services and stores the results.

        Args:
            value: The value to process, not used in this lane.
        """
        if self.__class__.storage is None:
            return

        self.__class__.catcher.open()
