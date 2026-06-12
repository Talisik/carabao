"""Static constants for the dev-mode lane UI (see ``ui.py``)."""

import re

from rich.highlighter import JSONHighlighter

#: Highlighter for pretty-printed JSON log payloads.
JSON_HL = JSONHighlighter()

#: Cap on rendered log entries, to keep full-pane rebuilds snappy.
MAX_LINES = 2000

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
}

#: Log levels whose filter checkbox starts unchecked (noisy by nature).
LEVELS_OFF_BY_DEFAULT = {"TRACE"}

#: Spinner frames for active lanes.
SPINNER = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"

#: Bottom-bar hotkey hints, per pipeline state.
HOTKEYS_RUNNING = "[b]esc[/] quit   [b]/[/] search"
# Highlight "esc quit" once the pipeline is done — the user can safely exit.
HOTKEYS_DONE = "[b #ff4d4d]esc quit[/]   [b]/[/] search"
# Shown while one or more lanes are parked at a breakpoint.
HOTKEYS_PAUSED = "[b]esc[/] quit   [b]/[/] search   [b #fbbf24]c continue[/]"
