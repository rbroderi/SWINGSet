"""Create a resizable native top-level window."""

from swingset import App
from swingset import Frame
from swingset import Size


def build() -> None:
    """Build the Window example."""
    window = Frame("Window example")
    window.size = Size(640, 480)
    window.visible = True


def build_toml() -> str:
    """Return the backend-independent TOML form of this example."""
    return """[config.app]
entry-window = "main"

[widgets.main]
type = "Window"
title = "Window"
children = ["demo"]

[widgets.demo]
type = "Label"
text = "Window built from TOML"
"""


if __name__ == "__main__":
    App.configure(backend="win32")
    App.run(build)
