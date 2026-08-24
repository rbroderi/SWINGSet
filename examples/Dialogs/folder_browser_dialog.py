"""Choose a folder through the native shell browser."""

from swingset import App
from swingset import Button
from swingset import FolderBrowserDialog
from swingset import Frame
from swingset import Label
from swingset import Rect
from swingset import Size


def build() -> None:
    """Build the FolderBrowserDialog example."""
    frame = Frame("FolderBrowserDialog example")
    frame.size = Size(460, 220)
    result = frame.add(Label("No folder selected"))
    result.bounds = Rect(20, 75, 410, 24)
    choose = frame.add(Button("Browse..."))
    choose.bounds = Rect(20, 25, 100, 30)
    dialog = FolderBrowserDialog()

    def choose_folder(_event: object) -> None:
        selected = dialog.show(frame)
        result.text = "Cancelled" if selected is None else str(selected)

    choose.on_click(choose_folder)
    frame.visible = True


def build_toml() -> str:
    """Return the backend-independent TOML form of this example."""
    return """[config.app]
entry-window = "main"

[widgets.main]
type = "Window"
title = "Folder Browser Dialog"
children = ["demo"]

[widgets.demo]
type = "Button"
text = "Show Folder Browser Dialog"
"""


if __name__ == "__main__":
    App.configure(backend="win32")
    App.run(build)
