"""Find and replace text with a modeless native-control dialog."""

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
    """Build the ReplaceDialog example."""
    frame = Frame("ReplaceDialog example")
    frame.size = Size(500, 310)
    document = frame.add(
        TextArea("one fish, two fish, red fish, blue fish", rows=7, columns=52)
    )
    document.bounds = Rect(20, 20, 450, 150)
    show = frame.add(Button("Replace..."))
    show.bounds = Rect(190, 190, 120, 30)

    def open_replace(_event: object) -> None:
        dialog = Dialog(frame, "Replace")
        dialog.size = Size(400, 190)
        dialog.add(Label("Find what:")).bounds = Rect(15, 22, 90, 24)
        find = dialog.add(TextField(columns=24))
        find.bounds = Rect(105, 20, 170, 24)
        dialog.add(Label("Replace with:")).bounds = Rect(15, 58, 90, 24)
        replacement = dialog.add(TextField(columns=24))
        replacement.bounds = Rect(105, 56, 170, 24)
        replace = dialog.add(Button("Replace"))
        replace.bounds = Rect(290, 18, 95, 28)
        replace_all = dialog.add(Button("Replace All"))
        replace_all.bounds = Rect(290, 54, 95, 28)
        close = dialog.add(Button("Cancel"))
        close.bounds = Rect(290, 90, 95, 28)
        replace.on_click(
            lambda _click: setattr(
                document, "text", document.text.replace(find.text, replacement.text, 1)
            )
        )
        replace_all.on_click(
            lambda _click: setattr(
                document, "text", document.text.replace(find.text, replacement.text)
            )
        )
        close.on_click(lambda _click: dialog.dispose())
        dialog.visible = True
        find.focus()

    show.on_click(open_replace)
    frame.visible = True


def build_toml() -> str:
    """Return the backend-independent TOML form of this example."""
    return """[config.app]
entry-window = "main"

[widgets.main]
type = "Window"
title = "Replace Dialog"
children = ["demo"]

[widgets.demo]
type = "Button"
text = "Show Replace Dialog"
"""


if __name__ == "__main__":
    App.configure(backend="win32")
    App.run(build)
