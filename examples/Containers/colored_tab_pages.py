"""Create native tab pages with individual background colors."""

from swingset import App
from swingset import Frame
from swingset import Label
from swingset import Panel
from swingset import Rect
from swingset import Size
from swingset import TabbedPane


def page(text: str) -> Panel:
    """Create one manually positioned tab page."""
    panel = Panel()
    panel.layout = None
    panel.add(Label(text)).bounds = Rect(100, 80, 180, 24)
    return panel


def build() -> None:
    """Build the ColoredTabPages example."""
    frame = Frame("ColoredTabPages example")
    frame.size = Size(440, 330)
    tabs = frame.add(TabbedPane())
    tabs.bounds = Rect(15, 15, 395, 260)
    tabs.add_tab("Red", page("Red tab page"), background=(255, 205, 205))
    tabs.add_tab("Green", page("Green tab page"), background=(205, 245, 210))
    tabs.add_tab("Blue", page("Blue tab page"), background=(205, 225, 255))
    frame.visible = True


def build_toml() -> str:
    """Return the backend-independent TOML form of this example."""
    return """[config.app]
entry-window = "main"
[widgets.main]
type = "Window"
title = "Colored Tab Pages"
children = ["tabs"]
[widgets.tabs]
type = "TabbedPane"
children = ["first", "second"]
[widgets.first]
type = "Label"
text = "First page"
tab-title = "First"
tab-background = "#dbeafe"
[widgets.second]
type = "Button"
text = "Second page"
tab-title = "Second"
"""


if __name__ == "__main__":
    App.configure(backend="win32")
    App.run(build)
