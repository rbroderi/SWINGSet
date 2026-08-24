"""Update a native label from a repeating UI-thread timer."""

from swingset import App
from swingset import Frame
from swingset import Label
from swingset import Rect
from swingset import Size
from swingset import Timer


def build() -> None:
    """Build the Timer example."""
    frame = Frame("Timer example")
    frame.size = Size(300, 220)
    label = frame.add(Label("Timer tick: 0"))
    label.bounds = Rect(85, 75, 140, 24)
    tick = 0

    def update() -> None:
        nonlocal tick
        tick += 1
        label.text = f"Timer tick: {tick}"

    timer = Timer(1000, update)
    timer.start()
    frame.visible = True


def build_toml() -> str:
    """Return the backend-independent TOML form of this example."""
    return """[config.app]
entry-window = "main"

[widgets.main]
type = "Window"
title = "Timer"
children = ["demo"]

[widgets.demo]
type = "Label"
text = "Timer updates are registered in Python"
"""


if __name__ == "__main__":
    App.configure(backend="win32")
    App.run(build)
