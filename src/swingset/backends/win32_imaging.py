"""Win32 adapter for backend-neutral SWINGSet image resources."""

from __future__ import annotations

import ctypes
from ctypes import wintypes
from dataclasses import dataclass
from io import BytesIO
from typing import Final

import win32con
import win32gui
from PIL import Image as PillowImage

from swingset.imaging import ImageResource
from swingset.theme import Theme
from swingset.theme import background_color

_BI_RGB: Final = 0
_DIB_RGB_COLORS: Final = 0


class BITMAPINFOHEADER(ctypes.Structure):
    """ctypes definition of BITMAPINFOHEADER."""

    _fields_ = [
        ("biSize", wintypes.DWORD),
        ("biWidth", wintypes.LONG),
        ("biHeight", wintypes.LONG),
        ("biPlanes", wintypes.WORD),
        ("biBitCount", wintypes.WORD),
        ("biCompression", wintypes.DWORD),
        ("biSizeImage", wintypes.DWORD),
        ("biXPelsPerMeter", wintypes.LONG),
        ("biYPelsPerMeter", wintypes.LONG),
        ("biClrUsed", wintypes.DWORD),
        ("biClrImportant", wintypes.DWORD),
    ]


class RGBQUAD(ctypes.Structure):
    """ctypes definition of RGBQUAD."""

    _fields_ = [
        ("rgbBlue", wintypes.BYTE),
        ("rgbGreen", wintypes.BYTE),
        ("rgbRed", wintypes.BYTE),
        ("rgbReserved", wintypes.BYTE),
    ]


class BITMAPINFO(ctypes.Structure):
    """ctypes definition of a one-entry BITMAPINFO."""

    _fields_ = [("bmiHeader", BITMAPINFOHEADER), ("bmiColors", RGBQUAD * 1)]


class ICONINFO(ctypes.Structure):
    """ctypes definition of ICONINFO."""

    _fields_ = [
        ("fIcon", wintypes.BOOL),
        ("xHotspot", wintypes.DWORD),
        ("yHotspot", wintypes.DWORD),
        ("hbmMask", wintypes.HBITMAP),
        ("hbmColor", wintypes.HBITMAP),
    ]


@dataclass(slots=True)
class NativeImageHandle:
    """Owned HBITMAP or HICON created for one render request."""

    handle: int
    image_type: int

    def close(self) -> None:
        """Release the native resource."""
        if self.handle == 0:
            return
        if self.image_type == win32con.IMAGE_ICON:
            win32gui.DestroyIcon(self.handle)
        else:
            win32gui.DeleteObject(self.handle)
        self.handle = 0


def _create_hbitmap(png: bytes, background: tuple[int, int, int] | None) -> int:
    with PillowImage.open(BytesIO(png)) as source:
        image = source.convert("RGBA")
        if background is not None:
            backdrop = PillowImage.new("RGBA", image.size, (*background, 255))
            image = PillowImage.alpha_composite(backdrop, image)
        bgra = image.tobytes("raw", "BGRA")
        width, height = image.size

    info = BITMAPINFO()
    info.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
    info.bmiHeader.biWidth = width
    info.bmiHeader.biHeight = -height
    info.bmiHeader.biPlanes = 1
    info.bmiHeader.biBitCount = 32
    info.bmiHeader.biCompression = _BI_RGB
    bits = ctypes.c_void_p()
    screen_dc = ctypes.windll.user32.GetDC(None)
    try:
        handle = int(
            ctypes.windll.gdi32.CreateDIBSection(
                screen_dc,
                ctypes.byref(info),
                _DIB_RGB_COLORS,
                ctypes.byref(bits),
                None,
                0,
            ),
        )
    finally:
        ctypes.windll.user32.ReleaseDC(None, screen_dc)
    if handle == 0 or bits.value is None:
        msg = "CreateDIBSection failed"
        raise OSError(msg)
    ctypes.memmove(bits, bgra, len(bgra))
    return handle


def render_bitmap(
    image: ImageResource,
    *,
    dpi: int,
    theme: Theme | str | None = None,
    size: tuple[int, int] | None = None,
    opacity: float = 1.0,
) -> NativeImageHandle:
    """Rasterize a portable resource and create an owned HBITMAP."""
    actual_theme = Theme.SYSTEM if theme is None else Theme(theme)
    frame = image.rasterize(dpi=dpi, theme=actual_theme, size=size, opacity=opacity)
    return NativeImageHandle(
        _create_hbitmap(frame.png, background_color(actual_theme)),
        win32con.IMAGE_BITMAP,
    )


def render_icon(
    image: ImageResource,
    *,
    dpi: int,
    theme: Theme | str | None = None,
    size: tuple[int, int] | None = None,
) -> NativeImageHandle:
    """Rasterize a portable resource and create an owned HICON."""
    actual_theme = Theme.SYSTEM if theme is None else Theme(theme)
    frame = image.rasterize(dpi=dpi, theme=actual_theme, size=size)
    color = _create_hbitmap(frame.png, None)
    mask = int(ctypes.windll.gdi32.CreateBitmap(frame.width, frame.height, 1, 1, None))
    icon_info = ICONINFO(1, 0, 0, mask, color)
    handle = int(ctypes.windll.user32.CreateIconIndirect(ctypes.byref(icon_info)))
    win32gui.DeleteObject(mask)
    win32gui.DeleteObject(color)
    if handle == 0:
        msg = "CreateIconIndirect failed"
        raise OSError(msg)
    return NativeImageHandle(handle, win32con.IMAGE_ICON)
