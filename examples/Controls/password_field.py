"""Demonstrate a native masked password field with reveal control."""

from swingset import App
from swingset import Button
from swingset import Frame
from swingset import Label
from swingset import PasswordField
from swingset import Rect
from swingset import Size


def build() -> None:
    """Build the PasswordField example."""
    frame = Frame("PasswordField example")
    frame.size = Size(360, 170)

    prompt = frame.add(Label("Password:"))
    prompt.bounds = Rect(20, 24, 80, 23)
    password = frame.add(PasswordField("correct horse", columns=24))
    password.bounds = Rect(105, 22, 210, 25)
    password.tooltip = "The password is masked until Reveal is pressed."
    reveal = frame.add(Button("Reveal"))
    reveal.bounds = Rect(105, 62, 90, 28)

    def toggle_reveal(_event: object) -> None:
        password.revealed = not password.revealed
        reveal.text = "Hide" if password.revealed else "Reveal"

    reveal.on_click(toggle_reveal)
    frame.visible = True


def build_toml() -> str:
    """Return the backend-independent TOML form of this example."""
    return """[config.app]
entry-window = "main"

[widgets.main]
type = "Window"
title = "Password Field"
children = ["demo"]

[widgets.demo]
type = "PasswordField"
text = "secret"
revealed = false
"""


if __name__ == "__main__":
    App.configure(backend="win32")
    App.run(build)
