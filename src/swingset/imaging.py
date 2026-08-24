"""Backend-neutral image resources with lazy SVG rasterization."""

from __future__ import annotations

from dataclasses import dataclass
from functools import cache
from importlib import resources
from io import BytesIO
from pathlib import Path
from typing import Final
from typing import Protocol
from typing import runtime_checkable

from PIL import Image as PillowImage
from resvg import render
from resvg import usvg

from .theme import Dpi
from .theme import Theme
from .theme import resolve_color

type Color = tuple[int, int, int, int]
type ColorLike = str | tuple[int, int, int] | Color

_DEFAULT_LOGICAL_SIZE: Final = (16, 16)
_OPACITY_FULL: Final = 255


@dataclass(frozen=True, slots=True)
class RasterKey:
    """Cache key describing a concrete rasterization request."""

    width: int
    height: int
    dpi: int
    theme: Theme
    tint: Color | None
    opacity: int


@dataclass(frozen=True, slots=True)
class RasterFrame:
    """Portable PNG raster generated from an image resource."""

    png: bytes
    width: int
    height: int
    dpi: int

    def rgba(self) -> bytes:
        """Return tightly packed RGBA bytes."""
        with PillowImage.open(BytesIO(self.png)) as image:
            converted = image.convert("RGBA")
            return converted.tobytes()


@runtime_checkable
class ImageResource(Protocol):
    """Protocol implemented by backend-neutral image resources."""

    @property
    def logical_size(self) -> tuple[int, int]:
        """Return the resource's preferred size in logical pixels."""
        ...

    @property
    def fallback(self) -> str | None:
        """Return optional textual fallback used by terminal backends."""
        ...

    def rasterize(
        self,
        *,
        dpi: int = Dpi.BASE,
        theme: Theme | str | None = None,
        size: tuple[int, int] | None = None,
        opacity: float = 1.0,
    ) -> RasterFrame:
        """Rasterize for a concrete DPI, theme, logical size, and opacity."""
        ...


def _validate_size(size: tuple[int, int]) -> tuple[int, int]:
    width, height = size
    if width <= 0 or height <= 0:
        msg = "image size values must be positive"
        raise ValueError(msg)
    return width, height


