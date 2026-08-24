"""Win32-only DPI and theme integration kept out of the portable core."""

from __future__ import annotations

import contextlib
import ctypes
from ctypes import wintypes

from swingset.theme import Dpi
from swingset.theme import Theme


class Win32Dpi:
    """Per-monitor DPI integration for the Win32 backend."""

    _enabled = False

    @classmethod
    def enable(cls) -> None:
        """Update enable."""
        if cls._enabled:
            return
        cls._enabled = True
        try:
            setter = ctypes.windll.user32.SetProcessDpiAwarenessContext
            setter.argtypes = [wintypes.HANDLE]
            setter.restype = wintypes.BOOL
            setter(wintypes.HANDLE(-4))
        except AttributeError, OSError:
            with contextlib.suppress(AttributeError, OSError):
                ctypes.windll.shcore.SetProcessDpiAwareness(2)

    @staticmethod
    def system() -> int:
        """Return system."""
        try:
            return int(ctypes.windll.user32.GetDpiForSystem()) or Dpi.BASE
        except AttributeError, OSError:
            return Dpi.BASE

    @staticmethod
    def for_window(hwnd: int | None) -> int:
        """Return for window."""
        if hwnd is None:
            return Dpi.BASE
        try:
            return int(ctypes.windll.user32.GetDpiForWindow(hwnd)) or Dpi.BASE
        except AttributeError, OSError:
            return Dpi.BASE


class Win32Theme:
    """Best-effort UxTheme/DWM integration."""

    @staticmethod
    def apply(hwnd: int, theme: Theme, *, window: bool = False) -> None:
        """Update apply."""
        if theme is Theme.CLASSIC:
            with contextlib.suppress(AttributeError, OSError):
                ctypes.windll.uxtheme.SetWindowTheme(hwnd, "", "")
            return
        dark = theme is Theme.DARK
        with contextlib.suppress(AttributeError, OSError):
            ctypes.windll.uxtheme.SetWindowTheme(
                hwnd,
                "DarkMode_Explorer" if dark else "Explorer",
                None,
            )
        if not window or theme is Theme.SYSTEM:
            return
        value = ctypes.c_int(1 if dark else 0)
        for attribute in (20, 19):
            try:
                result = ctypes.windll.dwmapi.DwmSetWindowAttribute(
                    hwnd,
                    attribute,
                    ctypes.byref(value),
                    ctypes.sizeof(value),
                )
            except AttributeError, OSError:
                break
            if result == 0:
                break
