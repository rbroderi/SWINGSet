"""Show native message-box button and icon options."""

from swingset import App
from swingset import Button
from swingset import Frame
from swingset import MessageBox
from swingset import MessageButtons
from swingset import MessageIcon
from swingset import Rect
from swingset import Size


def build() -> None:
    """Build the MessageBox example."""
    frame = Frame("MessageBox example")
    frame.size = Size(300, 300)
    show = frame.add(Button("Show message box"))
    show.bounds = Rect(75, 100, 150, 30)

    def show_message(_event: object) -> None:
        MessageBox.show(
            "Do you like native controls?",
            "Question",
            buttons=MessageButtons.YES_NO,
            icon=MessageIcon.QUESTION,
            owner=frame,
        )

    show.on_click(show_message)
    frame.visible = True


def build_toml() -> str:
    """Return the backend-independent TOML form of this example."""
    return """[config.app]
entry-window = "main"

[widgets.main]
type = "Window"
title = "Message Box"
children = ["demo"]

[widgets.demo]
type = "Button"
text = "Show Message Box"
"""


if __name__ == "__main__":
    App.configure(backend="win32")
    App.run(build)
