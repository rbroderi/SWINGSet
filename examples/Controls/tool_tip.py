"""Demonstrate native hover tooltips shared by every component."""

from swingset import App
from swingset import Button
from swingset import Frame
from swingset import Label
from swingset import Rect
from swingset import Size


def build() -> None:
    """Build the ToolTip example."""
    frame = Frame("ToolTip example")
    frame.size = Size(360, 170)

    instruction = frame.add(Label("Hover over either control."))
    instruction.bounds = Rect(20, 20, 220, 23)
    instruction.tooltip = "Tooltips are available on every SWINGSet component."
    action = frame.add(Button("Inspect"))
    action.bounds = Rect(20, 62, 100, 30)
    action.tooltip = "This is a native Win32 tooltip."
    frame.visible = True


def build_toml() -> str:
    """Return the backend-independent TOML form of this example."""
    return """[config.app]
entry-window = "main"

[widgets.main]
type = "Window"
title = "Tool Tip"
children = ["demo"]

[widgets.demo]
type = "Button"
text = "Hover me"
tooltip = "Portable tool tip"
"""


if __name__ == "__main__":
    App.configure(backend="win32")
    App.run(build)
