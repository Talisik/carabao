"""Live lane UI for dev mode.

A Textual app that runs the pipeline in a worker thread and shows, in real
time, which lane is active (a tree fed by ``l2l.events``) alongside a
searchable/filterable log pane (fed by ``l2l.logger`` via a sink).

Launched from the dev command when the "📊 UI" switch is on.
"""

import json
import logging
import os
import sys
import threading
from collections import deque
from datetime import datetime
from time import monotonic
from typing import Callable, ClassVar, Dict, List, Optional, Tuple

from l2l import events, logger
from rich.text import Text
from textual import on
from textual.app import App
from textual.binding import Binding, BindingType
from textual.containers import (
    Horizontal,
    ScrollableContainer,
    Vertical,
    VerticalScroll,
)
from textual.geometry import Offset
from textual.screen import ModalScreen
from textual.selection import Selection
from textual.widgets import (
    Button,
    Input,
    Label,
    Static,
    TabbedContent,
    TabPane,
)

from .constants import (
    HOTKEYS_DONE,
    HOTKEYS_PAUSED,
    HOTKEYS_RUNNING,
    JSON_HL,
    LANE_COL_MAX,
    LEVEL_COLOR,
    LEVELS_OFF_BY_DEFAULT,
    MAX_LINES,
    NODE_DONE,
    NODE_ERROR,
    NODE_PASSIVE_DONE,
    NODE_PASSIVE_RUNNING,
    NODE_RUNNING,
    PAGE_SIZE,
    SPINNER,
)
from .utils import (
    TRACEBACK_MARKER,
    fmt_bytes,
    fmt_elapsed,
    fmt_rate,
    format_value,
    highlight_traceback,
    inline_markdown,
    source_from_traceback,
)

try:
    import psutil

except ImportError:
    psutil = None


class _LogWriter:
    """File-like object that forwards complete lines to a log callback.

    Used to capture lane ``print()`` output (which Textual would otherwise
    swallow) and route it into the log pane.
    """

    def __init__(self, forward: Callable[[str, str], None], level: str = "PRINT"):
        self._forward = forward
        self._level = level
        self._buffer = ""

    def write(self, text) -> int:
        text = str(text)
        self._buffer += text

        while "\n" in self._buffer:
            line, self._buffer = self._buffer.split("\n", 1)

            if line:
                self._forward(self._level, line)

        return len(text)

    def flush(self):
        if self._buffer.strip():
            self._forward(self._level, self._buffer)

        self._buffer = ""

    def isatty(self) -> bool:
        return False


def _is_word_char(char: str) -> bool:
    return char.isalnum() or char == "_"


class _LogStatic(Static):
    """Log pane that selects a word on double-click, a line on triple-click.

    Textual's default double-click selects the *entire* widget (one giant
    multi-line blob, since the log is a single Static). This overrides that with
    word/line selection at the click position.
    """

    #: Plain text of the current content (set by the UI on every render), used
    #: to find word/line boundaries — the offsets are logical, so wrapping is OK.
    plain_text: str = ""

    async def _on_click(self, event):
        if event.chain == 2:
            self._select_at(event, word=True)
            event.stop()
        elif event.chain == 3:
            self._select_at(event, word=False)
            event.stop()
        # Single click / drag: leave default range-selection alone.

    def _select_at(self, event, word: bool):
        widget, offset = self.screen.get_widget_and_offset_at(
            event.screen_x, event.screen_y
        )

        if widget is not self or offset is None:
            return

        col, row = offset.x, offset.y
        lines = self.plain_text.splitlines()

        if not (0 <= row < len(lines)):
            return

        line = lines[row]

        if word:
            start, end = self._word_bounds(line, col)

            if start == end:  # not on a word (whitespace/punctuation)
                return
        else:
            start, end = 0, len(line)

        self.screen.selections = {self: Selection(Offset(start, row), Offset(end, row))}

    @staticmethod
    def _word_bounds(line: str, col: int):
        n = len(line)

        if n == 0:
            return 0, 0

        if col >= n:
            col = n - 1

        if col < 0 or not _is_word_char(line[col]):
            return col, col

        start = col

        while start > 0 and _is_word_char(line[start - 1]):
            start -= 1

        end = col + 1

        while end < n and _is_word_char(line[end]):
            end += 1

        return start, end


class _ConfirmQuit(ModalScreen[bool]):
    """Confirmation shown when quitting while the pipeline is still running."""

    CSS = """
    $accent: #3b82f6;
    _ConfirmQuit { align: center middle; }
    #confirm-box {
        width: 48; height: auto; padding: 1 2;
        border: round $accent; background: $surface;
    }
    #confirm-box Label { width: 100%; text-align: center; margin-bottom: 1; }
    #confirm-buttons { height: auto; align: center middle; }
    #confirm-buttons Button { margin: 0 1; border: none; height: 3; content-align: center middle; color: white; text-style: bold; }
    #confirm-yes { background: #f85149; }
    #confirm-yes:hover { background: #ff6b61; }
    #confirm-no { background: $accent; }
    #confirm-no:hover { background: #5a9bf8; }
    """

    BINDINGS: ClassVar[List[BindingType]] = [
        Binding("escape", "cancel", "Cancel"),
        Binding("y", "confirm", "Quit"),
        Binding("n", "cancel", "Cancel"),
    ]

    def compose(self):
        with Vertical(id="confirm-box"):
            yield Label("Pipeline is still running.\nQuit anyway?")

            with Horizontal(id="confirm-buttons"):
                yield Button("\\[y] Quit", variant="error", id="confirm-yes")
                yield Button("\\[n] Cancel", variant="primary", id="confirm-no")

    @on(Button.Pressed, "#confirm-yes")
    def _yes(self):
        self.dismiss(True)

    @on(Button.Pressed, "#confirm-no")
    def _no(self):
        self.dismiss(False)

    def action_confirm(self):
        self.dismiss(True)

    def action_cancel(self):
        self.dismiss(False)


