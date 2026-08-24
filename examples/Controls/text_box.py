"""Demonstrate native single-line text boxes."""

from swingset import App
from swingset import Frame
from swingset import Rect
from swingset import Size
from swingset import TextField


def build() -> None:
    """Build the TextBox example."""
    frame = Frame("TextBox example")
    frame.size = Size(300, 300)
    first = frame.add(TextField("textBox"))
    first.bounds = Rect(10, 10, 100, 23)
    second = frame.add(TextField("textBox"))
    second.bounds = Rect(10, 50, 100, 23)
    frame.visible = True


def build_toml() -> str:
    """Return the backend-independent TOML form of this example."""
    return """[config.app]
entry-window = "main"

[widgets.main]
type = "Window"
title = "Text Box"
children = ["demo"]

[widgets.demo]
type = "TextField"
text = "Editable text"
columns = 24
"""


if __name__ == "__main__":
    App.configure(backend="win32")
    App.run(build)
