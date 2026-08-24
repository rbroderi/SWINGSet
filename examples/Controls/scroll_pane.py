"""Demonstrate a native scrolling viewport around oversized content."""

from swingset import App
from swingset import Frame
from swingset import Label
from swingset import Panel
from swingset import Rect
from swingset import ScrollPane
from swingset import Size


def build() -> None:
    """Build the ScrollPane example."""
    content = Panel()
    content.size = Size(700, 500)
    for row in range(10):
        for column in range(5):
            label = content.add(Label(f"Row {row + 1}, column {column + 1}"))
            label.bounds = Rect(20 + column * 130, 20 + row * 45, 120, 23)

    frame = Frame("ScrollPane example")
    frame.size = Size(460, 300)
    viewport = frame.add(ScrollPane(content))
    viewport.bounds = Rect(20, 20, 400, 220)
    frame.visible = True


def build_toml() -> str:
    """Return the backend-independent TOML form of this example."""
    return """[config.app]
entry-window = "main"

[widgets.main]
type = "Window"
title = "Scroll Pane"
children = ["demo"]

[widgets.demo]
type = "ScrollPane"
children = ["content"]

[widgets.content]
type = "TextArea"
text = "Scrollable TOML content"
"""


if __name__ == "__main__":
    App.configure(backend="win32")
    App.run(build)
