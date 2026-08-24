"""Demonstrate native unchecked and checked boxes."""

from swingset import App
from swingset import CheckBox
from swingset import Frame
from swingset import Rect
from swingset import Size


def build() -> None:
    """Build the CheckBox example."""
    frame = Frame("CheckBox example")
    frame.size = Size(300, 300)
    unchecked = frame.add(CheckBox("Unchecked"))
    unchecked.bounds = Rect(30, 30, 104, 24)
    checked = frame.add(CheckBox("Checked", selected=True))
    checked.bounds = Rect(30, 60, 104, 24)
    frame.visible = True


def build_toml() -> str:
    """Return the backend-independent TOML form of this example."""
    return """[config.app]
entry-window = "main"

[widgets.main]
type = "Window"
title = "Check Box"
children = ["demo"]

[widgets.demo]
type = "CheckBox"
text = "Enable feature"
selected = true
"""


if __name__ == "__main__":
    App.configure(backend="win32")
    App.run(build)
