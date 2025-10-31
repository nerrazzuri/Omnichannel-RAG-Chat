from __future__ import annotations

import re


def normalize_multiline_text(text: str) -> str:
    if text is None:
        return ""
    # Normalize newlines
    s = text.replace("\r\n", "\n").replace("\r", "\n")
    # Collapse excessive blank lines to a single empty line
    s = re.sub(r"\n{3,}", "\n\n", s)
    # Trim leading/trailing blank lines
    s = s.strip("\n ")
    # Collapse long runs of spaces (but keep single spaces)
    s = re.sub(r" {2,}", " ", s)
    return s


