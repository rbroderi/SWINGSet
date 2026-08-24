"""Show a second native message-box button and icon combination."""

from swingset import App
from swingset import Button
from swingset import Frame
from swingset import Label
from swingset import MessageBox
from swingset import MessageButtons
from swingset import MessageIcon
from swingset import Rect
from swingset import Size


def build() -> None:
    """Build the MessageBox2 example."""
    frame = Frame("MessageBox2 example")
    frame.size = Size(340, 210)
    result = frame.add(Label("No answer yet"))
    result.bounds = Rect(105, 35, 160, 24)
    show = frame.add(Button("Ask question"))
    show.bounds = Rect(100, 90, 140, 30)

    def show_message(_event: object) -> None:
        answer = MessageBox.show(
            "Save your changes before closing?",
            "MessageBox2",
            buttons=MessageButtons.YES_NO_CANCEL,
            icon=MessageIcon.WARNING,
            owner=frame,
        )
        result.text = f"Selected: {answer.value}"

    show.on_click(show_message)
    frame.visible = True


def build_toml() -> str:
    """Return the backend-independent TOML form of this example."""
    return """[config.app]
entry-window = "main"

[widgets.main]
type = "Window"
title = "Message Box 2"
children = ["demo"]

[widgets.demo]
type = "Button"
text = "Show Message Box 2"
"""


if __name__ == "__main__":
    App.configure(backend="win32")
    App.run(build)
