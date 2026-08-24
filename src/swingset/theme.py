"""Backend-neutral theme intent, palettes, and logical DPI helpers."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import SupportsFloat

Color = tuple[int, int, int, int]
ColorInput = str | tuple[int, int, int] | Color
_RGB_COMPONENT_COUNT = 3


class Theme(StrEnum):
    """Supported application theme choices."""

    SYSTEM = "system"
    LIGHT = "light"
    DARK = "dark"
    CLASSIC = "classic"


@dataclass(frozen=True, slots=True)
class Palette:
    """Backend-neutral symbolic UI colors."""

    foreground: Color
    muted: Color
    accent: Color
    disabled: Color
    background: Color


_LIGHT = Palette(
    foreground=(32, 32, 32, 255),
    muted=(104, 104, 104, 255),
    accent=(0, 95, 184, 255),
    disabled=(150, 150, 150, 255),
    background=(255, 255, 255, 255),
)
_DARK = Palette(
    foreground=(240, 240, 240, 255),
    muted=(180, 180, 180, 255),
    accent=(96, 170, 255, 255),
    disabled=(112, 112, 112, 255),
    background=(32, 32, 32, 255),
)
_CLASSIC = Palette(
    foreground=(0, 0, 0, 255),
    muted=(128, 128, 128, 255),
    accent=(0, 0, 128, 255),
    disabled=(128, 128, 128, 255),
    background=(192, 192, 192, 255),
)


class Dpi:
    """Backend-neutral logical pixel conversion helpers."""

    BASE = 96

    @staticmethod
    def scale(value: SupportsFloat, dpi: int) -> int:
        """Convert a logical value to device pixels."""
        return round(float(value) * dpi / Dpi.BASE)

    @staticmethod
    def unscale(value: SupportsFloat, dpi: int) -> int:
        """Convert a device-pixel value back to logical pixels."""
        numeric_value = float(value)
        if dpi <= 0:
            return round(numeric_value)
        return round(numeric_value * Dpi.BASE / dpi)


def palette_for(theme: Theme | str = Theme.SYSTEM) -> Palette:
    """Return the symbolic palette for a theme intent."""
    actual = Theme(theme)
    if actual is Theme.DARK:
        return _DARK
    if actual is Theme.CLASSIC:
        return _CLASSIC
    return _LIGHT


def resolve_color(value: ColorInput, theme: Theme | str = Theme.SYSTEM) -> Color:
    """Resolve a concrete or symbolic color for a theme."""
    if isinstance(value, tuple):
        if len(value) == _RGB_COMPONENT_COUNT:
            red, green, blue = value
            return red, green, blue, 255
        return value
    palette = palette_for(theme)
    try:
        return getattr(palette, value)
    except AttributeError as exc:
        msg = f"unknown symbolic color: {value!r}"
        raise ValueError(msg) from exc


def background_color(theme: Theme | str = Theme.SYSTEM) -> tuple[int, int, int]:
    """Return the RGB background color for a theme."""
    red, green, blue, _alpha = palette_for(theme).background
    return red, green, blue
