"""Configure page margins with the native Win32 page-setup dialog."""

from swingset import App
from swingset import Button
from swingset import Frame
from swingset import Label
from swingset import PageSetupDialog
from swingset import Rect
from swingset import Size


def build() -> None:
    """Build the PageSetupDialog example."""
    frame = Frame("PageSetupDialog example")
    frame.size = Size(360, 190)
    result = frame.add(Label("Margins: 1.00, 1.00, 1.00, 1.00 inches"))
    result.bounds = Rect(30, 35, 300, 24)
    show = frame.add(Button("Page setup"))
    show.bounds = Rect(110, 90, 130, 30)

    def show_dialog(_event: object) -> None:
        margins = PageSetupDialog().show(frame)
        if margins is not None:
            values = (margins.left, margins.top, margins.right, margins.bottom)
            result.text = (
                "Margins: "
                + ", ".join(f"{value / 1000:.2f}" for value in values)
                + " inches"
            )

    show.on_click(show_dialog)
    frame.visible = True


def build_toml() -> str:
    """Return the backend-independent TOML form of this example."""
    return """[config.app]
entry-window = "main"

[widgets.main]
type = "Window"
title = "Page Setup Dialog"
children = ["demo"]

[widgets.demo]
type = "Button"
text = "Show Page Setup Dialog"
"""


if __name__ == "__main__":
    App.configure(backend="win32")
    App.run(build)
