"""Display version-resource information for the running executable."""

from swingset import App
from swingset import Frame
from swingset import Label
from swingset import Rect
from swingset import Size
from swingset import read_windows_version_info


def build() -> None:
    """Build the WindowVersionInfo example."""
    info = read_windows_version_info()
    frame = Frame("WindowVersionInfo example")
    frame.size = Size(560, 300)
    rows = (
        ("File", str(info.path)),
        ("Description", info.file_description or "(not specified)"),
        ("File version", info.file_version or "(not specified)"),
        ("Product", info.product_name or "(not specified)"),
        ("Product version", info.product_version or "(not specified)"),
        ("Company", info.company_name or "(not specified)"),
    )
    for index, (name, value) in enumerate(rows):
        top = 20 + index * 36
        frame.add(Label(f"{name}:")).bounds = Rect(20, top, 110, 24)
        frame.add(Label(value)).bounds = Rect(135, top, 390, 24)
    frame.visible = True


def build_toml() -> str:
    """Return the backend-independent TOML form of this example."""
    return """[config.app]
entry-window = "main"

[widgets.main]
type = "Window"
title = "Window Version Info"
children = ["demo"]

[widgets.demo]
type = "Label"
text = "Window Version Info built from TOML"
"""


if __name__ == "__main__":
    App.configure(backend="win32")
    App.run(build)
