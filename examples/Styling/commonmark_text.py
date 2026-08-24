"""Render CommonMark on ordinary controls and a rich text pane."""

from swingset import App
from swingset import Frame
from swingset import Label
from swingset import Rect
from swingset import RichTextPane
from swingset import Size


def build() -> None:
    """Build the portable CommonMark example."""
    frame = Frame("CommonMark text")
    frame.size = Size(580, 340)

    summary = frame.add(Label())
    summary.set_markdown("**Bold**, *italic*, and `inline code` work on labels")
    summary.bounds = Rect(24, 20, 520, 28)

    document = frame.add(RichTextPane(rows=10, columns=56, editable=False))
    document.set_markdown(
        "# Portable rich text\n\n"
        "- strong **emphasis**\n"
        "- [underlined links](https://example.com)\n"
        "- fenced and inline `code`"
    )
    document.bounds = Rect(24, 64, 520, 230)
    frame.visible = True


def build_toml() -> str:
    """Return the backend-independent TOML form of this example."""
    return """[config.app]
entry-window = "main"

[widgets.main]
type = "Window"
title = "CommonMark text"
children = ["content"]

[widgets.content]
type = "VBox"
gap = 12
children = ["summary", "document"]

[widgets.summary]
type = "Label"
markdown = "**Bold**, *italic*, and `inline code` work on labels"

[widgets.document]
type = "RichTextPane"
markdown = '''# Portable rich text

- strong **emphasis**
- [underlined links](https://example.com)
- fenced and inline `code`'''
rows = 10
columns = 56
editable = false
"""


if __name__ == "__main__":
    App.configure(backend="win32")
    App.run(build)
