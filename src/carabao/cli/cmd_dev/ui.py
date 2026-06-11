"""Live lane UI for dev mode.

A Textual app that runs the pipeline in a worker thread and shows, in real
time, which lane is active (a tree fed by ``l2l.events``) alongside a
searchable/filterable log pane (fed by ``l2l.logger`` via a sink).

Launched from the dev command when the "📊 UI" switch is on.
"""

import json
import logging
import os
import re
import sys
import threading
from datetime import datetime
from time import monotonic
from typing import Callable, Dict, List, Optional, Tuple

from l2l import events, logger
from rich.console import Group
from rich.highlighter import JSONHighlighter
from rich.table import Table
from rich.text import Text
from textual import on
from textual.app import App
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import (
    Button,
    Checkbox,
    Input,
    Label,
    Static,
    TabbedContent,
    TabPane,
    Tree,
)
from textual.widgets.tree import TreeNode

_JSON_HL = JSONHighlighter()
_MAX_LINES = 2000  # cap rendered log entries to keep rebuilds snappy

# Inline markdown: `code`, **bold**, ~~strike~~, *italic* / _italic_.
_MD_RE = re.compile(
    r"(?P<code>`[^`]+`)"
    r"|(?P<bold>\*\*[^*]+\*\*)"
    r"|(?P<strike>~~[^~]+~~)"
    # underscore italics require word boundaries so path/to_file_name is safe
    r"|(?P<italic>\*[^*\s][^*]*\*|(?<!\w)_[^_\s][^_]*_(?!\w))"
)
_MD_STYLE = {"code": "cyan", "bold": "bold", "strike": "strike", "italic": "italic"}


def _fmt_elapsed(seconds: float) -> str:
    """Compact elapsed time: 6.8s, 8m, 1h."""
    if seconds < 60:
        return f"{seconds:.1f}s"
    if seconds < 3600:
        return f"{int(seconds // 60)}m"
    return f"{int(seconds // 3600)}h"


def _abbrev_count(n: int) -> str:
    """Compact integer: 50, 5K, 1M, 2B (no decimals)."""
    for divisor, suffix in ((1_000_000_000, "B"), (1_000_000, "M"), (1_000, "K")):
        if n >= divisor:
            return f"{n // divisor}{suffix}"
    return str(n)


def _inline_markdown(text: str) -> Text:
    """Render inline markdown (bold/italic/code/strike) as styled Text.

    Block markdown is intentionally not handled — keeps the log selectable and
    avoids mangling plain log lines.
    """
    out = Text()
    pos = 0

    for match in _MD_RE.finditer(text):
        if match.start() > pos:
            out.append(text[pos : match.start()])

        kind = match.lastgroup
        token = match.group()
        pos = match.end()

        if kind is None:  # shouldn't happen (a named group always matches)
            out.append(token)
            continue

        inner = token[1:-1] if kind in ("code", "italic") else token[2:-2]
        out.append(inner, style=_MD_STYLE[kind])

    if pos < len(text):
        out.append(text[pos:])

    return out


# Noisy third-party loggers muted to WARNING while the UI runs, so the root
# logger can be DEBUG (to surface the user's own logs) without flooding the
# pane (e.g. pymongo command monitoring emits DEBUG JSON per operation).
_NOISY_LOGGERS = (
    "pymongo",
    "urllib3",
    "asyncio",
    "elasticsearch",
    "elastic_transport",
    "botocore",
    "s3transfer",
    "kafka",
    "redis",
)

_LEVEL_COLOR = {
    "DEBUG": "bright_black",
    "INFO": "cyan",
    "WARNING": "yellow",
    "ERROR": "bold red",
    "CRITICAL": "bold red",
    "SUCCESS": "green",
    "TRACE": "bright_black",
    "PRINT": "white",
}
_SPINNER = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
_HOTKEYS_RUNNING = "[b]esc[/] quit   [b]/[/] search"
# Highlight "esc quit" once the pipeline is done — the user can safely exit.
_HOTKEYS_DONE = "[b #ff4d4d]esc quit[/]   [b]/[/] search"


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


