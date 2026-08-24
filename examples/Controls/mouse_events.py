"""Display native mouse events from a button control."""

from swingset import App
from swingset import Button
from swingset import Frame
from swingset import Label
from swingset import Rect
from swingset import Size


def build() -> None:
    """Build the MouseEvents example."""
    frame = Frame("MouseEvents example")
    frame.size = Size(420, 240)
    target = frame.add(Button("Move and click here"))
    target.bounds = Rect(95, 45, 230, 70)
    result = frame.add(Label("Waiting for the mouse"))
    result.bounds = Rect(60, 145, 300, 24)

    def report(event: object) -> None:
        x = getattr(event, "x", 0)
        y = getattr(event, "y", 0)
        button = getattr(event, "button", 0)
        result.text = f"x={x}, y={y}, button={button}"

    target.on_mouse(report)
    frame.visible = True


def build_toml() -> str:
    """Return the backend-independent TOML form of this example."""
    return """[config.app]
entry-window = "main"

[widgets.main]
type = "Window"
title = "Mouse Events"
children = ["demo"]

[widgets.demo]
type = "Label"
text = "Move or click here"
[widgets.demo.events]
mouse = "report_mouse"
"""


if __name__ == "__main__":
    App.configure(backend="win32")
    App.run(build)
