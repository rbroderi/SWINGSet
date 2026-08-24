"""Create a native-looking toolbar above an editor area."""

from swingset import ActionEvent
from swingset import App
from swingset import BorderLayout
from swingset import Button
from swingset import Frame
from swingset import Size
from swingset import TextArea
from swingset import ToolBar


def build() -> None:
    """Build the Toolbar example."""
    frame = Frame("Toolbar example")
    frame.size = Size(640, 480)
    frame.layout = BorderLayout(vgap=0)
    toolbar = frame.add(ToolBar(), BorderLayout.NORTH)
    editor = frame.add(TextArea(rows=16, columns=60), BorderLayout.CENTER)

    for command in ("New", "Open...", "Save", "Print...", "About..."):
        button = toolbar.add_button(command)

        def report(event: ActionEvent[Button], name: str = command) -> None:
            editor.text = f"{name.replace('&', '')} selected\r\n{editor.text}"

        button.on_click(report)

    frame.visible = True


def build_toml() -> str:
    """Return the backend-independent TOML form of this example."""
    return """[config.app]
entry-window = "main"

[widgets.main]
type = "Window"
title = "Toolbar"
children = ["demo"]

[widgets.demo]
type = "ToolBar"
children = ["action"]

[widgets.action]
type = "Button"
text = "Action"
"""


if __name__ == "__main__":
    App.configure(backend="win32")
    App.run(build)
