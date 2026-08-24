"""Display native key events from an editable control."""

from swingset import App
from swingset import Frame
from swingset import Label
from swingset import Rect
from swingset import Size
from swingset import TextField


def build() -> None:
    """Build the KeyEvents example."""
    frame = Frame("KeyEvents example")
    frame.size = Size(420, 220)
    frame.add(Label("Type here:")).bounds = Rect(30, 35, 80, 24)
    field = frame.add(TextField(columns=28))
    field.bounds = Rect(110, 32, 250, 26)
    result = frame.add(Label("Waiting for a key"))
    result.bounds = Rect(30, 95, 340, 24)

    def report(event: object) -> None:
        key_code = getattr(event, "key_code", 0)
        char = getattr(event, "char", None)
        result.text = f"key_code={key_code}, char={char!r}"

    field.on_key(report)
    frame.visible = True
    field.focus()


def build_toml() -> str:
    """Return the backend-independent TOML form of this example."""
    return """[config.app]
entry-window = "main"

[widgets.main]
type = "Window"
title = "Key Events"
children = ["demo"]

[widgets.demo]
type = "TextField"
text = "Type here"
[widgets.demo.events]
key = "report_key"
"""


if __name__ == "__main__":
    App.configure(backend="win32")
    App.run(build)
