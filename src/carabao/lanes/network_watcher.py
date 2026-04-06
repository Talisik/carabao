import threading
import time
from dataclasses import dataclass
from typing import Callable, Optional

from l2l import Lane

from carabao.constants import C

try:
    from loguru import logger
except ImportError:
    logger = None

try:
    import psutil
except ImportError:
    psutil = None


_KB = 1024
_MB = _KB * 1024
_GB = _MB * 1024


def _fmt_rate(bps: float) -> str:
    if bps >= _GB:
        return f"{bps / _GB:.2f} GB/s"
    if bps >= _MB:
        return f"{bps / _MB:.2f} MB/s"
    if bps >= _KB:
        return f"{bps / _KB:.2f} KB/s"
    return f"{bps:.0f} B/s"


@dataclass
class _BandwidthTracker:
    threshold_bps: float

    def check(self, bps: float) -> bool:
        return bps >= self.threshold_bps


class NetworkWatcher(Lane):
    """
    A passive lane that starts a daemon thread to continuously monitor
    incoming and outgoing network bandwidth.

    Reports per-interval throughput in MB/s and flags sustained high
    usage when the rolling average exceeds the configured threshold.
    """

    debug_logger: Optional[Callable[[str]]] = lambda x: (
        logger.debug(x) if logger is not None else print(x)
    )
    info_logger: Optional[Callable[[str]]] = lambda x: (
        logger.info(x) if logger is not None else print(x)
    )

    @classmethod
    def passive(cls) -> bool:
        return True

    @classmethod
    def primary(cls) -> bool:
        return True

    @classmethod
    def priority_number(cls):
        return -1998

    @classmethod
    def max_run_count(cls) -> int:
        return 1

    @classmethod
    def condition(cls, name: str):
        return C(
            "NETWORK_WATCHER",
            cast=bool,
            default=True,
        )

    def process(self, value):
        if psutil is None and self.info_logger:
            self.info_logger(
                "psutil is required for NetworkWatcher: pip install psutil",
            )
            return

        threading.Thread(
            target=self._watch,
            daemon=True,
        ).start()

    def _watch(self) -> None:
        if psutil is None:
            return

        interval = 10
        threshold_bps = 96 * _KB

        recv_tracker = _BandwidthTracker(threshold_bps=threshold_bps)
        sent_tracker = _BandwidthTracker(threshold_bps=threshold_bps)

        prev = psutil.net_io_counters()
        prev_time = time.monotonic()
        time.sleep(interval)

        while True:
            curr = psutil.net_io_counters()
            now = time.monotonic()
            elapsed = now - prev_time

            if elapsed > 0:
                recv_bps = (curr.bytes_recv - prev.bytes_recv) / elapsed
                sent_bps = (curr.bytes_sent - prev.bytes_sent) / elapsed
            else:
                recv_bps = 0.0
                sent_bps = 0.0

            prev = curr
            prev_time = now

            high_recv = recv_tracker.check(recv_bps)
            high_sent = sent_tracker.check(sent_bps)

            msg = f"Recv: {_fmt_rate(recv_bps)} | Sent: {_fmt_rate(sent_bps)}"

            if high_recv or high_sent:
                if self.info_logger:
                    self.info_logger(msg)
            elif self.debug_logger:
                self.debug_logger(msg)

            time.sleep(interval)
