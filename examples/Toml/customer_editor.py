"""Load a backend-independent interface from TOML."""

from pathlib import Path

from swingset import App
from swingset import Frame
from swingset import TomlUILoader

_UI_FILE = Path(__file__).with_suffix(".toml")


def save(_event: object) -> None:
    """Handle the declarative save command."""
    print("Saved")


def build() -> None:
    """Build and show the TOML-defined interface."""
    loaded = TomlUILoader().load(_UI_FILE, handlers={"save": save})
    root = loaded.root
    if not isinstance(root, Frame):
        message = "the entry-window must resolve to a Frame"
        raise TypeError(message)
    root.visible = True


if __name__ == "__main__":
    App.configure(backend="auto")
    App.run(build)
