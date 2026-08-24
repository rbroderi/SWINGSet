"""Create the smallest native SWINGSet application."""

from swingset import App
from swingset import Frame
from swingset import Size


def build() -> None:
    """Build the Application example."""
    frame = Frame("Application example")
    frame.size = Size(640, 480)
    frame.visible = True


def build_toml() -> str:
    """Return the backend-independent TOML form of this example."""
    return """[config.app]
entry-window = "main"

[widgets.main]
type = "Window"
title = "Application"
children = ["demo"]

[widgets.demo]
type = "Label"
text = "Application built from TOML"
"""


if __name__ == "__main__":
    App.configure(backend="win32")
    App.run(build)
