"""Backend-neutral menu models."""

from __future__ import annotations

import itertools
from collections.abc import Callable

from .events import ActionEvent

MenuAction = Callable[[ActionEvent["MenuItem"]], None]
_menu_ids = itertools.count(20_000)


class MenuItem:
    """Clickable menu command."""

    def __init__(self, text: str, action: MenuAction | None = None) -> None:
        """Create a menu command with optional click handler."""
        self.text = text
        self.action = action
        self.id = next(_menu_ids)
        self.enabled = True

    def on_click(self, callback: MenuAction) -> MenuAction:
        """Register and return the click callback for decorator use."""
        self.action = callback
        return callback

    def _emit_action(self) -> None:
        if self.enabled and self.action is not None:
            self.action(ActionEvent(self, self.text))

    def trigger_action(self) -> None:
        """Invoke the menu item action when enabled."""
        self._emit_action()


class Menu:
    """Drop-down menu containing commands and separators."""

    def __init__(self, text: str) -> None:
        """Create a named menu container."""
        self.text = text
        self.items: list[MenuItem | None] = []

    def add(self, item: MenuItem | str, action: MenuAction | None = None) -> MenuItem:
        """Add an existing item or create one from text."""
        resolved = MenuItem(item, action) if isinstance(item, str) else item
        self.items.append(resolved)
        return resolved

    def add_separator(self) -> None:
        """Insert a separator marker in the menu."""
        self.items.append(None)


class MenuBar:
    """Portable top-level menu description."""

    def __init__(self) -> None:
        """Create an empty top-level menu collection."""
        self.menus: list[Menu] = []

    def add(self, menu: Menu) -> Menu:
        """Append a menu to the bar and return it."""
        self.menus.append(menu)
        return menu
