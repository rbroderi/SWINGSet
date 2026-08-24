"""Observe the application-idle event after startup work drains."""

from swingset import App
from swingset import Frame
from swingset import Label
from swingset import Rect
from swingset import Size


def build() -> None:
    """Build the ApplicationIdle example."""
    frame = Frame("ApplicationIdle example")
    frame.size = Size(420, 190)
    status = frame.add(Label("Waiting for the application to become idle..."))
    status.bounds = Rect(55, 65, 330, 24)
    count = 0

    def report_idle() -> None:
        nonlocal count
        count += 1
        status.text = f"Application idle event received ({count})"

    App.on_idle(report_idle)
    frame.visible = True


def build_toml() -> str:
    """Return the backend-independent TOML form of this example."""
    return """[config.app]
entry-window = "main"

[widgets.main]
type = "Window"
title = "Application Idle"
children = ["demo"]

[widgets.demo]
type = "Label"
text = "Application Idle built from TOML"
"""


if __name__ == "__main__":
    App.configure(backend="win32")
    App.run(build)
