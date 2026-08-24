"""Set a native application-window icon from a portable image resource."""

from swingset import App
from swingset import Frame
from swingset import Label
from swingset import Rect
from swingset import Size
from swingset import SvgImage

_ICON = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">
<rect width="64" height="64" rx="8" fill="#0b6a88"/>
<path d="M13 18h38v28H13z" fill="#fff"/>
<path d="M18 24h28v4H18zm0 8h18v4H18zm0 8h24v3H18z" fill="#0b6a88"/>
</svg>"""


def build() -> None:
    """Build the ApplicationIcon example."""
    frame = Frame("ApplicationIcon example")
    frame.size = Size(420, 220)
    frame.icon = SvgImage(_ICON, size=(32, 32), fallback="SWINGSet")
    frame.add(Label("The title bar and taskbar use the SWINGSet icon.")).bounds = Rect(
        45, 75, 330, 24
    )
    frame.visible = True


def build_toml() -> str:
    """Return the backend-independent TOML form of this example."""
    return """[config.app]
entry-window = "main"
[resources.icons]
app = "../assets/sample.svg"
[widgets.main]
type = "Window"
title = "Application Icon"
icon = "app"
children = ["message"]
[widgets.message]
type = "Label"
text = "Window icon loaded from a logical resource"
"""


if __name__ == "__main__":
    App.configure(backend="win32")
    App.run(build)
