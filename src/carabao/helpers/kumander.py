import urllib.parse
import urllib.request
from typing import Optional

from carabao.constants import C

try:
    from loguru import logger

    LOGGER_ERROR = logger.error

except Exception:
    LOGGER_ERROR = print


class Kumander:
    @property
    def format(self):
        return C(
            "UPTIME_KUMA_FORMAT",
            default="({APP_TAG}) {POD_NAME} @ {KIND} {ADDRESSES}",
        )

    @property
    def url(self):
        return C(
            "UPTIME_KUMA_URL",
            default=None,
        )

    @property
    def timeout(self):
        return C(
            "UPTIME_KUMA_TIMEOUT",
            cast=float,
            default=3.0,
        )

    @property
    def status(self):
        return C(
            "UPTIME_KUMA_STATUS",
            default="up",
        )

    def ping(
        self,
        url: Optional[str],
        kind: str,
        addresses: str,
    ):
        if not url:
            url = self.url

        parsed_url = urllib.parse.urlparse(url)
        parsed_url = parsed_url._replace(
            query=urllib.parse.urlencode(
                {
                    "status": self.status,
                    "msg": self.format.format(
                        APP_TAG=C(
                            "APP_TAG",
                            default="unknown_tag",
                        ),
                        POD_NAME=C.POD_NAME,
                        KIND=kind,
                        ADDRESSES=addresses,
                    ),
                }
            ),
        )

        urllib.request.urlopen(
            urllib.parse.urlunparse(parsed_url),
            timeout=self.timeout,
        )

        LOGGER_ERROR(f"[{kind}] {addresses} is unreachable!")


kumander = Kumander()
