"""Demonstrate a native combo-box selection."""

from swingset import App
from swingset import ComboBox
from swingset import Frame
from swingset import Rect
from swingset import Size


def build() -> None:
    """Build the ComboBox example."""
    frame = Frame("ComboBox example")
    frame.size = Size(300, 300)
    items = [f"Item{index}" for index in range(1, 11)]
    combo_box = frame.add(ComboBox(items))
    combo_box.bounds = Rect(10, 10, 120, 28)
    combo_box.selected_index = 1
    frame.visible = True


def build_toml() -> str:
    """Return the backend-independent TOML form of this example."""
    return """[config.app]
entry-window = "main"

[widgets.main]
type = "Window"
title = "Combo Box"
children = ["demo"]

[widgets.demo]
type = "ComboBox"
items = ["Alpha", "Beta", "Gamma"]
"""


if __name__ == "__main__":
    App.configure(backend="win32")
    App.run(build)
