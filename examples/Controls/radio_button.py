"""Select one option from a native radio-button group."""

from swingset import App
from swingset import Frame
from swingset import RadioButton
from swingset import RadioGroup
from swingset import Rect
from swingset import Size


def build() -> None:
    """Build the RadioButton example."""
    frame = Frame("RadioButton example")
    frame.size = Size(300, 240)
    group = RadioGroup()
    first = frame.add(RadioButton("Radio button 1", group=group, selected=True))
    first.bounds = Rect(30, 35, 180, 24)
    second = frame.add(RadioButton("Radio button 2", group=group))
    second.bounds = Rect(30, 70, 180, 24)
    third = frame.add(RadioButton("Radio button 3", group=group))
    third.bounds = Rect(30, 105, 180, 24)
    frame.visible = True


def build_toml() -> str:
    """Return the backend-independent TOML form of this example."""
    return """[config.app]
entry-window = "main"

[widgets.main]
type = "Window"
title = "Radio Button"
children = ["demo"]

[widgets.demo]
type = "RadioButton"
text = "Choice"
selected = true
group-id = "choices"
"""


if __name__ == "__main__":
    App.configure(backend="win32")
    App.run(build)
