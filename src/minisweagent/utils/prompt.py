"""Lazy wrapper around prompt_toolkit's `PromptSession`.

Constructing a `PromptSession` requires a console, which is not available at import
time when output is redirected or captured (e.g., on Windows this raises
`NoConsoleScreenBufferError`). This wrapper defers construction to the first prompt.
"""

from pathlib import Path

from prompt_toolkit.history import FileHistory
from prompt_toolkit.shortcuts import PromptSession


class LazyPromptSession:
    """Construct the underlying `PromptSession` on first use instead of at import time."""

    def __init__(self, history_file: Path):
        self._history_file = history_file
        self._session: PromptSession | None = None

    def prompt(self, *args, **kwargs) -> str:
        if self._session is None:
            self._session = PromptSession(history=FileHistory(self._history_file))
        return self._session.prompt(*args, **kwargs)