# Display toggles: (label, option, hotkey, UI state attribute).
_DISPLAY_TOGGLES = [
    ("panel", "panel", "p", "_show_panel"),
    ("time", "time", "t", "_show_time"),
    ("lvl", "level", "l", "_show_level"),
    ("src", "src", "s", "_show_source"),
    ("lane", "lane", "n", "_show_lane"),
    ("rich", "rich", "r", "_show_rich"),
    ("scroll", "scroll", "o", "_autoscroll"),
]


class _NodeState:
    __slots__ = ("name", "state", "work", "passive", "error", "children", "order")

    def __init__(self, name: str, passive: bool = False):
        self.name = name
        self.state = "pending"
        self.work: Optional[float] = None
        self.passive = passive
        self.error = False
        #: Ordered child nodes, for rendering the ASCII tree.
        self.children: list = []
        #: Sequence in which this node first ran (None until it does). Roots are
        #: sorted by it so they appear in start order — passive watchers (which
        #: run first) float to the top.
        self.order: Optional[int] = None


class _LogRecord:
    """One captured log line; ``text`` caches its rendered Text (rendered once)."""

    __slots__ = ("ts", "level", "message", "source", "lane", "text", "lane_w")

    def __init__(self, ts: datetime, level: str, message: str, source, lane=None):
        self.ts = ts
        self.level = level
        self.message = message
        self.source = source
        self.lane = lane
        self.text: Optional[Text] = None
        #: Lane-column width the cached `text` was rendered at (-1 = none yet).
        #: The column adapts to the lanes on the current page, so a change here
        #: re-renders the line.
        self.lane_w = -1


