"""Tests for backend-neutral image resources."""

from io import BytesIO

from PIL import Image as PillowImage

from swingset import SvgImage
from swingset import Theme

_RED_SVG = """\
<svg xmlns="http://www.w3.org/2000/svg" width="16" height="8">
  <rect width="16" height="8" fill="red"/>
</svg>
"""


def test_svg_rasterizes_to_requested_dpi_size() -> None:
    """SVG output has exact scaled dimensions and visible pixels."""
    image = SvgImage.from_text(_RED_SVG, size=(10, 20))

    frame = image.rasterize(dpi=192)

    assert (frame.width, frame.height, frame.dpi) == (20, 40, 192)
    with PillowImage.open(BytesIO(frame.png)) as raster:
        assert raster.size == (20, 40)
        assert raster.convert("RGBA").getpixel((10, 20)) == (255, 0, 0, 255)


def test_svg_rasterization_applies_tint_opacity_and_cache() -> None:
    """SVG transforms remain theme-aware and cache concrete variants."""
    image = SvgImage.from_text(_RED_SVG, tint=(10, 20, 30, 128))

    frame = image.rasterize(theme=Theme.CLASSIC, opacity=0.5)
    cached = image.rasterize(theme=Theme.CLASSIC, opacity=0.5)

    assert cached is frame
    assert image.cache_size == 1
    with PillowImage.open(BytesIO(frame.png)) as raster:
        assert raster.convert("RGBA").getpixel((8, 8)) == (10, 20, 30, 64)
