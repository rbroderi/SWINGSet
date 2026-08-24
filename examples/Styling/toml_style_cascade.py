"""Build a styled interface from TOML defaults, inheritance, and theme values."""

from swingset import App
from swingset import TomlUILoader


def build_toml() -> str:
    """Return the complete backend-independent styled interface."""
    return """[config.app]
entry-window = "main"

[theme.colors]
brand = "#0f766e"
on-brand = "#ffffff"
surface = [240, 253, 250]
muted = "#475569"

[style.defaults.Label]
foreground = "$muted"

[style.control]
min-width = 140
font-size = 10

[style.primary]
extends = ["control"]
background = "$brand"
foreground = "$on-brand"
font-weight = "bold"

[style.surface]
background = "$surface"
foreground = "$brand"

[widgets.main]
type = "Window"
title = "TOML style cascade"
children = ["content"]

[widgets.content]
type = "VBox"
gap = 12
children = ["heading", "description", "action"]

[widgets.heading]
type = "Label"
markdown = "## Theme values and inherited styles"
styles = ["surface"]

[widgets.description]
type = "Label"
text = "Defaults apply first; named and local styles override them."

[widgets.action]
type = "Button"
text = "Styled action"
styles = ["primary"]

[widgets.action.style]
min-width = 180
"""


def build() -> None:
    """Compile the embedded TOML and show its root window."""
    loaded = TomlUILoader().loads(build_toml(), filename=__file__)
    loaded.root.visible = True


if __name__ == "__main__":
    App.configure(backend="win32")
    App.run(build)
