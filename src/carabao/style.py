"""Minimal, dependency-free terminal styling for carabao.

Carabao's own chainable ANSI styler (no ``simple-chalk``, and independent of
lane2lane). Chain color/background/modifier names, then call with the text::

    style.yellow("dev mode")
    style.black.on_green(".env.release")
    style.bold.red("error")

Backgrounds use an ``on_`` prefix. Call ``style.disable()`` to emit plain text
(e.g. non-terminal output) and ``style.enable()`` to turn it back on.
"""

_RESET = "\033[0m"

_CODES = {
    # modifiers
    "bold": 1,
    "dim": 2,
    # foreground
    "black": 30,
    "red": 31,
    "green": 32,
    "yellow": 33,
    "blue": 34,
    "magenta": 35,
    "cyan": 36,
    "white": 37,
    "gray": 90,
    "grey": 90,
    # background
    "on_black": 40,
    "on_red": 41,
    "on_green": 42,
    "on_yellow": 43,
    "on_blue": 44,
    "on_magenta": 45,
    "on_cyan": 46,
    "on_white": 47,
}


class _Style:
    enabled: bool = True

    def __init__(self, codes=()):
        self._codes = codes

    def enable(self):
        """Turns coloring on (affects all chained styles)."""

        _Style.enabled = True

    def disable(self):
        """Turns coloring off; calls return plain text."""

        _Style.enabled = False

    def __getattr__(self, name):
        code = _CODES.get(name)

        if code is None:
            raise AttributeError(name)

        return _Style(self._codes + (code,))

    def __call__(self, text) -> str:
        text = str(text)

        if not _Style.enabled or not self._codes:
            return text

        prefix = "".join(f"\033[{code}m" for code in self._codes)

        return f"{prefix}{text}{_RESET}"


#: Shared style instance. Chain color/modifier names, then call with the text.
style = _Style()
