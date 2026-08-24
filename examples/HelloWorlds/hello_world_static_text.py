"""Display the classic Hello World in a native static-text control."""

from swingset import App
from swingset import Frame
from swingset import Label
from swingset import Rect
from swingset import Size


def build() -> None:
    """Build the HelloWorldStaticText example."""
    frame = Frame("Hello World")
    frame.size = Size(300, 300)
    frame.add(Label("Hello, World!")).bounds = Rect(10, 10, 120, 23)
    frame.visible = True


def build_toml() -> str:
    """Return the backend-independent TOML form of this example."""
    return """[config.app]
entry-window = "main"

[widgets.main]
type = "Window"
title = "Hello World Static Text"
children = ["demo"]

[widgets.demo]
type = "Label"
text = "Hello World Static Text built from TOML"
"""


if __name__ == "__main__":
    App.configure(backend="win32")
    App.run(build)
