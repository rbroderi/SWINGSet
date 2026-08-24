"""Style ordinary controls with portable foreground and background colors."""

from swingset import App
from swingset import Button
from swingset import Frame
from swingset import Label
from swingset import Rect
from swingset import Size


def build() -> None:
    """Build the portable component-color example."""
    frame = Frame("Component colors")
    frame.size = Size(520, 220)
    heading = frame.add(Label("Portable colors on every component"))
    heading.foreground = "accent"
    heading.bounds = Rect(24, 24, 320, 24)

    primary = frame.add(Button("Primary action"))
    primary.background = "accent"
    primary.foreground = "background"
    primary.bounds = Rect(24, 72, 150, 32)

    warning = frame.add(Label("Semantic and literal colors can be mixed"))
    warning.background = "#fef3c7"
    warning.foreground = "#92400e"
    warning.bounds = Rect(194, 72, 290, 32)
    frame.visible = True


def build_toml() -> str:
    """Return the backend-independent TOML form of this example."""
    return """[config.app]
entry-window = "main"

[theme.colors]
primary = "#2563eb"
on-primary = "#ffffff"
warning = "#92400e"
warning-surface = "#fef3c7"

[style.primary]
background = "$primary"
foreground = "$on-primary"
font-weight = "bold"

[style.warning]
background = "$warning-surface"
foreground = "$warning"

[widgets.main]
type = "Window"
title = "Component colors"
children = ["content"]

[widgets.content]
type = "VBox"
gap = 12
children = ["heading", "primary", "warning"]

[widgets.heading]
type = "Label"
markdown = "**Portable colors** on every component"
foreground = "accent"

[widgets.primary]
type = "Button"
text = "Primary action"
styles = ["primary"]

[widgets.warning]
type = "Label"
text = "Semantic and literal colors can be mixed"
styles = ["warning"]
"""


if __name__ == "__main__":
    App.configure(backend="win32")
    App.run(build)