class UI(App):
    """Runs ``runner`` in a worker thread and visualizes lane activity."""

    CSS_PATH = "ui.tcss"

    # Don't auto-focus the search box on mount — keep keystrokes free for the
    # f / c / / hotkeys. `/` focuses search when the user wants it.
    AUTO_FOCUS = None

    BINDINGS: ClassVar[List[BindingType]] = [
        Binding("escape", "request_quit", "Quit", priority=True),
        Binding("slash", "focus_search", "Search"),
        Binding("f", "filter_bar('levels')", "Levels"),
        Binding("d", "filter_bar('display')", "Display"),
        Binding("q", "prev_tab", "Prev tab"),
        Binding("e", "next_tab", "Next tab"),
        Binding("c", "continue_lane", "Continue"),
        Binding("enter", "continue_lane", "Continue"),
        Binding("left,left_square_bracket", "page(-1)", "Older logs"),
        Binding("right,right_square_bracket", "page(1)", "Newer logs"),
        Binding("up", "scroll_logs(-1)", "Scroll up"),
        Binding("down", "scroll_logs(1)", "Scroll down"),
        # Number keys toggle the n-th level in the levels strip.
        *(
            Binding(str(digit), f"bar_item({digit})", show=False)
            for digit in range(1, 10)
        ),
        # Letter keys toggle display options — globally, not just in the strip.
        *(
            Binding(hotkey, f"toggle_display('{option}')", show=False)
            for _label, option, hotkey, _attr in _DISPLAY_TOGGLES
        ),
    ]

    def __init__(
        self,
        runner: Callable[[], None],
        title: str = "Lane UI",
        lanes: Optional[list] = None,
        test_mode: bool = False,
        log_file: bool = False,
    ):
        # ansi_color=True renders with the terminal's own ANSI palette + default
        # (transparent) background instead of a painted theme color. Must be
        # passed to the constructor (it drives the render filters there); a class
        # attribute alone has no effect. No theme registration needed.
        super().__init__(ansi_color=True)

        self._runner = runner
        self._run_title = title
        self._test_mode = test_mode
        # Primary lane class(es) to pre-lay the structural tree from.
        self._structure_lanes = lanes or []
        # Tree state. _NodeState entries; structural nodes are pre-built from the
        # lanes field, then matched to running lanes by (parent, name).
        self._run_to_node: Dict[int, _NodeState] = {}
        # Ordered top-level nodes (primaries + passive/runtime roots), walked to
        # render the ASCII tree.
        self._roots: list = []
        # Hands out a start-order rank the first time each node runs.
        self._order_counter = 0
        self._struct_roots: Dict[str, _NodeState] = {}
        self._struct_children: Dict[int, Dict[str, _NodeState]] = {}
        # name -> [entries], for matching lanes whose parent hasn't been claimed
        # yet (e.g. before-lanes fire their event before the primary's own).
        self._struct_by_name: Dict[str, list] = {}
        self._claimed: set = set()
        self._active: set = set()
        # run_ids currently parked at a breakpoint (dev-only).
        self._paused: set = set()
        # Timer freezes while paused: total seconds spent paused, plus the
        # monotonic time the current pause began (None when not paused).
        self._paused_total = 0.0
        self._pause_started: Optional[float] = None
        # Latest value handed downstream (meta, body), for the Value tab.
        self._latest_value: Optional[Tuple[str, str]] = None
        # (timestamp, level, message, source) — source is "module:func:line"
        # or None when the origin is unknown (l2l logger, print()).
        self._records: List[_LogRecord] = []
        # Buffer cap + page size, env-overridable (CARABAO_LOG_MAX_LINES /
        # CARABAO_LOG_PAGE_SIZE), falling back to the constants.
        from carabao.constants import C

        self._max_lines = max(
            1, C("CARABAO_LOG_MAX_LINES", cast=int, default=MAX_LINES)
        )
        self._page_size = max(
            1, C("CARABAO_LOG_PAGE_SIZE", cast=int, default=PAGE_SIZE)
        )
        # Worker pushes log lines here (non-blocking); the flush timer drains
        # them onto _records and re-renders at ~10 fps.
        self._pending: deque = deque()
        # Pagination: only one page renders at a time (cheap selection). When
        # _follow is True the newest page is shown and tracks new logs; paging
        # back pins _page and stops following.
        self._follow = True
        self._page = 0
        # Levels seen (with counts) and which are enabled. The filter checkboxes
        # are built fresh each time the filters modal opens.
        self._enabled_levels: set = set()
        self._level_counts: Dict[str, int] = {}
        self._search: str = ""
        self._frame = 0
        # Display toggles (top-right of the log pane).
        self._show_time = True
        self._show_level = True
        self._show_rich = True
        self._autoscroll = True
        self._show_panel = True
        self._show_source = False  # log call site (module:func:line)
        self._show_lane = False  # which lane emitted the log
        self._finished = False
        # Bottom-bar mode: "normal" hotkeys, or "levels"/"display" filter strips.
        self._bar_mode = "normal"
        # Optional log-to-file streaming (moo.log, moo2.log, …).
        self._log_file_enabled = log_file
        self._log_fp = None
        self._log_lock = threading.Lock()

    # ---- layout ----------------------------------------------------------

    def compose(self):
        # Search stays hidden until `/` is pressed or it has a query
        # (see _update_search_visibility).
        self._search_input = Input(placeholder="Search…", id="search")
        self._search_input.display = False

        yield self._search_input

        with Horizontal(id="body"):
            # Left pane: Lanes tree + Environment, in tabs.
            self._left = TabbedContent(id="left")

            with self._left:
                with TabPane("Lanes", id="tab-lanes"):
                    # A plain-text ASCII tree in a Static (not Textual's Tree
                    # widget) so the whole structure is selectable/copyable, like
                    # the log and env panes.
                    with ScrollableContainer(id="tree"):
                        self._tree_static = Static(id="tree-static")

                        yield self._tree_static

                with TabPane("Env", id="tab-env"):
                    with VerticalScroll(id="env"):
                        self._env_file = Static(id="env-file")

                        yield self._env_file

                        # A Static of aligned Text (not a DataTable) so the
                        # values are selectable/copyable, like the log pane.
                        self._env_table = Static(
                            id="env-table",
                            markup=False,
                        )

                        yield self._env_table

                with TabPane("Value", id="tab-value"):
                    with VerticalScroll(id="value"):
                        self._value_static = Static(
                            id="value-content",
                            markup=False,
                        )

                        yield self._value_static

            with Vertical(id="logs"):
                # One small page renders at a time (cheap text selection). Pager:
                # "← X/Y →" on the left, line count on the right.
                with Horizontal(id="pager"):
                    self._pager_left = Static(id="pager-left")
                    yield self._pager_left
                    yield Static(id="pager-spacer")
                    self._pager_right = Static(id="pager-right")
                    yield self._pager_right

                # A Static inside a scroll: Static emits selection offsets (so
                # text is selectable/copyable, unlike RichLog) and lets us
                # render pretty, highlighted JSON.
                self._log_view = VerticalScroll(
                    id="log",
                )

                with self._log_view:
                    self._log_static = _LogStatic(
                        id="log-content",
                        markup=False,
                    )

                    yield self._log_static

        # Bottom bar: hotkeys (left) … resource stats + mode + timer (right).
        with Horizontal(id="bottombar"):
            self._hotkeys = Static(
                HOTKEYS_RUNNING,
                id="hotkeys",
            )

            yield self._hotkeys
            yield Static(id="bottombar-spacer")

            # System stats (RAM/CPU/network), shown only when psutil is present.
            self._stats = Static(id="stats")

            yield self._stats
            yield Static(self._mode_text(), id="mode")

            self._status_bar = Static(
                "Running…",
                id="status",
            )

            yield self._status_bar

    def _mode_text(self) -> str:
        # The UI only ever runs under `moo dev`, so DEV is implied — only flag
        # the non-default TEST mode.
        return "[b blue]TEST[/]" if self._test_mode else ""

    def _refresh_env(self):
        # Environment tab: the loaded .env file(s) + the env vars actually used.
        try:
            from fun_things.environment import mentioned_keys

            from carabao.constants import C

            files = getattr(C, "loaded_env_files", []) or []
        except Exception:
            return

        header = Text()

        header.append(", ".join(files) if files else "—", style="bold #3b82f6")
        self._env_file.update(header)

        # Two rows per entry: key on top (cyan), value below. No header.
        out = Text()

        for i, key in enumerate(sorted(mentioned_keys)):
            value = mentioned_keys[key]

            if i:
                out.append("\n")

            out.append(f"{key}\n", style="cyan")
            out.append("—" if value is None else str(value))
            out.append("\n")

        self._env_table.update(out)

    def _record_value(self, name, value):
        # Only the latest value flowing through the pipeline (Value tab).
        self._latest_value = format_value(value)

        self._render_value()

    def _render_value(self):
        if self._latest_value is None:
            self._value_static.update(Text(""))

            return

        meta, body = self._latest_value
        out = Text()

        out.append(f"{meta}\n\n", style="bright_black")

        body_text = Text(body)

        if body[:1] in "{[":  # highlight JSON payloads
            JSON_HL.highlight(body_text)

        out.append(body_text)
        self._value_static.update(out)

    def on_mount(self):
        self.title = self._run_title

        # Don't auto-focus the search box — keep keystrokes free for hotkeys
        # (f / c / /). `/` focuses search when the user actually wants it.
        self.set_focus(None)

        # Route logs to the pane only; silence the console stream so it can't
        # corrupt the TUI. Restored on unmount.
        self._null = open(os.devnull, "w")
        self._prev_stream = logger._stream

        logger.set_stream(self._null)
        # Open the log file (moo.log, or moo2.log… if taken) before any
        # logs flow, so nothing is missed.
        if self._log_file_enabled:
            try:
                from ..log_stream import next_log_path

                self._log_fp = open(next_log_path(), "w", encoding="utf-8")
            except Exception:
                self._log_fp = None

        events.subscribe(self._on_event)
        # Dev-only: arm breakpoints so lane.breakpoint() calls pause here.
        events.enable_breakpoints()
        logger.add_sink(self._on_log)
        self._bridge_loguru()
        self._bridge_logging()
        self._build_structure()
        self._refresh_env()
        self.set_interval(1.0, self._refresh_env)
        self.set_interval(0.1, self._tick_spinner)
        self.set_interval(0.1, self._flush_log)

        self._start_monotonic = monotonic()

        self.set_interval(0.1, self._update_status)
        self._init_stats()

        # Daemon thread: the pipeline keeps running off the UI thread, and
        # quitting the app can't hang on a run-forever loop.
        self._worker = threading.Thread(target=self._run_pipeline, daemon=True)

        self._worker.start()

    def _init_stats(self):
        # Live RAM/CPU/network in the bottom bar — only when psutil is present.
        self._proc = None

        if psutil is None:
            return

        try:
            self._proc = psutil.Process(os.getpid())

            self._proc.cpu_percent(None)  # prime (first call returns 0.0)

            self._net_prev = psutil.net_io_counters()
            self._net_prev_t = monotonic()
        except Exception:
            self._proc = None

            return

        self.set_interval(2.0, self._sample_stats)
        self._sample_stats()

    def _sample_stats(self):
        if self._proc is None:
            return

        if psutil is None:
            return

        try:
            rss = self._proc.memory_info().rss
            cpu = self._proc.cpu_percent(None)
            now = monotonic()
            net = psutil.net_io_counters()
            elapsed = now - self._net_prev_t

            if elapsed > 0:
                down = (net.bytes_recv - self._net_prev.bytes_recv) / elapsed
                up = (net.bytes_sent - self._net_prev.bytes_sent) / elapsed
            else:
                down = up = 0.0

            self._net_prev = net
            self._net_prev_t = now
        except Exception:
            return

        text = Text(style="bright_black")

        text.append(f"RAM {fmt_bytes(rss)}")
        text.append("   ")
        text.append(f"CPU {cpu:.0f}%")
        text.append("   ")
        text.append(f"↓ {fmt_rate(down)}  ↑ {fmt_rate(up)}")
        self._stats.update(text)

    def on_unmount(self):
        # Release anything parked at a breakpoint so the worker thread can end.
        events.disable_breakpoints()
        events.unsubscribe(self._on_event)
        logger.remove_sink(self._on_log)

        if getattr(self, "_loguru_removed", False):
            try:
                from loguru import logger as loguru_logger

                loguru_logger.remove()  # remove our sink
                loguru_logger.add(sys.stderr)  # restore a default handler
            except Exception:
                pass

        if getattr(self, "_orig_call_handlers", None) is not None:
            logging.Logger.callHandlers = self._orig_call_handlers  # type: ignore[assignment]
            root = logging.getLogger()

            for handler in getattr(self, "_detached_handlers", []):
                root.addHandler(handler)

        if hasattr(self, "_prev_stream"):
            logger.set_stream(self._prev_stream)

        if hasattr(self, "_null"):
            self._null.close()

        if self._log_fp is not None:
            try:
                self._log_fp.close()
            except Exception:
                pass

    def _bridge_loguru(self):
        """Route loguru output (carabao/user lanes) into the log pane only.

        loguru's default handler writes to the real stderr (captured at import,
        so it bypasses Textual's redirect) and paints over the TUI. Remove all
        loguru handlers for the duration, add our sink, and restore a default
        stderr handler on unmount.
        """

        self._loguru_id = None
        self._loguru_removed = False

        try:
            from loguru import logger as loguru_logger

            def sink(message):
                record = message.record
                text = record["message"]
                exc = record["exception"]

                if exc is not None:
                    import traceback as _tb

                    text = (
                        f"{text}\n"
                        + "".join(
                            _tb.format_exception(exc.type, exc.value, exc.traceback)
                        ).rstrip()
                    )

                source = f"{record['name']}:{record['function']}:{record['line']}"

                self._on_log(record["level"].name, text, source)

            loguru_logger.remove()  # drop the default stderr handler

            self._loguru_removed = True
            # TRACE so the watchers' trace-level logs reach the pane (TRACE < DEBUG).
            self._loguru_id = loguru_logger.add(sink, level="TRACE")
        except Exception:
            pass

    def _bridge_logging(self):
        """Mirror stdlib ``logging`` into the log pane — every logger, including
        ones with ``propagate=False`` (e.g. OpenTelemetry's direct logger).

        Works by tapping ``Logger.callHandlers`` (called once per record, after
        level filtering), so it doesn't depend on root propagation. Logger levels
        are left untouched, so the pane shows exactly what a normal terminal
        would (a record only reaches the tap if it passed its logger's level) —
        no flood from chatty libraries, no need to mute anything. Existing root
        console handlers are detached so libraries can't paint over the TUI.
        """

        root = logging.getLogger()
        self._detached_handlers = [
            h for h in list(root.handlers) if isinstance(h, logging.StreamHandler)
        ]

        for handler in self._detached_handlers:
            root.removeHandler(handler)

        forward = self._on_log
        original = logging.Logger.callHandlers
        self._orig_call_handlers = original

        def tap(logger_self, record):
            original(logger_self, record)

            try:
                message = record.getMessage()

                if record.exc_info:
                    message = f"{message}\n{logging.Formatter().formatException(record.exc_info).rstrip()}"
                elif record.exc_text:
                    message = f"{message}\n{record.exc_text.rstrip()}"

                source = f"{record.name}:{record.funcName}:{record.lineno}"

                forward(record.levelname, message, source)
            except Exception:
                pass

        logging.Logger.callHandlers = tap  # type: ignore[assignment]

    # ---- worker ----------------------------------------------------------

    def _run_pipeline(self):
        error_text = None

        # Capture plain print() output (Textual otherwise swallows stdout) and
        # route it into the log pane. l2l logs use the sink and loguru is
        # bridged, so only stdout needs capturing.
        prev_stdout = sys.stdout
        sys.stdout = _LogWriter(self._on_log)

        try:
            self._runner()
        except SystemExit:
            # LazyMain may call exit() when the loop finishes; in a worker
            # thread that just ends this worker, not the app.
            pass
        except Exception as error:  # surface, don't crash the app
            error_text = str(error)
        finally:
            sys.stdout.flush()

            sys.stdout = prev_stdout

        elapsed = fmt_elapsed(self._elapsed())

        # l2l catches lane errors internally (logs + terminates) rather than
        # re-raising, so check its global error count, not just a bubbled error.
        error_count = 0

        try:
            from l2l import Lane

            error_count = Lane.global_errors_count()

        except Exception:
            pass

        # Compact: just the elapsed time, green if clean, red if any errors.
        failed = error_text is not None or error_count
        final = Text(elapsed, style="bold red" if failed else "bold green")

        self._finished = True

        # The app may already be shutting down; ignore if so.
        try:
            # Nothing is running anymore: stop any spinners left active by
            # generators that were abandoned before fully draining.
            self.call_from_thread(self._finalize_active)
            self.call_from_thread(self._status_bar.update, final)
            self.call_from_thread(self._render_bottom_bar)
        except Exception:
            pass

    def _elapsed(self) -> float:
        # Wall-clock since start, excluding time parked at breakpoints. While
        # paused the clock is pinned to when the pause began.
        end = self._pause_started if self._pause_started is not None else monotonic()

        return end - self._start_monotonic - self._paused_total

    def _update_status(self):
        # Live elapsed timer while running; the final ✓/✕ is set on completion.
        if self._finished:
            return

        # Amber while frozen at a breakpoint, yellow while running.
        style = "bold #fbbf24" if self._pause_started is not None else "bold yellow"

        self._status_bar.update(Text(fmt_elapsed(self._elapsed()), style=style))

    def _finalize_active(self):
        for run_id in list(self._active):
            entry = self._run_to_node.get(run_id)

            if entry is not None:
                if entry.state == "active":
                    entry.state = "done"

                self._render_node(entry)

            self._active.discard(run_id)

    # ---- l2l callbacks (fire on the worker thread) -----------------------

    def _on_event(self, kind: str, payload: dict):
        self.call_from_thread(self._apply_event, kind, payload)

    def _on_log(self, level: str, message: str, source: Optional[str] = None):
        # Runs on the worker thread. loguru/stdlib pass an explicit source; for
        # l2l logger and print() we recover the call site by walking the stack
        # here (the frames are the real caller).
        if source is None:
            source = self._origin_from_stack()

        # For a logged traceback, point src at where the error was *raised*
        # (deepest frame) rather than where it was logged.
        if TRACEBACK_MARKER in message:
            source = source_from_traceback(message) or source

        if self._log_fp is not None:
            self._write_log_file(level, message, source)

        # The lane whose process() is on the stack right now owns this log.
        lane = self._lane_from_stack()

        # Non-blocking hand-off: queue for the UI's flush timer. deque.append is
        # thread-safe, and (unlike call_from_thread) never blocks the worker —
        # so a flood of logs can't serialize the pipeline against the UI thread.
        self._pending.append((datetime.now(), level, message, source, lane))

    def _write_log_file(self, level: str, message: str, source: Optional[str]):
        # Stream a plain-text (ANSI-stripped) line to the log file.
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        clean = Text.from_ansi(message).plain
        line = f"{ts} {level:<7} {source or '-'}  {clean}\n"

        try:
            with self._log_lock:
                if self._log_fp is None:
                    return

                self._log_fp.write(line)
                self._log_fp.flush()

        except Exception:
            pass

    def _lane_from_stack(self) -> Optional[str]:
        """Name of the innermost lane whose process() is on the stack right now.

        The log was emitted from inside that lane's execution (including lazy
        generator iteration, whose frame is live while a downstream lane pulls),
        so its frame's ``self`` is the owning lane.
        """

        frame = sys._getframe()

        while frame is not None:
            obj = frame.f_locals.get("self")

            if obj is not None and hasattr(obj, "_uid") and hasattr(obj, "first_name"):
                try:
                    return obj.first_name()
                except Exception:
                    return None

            frame = frame.f_back

        return None

    def _origin_from_stack(self) -> Optional[str]:
        """First caller frame outside the logging plumbing → 'module:func:line'."""

        skip = {__name__, "l2l.logger"}
        frame = sys._getframe()

        while frame is not None:
            module = frame.f_globals.get("__name__") or ""

            if module not in skip and not module.startswith("textual"):
                return f"{module}:{frame.f_code.co_name}:{frame.f_lineno}"

            frame = frame.f_back

        return None

    # ---- UI-thread handlers ---------------------------------------------

    def _build_structure(self):
        # Pre-lay the full lane tree from the `lanes` field (recursive), so the
        # whole plan shows up front; running lanes then highlight their node.
        for lane_cls in self._structure_lanes:
            try:
                self._add_struct_node(lane_cls, None, self._struct_roots, set())
            except Exception:
                pass

        self._render_tree()

    def _add_struct_node(self, lane_cls, parent_entry, siblings, seen):
        if lane_cls in seen:  # guard against cyclic lane references
            return

        seen = seen | {lane_cls}

        name = lane_cls.first_name()

        try:
            passive = lane_cls.passive()
        except Exception:
            passive = False

        entry = _NodeState(name, passive=passive)

        if parent_entry is None:
            self._roots.append(entry)
        else:
            parent_entry.children.append(entry)

        siblings.setdefault(name, entry)
        self._struct_by_name.setdefault(name, []).append(entry)

        children: Dict[str, _NodeState] = {}
        self._struct_children[id(entry)] = children

        lanes = lane_cls.get_lanes()

        for priority in sorted(lanes):
            ref = lanes[priority]

            if ref is None:
                continue

            try:
                resolved = lane_cls._resolve_lane_reference(ref)
            except Exception:
                resolved = None

            if isinstance(resolved, type):
                self._add_struct_node(resolved, entry, children, seen)
            # Mock/dict (anonymous groups) are matched lazily at runtime instead.

    def _is_passive(self, name: str) -> bool:
        """Whether a runtime lane name belongs to a passive lane (colored blue).

        Used for nodes not in the pre-built structure (passive watchers run on
        every queue, so they aren't part of the selected lane's plan).
        """

        from l2l import AsyncLane, Lane

        for registry in (Lane, AsyncLane):
            try:
                lane = registry.get_lane(name)

                if lane is not None:
                    return lane.passive()
            except Exception:
                pass

        return False

    def _node_for(self, run_id, name, parent_id) -> _NodeState:
        entry = self._run_to_node.get(run_id)

        if entry is not None:
            return entry

        parent = self._run_to_node.get(parent_id) if parent_id else None
        siblings = (
            self._struct_children.get(id(parent)) if parent else self._struct_roots
        )

        match = siblings.get(name) if siblings else None

        # Parent referenced but not yet claimed — e.g. before-lanes (negative
        # priority) emit their event before the primary's own, so the primary's
        # node isn't in _run_to_node yet. Match the pre-built node by name
        # anywhere in the structure instead of orphaning it to a root duplicate.
        if match is None and parent_id and parent is None:
            for cand in self._struct_by_name.get(name, ()):
                if id(cand) not in self._claimed:
                    match = cand
                    break

        if match is not None and id(match) not in self._claimed:
            self._claimed.add(id(match))

            self._run_to_node[run_id] = match

            return match

        # Not in the pre-built structure (goto/Mock/duplicate, or no lane passed)
        # — attach under the matched parent (or as a new root).
        entry = _NodeState(name, passive=self._is_passive(name))
        self._struct_children[id(entry)] = {}

        if parent is not None:
            parent.children.append(entry)
        else:
            self._roots.append(entry)

        if siblings is not None:
            siblings[f"{name}\x00{run_id}"] = entry

        self._run_to_node[run_id] = entry

        self._render_node(entry)

        return entry

    def _apply_event(self, kind: str, payload: dict):
        run_id = payload.get("run_id")

        if run_id is None:
            return

        if kind == "lane_active":
            entry = self._node_for(
                run_id, payload.get("name"), payload.get("parent_id")
            )
            entry.state = "active"

            self._stamp_order(entry)
            self._active.add(run_id)
            self._render_node(entry)

        elif kind == "lane_idle":
            entry = self._run_to_node.get(run_id)

            if entry is not None:
                # Stay active (spinner steady) between per-item calls; just
                # update the work time. lane_done is what finalizes the node.
                entry.work = payload.get("work")

                self._render_node(entry)
            if "value" in payload:
                self._record_value(payload.get("name"), payload["value"])

        elif kind == "lane_done":
            entry = self._run_to_node.get(run_id)

            if entry is not None:
                # The generator drained — finalize (the node stays active across
                # per-item idles, so done is set here regardless).
                entry.state = "terminated" if payload.get("terminated") else "done"

                if payload.get("errors"):
                    entry.error = True

                if payload.get("work") is not None:
                    entry.work = payload.get("work")

                self._active.discard(run_id)
                self._render_node(entry)

        elif kind == "lane_terminated":
            entry = self._run_to_node.get(run_id)

            if entry is not None:
                entry.state = "terminated"

                self._active.discard(run_id)
                self._render_node(entry)

        elif kind == "lane_breakpoint":
            entry = self._node_for(
                run_id, payload.get("name"), payload.get("parent_id")
            )
            entry.state = "paused"

            self._stamp_order(entry)
            self._active.discard(run_id)

            # Freeze the timer at the first concurrent pause.
            if not self._paused:
                self._pause_started = monotonic()

            self._paused.add(run_id)
            self._render_node(entry)
            self._sync_hotkeys()

        elif kind == "lane_resumed":
            self._paused.discard(run_id)

            # Resume the timer once nothing is paused anymore.
            if not self._paused and self._pause_started is not None:
                self._paused_total += monotonic() - self._pause_started
                self._pause_started = None

            entry = self._run_to_node.get(run_id)

            if entry is not None:
                # Back to running — process() continues after the breakpoint.
                entry.state = "active"

                self._active.add(run_id)
                self._render_node(entry)

            self._sync_hotkeys()

    def _node_markup(self, entry: _NodeState) -> str:
        """Console markup for a single node's label (name + state + timing)."""

        name = entry.name
        secs = f" [bright_black]{entry.work:.2f}s[/]" if entry.work is not None else ""

        # Color by state: dim pending -> running -> done. Passive lanes
        # (always-on watchers) use blues; active lanes use greens; anything
        # that errored or was terminated turns bright red.
        if entry.state == "active":
            frame = SPINNER[self._frame % len(SPINNER)]
            # Show the work time (if known) and the spinner together, so a lane
            # that flips active/idle per item doesn't blink between the two.
            color = NODE_PASSIVE_RUNNING if entry.passive else NODE_RUNNING
            return f"[{color}]{name}[/]{secs} [{color}]{frame}[/]"
        elif entry.state == "paused":
            return f"[{NODE_RUNNING}]{name}[/] [#fbbf24]⏸[/]"
        elif entry.state == "terminated" or entry.error:
            # Bright red, no marker — the color alone signals the failure.
            return f"[{NODE_ERROR}]{name}[/]{secs}"
        elif entry.state == "done":
            color = NODE_PASSIVE_DONE if entry.passive else NODE_DONE
            return f"[{color}]{name}[/]{secs}"

        return f"[bright_black]{name}[/]"  # pending — dim, no leading marker

    def _stamp_order(self, entry: _NodeState):
        """Record the order a node first ran, so roots sort by start order."""

        if entry.order is None:
            self._order_counter += 1
            entry.order = self._order_counter

    def _render_tree(self):
        """Redraw the whole ASCII lane tree into the Static.

        Connectors (├ └ │) are drawn dim; each line ends with the node's
        colored label. Rendering everything at once keeps the text selectable
        and copyable (Textual's Tree widget is not). The Text is no-wrap so long
        lane names are cropped at the pane edge instead of wrapping.
        """

        if not hasattr(self, "_tree_static"):
            return

        lines: list = []

        def walk(entry: _NodeState, prefix: str, is_last: bool):
            connector = "└ " if is_last else "├ "
            lines.append(
                f"[bright_black]{prefix}{connector}[/]" + self._node_markup(entry)
            )

            child_prefix = prefix + ("  " if is_last else "│ ")
            kids = entry.children

            for i, kid in enumerate(kids):
                walk(kid, child_prefix, i == len(kids) - 1)

        # Roots in start order (those that have run first; never-run pre-built
        # roots keep their structural order at the bottom).
        roots = sorted(
            self._roots,
            key=lambda r: r.order if r.order is not None else float("inf"),
        )

        # Top-level primaries render flush-left (no connector); their sub-lanes
        # nest beneath with connectors.
        for root in roots:
            lines.append(self._node_markup(root))

            for i, kid in enumerate(root.children):
                walk(kid, "", i == len(root.children) - 1)

        text = Text.from_markup("\n".join(lines))
        text.no_wrap = True
        text.overflow = "crop"

        self._tree_static.update(text)

    def _render_node(self, entry: Optional[_NodeState] = None):
        # The tree is one Static, so any node change redraws the whole thing.
        self._render_tree()

    def _tick_spinner(self):
        if not self._active:
            return

        self._frame += 1
        self._render_tree()

    def _flush_log(self):
        # Drain everything the worker queued since the last tick, then render
        # once. Keeps the worker non-blocking (it never waits on the UI thread)
        # so a flood of logs doesn't serialize the pipeline.
        if not self._pending:
            return

        added = False

        while self._pending:
            try:
                ts, level, message, source, lane = self._pending.popleft()
            except IndexError:
                break

            first_sighting = level not in self._level_counts
            self._level_counts[level] = self._level_counts.get(level, 0) + 1

            # Enable a level by default the first time it's seen (TRACE is noisy).
            if first_sighting and level not in LEVELS_OFF_BY_DEFAULT:
                self._enabled_levels.add(level)

            self._records.append(_LogRecord(ts, level, message, source, lane))
            added = True

        if len(self._records) > self._max_lines:
            del self._records[: len(self._records) - self._max_lines]

        if added:
            self._render_log()

    def _invalidate_renders(self):
        # Drop cached per-line renders (e.g. a display toggle changed).
        for record in self._records:
            record.text = None

    def _passes_filter(self, level: str, message: str) -> bool:
        if level not in self._enabled_levels:
            return False

        if self._search and self._search.lower() not in message.lower():
            return False

        return True

    def _render_record(self, record: "_LogRecord", lane_w: int = 0) -> Text:
        # Cache: render each line once; reuse until invalidated or the lane
        # column width (adaptive per page) changes.
        if record.text is not None and record.lane_w == lane_w:
            return record.text

        parts: List[Text] = []

        if self._show_time:
            parts.append(
                Text(
                    record.ts.strftime("%Y-%m-%d %H:%M:%S") + " ", style="bright_black"
                )
            )

        if self._show_level:
            color = LEVEL_COLOR.get(record.level, "white")

            parts.append(Text(f"{record.level:<7} ", style=color))

        if self._show_source:
            parts.append(Text(f"{record.source or '—'}  ", style="bright_black"))

        if self._show_lane:
            lane = (record.lane or "—").ljust(lane_w)
            parts.append(Text(f"{lane}  ", style="#3b82f6"))

        body = (
            self._render_body(record.message)
            if self._show_rich
            else Text.from_ansi(record.message)
        )

        # Indent a multi-line body (JSON, traceback) to the message column, so
        # the block lines up under the first line instead of starting at col 0.
        prefix_len = sum(len(part.plain) for part in parts)

        if prefix_len and "\n" in body.plain:
            pad = " " * prefix_len
            lines = body.split("\n")
            body = Text()

            for i, line in enumerate(lines):
                if i:
                    body.append("\n" + pad)

                body.append_text(line)

        parts.append(body)

        record.text = Text.assemble(*parts)
        record.lane_w = lane_w

        return record.text

    def _render_body(self, message: str) -> Text:
        # Color Python tracebacks.
        if TRACEBACK_MARKER in message:
            return highlight_traceback(message)

        # Pretty-print + syntax-highlight JSON payloads; otherwise keep ANSI.
        stripped = message.strip()

        if stripped[:1] in "{[":
            try:
                obj = json.loads(stripped)
            except ValueError:
                pass
            else:
                pretty = Text("\n" + json.dumps(obj, indent=2, ensure_ascii=False))

                JSON_HL.highlight(pretty)

                return pretty

        # Keep ANSI from print() as-is; otherwise apply inline markdown.
        if "\x1b" in message:
            return Text.from_ansi(message)

        return inline_markdown(message)

    def _render_log(self):
        # Filtered records, then slice to the current page (only the page is
        # rendered — keeps selection/scroll cheap regardless of buffer size).
        visible = [
            record
            for record in self._records
            if self._passes_filter(record.level, record.message)
        ]

        total = len(visible)
        size = self._page_size
        pages = max(1, (total + size - 1) // size)

        # End-aligned windows: page 0 = newest (a full, sliding tail of the last
        # `size` lines — no reset-to-1-line jump); higher pages tile backward,
        # only the oldest page is partial.
        if self._follow:
            self._page = 0
        else:
            self._page = max(0, min(self._page, pages - 1))

        end = total - self._page * size
        start = max(0, end - size)
        page_records = visible[start:end]

        # Lane column adapts to the lanes on THIS page (capped), so short-named
        # pages stay tight and only long-named pages widen.
        lane_w = (
            min(
                LANE_COL_MAX,
                max((len(r.lane) for r in page_records if r.lane), default=0),
            )
            if self._show_lane
            else 0
        )

        lines = [self._render_record(record, lane_w) for record in page_records]
        content = Text("\n").join(lines) if lines else Text("")

        # Keep the plain text for word/line selection boundary lookups.
        self._log_static.plain_text = content.plain
        self._log_static.update(content)
        self._render_pager(self._page, pages, total)

        if self._follow and self._autoscroll:
            self._log_view.scroll_end(animate=False)

    def _render_pager(self, page: int, pages: int, total: int):
        # page is the distance back from newest (0 = newest).
        if pages <= 1:
            self._pager_left.update(Text(""))
        else:
            older = page < pages - 1  # ← can go older
            newer = page > 0  # → can go newer

            left = Text()
            left.append("← ", style="#3b82f6" if older else "bright_black")
            left.append(f"{pages - page}/{pages}", style="bold #3b82f6")
            left.append(" →", style="#3b82f6" if newer else "bright_black")

            self._pager_left.update(left)

        self._pager_right.update(Text(f"{total} lines", style="bright_black"))

    def action_page(self, delta: int):
        # delta = -1 (older, ←) / +1 (newer, →). page is distance-from-newest,
        # so older increases it. Reaching page 0 resumes follow (live tail).
        visible = sum(
            1
            for record in self._records
            if self._passes_filter(record.level, record.message)
        )
        pages = max(1, (visible + self._page_size - 1) // self._page_size)
        target = max(0, min(self._page - delta, pages - 1))

        self._page = target
        self._follow = target == 0

        self._render_log()

    def action_scroll_logs(self, delta: int):
        # Scroll the current page up/down a line.
        self._log_view.scroll_relative(y=delta, animate=False)

    def _refilter(self):
        self._render_log()

    # ---- input events ----------------------------------------------------

    def _set_display(self, option: str, value: bool):
        # Apply a display toggle (called by the filters modal).
        if option == "time":
            self._show_time = value
        elif option == "level":
            self._show_level = value
        elif option == "rich":
            self._show_rich = value
        elif option == "scroll":
            self._autoscroll = value
        elif option == "panel":
            self._show_panel = value
            self._left.display = value
        elif option == "src":
            self._show_source = value
        elif option == "lane":
            self._show_lane = value

        # These change how each line renders → drop the per-line cache.
        if option in ("time", "level", "src", "lane", "rich"):
            self._invalidate_renders()

        self._render_log()

    def _set_level(self, level: str, value: bool):
        # Toggle a level filter (called by the filters modal).
        if value:
            self._enabled_levels.add(level)
        else:
            self._enabled_levels.discard(level)

        self._render_log()

    @on(Input.Changed, "#search")
    def _on_search(self, event: Input.Changed):
        self._search = event.value

        self._refilter()
        self._update_search_visibility()

    @on(Input.Submitted, "#search")
    def _on_search_submit(self):
        # Enter in the search box defocuses (doesn't quit the app).
        self.set_focus(None)
        self._update_search_visibility()

    def _update_search_visibility(self):
        # Visible only while focused or holding a query; hidden otherwise.
        focused = self.focused is self._search_input
        self._search_input.display = focused or bool(self._search)

    def _sync_hotkeys(self):
        # Kept for callers; the bottom bar tracks paused/filter state.
        self._render_bottom_bar()

    def _render_bottom_bar(self):
        # The bottom-left area swaps between normal hotkeys and the filter
        # strips (levels / display). Hide stats + mode while filtering for room.
        filtering = self._bar_mode != "normal"
        self._stats.display = not filtering

        try:
            self.query_one("#mode").display = not filtering
        except Exception:
            pass

        if self._bar_mode == "levels":
            self._hotkeys.update(self._levels_bar_text())
        elif self._bar_mode == "display":
            self._hotkeys.update(self._display_bar_text())
        elif self._finished:
            self._hotkeys.update(HOTKEYS_DONE)
        elif self._paused:
            self._hotkeys.update(HOTKEYS_PAUSED)
        else:
            self._hotkeys.update(HOTKEYS_RUNNING)

    def _levels_bar_text(self) -> Text:
        out = Text()

        out.append("esc/f back   ", style="bright_black")

        for index, level in enumerate(sorted(self._level_counts), 1):
            on = level in self._enabled_levels
            key = str(index) if index <= 9 else "·"

            out.append(f"{key} ", style="bold")
            out.append(f"{level}   ", style="#3b82f6" if on else "bright_black")

        return out

    def _display_bar_text(self) -> Text:
        out = Text()

        out.append("esc/d back   ", style="bright_black")

        for label, _option, hotkey, attr in _DISPLAY_TOGGLES:
            on = getattr(self, attr)

            out.append(f"{hotkey} ", style="bold")
            out.append(f"{label}   ", style="#3b82f6" if on else "bright_black")

        return out

    def action_continue_lane(self):
        # Release every lane parked at a breakpoint.
        if self._paused:
            events.resume_all()

    def action_focus_search(self):
        # Reveal then focus.
        self._search_input.display = True
        self._search_input.focus()

    def action_filter_bar(self, mode: str):
        # Toggle a filter strip in the bottom bar (press again to go back).
        self._bar_mode = "normal" if self._bar_mode == mode else mode

        self._render_bottom_bar()

    def action_bar_item(self, n: int):
        # Number key toggles the n-th level in the levels strip.
        if self._bar_mode != "levels":
            return

        levels = sorted(self._level_counts)

        if 1 <= n <= len(levels) and n <= 9:
            level = levels[n - 1]

            self._set_level(level, level not in self._enabled_levels)
            self._render_bottom_bar()

    def action_toggle_display(self, option: str):
        # Display options toggle globally via their letter key (and reflect in
        # the display strip when it's open).
        attr = next(a for _l, o, _h, a in _DISPLAY_TOGGLES if o == option)

        self._set_display(option, not getattr(self, attr))

        if self._bar_mode == "display":
            self._render_bottom_bar()

    def action_prev_tab(self):
        self._cycle_tab(-1)

    def action_next_tab(self):
        self._cycle_tab(1)

    def _cycle_tab(self, step: int):
        tabs = ["tab-lanes", "tab-env", "tab-value"]

        try:
            current = self._left.active
            index = tabs.index(current)
        except (ValueError, Exception):
            index = 0

        self._left.active = tabs[(index + step) % len(tabs)]

    def action_request_quit(self):
        # A modal is open (confirm) — Esc closes it, not the app.
        # (The app's escape binding is priority, so it runs before the modal's.)
        if len(self.screen_stack) > 1:
            self.pop_screen()

            return

        # Esc leaves a filter strip back to the normal hotkey bar.
        if self._bar_mode != "normal":
            self._bar_mode = "normal"

            self._render_bottom_bar()

            return

        # Esc while typing in search just defocuses — doesn't quit.
        if self.focused is self._search_input:
            self.set_focus(None)
            self._update_search_visibility()

            return

        # Quit immediately once the run is done; otherwise confirm first.
        if self._finished:
            self.exit()

            return

        def _on_result(confirmed: Optional[bool]):
            if confirmed:
                self.exit()

        self.push_screen(_ConfirmQuit(), _on_result)
