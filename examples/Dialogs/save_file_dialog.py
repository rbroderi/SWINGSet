"""Choose a destination through the native save common dialog."""

from swingset import App
from swingset import Button
from swingset import FileFilter
from swingset import Frame
from swingset import Label
from swingset import Rect
from swingset import SaveFileDialog
from swingset import Size


def build() -> None:
    """Build the SaveFileDialog example."""
    frame = Frame("SaveFileDialog example")
    frame.size = Size(460, 220)
    result = frame.add(Label("No destination selected"))
    result.bounds = Rect(20, 75, 410, 24)
    choose = frame.add(Button("Save as..."))
    choose.bounds = Rect(20, 25, 100, 30)
    dialog = SaveFileDialog(filters=(FileFilter("Text files", "*.txt"),))

    def save_file(_event: object) -> None:
        selected = dialog.show(frame)
        result.text = "Cancelled" if selected is None else str(selected)

    choose.on_click(save_file)
    frame.visible = True


def build_toml() -> str:
    """Return the backend-independent TOML form of this example."""
    return """[config.app]
entry-window = "main"

[widgets.main]
type = "Window"
title = "Save File Dialog"
children = ["demo"]

[widgets.demo]
type = "Button"
text = "Show Save File Dialog"
"""


if __name__ == "__main__":
    App.configure(backend="win32")
    App.run(build)
