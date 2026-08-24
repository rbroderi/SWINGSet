"""Arrange controls in equal-size GridLayout cells."""

from swingset import App
from swingset import Button
from swingset import Frame
from swingset import GridLayout
from swingset import Size


def build() -> None:
    """Build the GridLayout example."""
    frame = Frame("GridLayout example")
    frame.size = Size(360, 300)
    frame.layout = GridLayout(rows=3, cols=3, hgap=6, vgap=6)
    for value in ("7", "8", "9", "4", "5", "6", "1", "2", "3"):
        frame.add(Button(value))
    frame.visible = True


def build_toml() -> str:
    """Return the backend-independent TOML form of this example."""
    return """[config.app]
entry-window = "main"
[widgets.main]
type = "Window"
title = "Grid Layout"
children = ["layout"]
[widgets.layout]
type = "Grid"
columns = 2
children = ["one", "two"]
[widgets.one]
type = "Button"
text = "One"
[widgets.two]
type = "Button"
text = "Two"
"""


if __name__ == "__main__":
    App.configure(backend="win32")
    App.run(build)
