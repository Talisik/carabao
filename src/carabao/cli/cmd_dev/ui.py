"""Live lane UI for dev mode.

A Textual app that runs the pipeline in a worker thread and shows, in real
time, which lane is active (a tree fed by ``l2l.events``) alongside a
searchable/filterable log pane (fed by ``l2l.logger`` via a sink).

Launched from the dev command when the "📊 UI" switch is on.
"""

import logging
import os
import sys
import threading
from typing import Callable, Dict, List, Optional, Tuple

from l2l import events, logger
from rich.text import Text
from textual import on
from textual.app import App
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Checkbox, Input, Label, RichLog, Static, Tree
from textual.widgets.tree import TreeNode

_LEVELS = ["DEBUG", "INFO", "WARNING", "ERROR"]
_LEVEL_COLOR = {
    "DEBUG": "bright_black",
    "INFO": "cyan",
    "WARNING": "yellow",
    "ERROR": "bold red",
    "PRINT": "white",
}
_SPINNER = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"


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


class _LoggingHandler(logging.Handler):
    """Bridges the stdlib ``logging`` module into the log pane."""

    def __init__(self, forward: Callable[[str, str], None]):
        super().__init__()
        self._forward = forward

    def emit(self, record: logging.LogRecord):
        try:
            self._forward(record.levelname, record.getMessage())
        except Exception:
            pass


class _Checkbox(Checkbox):
    """Checkbox without the ``▐ ▌`` side bars (the white block)."""

    BUTTON_LEFT = ""
    BUTTON_RIGHT = ""


