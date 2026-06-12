"""Small rendering helpers for the dev-mode lane UI (see ``ui.py``)."""

import json

from rich.text import Text

from .constants import MD_RE, MD_STYLE


def fmt_bytes(n: int) -> str:
    """Human-readable byte size: 42 B, 1.2 KB, 3.4 MB, 1.1 GB."""

    for divisor, suffix in ((1 << 30, "GB"), (1 << 20, "MB"), (1 << 10, "KB")):
        if n >= divisor:
            return f"{n / divisor:.1f} {suffix}"

    return f"{n} B"


def fmt_rate(bps: float) -> str:
    """Human-readable throughput: 0 B/s, 1.2 KB/s, 3.4 MB/s."""

    return f"{fmt_bytes(int(bps))}/s"


def format_value(value, max_len: int = 4000):
    """Summarize a value flowing between lanes for the Values tab.

    Returns ``(meta, body)``: ``meta`` is the type name, its ``len`` when it has
    one (e.g. ``dict · 5``), and the serialized byte size (e.g. ``· 1.2 KB``);
    ``body`` is pretty JSON when the value is JSON-serializable, otherwise its
    ``repr``. Generators are never iterated — ``json.dumps`` rejects them, so
    they fall through to ``repr`` (e.g. ``<generator object …>``). ``body`` is
    truncated to ``max_len`` chars.
    """

    type_name = type(value).__name__

    size = None

    if hasattr(value, "__len__"):
        try:
            size = len(value)
        except Exception:
            size = None

    try:
        # No `default=` so non-serializable values (incl. generators) raise and
        # fall back to repr rather than being coerced or iterated.
        body = json.dumps(value, indent=2, ensure_ascii=False)
    except (TypeError, ValueError):
        body = repr(value)

    nbytes = len(body.encode("utf-8"))
    meta = type_name if size is None else f"{type_name} · {size}"
    meta = f"{meta} · {fmt_bytes(nbytes)}"

    if len(body) > max_len:
        body = f"{body[:max_len]}… (+{len(body) - max_len} chars)"

    return meta, body


def fmt_elapsed(seconds: float) -> str:
    """Compact elapsed time: 6.8s, 8m, 1h."""

    if seconds < 60:
        return f"{seconds:.1f}s"
    if seconds < 3600:
        return f"{int(seconds // 60)}m"

    return f"{int(seconds // 3600)}h"


def abbrev_count(n: int) -> str:
    """Compact integer: 50, 5K, 1M, 2B (no decimals)."""

    for divisor, suffix in ((1_000_000_000, "B"), (1_000_000, "M"), (1_000, "K")):
        if n >= divisor:
            return f"{n // divisor}{suffix}"

    return str(n)


#: Marker that identifies a Python traceback body.
TRACEBACK_MARKER = "Traceback (most recent call last):"


def highlight_traceback(text: str) -> Text:
    """Color a Python traceback body, keeping it selectable plain text.

    Highlights the header, ``File "…", line N, in func`` frames, and the final
    ``SomeError: message`` line.
    """

    out = Text(text)

    out.highlight_regex(r"Traceback \(most recent call last\):", "bold red")
    out.highlight_regex(r'File "[^"]+"', "cyan")
    out.highlight_regex(r"line \d+", "yellow")
    out.highlight_regex(r"(?m)\bin \S+$", "magenta")
    # Final exception line: `pkg.SomeError: message` at column 0.
    out.highlight_regex(r"(?m)^[\w.]*(?:Error|Exception|Warning|Interrupt)\b.*$", "bold red")

    return out


def inline_markdown(text: str) -> Text:
    """Render inline markdown (bold/italic/code/strike) as styled Text.

    Block markdown is intentionally not handled — keeps the log selectable and
    avoids mangling plain log lines.
    """

    out = Text()
    pos = 0

    for match in MD_RE.finditer(text):
        if match.start() > pos:
            out.append(text[pos : match.start()])

        kind = match.lastgroup
        token = match.group()
        pos = match.end()

        if kind is None:  # shouldn't happen (a named group always matches)
            out.append(token)

            continue

        inner = token[1:-1] if kind in ("code", "italic") else token[2:-2]

        out.append(inner, style=MD_STYLE[kind])

    if pos < len(text):
        out.append(text[pos:])

    return out
