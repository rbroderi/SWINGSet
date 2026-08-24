"""Demonstrate portable colors and CommonMark text styling."""

from swingset import App
from swingset import Button
from swingset import Frame
from swingset import Label
from swingset import Rect
from swingset import RichTextPane
from swingset import RichTextStyle
from swingset import Size


def build() -> None:
    """Build the RichTextPane example."""
    frame = Frame("RichTextPane example")
    frame.size = Size(560, 360)

    heading = frame.add(Label())
    heading.set_markdown("**Portable colors** on ordinary controls")
    heading.foreground = "accent"
    heading.bounds = Rect(20, 18, 340, 24)

    action = frame.add(Button())
    action.set_markdown("**Styled** action")
    action.background = "accent"
    action.foreground = "background"
    action.bounds = Rect(390, 14, 130, 30)

    pane = RichTextPane(rows=10, columns=52)
    pane.set_markdown(
        "# CommonMark\n\n"
        "- **bold** and *italic* emphasis\n"
        "- [underlined links](https://example.com)\n"
        "- inline `code` with a background"
    )
    color_start = pane.snapshot_text().index("CommonMark")
    pane.add_style(
        color_start,
        color_start + len("CommonMark"),
        RichTextStyle(bold=True, foreground="#1d4ed8"),
    )
    frame.add(pane)
    pane.bounds = Rect(20, 62, 500, 230)
    frame.visible = True


def build_toml() -> str:
    """Return the backend-independent TOML form of this example."""
    return """[config.app]
entry-window = "main"

[widgets.main]
type = "Window"
title = "Rich Text Pane"
children = ["demo"]

[widgets.demo]
type = "RichTextPane"
markdown = "# CommonMark\\n\\n**Bold**, *italic*, and `code`."
editable = false
"""


if __name__ == "__main__":
    App.configure(backend="win32")
    App.run(build)
