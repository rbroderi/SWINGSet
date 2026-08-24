"""Arrange controls left-to-right and wrap them onto new rows."""

from swingset import App
from swingset import Button
from swingset import FlowAlignment
from swingset import FlowLayout
from swingset import Frame
from swingset import Size


def build() -> None:
    """Build the FlowLayout example."""
    frame = Frame("FlowLayout example")
    frame.size = Size(430, 220)
    frame.layout = FlowLayout(FlowAlignment.CENTER, hgap=10, vgap=12)
    for name in ("New", "Open", "Save", "Print", "Preferences", "Close"):
        frame.add(Button(name))
    frame.visible = True


def build_toml() -> str:
    """Return the backend-independent TOML form of this example."""
    return """[config.app]
entry-window = "main"
[widgets.main]
type = "Window"
title = "Flow Layout"
children = ["layout"]
[widgets.layout]
type = "FlowLayout"
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
