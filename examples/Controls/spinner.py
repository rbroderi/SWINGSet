"""Demonstrate a bounded native integer spinner."""

from swingset import App
from swingset import Frame
from swingset import Label
from swingset import Rect
from swingset import Size
from swingset import Spinner


def build() -> None:
    """Build the Spinner example."""
    frame = Frame("Spinner example")
    frame.size = Size(320, 160)

    prompt = frame.add(Label("Quantity:"))
    prompt.bounds = Rect(20, 25, 75, 23)
    spinner = frame.add(Spinner(minimum=0, maximum=50, value=10, step=5))
    spinner.bounds = Rect(100, 22, 100, 26)
    value = frame.add(Label("10"))
    value.bounds = Rect(215, 25, 70, 23)
    spinner.on_change(lambda current: setattr(value, "text", str(current)))
    frame.visible = True


def build_toml() -> str:
    """Return the backend-independent TOML form of this example."""
    return """[config.app]
entry-window = "main"

[widgets.main]
type = "Window"
title = "Spinner"
children = ["demo"]

[widgets.demo]
type = "Spinner"
minimum = 0
maximum = 10
value = 3
step = 1
"""


if __name__ == "__main__":
    App.configure(backend="win32")
    App.run(build)
