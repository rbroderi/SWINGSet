"""Draw Hello World through a native Win32 GDI paint surface."""

from swingset import App
from swingset import Frame
from swingset import PaintEvent
from swingset import PaintSurface
from swingset import Point
from swingset import Rect
from swingset import Size


def build() -> None:
    """Build the HelloWorldPaint example."""
    frame = Frame("Hello World Paint")
    frame.size = Size(400, 300)
    surface = frame.add(PaintSurface(360, 220))
    surface.bounds = Rect(12, 12, 360, 220)

    def paint(event: PaintEvent) -> None:
        event.graphics.fill_rectangle(Rect(0, 0, 360, 220))
        event.graphics.draw_rectangle(Rect(8, 8, 343, 203), color="accent")
        event.graphics.draw_line(Point(20, 55), Point(335, 55), color="muted")
        event.graphics.draw_text("Hello, World!", 125, 90)

    surface.on_paint(paint)
    frame.visible = True


def build_toml() -> str:
    """Return the backend-independent TOML form of this example."""
    return """[config.app]
entry-window = "main"

[widgets.main]
type = "Window"
title = "Hello World Paint"
children = ["demo"]

[widgets.demo]
type = "PaintSurface"
width = 360
height = 220
"""


if __name__ == "__main__":
    App.configure(backend="win32")
    App.run(build)
