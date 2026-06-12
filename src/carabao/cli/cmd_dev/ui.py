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
from datetime import datetime
from time import monotonic
from typing import Callable, Dict, List, Optional, Tuple

from l2l import events, logger
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

from .constants import (
    HOTKEYS_DONE,
    HOTKEYS_PAUSED,
    HOTKEYS_RUNNING,
    JSON_HL,
    LEVEL_COLOR,
    LEVELS_OFF_BY_DEFAULT,
    MAX_LINES,
    SPINNER,
)
from .utils import abbrev_count, fmt_elapsed, format_value, inline_markdown


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
    $accent: #3b82f6;
    _ConfirmQuit { align: center middle; }
    #confirm-box {
        width: 48; height: auto; padding: 1 2;
        border: round $accent; background: $surface;
    }
    #confirm-box Label { width: 100%; text-align: center; margin-bottom: 1; }
    #confirm-buttons { height: auto; align: center middle; }
    #confirm-buttons Button { margin: 0 1; border: none; color: white; text-style: bold; }
    #confirm-yes { background: #f85149; }
    #confirm-yes:hover { background: #ff6b61; }
    #confirm-no { background: $accent; }
    #confirm-no:hover { background: #5a9bf8; }
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

    CSS_PATH = "ui.tcss"

    BINDINGS = [
        Binding("escape", "request_quit", "Quit", priority=True),
        Binding("slash", "focus_search", "Search"),
        Binding("c", "continue_lane", "Continue"),
    ]

    def __init__(
        self,
        runner: Callable[[], None],
        title: str = "Lane UI",
        lanes: Optional[list] = None,
        test_mode: bool = False,
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
        self._struct_roots: Dict[str, _NodeState] = {}
        self._struct_children: Dict[int, Dict[str, _NodeState]] = {}
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
        self._show_panel = True
        self._finished = False

    # ---- layout ----------------------------------------------------------

    def compose(self):
        # Filters + search span the full width, above both panes. Level filter
        # checkboxes are added dynamically as levels appear (see _add_log).
        with Horizontal(id="filters"):
            # Spacer pushes the display toggles to the top-right.
            yield Static(id="filters-spacer")
            for label, key in (
                ("panel", "show:panel"),
                ("time", "show:time"),
                ("lvl", "show:level"),
                ("rich", "show:rich"),
                ("scroll", "show:scroll"),
            ):
                yield _Checkbox(label, value=True, name=key)

        yield Input(placeholder="Search…", id="search")

        with Horizontal(id="body"):
            # Left pane: Lanes tree + Environment, in tabs.
            self._left = TabbedContent(id="left")
            with self._left:
                with TabPane("Lanes", id="tab-lanes"):
                    tree: Tree = Tree("Lanes", id="tree")
                    tree.root.expand()
                    tree.root.allow_expand = False
                    # Hide the root — it's redundant with the tab name; primary
                    # lanes render at the top level instead.
                    tree.show_root = False
                    self._tree = tree
                    yield tree

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
                # A Static inside a scroll: Static emits selection offsets (so
                # text is selectable/copyable, unlike RichLog) and lets us
                # render pretty, highlighted JSON.
                self._log_view = VerticalScroll(
                    id="log",
                )

                with self._log_view:
                    self._log_static = Static(
                        id="log-content",
                        markup=False,
                    )
                    yield self._log_static

        # Bottom bar: hotkeys (left) … mode + timer (right).
        with Horizontal(id="bottombar"):
            self._hotkeys = Static(
                HOTKEYS_RUNNING,
                id="hotkeys",
            )
            yield self._hotkeys
            yield Static(id="bottombar-spacer")
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

        keys = sorted(mentioned_keys)
        table = Text()
        if keys:
            width = max(len(key) for key in keys)
            table.append(f"{'KEY':<{width}}  ", style="bold #3b82f6")
            table.append("VALUE\n", style="bold #3b82f6")
            for key in keys:
                value = mentioned_keys[key]
                table.append(f"{key:<{width}}  ", style="cyan")
                table.append("—" if value is None else str(value))
                table.append("\n")
        self._env_table.update(table)

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
        # Route logs to the pane only; silence the console stream so it can't
        # corrupt the TUI. Restored on unmount.
        self._null = open(os.devnull, "w")
        self._prev_stream = logger._stream
        logger.set_stream(self._null)
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
        self._start_monotonic = monotonic()
        self.set_interval(0.1, self._update_status)
        # Daemon thread: the pipeline keeps running off the UI thread, and
        # quitting the app can't hang on a run-forever loop.
        self._worker = threading.Thread(target=self._run_pipeline, daemon=True)
        self._worker.start()

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

        elapsed = fmt_elapsed(self._elapsed())
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
            self.call_from_thread(self._hotkeys.update, HOTKEYS_DONE)
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
                self._add_struct_node(
                    lane_cls, self._tree.root, self._struct_roots, set()
                )
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
        siblings = (
            self._struct_children.get(id(parent)) if parent else self._struct_roots
        )

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
            if "value" in payload:
                self._record_value(payload.get("name"), payload["value"])

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

        elif kind == "lane_breakpoint":
            entry = self._node_for(
                run_id, payload.get("name"), payload.get("parent_id")
            )
            entry.state = "paused"
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

    def _render_node(self, entry: _NodeState):
        name = entry.name

        if entry.state == "active":
            frame = SPINNER[self._frame % len(SPINNER)]
            label = f"[bold]{name}[/] [#3b82f6]{frame}[/]"
        elif entry.state == "paused":
            label = f"[bold]{name}[/] [#fbbf24]⏸[/]"
        elif entry.state == "done":
            secs = (
                f" [bright_black]{entry.work:.2f}s[/]" if entry.work is not None else ""
            )
            label = f"{name}{secs}"
        elif entry.state == "terminated":
            label = f"[red]✕[/] {name}"
        else:  # pending — dim, no leading marker
            label = f"[bright_black]{name}[/]"

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

        if len(self._records) > MAX_LINES:
            del self._records[: len(self._records) - MAX_LINES]

        self._render_log()

    def _sync_level_checkbox(self, level: str):
        # Create the level's filter checkbox on first sighting, and keep its
        # label's count up to date. Any level (CRITICAL/SUCCESS/TRACE/PRINT/…)
        # becomes toggleable; a level with no logs shows no checkbox.
        label = f"{level} {abbrev_count(self._level_counts.get(level, 0))}"
        checkbox = self._level_checkboxes.get(level)

        if checkbox is None:
            # TRACE is noisy (lane lifecycle + watchers) — off by default.
            on = level not in LEVELS_OFF_BY_DEFAULT
            if on:
                self._enabled_levels.add(level)
            checkbox = _Checkbox(label, value=on, name=level)
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
            color = LEVEL_COLOR.get(level, "white")
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
                JSON_HL.highlight(pretty)
                return pretty

        # Keep ANSI from print() as-is; otherwise apply inline markdown.
        if "\x1b" in message:
            return Text.from_ansi(message)

        return inline_markdown(message)

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
            elif option == "panel":
                self._show_panel = event.value
                self._left.display = event.value
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

    def _sync_hotkeys(self):
        # Reflect paused state in the bottom bar (skip once the run is done).
        if self._finished:
            return
        self._hotkeys.update(HOTKEYS_PAUSED if self._paused else HOTKEYS_RUNNING)

    def action_continue_lane(self):
        # Release every lane parked at a breakpoint.
        if self._paused:
            events.resume_all()

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
