"""Arrange controls in the five BorderLayout regions."""

from swingset import App
from swingset import BorderLayout
from swingset import Button
from swingset import Frame
from swingset import Label
from swingset import Size
from swingset import TextArea


def build() -> None:
    """Build the BorderLayout example."""
    frame = Frame("BorderLayout example")
    frame.size = Size(520, 340)
    frame.layout = BorderLayout(hgap=8, vgap=8)

    header = Label("NORTH: application header")
    header.height = 36
    frame.add(header, BorderLayout.NORTH)

    footer = Label("SOUTH: status information")
    footer.height = 30
    frame.add(footer, BorderLayout.SOUTH)

    west = Button("WEST")
    west.width = 90
    frame.add(west, BorderLayout.WEST)

    east = Button("EAST")
    east.width = 90
    frame.add(east, BorderLayout.EAST)

    frame.add(
        TextArea("CENTER expands when the window is resized."), BorderLayout.CENTER
    )
    frame.visible = True


def build_toml() -> str:
    """Return the backend-independent TOML form of this example."""
    return """[config.app]
entry-window = "main"
[widgets.main]
type = "Window"
title = "Border Layout"
children = ["layout"]
[widgets.layout]
type = "BorderLayout"
children = ["north", "center"]
[widgets.north]
type = "Label"
text = "North"
constraint = "north"
[widgets.center]
type = "Button"
text = "Center"
constraint = "center"
"""


if __name__ == "__main__":
    App.configure(backend="win32")
    App.run(build)
