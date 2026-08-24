"""Create a native tab control with four pages."""

from swingset import App
from swingset import Button
from swingset import Frame
from swingset import Label
from swingset import Panel
from swingset import Rect
from swingset import Size
from swingset import Slider
from swingset import TabbedPane


def build() -> None:
    """Build the TabControl example."""
    frame = Frame("TabControl example")
    frame.size = Size(406, 316)
    tabs = frame.add(TabbedPane())
    tabs.bounds = Rect(10, 10, 370, 250)

    first = Panel()
    first.layout = None
    first.add(Button("button1")).bounds = Rect(40, 20, 75, 25)
    tabs.add_tab("tabPage1", first)

    second = Panel()
    second.layout = None
    second.add(Label("label1")).bounds = Rect(100, 80, 100, 23)
    tabs.add_tab("tabPage2", second)

    tabs.add_tab("tabPage3", Panel())
    fourth = Panel()
    fourth.layout = None
    fourth.add(Slider(value=50)).bounds = Rect(10, 10, 105, 45)
    tabs.add_tab("tabPage4", fourth)
    frame.visible = True


def build_toml() -> str:
    """Return the backend-independent TOML form of this example."""
    return """[config.app]
entry-window = "main"
[widgets.main]
type = "Window"
title = "Tab Control"
children = ["tabs"]
[widgets.tabs]
type = "TabbedPane"
children = ["first", "second"]
[widgets.first]
type = "Label"
text = "First page"
tab-title = "First"
[widgets.second]
type = "Button"
text = "Second page"
tab-title = "Second"
"""


if __name__ == "__main__":
    App.configure(backend="win32")
    App.run(build)
