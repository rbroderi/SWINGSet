"""Portable custom-paint surface and short-lived graphics contract."""

from __future__ import annotations

from abc import ABC
from abc import abstractmethod
from collections.abc import Callable
from dataclasses import dataclass

from .core import Component
from .geometry import Point
from .geometry import Rect
from .geometry import Size
from .peers import PaintPeer
from .theme import ColorInput


class Graphics(ABC):
    """Drawing operations valid only during one paint callback."""

    @abstractmethod
    def draw_line(
        self,
        start: Point,
        end: Point,
        *,
        color: ColorInput = "foreground",
        width: int = 1,
    ) -> None:
        """Draw one line."""

    @abstractmethod
    def draw_rectangle(
        self,
        bounds: Rect,
        *,
        color: ColorInput = "foreground",
        width: int = 1,
    ) -> None:
        """Draw a rectangle outline."""

    @abstractmethod
    def fill_rectangle(
        self,
        bounds: Rect,
        *,
        color: ColorInput = "background",
    ) -> None:
        """Fill a rectangle."""

    @abstractmethod
    def draw_text(
        self,
        text: str,
        x: int,
        y: int,
        *,
        color: ColorInput = "foreground",
    ) -> None:
        """Draw text using the surface's current native font."""


@dataclass(frozen=True, slots=True)
class PaintEvent:
    """Graphics context and invalidated region for one paint operation."""

    source: PaintSurface
    graphics: Graphics
    clip: Rect


type PaintListener = Callable[[PaintEvent], object]


class PaintSurface(Component):
    """Component that redraws itself through short-lived paint events."""

    def __init__(self, width: int = 320, height: int = 200) -> None:
        """Initialize an empty custom-paint surface."""
        super().__init__()
        self.size = Size(width, height)
        self._paint_listeners: list[PaintListener] = []

    def on_paint(self, listener: PaintListener) -> PaintListener:
        """Register a paint listener and return it."""
        self._paint_listeners.append(listener)
        return listener

    def dispatch_paint(self, graphics: Graphics, clip: Rect) -> None:
        """Dispatch one backend-owned graphics context to listeners."""
        event = PaintEvent(self, graphics, clip)
        for listener in tuple(self._paint_listeners):
            listener(event)

    def invalidate(self) -> None:
        """Request repainting of the complete surface."""
        peer = self.peer
        if isinstance(peer, PaintPeer) and self.created:
            peer.invalidate()
