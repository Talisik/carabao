import urllib
import urllib.parse
import urllib.request
from abc import ABC, abstractmethod

from l2l import Lane, TerminateKind

from carabao.constants import C

try:
    import pymongo

    from carabao.constants import mongo

except Exception:
    mongo = None
    pymongo = None

try:
    from loguru import logger

    LOGGER_ERROR = logger.error

except Exception:
    LOGGER_ERROR = print


class UptimeKuma(Lane, ABC):
    kind: str

    @classmethod
    def passive(cls) -> bool:
        return True

    @classmethod
    def primary(cls) -> bool:
        return True

    @classmethod
    def priority_number(cls):
        return -3000

    @classmethod
    def max_run_count(cls) -> int:
        return 1

    def ping(
        self,
        format: str,
        url: str,
        addresses: str,
    ):
        parsed_url = urllib.parse.urlparse(url)
        parsed_url = parsed_url._replace(
            query=urllib.parse.urlencode(
                {
                    "status": C(
                        "UPTIME_KUMA_STATUS",
                        default="up",
                    ),
                    "msg": format.format(
                        APP_TAG=C(
                            "APP_TAG",
                            "unknown_tag",
                        ),
                        POD_NAME=C.POD_NAME,
                        KIND=self.kind,
                        ADDRESSES=addresses,
                    ),
                }
            ),
        )

        urllib.request.urlopen(
            urllib.parse.urlunparse(parsed_url),
            timeout=C(
                "UPTIME_KUMA_TIMEOUT",
                cast=float,
                default=3.0,
            ),
        )

        LOGGER_ERROR(f"[{self.kind}] {addresses} is unreachable!")

    @abstractmethod
    def check(
        self,
        format: str,
        url: str,
    ) -> bool: ...

    def process(self, value):
        if not mongo:
            return

        if not pymongo:
            return

        format = C(
            "UPTIME_KUMA_FORMAT",
            default="({APP_TAG}) {POD_NAME} @ {KIND} {ADDRESSES}",
        )

        url = C(
            "UPTIME_KUMA_URL",
            default=None,
        )

        ok = self.check(
            format,
            url,
        )

        if ok:
            return

        self.terminate(TerminateKind.ALL)
