"""Display controls with a Windows 95/98-inspired classic theme."""

from swingset import App
from swingset import Button
from swingset import CheckBox
from swingset import Frame
from swingset import GroupBox
from swingset import RadioButton
from swingset import RadioGroup
from swingset import Rect
from swingset import Size
from swingset import TextField
from swingset import Theme


def build() -> None:
    """Build the classic-theme example."""
    App.set_theme(Theme.CLASSIC)
    frame = Frame("Classic Windows theme")
    frame.size = Size(420, 300)

    group = frame.add(GroupBox("Options"))
    group.bounds = Rect(16, 16, 380, 150)
    group.add(CheckBox("Enable sounds", selected=True))
    radio_group = RadioGroup()
    group.add(RadioButton("Windows 95", group=radio_group, selected=True))
    group.add(RadioButton("Windows 98", group=radio_group))

    frame.add(TextField("C:\\WINDOWS")).bounds = Rect(20, 190, 250, 24)
    frame.add(Button("OK")).bounds = Rect(210, 230, 85, 28)
    frame.add(Button("Cancel")).bounds = Rect(305, 230, 85, 28)
    frame.visible = True


def build_toml() -> str:
    """Return the backend-independent TOML form of this example."""
    return """[config.app]
entry-window = "main"

[widgets.main]
type = "Window"
title = "Classic Theme"
children = ["demo"]

[widgets.demo]
type = "Label"
text = "Classic Theme built from TOML"
"""


if __name__ == "__main__":
    App.configure(backend="win32")
    App.run(build)
