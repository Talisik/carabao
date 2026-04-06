import gc
import os
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

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


_MB = 1024 * 1024
_WARN = "\u26a0\ufe0f "
_WINDOW = 20


@dataclass
class _RisingLeakTracker:
    threshold: int | float
    history: deque = field(
        default=None,
        repr=False,
    )  # type: ignore[assignment]

    def __post_init__(self) -> None:
        self.history = deque(maxlen=_WINDOW)

    def check(
        self,
        value: int | float,
        rises_pct: float = 0.75,
    ) -> bool:
        self.history.append(value)
        if len(self.history) < _WINDOW:
            return False

        samples = list(self.history)
        growth = samples[-1] - samples[0]
        rises = sum(1 for i in range(1, len(samples)) if samples[i] > samples[i - 1])
        rise_ratio = rises / (len(samples) - 1)

        return growth >= self.threshold and rise_ratio >= rises_pct


class ResourceWatcher(Lane):
    """
    A passive lane that starts a daemon thread to continuously monitor
    system resource usage.

    Reports RAM, swap, CPU, file descriptors, threads, connections,
    I/O rate, and GC pressure — flagging any that exceed their thresholds.
    """

    debug_logger: Optional[Callable[[str], Any]] = lambda x: (
        logger.debug(x) if logger is not None else print(x)
    )
    info_logger: Optional[Callable[[str], Any]] = lambda x: (
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
        return -1999

    @classmethod
    def max_run_count(cls) -> int:
        return 1

    @classmethod
    def condition(cls, name: str):
        return C(
            "RESOURCE_WATCHER",
            cast=bool,
            default=True,
        )

    def process(self, value):
        if psutil is None and ResourceWatcher.info_logger:
            ResourceWatcher.info_logger(
                "psutil is required for ResourceWatcher: pip install psutil",
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
        proc = psutil.Process(os.getpid())
        sys_ram_total = psutil.virtual_memory().total

        cpu_history: deque[float] = deque(maxlen=_WINDOW)
        fd_tracker = _RisingLeakTracker(threshold=50)
        thread_tracker = _RisingLeakTracker(threshold=10)
        conn_tracker = _RisingLeakTracker(threshold=20)

        prev_io_bytes: int | None = None
        prev_io_time: float | None = None

        while True:
            mem = proc.memory_full_info()
            rss_mb = mem.rss / _MB
            swap_mb = getattr(mem, "swap", 0) / _MB
            proc_cpu = proc.cpu_percent(interval=1)
            sys_ram_pct = psutil.virtual_memory().percent
            sys_cpu = psutil.cpu_percent(interval=0)
            num_fds = proc.num_fds()
            num_threads = proc.num_threads()
            num_conns = len(proc.net_connections())
            io = proc.io_counters()
            io_bytes = io.read_bytes + io.write_bytes

            # CPU rolling average
            cpu_history.append(sys_cpu)
            high_cpu = (
                len(cpu_history) >= _WINDOW
                and sum(cpu_history) / len(cpu_history) >= 80.0
            )

            # I/O rate
            now = time.monotonic()
            high_io = False
            if prev_io_bytes is not None and prev_io_time is not None:
                elapsed = now - prev_io_time
                if elapsed > 0:
                    high_io = (io_bytes - prev_io_bytes) / _MB / elapsed >= 100.0
            prev_io_bytes = io_bytes
            prev_io_time = now

            uncollectable = sum(s.get("uncollectable", 0) for s in gc.get_stats())

            checks = {
                "mem": mem.rss / sys_ram_total >= 0.9,
                "swap": swap_mb >= 50.0,
                "cpu": high_cpu,
                "fd": fd_tracker.check(num_fds),
                "thread": thread_tracker.check(num_threads),
                "conn": conn_tracker.check(num_conns),
                "io": high_io,
                "gc": uncollectable >= 100,
            }

            def w(key: str) -> str:
                return _WARN if checks[key] else ""

            parts = [
                f"{w('mem')}RAM: {rss_mb:.1f} MB ({sys_ram_pct}%)",
                f"{w('swap')}Swap: {swap_mb:.1f} MB",
                f"{w('cpu')}CPU: {sys_cpu:.1f}% ({proc_cpu:.1f}%)",
                f"{w('fd')}FDs: {num_fds}",
                f"{w('thread')}Threads: {num_threads}",
                f"{w('conn')}Conns: {num_conns}",
            ]
            if checks["io"]:
                parts.append(f"{_WARN}IO")
            if checks["gc"]:
                parts.append(f"{_WARN}GC")

            msg = " | ".join(parts)

            if any(checks.values()):
                if ResourceWatcher.info_logger:
                    ResourceWatcher.info_logger(msg)
            elif ResourceWatcher.debug_logger:
                ResourceWatcher.debug_logger(msg)

            time.sleep(interval)
