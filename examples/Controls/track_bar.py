"""Keep native track-bar, progress-bar, and label values synchronized."""

from swingset import App
from swingset import Frame
from swingset import Label
from swingset import ProgressBar
from swingset import Rect
from swingset import Size
from swingset import Slider


def build() -> None:
    """Build the TrackBar example."""
    frame = Frame("TrackBar example")
    frame.size = Size(300, 300)
    track_bar = frame.add(Slider(minimum=0, maximum=200, value=100))
    track_bar.bounds = Rect(20, 50, 200, 32)
    progress_bar = frame.add(ProgressBar(minimum=0, maximum=200, value=100))
    progress_bar.bounds = Rect(20, 100, 200, 23)
    value_label = frame.add(Label("100"))
    value_label.bounds = Rect(20, 150, 100, 23)

    def value_changed(value: int) -> None:
        progress_bar.value = value
        value_label.text = str(value)

    track_bar.on_change(value_changed)
    frame.visible = True


def build_toml() -> str:
    """Return the backend-independent TOML form of this example."""
    return """[config.app]
entry-window = "main"

[widgets.main]
type = "Window"
title = "Track Bar"
children = ["demo"]

[widgets.demo]
type = "Slider"
minimum = 0
maximum = 100
value = 50
"""


if __name__ == "__main__":
    App.configure(backend="win32")
    App.run(build)
