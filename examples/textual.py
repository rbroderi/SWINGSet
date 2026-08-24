"""Small example that can run as a Textual/Rich terminal application."""

from swingset import App
from swingset import BorderLayout
from swingset import Button
from swingset import Frame
from swingset import Label
from swingset import ProgressBar
from swingset import TextField


def build() -> None:
    """Build and show the terminal-friendly demo window."""
    frame = Frame("SWINGSet Terminal Demo")
    frame.layout = BorderLayout()

    name = TextField("World")
    status = Label("Ready")
    progress = ProgressBar(value=25)
    button = Button("Greet")

    def greet(_event: object) -> None:
        status.text = f"Hello, {name.text}!"
        progress.value = min(progress.maximum, progress.value + 25)

    button.on_click(greet)
    frame.add(name, BorderLayout.NORTH)
    frame.add(button, BorderLayout.CENTER)
    frame.add(progress, BorderLayout.SOUTH)
    frame.add(status, BorderLayout.SOUTH)
    frame.visible = True


if __name__ == "__main__":
    App.configure(backend="textual")
    App.run(build)
