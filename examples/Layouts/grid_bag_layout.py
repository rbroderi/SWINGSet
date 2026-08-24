"""Build a weighted form with GridBagLayout constraints."""

from swingset import App
from swingset import Button
from swingset import Fill
from swingset import Frame
from swingset import GridBagConstraints
from swingset import GridBagLayout
from swingset import Label
from swingset import Size
from swingset import TextArea
from swingset import TextField


def constraints(
    x: int,
    y: int,
    *,
    weightx: float = 0.0,
    weighty: float = 0.0,
    fill: Fill = Fill.BOTH,
) -> GridBagConstraints:
    """Create concise constraints for the example form."""
    return GridBagConstraints(
        gridx=x,
        gridy=y,
        weightx=weightx,
        weighty=weighty,
        fill=fill,
        inset=8,
    )


def build() -> None:
    """Build the GridBagLayout example."""
    frame = Frame("GridBagLayout example")
    frame.size = Size(560, 360)
    frame.layout = GridBagLayout()

    frame.add(Label("Name:"), constraints(0, 0, fill=Fill.NONE))
    frame.add(
        TextField(columns=30), constraints(1, 0, weightx=1.0, fill=Fill.HORIZONTAL)
    )
    frame.add(Label("Notes:"), constraints(0, 1, fill=Fill.NONE))
    frame.add(
        TextArea(rows=8, columns=30),
        constraints(1, 1, weightx=1.0, weighty=1.0),
    )
    frame.add(
        Button("Save"),
        GridBagConstraints(
            gridx=0,
            gridy=2,
            gridwidth=2,
            fill=Fill.NONE,
            inset=8,
        ),
    )
    frame.visible = True


def build_toml() -> str:
    """Return the backend-independent TOML form of this example."""
    return """[config.app]
entry-window = "main"
[widgets.main]
type = "Window"
title = "Grid Bag Layout"
children = ["layout"]
[widgets.layout]
type = "GridBagLayout"
children = ["name", "field"]
[widgets.name]
type = "Label"
text = "Name"
constraint = { gridx = 0, gridy = 0, fill = "none" }
[widgets.field]
type = "TextField"
constraint = { gridx = 1, gridy = 0, weightx = 1.0, fill = "horizontal" }
"""


if __name__ == "__main__":
    App.configure(backend="win32")
    App.run(build)
