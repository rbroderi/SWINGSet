"""Choose a color with the native Win32 color dialog."""

from swingset import App
from swingset import Button
from swingset import ColorDialog
from swingset import Frame
from swingset import Label
from swingset import Rect
from swingset import Size


def build() -> None:
    """Build the ColorDialog example."""
    frame = Frame("ColorDialog example")
    frame.size = Size(320, 180)
    result = frame.add(Label("Selected color: (0, 0, 0)"))
    result.bounds = Rect(30, 30, 250, 24)
    choose = frame.add(Button("Choose color"))
    choose.bounds = Rect(90, 80, 130, 30)

    def show_dialog(_event: object) -> None:
        selected = ColorDialog().show(frame)
        if selected is not None:
            result.text = f"Selected color: {selected}"

    choose.on_click(show_dialog)
    frame.visible = True


def build_toml() -> str:
    """Return the backend-independent TOML form of this example."""
    return """[config.app]
entry-window = "main"

[widgets.main]
type = "Window"
title = "Color Dialog"
children = ["demo"]

[widgets.demo]
type = "Button"
text = "Show Color Dialog"
"""


if __name__ == "__main__":
    App.configure(backend="win32")
    App.run(build)