class _Checkbox(Checkbox):
    """Checkbox without the ``▐ ▌`` side bars (the white block)."""

    BUTTON_LEFT = ""
    BUTTON_RIGHT = ""


class _ConfirmQuit(ModalScreen[bool]):
    """Confirmation shown when quitting while the pipeline is still running."""

    CSS = """
    _ConfirmQuit { align: center middle; }
    #confirm-box {
        width: 48; height: auto; padding: 1 2;
        border: round $warning; background: $surface;
    }
    #confirm-box Label { width: 100%; text-align: center; margin-bottom: 1; }
    #confirm-buttons { height: auto; align: center middle; }
    #confirm-buttons Button { margin: 0 1; }
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
        Binding("y", "confirm", "Quit"),
        Binding("n", "cancel", "Cancel"),
    ]

    def compose(self):
        with Vertical(id="confirm-box"):
            yield Label("Pipeline is still running.\nQuit anyway?")
            with Horizontal(id="confirm-buttons"):
                yield Button("Quit", variant="error", id="confirm-yes")
                yield Button("Cancel", variant="primary", id="confirm-no")

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


class _NodeState:
    __slots__ = ("node", "name", "state", "work")

    def __init__(self, node: TreeNode, name: str):
        self.node = node
        self.name = name
        self.state = "pending"
        self.work: Optional[float] = None


class UI(App):
    """Runs ``runner`` in a worker thread and visualizes lane activity."""

    CSS = """
    $accent: #3b82f6;
    Screen { background: transparent; }
    #body { height: 1fr; background: transparent; }
    #left { width: 25%; border-right: solid $accent; background: transparent; }
    #left Tabs { background: transparent; }
    #left ContentSwitcher, #left TabPane { background: transparent; padding: 0; }
    #tree { background: transparent; }
    #env { background: transparent; }
    #env-content { width: 1fr; height: auto; background: transparent; padding: 0 1; }
    #logs { width: 1fr; margin-left: 2; background: transparent; }
    #filters { height: auto; padding: 0 1; background: transparent; }
    #filters-spacer { width: 1fr; height: 1; background: transparent; }
    #filters Checkbox { width: auto; height: 1; border: none; padding: 0; margin-right: 2; background: transparent; }
    #filters Checkbox > .toggle--button { background: transparent; color: $panel; }
    #filters Checkbox.-on > .toggle--button { background: transparent; color: $text-success; }
    /* Thin border puts the text on the inner row → vertically centered. */
    #search { width: 1fr; background: transparent; border: round $accent; height: auto; margin-bottom: 1; }
    #log { height: 1fr; background: transparent; }
    #log-content { width: 1fr; height: auto; background: transparent; }
    Tree { background: transparent; }

    /* Live tree: guides always visible, no hover/cursor line highlight. */
    #tree > .tree--guides,
    #tree > .tree--guides-hover,
    #tree > .tree--guides-selected { color: $accent; text-style: none; }
    #tree > .tree--cursor,
    #tree > .tree--highlight,
    #tree > .tree--highlight-line { background: transparent; text-style: none; }

    /* Bottom bar: hotkeys (left) … mode + timer (right). */
    #bottombar { dock: bottom; height: 1; margin-top: 1; background: transparent; }
    #hotkeys { width: auto; color: $text-muted; }
    #bottombar-spacer { width: 1fr; }
    #mode { width: auto; margin-right: 2; }
    #status { width: auto; color: $text-muted; }
    """

    BINDINGS = [
        Binding("escape", "request_quit", "Quit", priority=True),
        Binding("slash", "focus_search", "Search"),
    ]

    def __init__(
        self,
        runner: Callable[[], None],
        title: str = "Lane UI",
        lanes: Optional[list] = None,
        dev_mode: bool = True,
        test_mode: bool = False,
    ):
        # ansi_color=True renders with the terminal's own ANSI palette + default
        # (transparent) background instead of a painted theme color. Must be
        # passed to the constructor (it drives the render filters there); a class
        # attribute alone has no effect. No theme registration needed.
        super().__init__(ansi_color=True)
        self._runner = runner
        self._run_title = title
        self._dev_mode = dev_mode
        self._test_mode = test_mode
        # Primary lane class(es) to pre-lay the structural tree from.
        self._structure_lanes = lanes or []
        # Tree state. _NodeState entries; structural nodes are pre-built from the
        # lanes field, then matched to running lanes by (parent, name).
        self._run_to_node: Dict[int, _NodeState] = {}
        self._struct_roots: Dict[str, _NodeState] = {}
        self._struct_children: Dict[int, Dict[str, _NodeState]] = {}
        self._claimed: set = set()
        self._active: set = set()
        self._records: List[Tuple[datetime, str, str]] = []
        # Level filter checkboxes are created on first sighting of each level
        # (so a level with no logs shows no checkbox), labeled with a count.
        self._enabled_levels: set = set()
        self._level_counts: Dict[str, int] = {}
        self._level_checkboxes: Dict[str, _Checkbox] = {}
        self._search: str = ""
        self._frame = 0
        # Display toggles (top-right of the log pane).
        self._show_time = True
        self._show_level = True
        self._show_rich = True
        self._autoscroll = True
        self._show_tree = True
        self._finished = False

    # ---- layout ----------------------------------------------------------

    def compose(self):
        # Filters + search span the full width, above both panes. Level filter
        # checkboxes are added dynamically as levels appear (see _add_log).
        with Horizontal(id="filters"):
            # Spacer pushes the display toggles to the top-right.
            yield Static(id="filters-spacer")
            for label, key in (
                ("tree", "show:tree"),
                ("time", "show:time"),
                ("lvl", "show:level"),
                ("rich", "show:rich"),
                ("scroll", "show:scroll"),
            ):
                yield _Checkbox(label, value=True, name=key)

        yield Input(placeholder="Search…", id="search")

        with Horizontal(id="body"):
            # Left pane: Lanes tree + Environment, in tabs.
            with TabbedContent(id="left"):
                with TabPane("Lanes", id="tab-lanes"):
                    tree: Tree = Tree("Lanes", id="tree")
                    tree.root.expand()
                    tree.root.allow_expand = False
                    self._tree = tree
                    yield tree

                with TabPane("Environment", id="tab-env"):
                    with VerticalScroll(id="env"):
                        self._env_static = Static(id="env-content")
                        yield self._env_static

            with Vertical(id="logs"):
                # A Static inside a scroll: Static emits selection offsets (so
                # text is selectable/copyable, unlike RichLog) and lets us
                # render pretty, highlighted JSON.
                self._log_view = VerticalScroll(id="log")
                with self._log_view:
                    self._log_static = Static(id="log-content", markup=False)
                    yield self._log_static

        # Bottom bar: hotkeys (left) … mode + timer (right).
        with Horizontal(id="bottombar"):
            self._hotkeys = Static(_HOTKEYS_RUNNING, id="hotkeys")
            yield self._hotkeys
            yield Static(id="bottombar-spacer")
            yield Static(self._mode_text(), id="mode")
            self._status_bar = Static("Running…", id="status")
            yield self._status_bar

    def _mode_text(self) -> str:
        parts = []
        if self._dev_mode:
            parts.append("[b yellow]DEV[/]")
        else:
            parts.append("[b green]RELEASE[/]")
        if self._test_mode:
            parts.append("[b blue]TEST[/]")
        return "  ".join(parts)

    def _refresh_env(self):
        # Environment tab: the loaded .env file(s) + the env vars actually used.
        try:
            from fun_things.environment import mentioned_keys

            from carabao.constants import C

            files = getattr(C, "loaded_env_files", []) or []
        except Exception:
            return

        header = Text()
        header.append("env file: ", style="bright_black")
        header.append(", ".join(files) if files else "—", style="bold #3b82f6")

        table = Table(expand=True, show_edge=False, pad_edge=False)
        table.add_column("KEY", style="cyan", no_wrap=True)
        table.add_column("VALUE", overflow="fold")
        for key in sorted(mentioned_keys):
            value = mentioned_keys[key]
            table.add_row(key, "—" if value is None else str(value))

        self._env_static.update(Group(header, Text(), table))

    def on_mount(self):
        self.title = self._run_title
        # Route logs to the pane only; silence the console stream so it can't
        # corrupt the TUI. Restored on unmount.
        self._null = open(os.devnull, "w")
        self._prev_stream = logger._stream
        logger.set_stream(self._null)
        events.subscribe(self._on_event)
        logger.add_sink(self._on_log)
        self._bridge_loguru()
        self._bridge_logging()
        self._build_structure()
        self._refresh_env()
        self.set_interval(1.0, self._refresh_env)
        self.set_interval(0.1, self._tick_spinner)
        self._start_monotonic = monotonic()
        self.set_interval(0.1, self._update_status)
        # Daemon thread: the pipeline keeps running off the UI thread, and
        # quitting the app can't hang on a run-forever loop.
        self._worker = threading.Thread(target=self._run_pipeline, daemon=True)
        self._worker.start()

    def on_unmount(self):
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
            if hasattr(self, "_prev_root_level"):
                root.setLevel(self._prev_root_level)
            for name, level in getattr(self, "_muted_levels", {}).items():
                logging.getLogger(name).setLevel(level)

        if hasattr(self, "_prev_stream"):
            logger.set_stream(self._prev_stream)

        if hasattr(self, "_null"):
            self._null.close()

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
                self._on_log(record["level"].name, record["message"])

            loguru_logger.remove()  # drop the default stderr handler
            self._loguru_removed = True
            self._loguru_id = loguru_logger.add(sink, level="DEBUG")
        except Exception:
            pass

    def _bridge_logging(self):
        """Mirror stdlib ``logging`` into the log pane — every logger, including
        ones with ``propagate=False`` (e.g. OpenTelemetry's direct logger).

        Works by tapping ``Logger.callHandlers`` (called once per record, after
        level filtering), so it doesn't depend on root propagation. Root is set
        to DEBUG and noisy libraries muted; existing root console handlers are
        detached to avoid painting over the TUI.
        """
        root = logging.getLogger()
        self._prev_root_level = root.level
        root.setLevel(logging.DEBUG)
        self._muted_levels = {}
        for name in _NOISY_LOGGERS:
            noisy = logging.getLogger(name)
            self._muted_levels[name] = noisy.level
            noisy.setLevel(logging.WARNING)

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
                forward(record.levelname, record.getMessage())
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

        # Pipeline done — stop the background watchers so they don't keep
        # logging after the run finishes.
        try:
            from carabao.lanes import NetworkWatcher, ResourceWatcher

            ResourceWatcher.stop()
            NetworkWatcher.stop()
        except Exception:
            pass

        elapsed = _fmt_elapsed(monotonic() - self._start_monotonic)
        if error_text is not None:
            final = Text(f"Error: {error_text}", style="bold red")
        else:
            final = Text(f"Done in {elapsed}", style="bold green")

        self._finished = True

        # The app may already be shutting down; ignore if so.
        try:
            # Nothing is running anymore: stop any spinners left active by
            # generators that were abandoned before fully draining.
            self.call_from_thread(self._finalize_active)
            self.call_from_thread(self._status_bar.update, final)
            self.call_from_thread(self._hotkeys.update, _HOTKEYS_DONE)
        except Exception:
            pass

    def _update_status(self):
        # Live elapsed timer while running; the final ✓/✕ is set on completion.
        if self._finished:
            return
        elapsed = _fmt_elapsed(monotonic() - self._start_monotonic)
        self._status_bar.update(Text(elapsed, style="bold yellow"))

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

    def _on_log(self, level: str, message: str):
        # Worker thread → marshal to the UI; ignore if the app is gone.
        try:
            self.call_from_thread(self._add_log, level, message)
        except Exception:
            pass

    # ---- UI-thread handlers ---------------------------------------------

    def _build_structure(self):
        # Pre-lay the full lane tree from the `lanes` field (recursive), so the
        # whole plan shows up front; running lanes then highlight their node.
        for lane_cls in self._structure_lanes:
            try:
                self._add_struct_node(lane_cls, self._tree.root, self._struct_roots, set())
            except Exception:
                pass

    def _add_struct_node(self, lane_cls, parent_node, siblings, seen):
        if lane_cls in seen:  # guard against cyclic lane references
            return
        seen = seen | {lane_cls}

        name = lane_cls.first_name()
        node = parent_node.add(name, expand=True, allow_expand=False)
        entry = _NodeState(node, name)
        siblings.setdefault(name, entry)
        children: Dict[str, _NodeState] = {}
        self._struct_children[id(entry)] = children
        self._render_node(entry)

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
                self._add_struct_node(resolved, node, children, seen)
            # Mock/dict (anonymous groups) are matched lazily at runtime instead.

    def _node_for(self, run_id, name, parent_id) -> _NodeState:
        entry = self._run_to_node.get(run_id)
        if entry is not None:
            return entry

        parent = self._run_to_node.get(parent_id) if parent_id else None
        siblings = self._struct_children.get(id(parent)) if parent else self._struct_roots

        match = siblings.get(name) if siblings else None
        if match is not None and id(match) not in self._claimed:
            self._claimed.add(id(match))
            self._run_to_node[run_id] = match
            return match

        # Not in the pre-built structure (goto/Mock/duplicate, or no lane passed)
        # — attach under the matched parent (or root).
        parent_node = parent.node if parent else self._tree.root
        node = parent_node.add(name, expand=True, allow_expand=False)
        entry = _NodeState(node, name)
        self._struct_children[id(entry)] = {}
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
            self._active.add(run_id)
            self._render_node(entry)

        elif kind == "lane_idle":
            entry = self._run_to_node.get(run_id)
            if entry is not None:
                entry.state = "done"
                entry.work = payload.get("work")
                self._active.discard(run_id)
                self._render_node(entry)

        elif kind == "lane_done":
            entry = self._run_to_node.get(run_id)
            if entry is not None:
                if payload.get("terminated"):
                    entry.state = "terminated"
                elif entry.state != "active":
                    entry.state = "done"
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

    def _render_node(self, entry: _NodeState):
        name = entry.name

        if entry.state == "active":
            frame = _SPINNER[self._frame % len(_SPINNER)]
            label = f"[#3b82f6]{frame}[/] [bold]{name}[/]"
        elif entry.state == "done":
            secs = (
                f" [bright_black]{entry.work:.2f}s[/]" if entry.work is not None else ""
            )
            label = f"[green]✓[/] {name}{secs}"
        elif entry.state == "terminated":
            label = f"[red]✕[/] {name}"
        else:
            label = f"[bright_black]·[/] {name}"

        entry.node.set_label(label)

    def _tick_spinner(self):
        if not self._active:
            return

        self._frame += 1

        for run_id in list(self._active):
            entry = self._run_to_node.get(run_id)
            if entry is not None:
                self._render_node(entry)

    def _add_log(self, level: str, message: str):
        self._level_counts[level] = self._level_counts.get(level, 0) + 1
        self._sync_level_checkbox(level)
        self._records.append((datetime.now(), level, message))

        if len(self._records) > _MAX_LINES:
            del self._records[: len(self._records) - _MAX_LINES]

        self._render_log()

    def _sync_level_checkbox(self, level: str):
        # Create the level's filter checkbox on first sighting, and keep its
        # label's count up to date. Any level (CRITICAL/SUCCESS/TRACE/PRINT/…)
        # becomes toggleable; a level with no logs shows no checkbox.
        label = f"{level} {_abbrev_count(self._level_counts.get(level, 0))}"
        checkbox = self._level_checkboxes.get(level)

        if checkbox is None:
            self._enabled_levels.add(level)
            checkbox = _Checkbox(label, value=True, name=level)
            self._level_checkboxes[level] = checkbox
            try:
                self.query_one("#filters").mount(
                    checkbox,
                    before=self.query_one("#filters-spacer"),
                )
            except Exception:
                pass
        else:
            checkbox.label = label

    def _passes_filter(self, level: str, message: str) -> bool:
        if level not in self._enabled_levels:
            return False

        if self._search and self._search.lower() not in message.lower():
            return False

        return True

    def _render_record(self, ts: datetime, level: str, message: str) -> Text:
        parts: List[Text] = []

        if self._show_time:
            parts.append(
                Text(ts.strftime("%Y-%m-%d %H:%M:%S") + " ", style="bright_black")
            )

        if self._show_level:
            color = _LEVEL_COLOR.get(level, "white")
            parts.append(Text(f"{level:<7} ", style=color))

        body = (
            self._render_body(message) if self._show_rich else Text.from_ansi(message)
        )
        parts.append(body)
        return Text.assemble(*parts)

    def _render_body(self, message: str) -> Text:
        # Pretty-print + syntax-highlight JSON payloads; otherwise keep ANSI.
        stripped = message.strip()

        if stripped[:1] in "{[":
            try:
                obj = json.loads(stripped)
            except ValueError:
                pass
            else:
                pretty = Text("\n" + json.dumps(obj, indent=2, ensure_ascii=False))
                _JSON_HL.highlight(pretty)
                return pretty

        # Keep ANSI from print() as-is; otherwise apply inline markdown.
        if "\x1b" in message:
            return Text.from_ansi(message)

        return _inline_markdown(message)

    def _render_log(self):
        lines = [
            self._render_record(ts, level, message)
            for ts, level, message in self._records
            if self._passes_filter(level, message)
        ]
        self._log_static.update(Text("\n").join(lines) if lines else Text(""))
        if self._autoscroll:
            self._log_view.scroll_end(animate=False)

    def _refilter(self):
        self._render_log()

    # ---- input events ----------------------------------------------------

    @on(Checkbox.Changed)
    def _on_checkbox(self, event: Checkbox.Changed):
        name = event.checkbox.name

        if name is None:
            return

        # Display toggles (top-right) vs level filters.
        if name.startswith("show:"):
            option = name.split(":", 1)[1]
            if option == "time":
                self._show_time = event.value
            elif option == "level":
                self._show_level = event.value
            elif option == "rich":
                self._show_rich = event.value
            elif option == "scroll":
                self._autoscroll = event.value
            elif option == "tree":
                self._show_tree = event.value
                self._tree.display = event.value
            self._render_log()
            return

        if event.value:
            self._enabled_levels.add(name)
        else:
            self._enabled_levels.discard(name)

        self._refilter()

    @on(Input.Changed, "#search")
    def _on_search(self, event: Input.Changed):
        self._search = event.value
        self._refilter()

    def action_focus_search(self):
        self.query_one("#search", Input).focus()

    def action_request_quit(self):
        # Quit immediately once the run is done; otherwise confirm first.
        if self._finished:
            self.exit()
            return

        def _on_result(confirmed: Optional[bool]):
            if confirmed:
                self.exit()

        self.push_screen(_ConfirmQuit(), _on_result)
