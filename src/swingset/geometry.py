"""Small immutable geometry value objects used by every backend."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Point:
    """Logical x/y coordinates."""

    x: int = 0
    y: int = 0

    def __iter__(self) -> Iterator[int]:
        """Iterate as x, then y."""
        yield self.x
        yield self.y


@dataclass(frozen=True, slots=True)
class Size:
    """Logical width/height dimensions."""

    width: int = 0
    height: int = 0

    def __iter__(self) -> Iterator[int]:
        """Iterate as width, then height."""
        yield self.width
        yield self.height


@dataclass(frozen=True, slots=True)
class Rect:
    """Logical rectangle."""

    x: int = 0
    y: int = 0
    width: int = 0
    height: int = 0

    @property
    def location(self) -> Point:
        """Return the rectangle origin."""
        return Point(self.x, self.y)

    @property
    def size(self) -> Size:
        """Return the rectangle dimensions."""
        return Size(self.width, self.height)

    def with_location(self, point: Point) -> Rect:
        """Return a copy with a different origin."""
        return Rect(point.x, point.y, self.width, self.height)

    def with_size(self, size: Size) -> Rect:
        """Return a copy with different dimensions."""
        return Rect(self.x, self.y, size.width, size.height)

    def __iter__(self) -> Iterator[int]:
        """Iterate as x, y, width, then height."""
        yield self.x
        yield self.y
        yield self.width
        yield self.height
