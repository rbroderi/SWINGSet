"""Display a static picture loaded from a bitmap file."""

from pathlib import Path

from swingset import App
from swingset import Frame
from swingset import ImageLabel
from swingset import RasterImage
from swingset import Rect
from swingset import Size

_IMAGE_PATH = Path(__file__).parents[2] / "example-layout.png"


def build() -> None:
    """Build the StaticPicture file example."""
    frame = Frame("StaticPicture example")
    frame.size = Size(420, 320)
    image = RasterImage.from_file(_IMAGE_PATH, size=(360, 240))
    frame.add(ImageLabel(image)).bounds = Rect(20, 20, 360, 240)
    frame.visible = True


def build_toml() -> str:
    """Return the backend-independent TOML form of this example."""
    return """[config.app]
entry-window = "main"
[resources.images]
sample = "../assets/sample.svg"
[widgets.main]
type = "Window"
title = "Static Picture"
children = ["picture"]
[widgets.picture]
type = "ImageLabel"
image = "sample"
text = "Image fallback"
"""


if __name__ == "__main__":
    App.configure(backend="win32")
    App.run(build)
