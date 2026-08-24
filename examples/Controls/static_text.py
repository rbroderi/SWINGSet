"""Demonstrate a native static-text control."""

from swingset import App
from swingset import Frame
from swingset import Label
from swingset import Rect
from swingset import Size


def build() -> None:
    """Build the StaticText example."""
    frame = Frame("StaticText example")
    frame.size = Size(300, 300)
    frame.add(Label("staticText1")).bounds = Rect(10, 10, 100, 23)
    frame.visible = True


def build_toml() -> str:
    """Return the backend-independent TOML form of this example."""
    return """[config.app]
entry-window = "main"

[widgets.main]
type = "Window"
title = "Static Text"
children = ["demo"]

[widgets.demo]
type = "Label"
markdown = "**Styled** static text"
"""


if __name__ == "__main__":
    App.configure(backend="win32")
    App.run(build)