@cache
def _opacity_lut(opacity: int) -> list[int]:
    return [value * opacity // _OPACITY_FULL for value in range(256)]


def _transform_png(png: bytes, tint: Color | None, opacity: int) -> bytes:
    with PillowImage.open(BytesIO(png)) as source:
        image = source.convert("RGBA")
        alpha = image.getchannel("A")
        if opacity != _OPACITY_FULL:
            alpha = alpha.point(_opacity_lut(opacity))
        if tint is not None:
            red, green, blue, tint_alpha = tint
            image = PillowImage.new(
                "RGBA", image.size, (red, green, blue, _OPACITY_FULL)
            )
            if tint_alpha != _OPACITY_FULL:
                alpha = alpha.point(_opacity_lut(tint_alpha))
        image.putalpha(alpha)
        buffer = BytesIO()
        image.save(buffer, format="PNG")
        return buffer.getvalue()


def _resize_png(png: bytes, size: tuple[int, int]) -> bytes:
    with PillowImage.open(BytesIO(png)) as source:
        image = source.convert("RGBA")
        if image.size == size:
            return png
        resized = image.resize(size, PillowImage.Resampling.LANCZOS)
        buffer = BytesIO()
        resized.save(buffer, format="PNG")
        return buffer.getvalue()


class SvgImage:
    """SVG resource that rasterizes lazily and caches rendered variants."""

    def __init__(
        self,
        svg: str | bytes,
        *,
        size: tuple[int, int] = _DEFAULT_LOGICAL_SIZE,
        tint: ColorLike | None = None,
        fallback: str | None = None,
        source_name: str | None = None,
    ) -> None:
        """Store SVG bytes and initialize lazy raster caches."""
        self._svg = svg.encode("utf-8") if isinstance(svg, str) else svg
        self._logical_size = _validate_size(size)
        self.tint = tint
        self.fallback = fallback
        self.source_name = source_name
        self._cache: dict[RasterKey, RasterFrame] = {}

    @classmethod
    def from_file(
        cls,
        path: str | Path,
        *,
        size: tuple[int, int] = _DEFAULT_LOGICAL_SIZE,
        tint: ColorLike | None = None,
        fallback: str | None = None,
    ) -> SvgImage:
        """Create an SVG resource without rasterizing it."""
        file_path = Path(path)
        return cls(
            file_path.read_bytes(),
            size=size,
            tint=tint,
            fallback=fallback,
            source_name=str(file_path),
        )

    @classmethod
    def from_text(
        cls,
        svg: str,
        *,
        size: tuple[int, int] = _DEFAULT_LOGICAL_SIZE,
        tint: ColorLike | None = None,
        fallback: str | None = None,
    ) -> SvgImage:
        """Create an SVG resource from text without rasterizing it."""
        return cls(svg, size=size, tint=tint, fallback=fallback)

    @classmethod
    def from_resource(
        cls,
        package: str,
        resource: str,
        *,
        size: tuple[int, int] = _DEFAULT_LOGICAL_SIZE,
        tint: ColorLike | None = None,
        fallback: str | None = None,
    ) -> SvgImage:
        """Create an SVG from an importable package resource lazily."""
        data = resources.files(package).joinpath(resource).read_bytes()
        return cls(
            data,
            size=size,
            tint=tint,
            fallback=fallback,
            source_name=f"{package}:{resource}",
        )

    @property
    def logical_size(self) -> tuple[int, int]:
        """Return preferred logical width and height."""
        return self._logical_size

    @property
    def cache_size(self) -> int:
        """Return the number of cached concrete raster variants."""
        return len(self._cache)

    def clear_cache(self) -> None:
        """Discard all cached raster variants."""
        self._cache.clear()

    def rasterize(
        self,
        *,
        dpi: int = Dpi.BASE,
        theme: Theme | str | None = None,
        size: tuple[int, int] | None = None,
        opacity: float = 1.0,
    ) -> RasterFrame:
        """Rasterize the SVG only when a backend requests concrete pixels."""
        logical_width, logical_height = _validate_size(size or self._logical_size)
        actual_theme = Theme.SYSTEM if theme is None else Theme(theme)
        resolved_tint = resolve_color(self.tint, actual_theme) if self.tint else None
        opacity_byte = round(max(0.0, min(1.0, opacity)) * _OPACITY_FULL)
        key = RasterKey(
            logical_width,
            logical_height,
            dpi,
            actual_theme,
            resolved_tint,
            opacity_byte,
        )
        cached = self._cache.get(key)
        if cached is not None:
            return cached

        width = max(1, Dpi.scale(logical_width, dpi))
        height = max(1, Dpi.scale(logical_height, dpi))
        options = usvg.Options.default()
        options.load_system_fonts()
        tree = usvg.Tree.from_str(self._svg.decode("utf-8"), options)
        png = _resize_png(render(tree, (1, 0, 0, 0, 1, 0)), (width, height))
        if resolved_tint is not None or opacity_byte != _OPACITY_FULL:
            png = _transform_png(png, resolved_tint, opacity_byte)
        frame = RasterFrame(png=png, width=width, height=height, dpi=dpi)
        self._cache[key] = frame
        return frame


class RasterImage:
    """Portable raster resource used for PNG/JPEG/BMP fallback assets."""

    def __init__(
        self,
        data: bytes,
        *,
        size: tuple[int, int] | None = None,
        fallback: str | None = None,
        source_name: str | None = None,
    ) -> None:
        """Normalize raster bytes to PNG and initialize resize caches."""
        with PillowImage.open(BytesIO(data)) as image:
            natural_size = (image.width, image.height)
            converted = image.convert("RGBA")
            buffer = BytesIO()
            converted.save(buffer, format="PNG")
        self._png = buffer.getvalue()
        self._logical_size = _validate_size(size or natural_size)
        self.fallback = fallback
        self.source_name = source_name
        self._cache: dict[tuple[int, int, int], RasterFrame] = {}

    @classmethod
    def from_file(
        cls,
        path: str | Path,
        *,
        size: tuple[int, int] | None = None,
        fallback: str | None = None,
    ) -> RasterImage:
        """Load a raster fallback asset."""
        file_path = Path(path)
        return cls(
            file_path.read_bytes(),
            size=size,
            fallback=fallback,
            source_name=str(file_path),
        )

    @property
    def logical_size(self) -> tuple[int, int]:
        """Return preferred logical width and height."""
        return self._logical_size

    @property
    def cache_size(self) -> int:
        """Return the number of cached concrete raster variants."""
        return len(self._cache)

    def rasterize(
        self,
        *,
        dpi: int = Dpi.BASE,
        theme: Theme | str | None = None,
        size: tuple[int, int] | None = None,
        opacity: float = 1.0,
    ) -> RasterFrame:
        """Resize the raster source for the target DPI."""
        del theme
        logical_width, logical_height = _validate_size(size or self._logical_size)
        opacity_byte = round(max(0.0, min(1.0, opacity)) * _OPACITY_FULL)
        key = (
            Dpi.scale(logical_width, dpi),
            Dpi.scale(logical_height, dpi),
            opacity_byte,
        )
        cached = self._cache.get(key)
        if cached is not None:
            return cached
        width, height, _ = key
        with PillowImage.open(BytesIO(self._png)) as source:
            target_size = (max(1, width), max(1, height))
            image = source.convert("RGBA").resize(
                target_size,
                PillowImage.Resampling.LANCZOS,
            )
            if opacity_byte != _OPACITY_FULL:
                alpha = image.getchannel("A").point(_opacity_lut(opacity_byte))
                image.putalpha(alpha)
            buffer = BytesIO()
            image.save(buffer, format="PNG")
        frame = RasterFrame(buffer.getvalue(), max(1, width), max(1, height), dpi)
        self._cache[key] = frame
        return frame


type ImageSource = SvgImage | RasterImage
Image = SvgImage


def load_image(
    path: str | Path,
    *,
    size: tuple[int, int] | None = None,
    tint: ColorLike | None = None,
    fallback: str | None = None,
) -> ImageSource:
    """Load an image, preferring SVG semantics when the extension is .svg."""
    file_path = Path(path)
    if file_path.suffix.lower() == ".svg":
        return SvgImage.from_file(
            file_path,
            size=size or _DEFAULT_LOGICAL_SIZE,
            tint=tint,
            fallback=fallback,
        )
    return RasterImage.from_file(file_path, size=size, fallback=fallback)
