"""Find text with a modeless native-control dialog."""

from swingset import App
from swingset import Button
from swingset import Dialog
from swingset import Frame
from swingset import Label
from swingset import Rect
from swingset import Size
from swingset import TextArea
from swingset import TextField


def build() -> None:
    """Build the FindDialog example."""
    frame = Frame("FindDialog example")
    frame.size = Size(480, 300)
    document = frame.add(
        TextArea("The quick brown fox jumps over the lazy dog.", rows=7, columns=50)
    )
    document.bounds = Rect(20, 20, 430, 150)
    status = frame.add(Label("Ready"))
    status.bounds = Rect(20, 230, 420, 24)
    show = frame.add(Button("Find..."))
    show.bounds = Rect(180, 185, 110, 30)

    def open_find(_event: object) -> None:
        dialog = Dialog(frame, "Find")
        dialog.size = Size(360, 150)
        dialog.add(Label("Find what:")).bounds = Rect(15, 22, 80, 24)
        query = dialog.add(TextField(columns=24))
        query.bounds = Rect(95, 20, 170, 24)
        find_next = dialog.add(Button("Find Next"))
        find_next.bounds = Rect(270, 18, 80, 28)
        close = dialog.add(Button("Cancel"))
        close.bounds = Rect(270, 58, 80, 28)
        find_next.on_click(
            lambda _click: setattr(
                status, "text", f"Found at index {document.text.find(query.text)}"
            )
        )
        close.on_click(lambda _click: dialog.dispose())
        dialog.visible = True
        query.focus()

    show.on_click(open_find)
    frame.visible = True


def build_toml() -> str:
    """Return the backend-independent TOML form of this example."""
    return """[config.app]
entry-window = "main"

[widgets.main]
type = "Window"
title = "Find Dialog"
children = ["demo"]

[widgets.demo]
type = "Button"
text = "Show Find Dialog"
"""


if __name__ == "__main__":
    App.configure(backend="win32")
    App.run(build)
