"""Strongly typed event objects used by SWINGSet."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class Event[SourceT]:
    """Base event carrying its source object."""

    source: SourceT


@dataclass(slots=True)
class ActionEvent[SourceT](Event[SourceT]):
    """Event raised by an actionable control."""

    command: str | None = None


@dataclass(slots=True)
class ItemEvent[SourceT, ItemT](Event[SourceT]):
    """Event raised when a selected item changes."""

    item: ItemT | None = None
    selected: bool = False


@dataclass(slots=True)
class ListSelectionEvent[SourceT](Event[SourceT]):
    """Event raised when a list selection changes."""

    index: int = -1


@dataclass(slots=True)
class MouseEvent[SourceT](Event[SourceT]):
    """Mouse event in client coordinates."""

    x: int = 0
    y: int = 0
    button: int = 0
    wheel_delta: int = 0


@dataclass(slots=True)
class KeyEvent[SourceT](Event[SourceT]):
    """Keyboard event."""

    key_code: int = 0
    char: str | None = None
