"""Display Hello World through the native Win32 MessageBox API."""

from swingset import App
from swingset import Frame
from swingset import MessageBox
from swingset import MessageIcon
from swingset import Size


def build() -> None:
    """Build the HelloWorldMessageBox example."""
    frame = Frame("Hello World MessageBox")
    frame.size = Size(300, 300)
    frame.visible = True
    MessageBox.show(
        "Hello, World!",
        "Hello World",
        icon=MessageIcon.INFORMATION,
        owner=frame,
    )


def build_toml() -> str:
    """Return the backend-independent TOML form of this example."""
    return """[config.app]
entry-window = "main"

[widgets.main]
type = "Window"
title = "Hello World Message Box"
children = ["demo"]

[widgets.demo]
type = "Button"
text = "Show Hello World Message Box"
"""


if __name__ == "__main__":
    App.configure(backend="win32")
    App.run(build)
