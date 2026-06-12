"""Stream captured logs to a file, without needing the dev UI.

Used when ``moo dev`` runs with the UI toggle off but log-to-file on. Captures
the same sources the UI does — the ``l2l`` logger, **loguru**, the stdlib
``logging`` module (including non-propagating loggers), and ``print()`` — and
writes normalized plain-text lines to the file, while leaving the console
output intact (it tees ``print`` and keeps existing log handlers).
"""

import datetime as _dt
import logging
import os
import re
import sys
import threading
import traceback as _tb

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")
_TB_FRAME_RE = re.compile(r'File "(?P<path>[^"]+)", line (?P<line>\d+), in (?P<func>\S+)')
_TRACEBACK_MARKER = "Traceback (most recent call last):"


def next_log_path() -> str:
    """First free ``moo.log`` / ``moo2.log`` / … in the cwd."""
    candidate = "moo.log"
    index = 2

    while os.path.exists(candidate):
        candidate = f"moo{index}.log"
        index += 1

    return candidate


def _module_for_path(path: str):
    target = os.path.abspath(path)

    for module in list(sys.modules.values()):
        file = getattr(module, "__file__", None)

        if file and os.path.abspath(file) == target:
            return module.__name__

    return None


def _source_from_traceback(message: str):
    frames = _TB_FRAME_RE.findall(message)

    if not frames:
        return None

    path, line, func = frames[-1]
    module = _module_for_path(path) or os.path.splitext(os.path.basename(path))[0]

    return f"{module}:{func}:{line}"


class _Tee:
    """stdout proxy: writes through to the real stream and forwards lines."""

    def __init__(self, real, forward):
        self._real = real
        self._forward = forward
        self._buffer = ""

    def write(self, text) -> int:
        text = str(text)

        self._real.write(text)

        self._buffer += text

        while "\n" in self._buffer:
            line, self._buffer = self._buffer.split("\n", 1)

            if line:
                self._forward(line)

        return len(text)

    def flush(self):
        self._real.flush()

    def __getattr__(self, name):
        return getattr(self._real, name)


class FileLogStream:
    """Captures logs and writes them to ``path`` until :meth:`stop`."""

    def __init__(self, path: str):
        self.path = path
        self._fp = None
        self._lock = threading.Lock()
        self._loguru_id = None
        self._orig_call_handlers = None
        self._prev_stdout = None

    def start(self) -> "FileLogStream":
        self._fp = open(self.path, "w", encoding="utf-8")

        from l2l import logger as l2l_logger

        self._l2l_logger = l2l_logger

        l2l_logger.add_sink(self._l2l_sink)
        self._bridge_loguru()
        self._bridge_logging()

        self._prev_stdout = sys.stdout
        sys.stdout = _Tee(self._prev_stdout, self._on_print)

        return self

    def stop(self):
        if self._prev_stdout is not None:
            sys.stdout = self._prev_stdout

        try:
            self._l2l_logger.remove_sink(self._l2l_sink)
        except Exception:
            pass

        if self._orig_call_handlers is not None:
            logging.Logger.callHandlers = self._orig_call_handlers  # type: ignore[assignment]

        if self._loguru_id is not None:
            try:
                from loguru import logger as loguru_logger

                loguru_logger.remove(self._loguru_id)
            except Exception:
                pass

        if self._fp is not None:
            try:
                self._fp.close()
            except Exception:
                pass

    # ---- capture ----------------------------------------------------------

    def _l2l_sink(self, level: str, message: str):
        self._write(level, message, self._origin())

    def _on_print(self, message: str):
        self._write("PRINT", message, self._origin())

    def _bridge_loguru(self):
        try:
            from loguru import logger as loguru_logger

            def sink(message):
                record = message.record
                text = record["message"]
                exc = record["exception"]

                if exc is not None:
                    text = f"{text}\n" + "".join(
                        _tb.format_exception(exc.type, exc.value, exc.traceback)
                    ).rstrip()

                source = f"{record['name']}:{record['function']}:{record['line']}"

                self._write(record["level"].name, text, source)

            # Add a sink (keep the console handler so the terminal still shows).
            self._loguru_id = loguru_logger.add(sink, level="TRACE")
        except Exception:
            pass

    def _bridge_logging(self):
        original = logging.Logger.callHandlers
        self._orig_call_handlers = original
        write = self._write

        def tap(logger_self, record):
            original(logger_self, record)

            try:
                message = record.getMessage()

                if record.exc_info:
                    message = f"{message}\n{logging.Formatter().formatException(record.exc_info).rstrip()}"
                elif record.exc_text:
                    message = f"{message}\n{record.exc_text.rstrip()}"

                source = f"{record.name}:{record.funcName}:{record.lineno}"

                write(record.levelname, message, source)
            except Exception:
                pass

        logging.Logger.callHandlers = tap  # type: ignore[assignment]

    def _origin(self):
        skip = {__name__, "l2l.logger"}
        frame = sys._getframe()

        while frame is not None:
            module = frame.f_globals.get("__name__") or ""

            if module not in skip:
                return f"{module}:{frame.f_code.co_name}:{frame.f_lineno}"

            frame = frame.f_back

        return None

    def _write(self, level: str, message: str, source):
        if self._fp is None:
            return

        if _TRACEBACK_MARKER in message:
            source = _source_from_traceback(message) or source

        ts = _dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        clean = _ANSI_RE.sub("", message)
        line = f"{ts} {level:<7} {source or '-'}  {clean}\n"

        try:
            with self._lock:
                self._fp.write(line)
                self._fp.flush()
        except Exception:
            pass
