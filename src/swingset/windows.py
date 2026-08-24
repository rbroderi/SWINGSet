"""Portable frame and dialog window components."""

from __future__ import annotations

from enum import StrEnum
from types import TracebackType
from typing import Self

from .context import UIContext
from .core import Container
from .core import Window
from .imaging import ImageResource
from .layout import BorderLayout
from .lifecycle import ComponentState
from .peers import WindowPeer


class CloseOperation(StrEnum):
    """Behavior applied when a frame receives a close request."""

    DISPOSE = "dispose"
    HIDE = "hide"


class Frame(Window):
    """Resizable top-level application window."""

    def __init__(self, title: str = "", *, context: UIContext | None = None) -> None:
        """Create a top-level frame with optional context."""
        super().__init__(title, context=context)
        self.layout = BorderLayout()
        self.close_operation = CloseOperation.DISPOSE
        self._icon: ImageResource | None = None

    @property
    def icon(self) -> ImageResource | None:
        """Return the frame icon resource, if set."""
        return self._icon

    @icon.setter
    def icon(self, value: ImageResource | None) -> None:
        self._icon = value
        peer = self.peer
        if isinstance(peer, WindowPeer) and self.created:
            peer.set_icon(value)

    def _mount(self, parent: Container | None = None) -> None:
        super()._mount(parent)
        peer = self.peer
        if isinstance(peer, WindowPeer):
            peer.set_icon(self._icon)

    def _request_close(self) -> None:
        if self.close_operation is CloseOperation.HIDE:
            self.visible = False
            return
        self.dispose()


class Dialog(Window):
    """Owned top-level window, optionally modal and usable as a context manager."""

    def __init__(
        self,
        owner: Window | None = None,
        title: str = "",
        *,
        modal: bool = False,
        context: UIContext | None = None,
    ) -> None:
        """Create a dialog with optional owner, modality, and context."""
        resolved_context = (
            context
            if context is not None
            else (None if owner is None else owner.context)
        )
        super().__init__(title, context=resolved_context)
        self.layout = BorderLayout()
        self.owner = owner
        self.modal = modal

    def _mount(self, parent: Container | None = None) -> None:
        super()._mount(self.owner if self.owner is not None else parent)
        if self.modal and self.owner is not None:
            self.owner.enabled = False

    def dispose(self) -> None:
        """Dispose the dialog and restore owner state when needed."""
        super().dispose()
        if (
            self.modal
            and self.owner is not None
            and self.owner.state is not ComponentState.DESTROYED
        ):
            self.owner.enabled = True

    def __enter__(self) -> Self:
        """Show the dialog when entering a context."""
        self.visible = True
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Dispose the dialog when leaving a context."""
        del exc_type, exc_value, traceback
        self.dispose()
