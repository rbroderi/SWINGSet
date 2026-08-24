"""Place two native panel surfaces side by side."""

from swingset import App
from swingset import Frame
from swingset import Label
from swingset import Panel
from swingset import Rect
from swingset import Size


def build() -> None:
    """Build the Panel example."""
    frame = Frame("Panel example")
    frame.size = Size(656, 521)

    left = frame.add(Panel())
    left.bounds = Rect(10, 10, 305, 460)
    left.add(Label("Panel 1"))

    right = frame.add(Panel())
    right.bounds = Rect(325, 10, 305, 460)
    right.add(Label("Panel 2"))
    frame.visible = True


def build_toml() -> str:
    """Return the backend-independent TOML form of this example."""
    return """[config.app]
entry-window = "main"

[widgets.main]
type = "Window"
title = "Panel"
children = ["demo"]

[widgets.demo]
type = "Panel"
children = ["message"]
[widgets.message]
type = "Label"
text = "Panel content"
"""


if __name__ == "__main__":
    App.configure(backend="win32")
    App.run(build)
