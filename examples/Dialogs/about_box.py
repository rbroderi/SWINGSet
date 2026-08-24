"""Show a dedicated native-looking About dialog."""

from swingset import App
from swingset import Button
from swingset import Dialog
from swingset import Frame
from swingset import Label
from swingset import Rect
from swingset import Size


def build() -> None:
    """Build the AboutBox example."""
    frame = Frame("AboutBox example")
    frame.size = Size(320, 180)
    show = frame.add(Button("About"))
    show.bounds = Rect(105, 65, 110, 30)

    def show_about(_event: object) -> None:
        dialog = Dialog(frame, "About SWINGSet", modal=True)
        dialog.size = Size(300, 170)
        dialog.add(Label("SWINGSet Examples")).set_bounds(75, 30, 170, 24).set_font(
            bold=True
        )
        dialog.add(Label("Native Win32 controls in Python")).bounds = Rect(
            45, 62, 230, 24
        )
        close = dialog.add(Button("OK"))
        close.bounds = Rect(105, 105, 90, 28)
        close.on_click(lambda _click: dialog.dispose())
        dialog.visible = True

    show.on_click(show_about)
    frame.visible = True


def build_toml() -> str:
    """Return the backend-independent TOML form of this example."""
    return """[config.app]
entry-window = "main"

[widgets.main]
type = "Window"
title = "About Box"
children = ["demo"]

[widgets.demo]
type = "Button"
text = "Show About Box"
"""


if __name__ == "__main__":
    App.configure(backend="win32")
    App.run(build)
