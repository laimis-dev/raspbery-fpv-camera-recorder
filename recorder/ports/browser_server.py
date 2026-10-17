"""Lifecycle of the browser interface, independent of its HTTP implementation."""

from typing import Protocol


class BrowserServer(Protocol):
    def start(self) -> None: ...

    def stop(self) -> None: ...
