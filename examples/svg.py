"""SVG-first SWINGSet example."""

from pathlib import Path

from swingset import App
from swingset import Button
from swingset import FlowLayout
from swingset import Frame
from swingset import Image
from swingset import ImageLabel
from swingset import Panel
from swingset import Size
from swingset import Theme


def build() -> None:
    """Build the demo window."""
    App.set_theme(Theme.DARK)

    asset_path = Path(__file__).parent / "assets" / "sample.svg"
    icon = Image.from_file(asset_path, size=(20, 20), tint="foreground")

    frame = Frame("SVG-first SWINGSet")
    frame.size = Size(420, 180)

    panel = frame.add(Panel())
    panel.layout = FlowLayout()
    panel.add(ImageLabel(icon))

    button = panel.add(Button("Save"))
    button.image = icon

    frame.icon = icon
    frame.visible = True


if __name__ == "__main__":
    App.run(build)
