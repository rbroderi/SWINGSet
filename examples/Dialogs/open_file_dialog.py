"""Select an existing file through the native common dialog."""

from swingset import App
from swingset import Button
from swingset import FileFilter
from swingset import Frame
from swingset import Label
from swingset import OpenFileDialog
from swingset import Rect
from swingset import Size


def build() -> None:
    """Build the OpenFileDialog example."""
    frame = Frame("OpenFileDialog example")
    frame.size = Size(460, 220)
    result = frame.add(Label("No file selected"))
    result.bounds = Rect(20, 75, 410, 24)
    choose = frame.add(Button("Open..."))
    choose.bounds = Rect(20, 25, 100, 30)
    dialog = OpenFileDialog(
        filters=(FileFilter("Text files", "*.txt"), FileFilter("All files", "*.*"))
    )

    def open_file(_event: object) -> None:
        selected = dialog.show(frame)
        result.text = "Cancelled" if selected is None else str(selected)

    choose.on_click(open_file)
    frame.visible = True


def build_toml() -> str:
    """Return the backend-independent TOML form of this example."""
    return """[config.app]
entry-window = "main"

[widgets.main]
type = "Window"
title = "Open File Dialog"
children = ["demo"]

[widgets.demo]
type = "Button"
text = "Show Open File Dialog"
"""


if __name__ == "__main__":
    App.configure(backend="win32")
    App.run(build)
