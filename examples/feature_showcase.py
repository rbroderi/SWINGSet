"""SWINGSet feature showcase."""

import asyncio

from swingset import App
from swingset import BorderLayout
from swingset import Button
from swingset import Frame
from swingset import Label
from swingset import Menu
from swingset import MenuBar
from swingset import Panel
from swingset import ProgressBar
from swingset import Size
from swingset import Slider
from swingset import StatusBar
from swingset import TabbedPane
from swingset import Table
from swingset import TableModel
from swingset import TextField
from swingset import Theme
from swingset import ToolBar
from swingset import TreeNode
from swingset import TreeView


def build_ui() -> None:
    """Build and show the feature showcase window."""
    App.set_theme(Theme.DARK)

    frame = Frame("SWINGSet")
    frame.size = Size(840, 560)
    frame.layout = BorderLayout()

    toolbar = ToolBar()
    save = toolbar.add_button("Save")
    frame.add(toolbar, BorderLayout.NORTH)

    tabs = TabbedPane()
    frame.add(tabs, BorderLayout.CENTER)

    form = Panel()
    name = form.add(TextField(columns=22))
    greeting = form.add(Label("Ready"))
    greeting.width = 160
    hello = form.add(Button("Hello"))

    def greet(_event: object) -> None:
        greeting.text = f"Hello, {name.text or 'Windows'}!"

    def save_clicked(_event: object) -> None:
        status.text = "Saved"

    hello.on_click(greet)
    save.on_click(save_clicked)
    tabs.add_tab("Form", form)
    tabs.add_tab(
        "Table",
        Table(
            model=TableModel(
                [["Nick", "Fox"], ["Judy", "Rabbit"]],
                ["Name", "Species"],
            ),
        ),
    )

    root = TreeNode("Zootopia")
    root.add("Nick")
    root.add("Judy")
    tabs.add_tab("Tree", TreeView([root]))

    progress_panel = Panel()
    slider = progress_panel.add(Slider(value=35))
    progress = progress_panel.add(ProgressBar(value=35))

    def sync_progress(value: int) -> None:
        progress.value = value

    slider.on_change(sync_progress)
    tabs.add_tab("Progress", progress_panel)

    status = StatusBar("Ready")
    frame.add(status, BorderLayout.SOUTH)

    menu_bar = MenuBar()
    file_menu = menu_bar.add(Menu("File"))
    exit_item = file_menu.add("Exit")

    def close_app(_event: object) -> None:
        frame.dispose()

    exit_item.on_click(close_app)
    frame.menu_bar = menu_bar
    frame.visible = True


async def async_main() -> None:
    """Show how the GUI can coexist with an asyncio application."""
    await App.run_async(build_ui)


if __name__ == "__main__":
    asyncio.run(async_main())
