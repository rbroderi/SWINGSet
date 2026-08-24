"""Demonstrate native buttons and click events."""

from swingset import ActionEvent
from swingset import App
from swingset import Button
from swingset import Frame
from swingset import Label
from swingset import Rect
from swingset import Size


def build() -> None:
    """Build the Button example."""
    frame = Frame("Button example")
    frame.size = Size(300, 300)
    button1 = frame.add(Button("button1"))
    button1.bounds = Rect(50, 50, 75, 25)
    button2 = frame.add(Button("button2"))
    button2.bounds = Rect(50, 100, 200, 75)
    status = frame.add(Label("button1 clicked 0 times"))
    status.bounds = Rect(50, 200, 200, 23)
    clicks = 0

    def clicked(_event: ActionEvent[Button]) -> None:
        nonlocal clicks
        clicks += 1
        status.text = f"button1 clicked {clicks} times"

    button1.on_click(clicked)
    frame.visible = True


def build_toml() -> str:
    """Return the backend-independent TOML form of this example."""
    return """[config.app]
entry-window = "main"

[widgets.main]
type = "Window"
title = "Button"
children = ["demo"]

[widgets.demo]
type = "Button"
text = "Click me"
"""


if __name__ == "__main__":
    App.configure(backend="win32")
    App.run(build)
