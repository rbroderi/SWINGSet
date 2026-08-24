"""Show the second Hello World native message-box variant."""

from swingset import App
from swingset import MessageBox
from swingset import MessageIcon


def build() -> None:
    """Build the HelloWorldMessageBox2 example."""
    MessageBox.show(
        "Hello, World!\nWelcome to SWINGSet.",
        "Hello World 2",
        icon=MessageIcon.INFORMATION,
    )


def build_toml() -> str:
    """Return the backend-independent TOML form of this example."""
    return """[config.app]
entry-window = "main"

[widgets.main]
type = "Window"
title = "Hello World Message Box 2"
children = ["demo"]

[widgets.demo]
type = "Button"
text = "Show Hello World Message Box 2"
"""


if __name__ == "__main__":
    App.configure(backend="win32")
    App.run(build)
