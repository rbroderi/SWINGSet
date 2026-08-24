"""Display a static picture loaded as an in-memory bitmap resource."""

from pathlib import Path

from swingset import App
from swingset import Frame
from swingset import ImageLabel
from swingset import RasterImage
from swingset import Rect
from swingset import Size

_IMAGE_PATH = Path(__file__).parents[2] / "example-layout.png"


def build() -> None:
    """Build the StaticPicture resource example."""
    frame = Frame("StaticPictureResource example")
    frame.size = Size(340, 260)
    resource = RasterImage(
        _IMAGE_PATH.read_bytes(),
        size=(280, 180),
        source_name="layout-resource",
    )
    frame.add(ImageLabel(resource)).bounds = Rect(20, 20, 280, 180)
    frame.visible = True


def build_toml() -> str:
    """Return the backend-independent TOML form of this example."""
    return """[config.app]
entry-window = "main"
[resources.images]
sample = "../assets/sample.svg"
[widgets.main]
type = "Window"
title = "Static Picture Resource"
children = ["picture"]
[widgets.picture]
type = "ImageLabel"
image = "sample"
text = "Image fallback"
"""


if __name__ == "__main__":
    App.configure(backend="win32")
    App.run(build)
