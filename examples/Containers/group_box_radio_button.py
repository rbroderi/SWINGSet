"""Combine a group box with an exclusive native radio-button group."""

from swingset import App
from swingset import Frame
from swingset import GroupBox
from swingset import RadioButton
from swingset import RadioGroup
from swingset import Rect
from swingset import Size


def build() -> None:
    """Build the GroupBoxRadioButton example."""
    frame = Frame("GroupBox and RadioButton example")
    frame.size = Size(360, 240)
    group_box = frame.add(GroupBox("Delivery speed"))
    group_box.bounds = Rect(30, 25, 290, 145)
    radio_group = RadioGroup()
    group_box.add(RadioButton("Standard", group=radio_group, selected=True))
    group_box.add(RadioButton("Express", group=radio_group))
    group_box.add(RadioButton("Overnight", group=radio_group))
    frame.visible = True


def build_toml() -> str:
    """Return the backend-independent TOML form of this example."""
    return """[config.app]
entry-window = "main"

[widgets.main]
type = "Window"
title = "Group Box Radio Button"
children = ["demo"]

[widgets.demo]
type = "GroupBox"
title = "Options"
children = ["option"]
[widgets.option]
type = "RadioButton"
text = "Portable option"
group-id = "options"
"""


if __name__ == "__main__":
    App.configure(backend="win32")
    App.run(build)
