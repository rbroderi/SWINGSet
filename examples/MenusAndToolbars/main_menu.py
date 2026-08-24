"""Create a native main menu with commands and separators."""

from swingset import ActionEvent
from swingset import App
from swingset import Frame
from swingset import Label
from swingset import Menu
from swingset import MenuBar
from swingset import MenuItem
from swingset import Rect
from swingset import Size


def build() -> None:
    """Build the MainMenu example."""
    frame = Frame("MainMenu example")
    frame.size = Size(640, 480)
    status = frame.add(Label("Choose a menu command"))
    status.bounds = Rect(10, 10, 240, 23)

    menu_bar = MenuBar()
    file_menu = menu_bar.add(Menu("&File"))
    new_item = file_menu.add("&New")
    open_item = file_menu.add("&Open...")
    file_menu.add_separator()
    exit_item = file_menu.add("E&xit")
    help_menu = menu_bar.add(Menu("&Help"))
    about_item = help_menu.add("&About...")

    def show_command(event: ActionEvent[MenuItem]) -> None:
        status.text = (event.command or "").replace("&", "")

    new_item.on_click(show_command)
    open_item.on_click(show_command)
    about_item.on_click(show_command)

    def close_window(_event: ActionEvent[MenuItem]) -> None:
        frame.dispose()

    exit_item.on_click(close_window)
    frame.menu_bar = menu_bar
    frame.visible = True


def build_toml() -> str:
    """Return the backend-independent TOML form of this example."""
    return """[config.app]
entry-window = "main"
[commands.open]
text = "&Open"
[commands.exit]
text = "E&xit"
[menu-bars.main]
menus = ["file"]
[menus.file]
text = "&File"
items = ["open", "-", "exit"]
[widgets.main]
type = "Window"
title = "Main Menu"
menu-bar = "main"
children = ["status"]
[widgets.status]
type = "StatusBar"
text = "Choose a command"
"""


if __name__ == "__main__":
    App.configure(backend="win32")
    App.run(build)
