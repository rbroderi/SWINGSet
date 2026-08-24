"""Demonstrate horizontal and vertical native separators."""

from swingset import App
from swingset import Frame
from swingset import Label
from swingset import Rect
from swingset import Separator
from swingset import SeparatorOrientation
from swingset import Size


def build() -> None:
    """Build the Separator example."""
    frame = Frame("Separator example")
    frame.size = Size(360, 200)

    heading = frame.add(Label("Account settings"))
    heading.bounds = Rect(20, 18, 150, 23)
    horizontal = frame.add(Separator())
    horizontal.bounds = Rect(20, 48, 300, 2)
    left = frame.add(Label("Profile"))
    left.bounds = Rect(35, 75, 100, 23)
    vertical = frame.add(Separator(SeparatorOrientation.VERTICAL))
    vertical.bounds = Rect(165, 68, 2, 70)
    right = frame.add(Label("Security"))
    right.bounds = Rect(200, 75, 100, 23)
    frame.visible = True


def build_toml() -> str:
    """Return the backend-independent TOML form of this example."""
    return """[config.app]
entry-window = "main"

[widgets.main]
type = "Window"
title = "Separator"
children = ["demo"]

[widgets.demo]
type = "Separator"
orientation = "horizontal"
"""


if __name__ == "__main__":
    App.configure(backend="win32")
    App.run(build)
