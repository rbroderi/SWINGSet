"""Demonstrate native progress bars at several values."""

from swingset import App
from swingset import Frame
from swingset import ProgressBar
from swingset import Rect
from swingset import Size


def build() -> None:
    """Build the ProgressBar example."""
    frame = Frame("ProgressBar example")
    frame.size = Size(300, 300)
    for index, value in enumerate((0, 50, 100, 70)):
        progress = frame.add(ProgressBar(value=value))
        progress.bounds = Rect(50, 50 + index * 30, 200, 23)
    frame.visible = True


def build_toml() -> str:
    """Return the backend-independent TOML form of this example."""
    return """[config.app]
entry-window = "main"

[widgets.main]
type = "Window"
title = "Progress Bar"
children = ["demo"]

[widgets.demo]
type = "ProgressBar"
minimum = 0
maximum = 100
value = 65
"""


if __name__ == "__main__":
    App.configure(backend="win32")
    App.run(build)
