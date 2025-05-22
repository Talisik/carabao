import re


def clean_docstring(text: str):
    try:
        lines = text.splitlines()
        indent_len = min(
            len(match.group(0))
            for line in lines
            if line.strip()
            and (
                match := re.match(
                    r"^\s*",
                    line,
                )
            )
        )

        return "\n".join(line[indent_len:] for line in lines).strip()

    except Exception:
        return text.strip()
