"""Typed backend peer interfaces implementing the Bridge pattern."""

from __future__ import annotations

from abc import ABC
from abc import abstractmethod
from typing import TYPE_CHECKING

from .geometry import Rect
from .geometry import Size

if TYPE_CHECKING:
    import swingset.core
    import swingset.imaging
    import swingset.menu
    import swingset.models
    import swingset.theme


class ComponentPeer(ABC):
    """Backend half of a portable component/peer bridge."""

    def __init__(self, component: swingset.core.Component) -> None:
        """Bind this peer instance to its portable component."""
        self.component = component

    @property
    @abstractmethod
    def native(self) -> object:
        """Return the backend-native object/handle."""

    @property
    def dpi(self) -> int:
        """Return effective DPI; terminal/non-DPI backends use 96."""
        return 96

    @property
    def text(self) -> str:
        """Return peer text when readable."""
        return self.component.snapshot_text()

    @text.setter
    def text(self, value: str) -> None:
        """Update peer text."""
        del value

    @abstractmethod
    def destroy(self) -> None:
        """Destroy this peer."""

    def set_visible(self, *, visible: bool) -> None:
        """Apply visibility when meaningful."""
        del visible

    def set_enabled(self, *, enabled: bool) -> None:
        """Apply enabled state when meaningful."""
        del enabled

    def set_bounds(self, bounds: Rect) -> None:
        """Apply logical bounds when meaningful."""
        del bounds

    def client_size(self) -> Size:
        """Return client size, defaulting to requested component size."""
        return self.component.size

    def focus(self) -> None:
        """Request focus using common backend-native focus conventions."""
        native = self.native
        for method_name in ("focus_set", "focus"):
            method = getattr(native, method_name, None)
            if callable(method):
                method()
                return

    def set_font(self, face: str, size: int, *, bold: bool) -> None:
        """Apply a font request when supported."""
        del face, size, bold

    def set_tooltip(self, text: str | None) -> None:
        """Apply component tooltip text when supported."""
        del text

    def set_foreground(self, color: swingset.theme.ColorInput | None) -> None:
        """Apply a foreground color or restore the theme default."""
        del color

    def set_background(self, color: swingset.theme.ColorInput | None) -> None:
        """Apply a background color or restore the theme default."""
        del color

    def apply_text_styles(self) -> None:
        """Apply portable character spans when this peer supports them."""
        return

    def refresh(self) -> None:
        """Synchronize baseline native state from portable component properties."""
        self.text = self.component.snapshot_text()
        self.set_visible(visible=self.component.visible)
        self.set_enabled(enabled=self.component.enabled)
        self.set_bounds(self.component.bounds)

    def apply_theme(self, theme: swingset.theme.Theme) -> None:
        """Apply current theme intent when supported."""
        del theme

    def on_model_event(self, event: swingset.models.ModelEvent) -> None:
        """Handle a typed model delta; default safely performs a full refresh."""
        del event
        self.refresh()

    def attach_child(self, child: ComponentPeer) -> None:
        """Let special containers attach/manage a newly created child peer."""
        del child


class SelectionPeer(ComponentPeer):
    """Peer supporting one selected index."""

    @property
    @abstractmethod
    def selected_index(self) -> int:
        """Return selected index or -1."""

    @selected_index.setter
    @abstractmethod
    def selected_index(self, index: int) -> None:
        """Set selected index."""


class BooleanPeer(ComponentPeer):
    """Peer exposing a boolean state."""

    @property
    @abstractmethod
    def selected(self) -> bool:
        """Return boolean state."""

    @selected.setter
    @abstractmethod
    def selected(self, value: bool) -> None:
        """Set boolean state."""


class IntValuePeer(ComponentPeer):
    """Peer exposing an integer value."""

    @property
    @abstractmethod
    def value(self) -> int:
        """Return current integer value."""

    @value.setter
    @abstractmethod
    def value(self, value: int) -> None:
        """Set current integer value."""


class PasswordPeer(ComponentPeer):
    """Peer supporting runtime password masking changes."""

    @abstractmethod
    def set_revealed(self, *, revealed: bool) -> None:
        """Show or mask the underlying password text."""


class RichTextPeer(ComponentPeer):
    """Peer capable of applying portable rich-text style spans."""

    @abstractmethod
    def selection_range(self) -> tuple[int, int]:
        """Return the selected half-open character range."""

    @abstractmethod
    def set_selection_range(self, start: int, end: int) -> None:
        """Select a half-open character range."""

    @abstractmethod
    def apply_styles(self) -> None:
        """Apply the component's current rich-text spans."""

    def apply_text_styles(self) -> None:
        """Apply portable spans through the rich-text implementation."""
        self.apply_styles()


class PaintPeer(ComponentPeer):
    """Peer for a component that supports invalidation and custom painting."""

    @abstractmethod
    def invalidate(self) -> None:
        """Request repainting of the component."""


class WindowPeer(ComponentPeer):
    """Peer for top-level window-only features."""

    def set_menu(self, menu_bar: swingset.menu.MenuBar | None) -> None:
        """Attach a menu bar. Unsupported backends intentionally no-op."""
        del menu_bar

    def set_icon(self, image: swingset.imaging.ImageResource | None) -> None:
        """Set a window icon. Unsupported backends intentionally no-op."""
        del image


class NullComponentPeer(ComponentPeer):
    """Null Object peer for semantically unsupported optional components."""

    _native = object()

    @property
    def native(self) -> object:
        """Return a stable sentinel native object."""
        return self._native

    def destroy(self) -> None:
        """Perform no operation for the null peer."""
        return
