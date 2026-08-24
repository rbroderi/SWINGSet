"""Choose a page range with the native Win32 print dialog."""

from swingset import App
from swingset import Button
from swingset import Frame
from swingset import Label
from swingset import PrintDialog
from swingset import PrintSettings
from swingset import Rect
from swingset import Size


def build() -> None:
    """Build the PrintDialog example."""
    frame = Frame("PrintDialog example")
    frame.size = Size(340, 190)
    result = frame.add(Label("No print settings selected"))
    result.bounds = Rect(55, 35, 240, 24)
    show = frame.add(Button("Print"))
    show.bounds = Rect(115, 90, 110, 30)

    def show_dialog(_event: object) -> None:
        settings = PrintDialog(PrintSettings(1, 10)).show(frame)
        if settings is not None:
            page_range = f"{settings.from_page}-{settings.to_page}"
            result.text = f"Pages {page_range}, copies: {settings.copies}"

    show.on_click(show_dialog)
    frame.visible = True


def build_toml() -> str:
    """Return the backend-independent TOML form of this example."""
    return """[config.app]
entry-window = "main"

[widgets.main]
type = "Window"
title = "Print Dialog"
children = ["demo"]

[widgets.demo]
type = "Button"
text = "Show Print Dialog"
"""


if __name__ == "__main__":
    App.configure(backend="win32")
    App.run(build)
