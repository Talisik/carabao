import re


def clean_docstring(text: str):
    lines = text.splitlines()
    indent_len = min(
        len(match.group(0))
        for line in lines
        if (
            match := re.match(
                r"^\s+",
                line,
            )
        )
    )

    return "\n".join(line[indent_len:] for line in lines)
