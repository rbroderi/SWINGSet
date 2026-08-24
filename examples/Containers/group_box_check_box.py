"""Combine a group box with native check boxes."""

from swingset import App
from swingset import CheckBox
from swingset import Frame
from swingset import GroupBox
from swingset import Rect
from swingset import Size


def build() -> None:
    """Build the GroupBoxCheckBox example."""
    frame = Frame("GroupBox and CheckBox example")
    frame.size = Size(360, 240)
    group = frame.add(GroupBox("Pizza toppings"))
    group.bounds = Rect(30, 25, 290, 145)
    group.add(CheckBox("Cheese", selected=True))
    group.add(CheckBox("Mushrooms"))
    group.add(CheckBox("Peppers"))
    frame.visible = True


def build_toml() -> str:
    """Return the backend-independent TOML form of this example."""
    return """[config.app]
entry-window = "main"

[widgets.main]
type = "Window"
title = "Group Box Check Box"
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
