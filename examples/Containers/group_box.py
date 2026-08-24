"""Group controls inside native Win32 group boxes."""

from swingset import App
from swingset import CheckBox
from swingset import Frame
from swingset import GroupBox
from swingset import Rect
from swingset import Size


def build() -> None:
    """Build the GroupBox example."""
    frame = Frame("GroupBox example")
    frame.size = Size(360, 260)
    group = frame.add(GroupBox("Options"))
    group.bounds = Rect(20, 20, 300, 150)
    group.add(CheckBox("First option", selected=True))
    group.add(CheckBox("Second option"))
    frame.visible = True


def build_toml() -> str:
    """Return the backend-independent TOML form of this example."""
    return """[config.app]
entry-window = "main"

[widgets.main]
type = "Window"
title = "Group Box"
children = ["demo"]

[widgets.demo]
type = "GroupBox"
title = "Options"
children = ["option"]
[widgets.option]
type = "CheckBox"
text = "Portable option"
"""


if __name__ == "__main__":
    App.configure(backend="win32")
    App.run(build)
