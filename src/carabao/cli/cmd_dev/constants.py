"""Static constants for the dev-mode lane UI (see ``ui.py``)."""

import re

from rich.highlighter import JSONHighlighter

#: Highlighter for pretty-printed JSON log payloads.
JSON_HL = JSONHighlighter()

#: Cap on retained log entries (only one PAGE_SIZE page renders at a time).
MAX_LINES = 10000

#: Log lines rendered per page — small, so text selection stays snappy.
PAGE_SIZE = 200

# Inline markdown: `code`, **bold**, ~~strike~~, *italic* / _italic_.
MD_RE = re.compile(
    r"(?P<code>`[^`]+`)"
    r"|(?P<bold>\*\*[^*]+\*\*)"
    r"|(?P<strike>~~[^~]+~~)"
    # underscore italics require word boundaries so path/to_file_name is safe
    r"|(?P<italic>\*[^*\s][^*]*\*|(?<!\w)_[^_\s][^_]*_(?!\w))"
)
MD_STYLE = {"code": "cyan", "bold": "bold", "strike": "strike", "italic": "italic"}

#: Log-level → rich style for the level column.
LEVEL_COLOR = {
    "DEBUG": "bright_black",
    "INFO": "cyan",
    "WARNING": "yellow",
    "ERROR": "bold red",
    "CRITICAL": "bold red",
    "SUCCESS": "green",
    "TRACE": "bright_black",
    "PRINT": "white",
    "PAUSE": "bold #fbbf24",  # amber, matches the ⏸ marker
}

#: Log levels whose filter checkbox starts unchecked (noisy by nature).
LEVELS_OFF_BY_DEFAULT = {"TRACE"}

#: Spinner frames for active lanes.
SPINNER = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"

#: Lane-tree node colors. Pending nodes are dim; running -> done brightens.
#: Active lanes use greens, passive lanes (always-on watchers) use blues, and
#: anything that errored or terminated turns bright red.
NODE_RUNNING = "#3fb950"  # active lane, running
NODE_DONE = "#56d364"  # active lane, finished (brighter green)
NODE_PASSIVE_RUNNING = "#3b82f6"  # passive lane, running
NODE_PASSIVE_DONE = "#79c0ff"  # passive lane, finished (brighter blue)
NODE_ERROR = "#ff5555"  # errored or terminated (bright red)

#: Max width the log's lane column pads to. Names longer than this overflow
#: (their message won't align) rather than forcing a huge gap on every line.
LANE_COL_MAX = 22

#: Bottom-bar hotkey hints, per pipeline state.
HOTKEYS_RUNNING = "[b]esc[/] quit   [b]/[/] search   [b]f[/] levels   [b]d[/] display"
# Highlight "esc quit" once the pipeline is done — the user can safely exit.
HOTKEYS_DONE = (
    "[b #ff4d4d]esc quit[/]   [b]/[/] search   [b]f[/] levels   [b]d[/] display"
)
# Shown while one or more lanes are parked at a breakpoint.
HOTKEYS_PAUSED = (
    "[b]esc[/] quit   [b]/[/] search   [b]f[/] levels   [b]d[/] display"
    "   [b #fbbf24]c continue[/]"
)
