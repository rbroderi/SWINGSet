"""Show a Unicode Hello World with emoticons."""

from swingset import App
from swingset import Frame
from swingset import Label
from swingset import Rect
from swingset import Size


def build() -> None:
    """Build the HelloWorldEmoticons example."""
    frame = Frame("Hello World Emoticons")
    frame.size = Size(420, 180)
    greeting = frame.add(Label("Hello, World! 😀 🌍 🚀"))
    greeting.bounds = Rect(85, 55, 260, 40)
    greeting.set_font("Segoe UI Emoji", 18)
    frame.visible = True


def build_toml() -> str:
    """Return the backend-independent TOML form of this example."""
    return """[config.app]
entry-window = "main"

[widgets.main]
type = "Window"
title = "Hello World Emoticons"
children = ["demo"]

[widgets.demo]
type = "Label"
text = "Hello World Emoticons built from TOML"
"""


if __name__ == "__main__":
    App.configure(backend="win32")
    App.run(build)
