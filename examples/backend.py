"""Run the same UI on Win32 or the Tkinter fallback."""

from swingset import App
from swingset import BorderLayout
from swingset import Button
from swingset import Capability
from swingset import Frame
from swingset import Image
from swingset import Label
from swingset import Panel
from swingset import Size


def build() -> None:
    """Build and show the backend capability demo window."""
    icon = Image.from_text(
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">'
        '<path fill="black" d="M4 4h16v16H4z"/></svg>',
        size=(16, 16),
        tint="accent",
    )
    frame = Frame(f"SWINGSet backend: {App.backend_name()}")
    frame.size = Size(520, 220)
    frame.icon = icon
    frame.layout = BorderLayout()

    content = frame.add(Panel(), BorderLayout.CENTER)
    output = content.add(Label("Ready"))
    button = content.add(Button("Show backend", image=icon))

    def clicked(_event: object) -> None:
        native_dark = App.supports(Capability.NATIVE_DARK_MODE)
        output.text = f"{App.backend_name()} / native dark mode={native_dark}"

    button.on_click(clicked)
    frame.visible = True


if __name__ == "__main__":
    App.configure(backend="auto")
    App.run(build)
