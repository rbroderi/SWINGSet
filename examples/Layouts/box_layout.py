"""Stack controls along one axis with BoxLayout."""

from swingset import App
from swingset import BoxAxis
from swingset import BoxLayout
from swingset import Button
from swingset import Frame
from swingset import Label
from swingset import Size


def build() -> None:
    """Build the BoxLayout example."""
    frame = Frame("BoxLayout example")
    frame.size = Size(380, 260)
    frame.layout = BoxLayout(BoxAxis.Y, gap=12)
    frame.add(Label("A vertical box keeps each preferred height."))
    frame.add(Button("First action"))
    frame.add(Button("Second action"))
    frame.add(Button("Third action"))
    frame.visible = True


def build_toml() -> str:
    """Return the backend-independent TOML form of this example."""
    return """[config.app]
entry-window = "main"
[widgets.main]
type = "Window"
title = "Box Layout"
children = ["layout"]
[widgets.layout]
type = "VBox"
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
