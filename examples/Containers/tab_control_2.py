"""Create a second native tab-control arrangement."""

from swingset import App
from swingset import CheckBox
from swingset import Frame
from swingset import Label
from swingset import ListBox
from swingset import Panel
from swingset import Rect
from swingset import Size
from swingset import TabbedPane
from swingset import TextArea


def build() -> None:
    """Build the TabControl2 example."""
    frame = Frame("TabControl2 example")
    frame.size = Size(460, 340)
    tabs = frame.add(TabbedPane())
    tabs.bounds = Rect(15, 15, 410, 270)

    general = Panel()
    general.layout = None
    general.add(Label("General settings")).bounds = Rect(25, 25, 150, 24)
    general.add(CheckBox("Start automatically", selected=True)).bounds = Rect(
        25, 65, 180, 24
    )
    tabs.add_tab("General", general)

    details = Panel()
    details.layout = None
    details.add(
        TextArea("Details for the selected item", rows=7, columns=35)
    ).bounds = Rect(20, 20, 330, 150)
    tabs.add_tab("Details", details)

    history = Panel()
    history.layout = None
    history.add(ListBox(["Created", "Edited", "Saved"])).bounds = Rect(20, 20, 220, 150)
    tabs.add_tab("History", history)
    frame.visible = True


def build_toml() -> str:
    """Return the backend-independent TOML form of this example."""
    return """[config.app]
entry-window = "main"
[widgets.main]
type = "Window"
title = "Tab Control 2"
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
