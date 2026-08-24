"""Choose a font with the native Win32 font dialog."""

from swingset import App
from swingset import Button
from swingset import FontDialog
from swingset import Frame
from swingset import Label
from swingset import Rect
from swingset import Size


def build() -> None:
    """Build the FontDialog example."""
    frame = Frame("FontDialog example")
    frame.size = Size(360, 200)
    sample = frame.add(Label("The quick brown fox jumps over the lazy dog"))
    sample.bounds = Rect(20, 35, 320, 30)
    choose = frame.add(Button("Choose font"))
    choose.bounds = Rect(110, 100, 130, 30)

    def show_dialog(_event: object) -> None:
        selected = FontDialog().show(frame)
        if selected is not None:
            sample.set_font(selected.face, selected.size, bold=selected.bold)

    choose.on_click(show_dialog)
    frame.visible = True


def build_toml() -> str:
    """Return the backend-independent TOML form of this example."""
    return """[config.app]
entry-window = "main"

[widgets.main]
type = "Window"
title = "Font Dialog"
children = ["demo"]

[widgets.demo]
type = "Button"
text = "Show Font Dialog"
"""


if __name__ == "__main__":
    App.configure(backend="win32")
    App.run(build)