class _SelectableRichLog(RichLog):
    """RichLog that supports mouse text selection + copy (Ctrl+C).

    RichLog is a ScrollView (a container), so Textual disables selection on it
    by default, and its Strip-based render isn't extractable by the base
    ``get_selection``. This re-enables both.
    """

    @property
    def allow_select(self) -> bool:
        return True

    def get_selection(self, selection):
        # Build the full text from the rendered lines and let the Selection
        # extract the highlighted span.
        text = "\n".join(strip.text for strip in self.lines)
        return selection.extract(text), "\n"


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
    #tree { width: 25%; border-right: solid $accent; background: transparent; }
    #logs { width: 1fr; margin-left: 2; background: transparent; }
    #filters { height: auto; padding: 0 1; background: transparent; }
    #filters Checkbox { width: auto; height: 1; border: none; padding: 0; margin-right: 2; background: transparent; }
    #filters Checkbox > .toggle--button { background: transparent; color: $panel; }
    #filters Checkbox.-on > .toggle--button { background: transparent; color: $text-success; }
    /* Thin border puts the text on the inner row → vertically centered. */
    #search { width: 1fr; background: transparent; border: round $accent; height: auto; margin-bottom: 1; }
    RichLog { height: 1fr; background: transparent; }
    Tree { background: transparent; }

    /* Live tree: guides always visible, no hover/cursor line highlight. */
    #tree > .tree--guides,
    #tree > .tree--guides-hover,
    #tree > .tree--guides-selected { color: $accent; text-style: none; }
    #tree > .tree--highlight,
    #tree > .tree--highlight-line { background: transparent; text-style: none; }

    /* Bottom bar: hotkeys (left) + run status (right), like a footer. */
    #bottombar { dock: bottom; height: 1; margin-top: 1; background: transparent; }
    #hotkeys { width: auto; color: $text-muted; }
    #status { width: 1fr; content-align: right middle; color: $text-muted; }
    """

    BINDINGS = [
        Binding("escape", "request_quit", "Quit", priority=True),
        Binding("slash", "focus_search", "Search"),
    ]

    def __init__(self, runner: Callable[[], None], title: str = "Lane UI"):
        # ansi_color=True renders with the terminal's own ANSI palette + default
        # (transparent) background instead of a painted theme color. Must be
        # passed to the constructor (it drives the render filters there); a class
        # attribute alone has no effect. No theme registration needed.
        super().__init__(ansi_color=True)
        self._runner = runner
        self._run_title = title
        self._lane_nodes: Dict[int, _NodeState] = {}
        self._active: set = set()
        self._records: List[Tuple[str, str]] = []
        self._enabled_levels: set = set(_LEVELS)
        self._search: str = ""
        self._frame = 0
        self._finished = False

    # ---- layout ----------------------------------------------------------

    def compose(self):
        with Horizontal(id="body"):
            tree: Tree = Tree("Lanes", id="tree")
            tree.root.expand()
            tree.show_cursor = False
            self._tree = tree
            yield tree

            with Vertical(id="logs"):
                with Horizontal(id="filters"):
                    for level in _LEVELS:
                        yield _Checkbox(level, value=True, name=level)

                yield Input(placeholder="Search logs…", id="search")
                self._richlog = _SelectableRichLog(
                    highlight=True,
                    markup=True,
                    wrap=False,
                    id="log",
                )
                yield self._richlog

        # Bottom bar: hotkeys on the left, run status on the right.
        with Horizontal(id="bottombar"):
            yield Static("[b]esc[/] quit   [b]/[/] search", id="hotkeys")
            self._status_bar = Static("Running…", id="status")
            yield self._status_bar

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
        self.set_interval(0.1, self._tick_spinner)
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

        if getattr(self, "_logging_handler", None) is not None:
            root = logging.getLogger()
            root.removeHandler(self._logging_handler)
            for handler in getattr(self, "_detached_handlers", []):
                root.addHandler(handler)
            root.setLevel(self._prev_root_level)

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
        """Mirror stdlib ``logging`` (user lanes / libraries) into the log pane.

        Also detach existing root StreamHandlers (they write to the real
        stderr/stdout and would paint over the TUI); restored on unmount.
        """
        self._logging_handler = _LoggingHandler(self._on_log)
        self._logging_handler.setLevel(logging.DEBUG)

        root = logging.getLogger()
        self._prev_root_level = root.level
        self._detached_handlers = [
            h for h in list(root.handlers) if isinstance(h, logging.StreamHandler)
        ]
        for handler in self._detached_handlers:
            root.removeHandler(handler)
        # Lower the root level so DEBUG/INFO records reach the handler; restored
        # on unmount.
        root.setLevel(logging.DEBUG)
        root.addHandler(self._logging_handler)

    # ---- worker ----------------------------------------------------------

    def _run_pipeline(self):
        message = "Done"

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
            message = f"Error: {error}"
        finally:
            sys.stdout.flush()
            sys.stdout = prev_stdout

        self._finished = True

        # The app may already be shutting down; ignore if so.
        try:
            # Nothing is running anymore: stop any spinners left active by
            # generators that were abandoned before fully draining.
            self.call_from_thread(self._finalize_active)
            self.call_from_thread(self._status_bar.update, message)
        except Exception:
            pass

    def _finalize_active(self):
        for run_id in list(self._active):
            entry = self._lane_nodes.get(run_id)
            if entry is not None and entry.state == "active":
                entry.state = "done"
            self._active.discard(run_id)
            self._render_node(run_id)

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

    def _ensure_node(
        self,
        run_id: int,
        name: Optional[str],
        parent_id: Optional[int],
    ) -> _NodeState:
        entry = self._lane_nodes.get(run_id)

        if entry is not None:
            if name and entry.name != name:
                entry.name = name
                self._render_node(run_id)

            return entry

        if parent_id is None:
            parent_node = self._tree.root
        else:
            parent_node = self._ensure_node(parent_id, None, None).node

        node = parent_node.add(name or "…", expand=True)
        entry = _NodeState(node, name or "…")
        self._lane_nodes[run_id] = entry

        return entry

    def _apply_event(self, kind: str, payload: dict):
        run_id = payload.get("run_id")

        if run_id is None:
            return

        if kind == "lane_started":
            # Ignored: generator-entry order is lazy/reversed. The tree is built
            # from lane_active instead, which fires in true execution order.
            return

        elif kind == "lane_active":
            # A process() call is running now — exactly one lane at a time, in
            # real execution order. Creating nodes here keeps the tree ordered
            # and drives the spinner truthfully.
            entry = self._ensure_node(
                run_id,
                payload.get("name"),
                payload.get("parent_id"),
            )
            entry.state = "active"
            self._active.add(run_id)
            self._render_node(run_id)

        elif kind == "lane_idle":
            entry = self._ensure_node(run_id, payload.get("name"), None)
            entry.state = "done"
            entry.work = payload.get("work")
            self._active.discard(run_id)
            self._render_node(run_id)

        elif kind == "lane_done":
            entry = self._ensure_node(run_id, payload.get("name"), None)
            if payload.get("terminated"):
                entry.state = "terminated"
            elif entry.state != "active":
                entry.state = "done"
            # 'work' = truthful self-compute time.
            if payload.get("work") is not None:
                entry.work = payload.get("work")
            self._active.discard(run_id)
            self._render_node(run_id)

        elif kind == "lane_terminated":
            entry = self._lane_nodes.get(run_id)
            if entry is not None:
                entry.state = "terminated"
                self._active.discard(run_id)
                self._render_node(run_id)

    def _render_node(self, run_id: int):
        entry = self._lane_nodes.get(run_id)

        if entry is None:
            return

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
            self._render_node(run_id)

    def _add_log(self, level: str, message: str):
        self._records.append((level, message))

        if self._passes_filter(level, message):
            self._write_record(level, message)

    def _passes_filter(self, level: str, message: str) -> bool:
        # Level filter applies only to the known levels; loguru extras
        # (SUCCESS/TRACE/CRITICAL/…) bypass it but still honor the search.
        if level in _LEVELS and level not in self._enabled_levels:
            return False

        if self._search and self._search.lower() not in message.lower():
            return False

        return True

    def _write_record(self, level: str, message: str):
        color = _LEVEL_COLOR.get(level, "white")
        line = Text.assemble(
            (f"{level:<7} ", color),
            Text.from_ansi(message),  # render ANSI from print(), no markup injection
        )
        self._richlog.write(line)

    def _refilter(self):
        self._richlog.clear()

        for level, message in self._records:
            if self._passes_filter(level, message):
                self._write_record(level, message)

    # ---- input events ----------------------------------------------------

    @on(Checkbox.Changed)
    def _on_checkbox(self, event: Checkbox.Changed):
        level = event.checkbox.name

        if level is None:
            return

        if event.value:
            self._enabled_levels.add(level)
        else:
            self._enabled_levels.discard(level)

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
