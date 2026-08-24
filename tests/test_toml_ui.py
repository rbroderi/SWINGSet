"""Tests for the backend-independent TOML UI compiler."""

from collections.abc import Mapping
from pathlib import Path

import pytest

from swingset import BorderLayout
from swingset import BoxLayout
from swingset import Button
from swingset import CheckBox
from swingset import Frame
from swingset import GridBagConstraints
from swingset import ImageLabel
from swingset import Label
from swingset import PaintSurface
from swingset import Panel
from swingset import RichTextPane
from swingset import ScrollPane
from swingset import SplitPane
from swingset import TabbedPane
from swingset import Table
from swingset import TextField
from swingset import TomlUIError
from swingset import TomlUILoader
from swingset import TreeView
from swingset import WidgetRegistry


def test_loads_tree_styles_commands_events_and_bindings() -> None:
    """Compile the main Phase 1 features without mounting a backend."""
    clicks: list[str] = []
    source = """
[config.app]
name = "Customer Editor"
entry-window = "main"

[resources.icons]
save = "assets/save.svg"

[theme.colors]
primary = "#3b82f6"

[style.defaults.Button]
min-width = 80

[style.base]
width = 100

[style.primary]
extends = ["base"]
background = "$primary"
font-weight = "bold"

[commands.save]
text = "Save"
icon = "save"
tooltip = "Save the customer"

[widgets.main]
type = "Window"
title = "Customer Editor"
children = ["content"]

[widgets.content]
type = "VBox"
styles = ["base"]
children = ["name", "active", "save"]

[widgets.name]
type = "TextField"
id = "customer-name"

[widgets.name.bind]
text = "customer.name"

[widgets.active]
type = "CheckBox"
text = "Active"
selected = true

[widgets.save]
type = "Button"
command = "save"
styles = ["primary"]

[widgets.save.style]
min-width = 120
"""

    loaded = TomlUILoader().loads(
        source,
        handlers={"save": lambda _event: clicks.append("save")},
    )

    assert isinstance(loaded.root, Frame)
    assert loaded.root.title == "Customer Editor"
    assert isinstance(loaded.root.layout, BorderLayout)
    assert loaded.root.children[0].constraint == BorderLayout.CENTER
    content = loaded["content"]
    assert isinstance(content, Panel)
    assert isinstance(content.layout, BoxLayout)
    assert isinstance(loaded.by_id("customer-name"), TextField)
    active = loaded["active"]
    assert isinstance(active, CheckBox)
    assert active.selected
    save = loaded["save"]
    assert isinstance(save, Button)
    assert save.text == "Save"
    assert save.tooltip == "Save the customer"
    expected_width = 120
    assert save.width == expected_width
    assert loaded.resolved_styles["save"]["background"] == "#3b82f6"
    assert loaded.ignored_styles["save"] == ()
    assert loaded.resources.resolve("save") == "assets/save.svg"

    loaded.apply_bindings({"customer": {"name": "Ada"}})
    assert loaded["name"].text == "Ada"
    save.trigger_action()
    assert clicks == ["save"]


@pytest.mark.parametrize(
    ("fragment", "message"),
    [
        ('type = "Buton"', "Did you mean 'Button'?"),
        ('type = "Window"\nchildren = ["missing"]', "unknown widget reference"),
    ],
)
def test_reports_unknown_references_with_context(fragment: str, message: str) -> None:
    """Report source location and useful typo guidance."""
    source = f'[config.app]\nentry-window = "main"\n[widgets.main]\n{fragment}'

    with pytest.raises(TomlUIError, match=message) as caught:
        TomlUILoader().loads(source, filename="broken.toml")

    assert "broken.toml" in str(caught.value)
    assert "widgets.main" in str(caught.value)


def test_rejects_duplicate_ids() -> None:
    """Keep registry names and public IDs separate and unique."""
    source = """
[config.app]
entry-window = "main"
[widgets.main]
type = "Window"
children = ["first", "second"]
[widgets.first]
type = "Label"
id = "same"
[widgets.second]
type = "Label"
id = "same"
"""

    with pytest.raises(TomlUIError, match="duplicate public id"):
        TomlUILoader().loads(source)


@pytest.mark.parametrize(
    ("source", "message"),
    [
        (
            """
[config.app]
entry-window = "a"
[widgets.a]
type = "VBox"
children = ["b"]
[widgets.b]
type = "VBox"
children = ["a"]
""",
            "circular widget hierarchy: a -> b -> a",
        ),
        (
            """
[config.app]
entry-window = "main"
[style.a]
extends = ["b"]
[style.b]
extends = ["a"]
[widgets.main]
type = "Window"
""",
            "circular style inheritance: a -> b -> a",
        ),
    ],
)
def test_rejects_cycles(source: str, message: str) -> None:
    """Reject style and containment cycles before construction."""
    with pytest.raises(TomlUIError, match=message):
        TomlUILoader().loads(source)


def test_custom_widget_registry() -> None:
    """Resolve application widgets through the extensible registry."""
    registry = WidgetRegistry.defaults()

    def factory(_props: Mapping[str, object]) -> Label:
        return Label("custom")

    registry.register("CustomLabel", factory)
    source = """
[config.app]
entry-window = "main"
[widgets.main]
type = "CustomLabel"
"""

    loaded = TomlUILoader(registry).loads(source)

    assert isinstance(loaded.root, Label)
    assert loaded.root.text == "custom"


def test_primary_binding_shortcut() -> None:
    """Apply a widget-specific primary binding shortcut."""
    source = """
[config.app]
entry-window = "main"
[widgets.main]
type = "CheckBox"
bind = "customer.active"
"""
    loaded = TomlUILoader().loads(source)

    loaded.apply_bindings({"customer": {"active": True}})
    root = loaded.root
    assert isinstance(root, CheckBox)
    assert root.selected


def test_rejects_nonfunctional_state_styles() -> None:
    """Reject state style tables instead of silently retaining dead metadata."""
    source = """
[config.app]
entry-window = "main"
[style.primary.disabled]
opacity = 0.5
[widgets.main]
type = "Button"
styles = ["primary"]
"""

    with pytest.raises(TomlUIError, match="state styles are not supported"):
        TomlUILoader().loads(source)


def test_toml_markdown_and_component_colors() -> None:
    """Apply semantic colors and CommonMark through backend-neutral TOML."""
    source = """
[config.app]
entry-window = "main"
[theme.colors]
primary = "#2563eb"
surface = [250, 250, 250]
[style.message]
foreground = "$primary"
background = "$surface"
[widgets.main]
type = "Label"
markdown = "Hello **TOML**"
styles = ["message"]
"""

    loaded = TomlUILoader().loads(source)

    assert loaded.root.text == "Hello TOML"
    assert loaded.root.styles[0].style.bold
    assert loaded.root.foreground == "#2563eb"
    assert loaded.root.background == (250, 250, 250)
    assert loaded.ignored_styles["main"] == ()


def test_advanced_types_and_container_relationships() -> None:
    """Construct specialized controls, layouts, constraints, and radio groups."""
    source = """
[config.app]
entry-window = "main"
[widgets.main]
type = "Window"
children = ["content"]
[widgets.content]
type = "VBox"
children = ["border", "tabs", "split", "scroll", "table", "tree", "paint", "rich"]
[widgets.border]
type = "BorderLayout"
children = ["north", "center"]
[widgets.north]
type = "Label"
text = "North"
constraint = "north"
[widgets.center]
type = "GridBagLayout"
children = ["first", "second"]
[widgets.first]
type = "RadioButton"
text = "First"
selected = true
group-id = "choice"
constraint = { gridx = 0, gridy = 0, weightx = 1.0, fill = "horizontal" }
[widgets.second]
type = "RadioButton"
text = "Second"
group-id = "choice"
constraint = { gridx = 1, gridy = 0, fill = "none" }
[widgets.tabs]
type = "TabbedPane"
children = ["tab-one", "tab-two"]
[widgets.tab-one]
type = "Label"
text = "One"
tab-title = "First tab"
[widgets.tab-two]
type = "Label"
text = "Two"
tab-title = "Second tab"
tab-background = "#224466"
[widgets.split]
type = "SplitPane"
orientation = "vertical"
divider-location = 0.4
children = ["top", "bottom"]
[widgets.top]
type = "Label"
text = "Top"
[widgets.bottom]
type = "Label"
text = "Bottom"
[widgets.scroll]
type = "ScrollPane"
children = ["long-text"]
[widgets.long-text]
type = "TextArea"
text = "Scrollable"
[widgets.table]
type = "Table"
columns = ["Name", "Value"]
rows = [["alpha", 1], ["beta", 2]]
[widgets.tree]
type = "TreeView"
nodes = [{ text = "root", children = ["leaf"] }]
[widgets.paint]
type = "PaintSurface"
width = 200
height = 100
[widgets.rich]
type = "RichTextPane"
markdown = "**Rich** text"
editable = false
"""

    loaded = TomlUILoader().loads(source)

    border = loaded["border"]
    assert isinstance(border, Panel)
    assert isinstance(border.layout, BorderLayout)
    assert border.children[0].constraint == BorderLayout.NORTH
    grid_bag = loaded["center"]
    assert isinstance(grid_bag, Panel)
    assert isinstance(grid_bag.children[0].constraint, GridBagConstraints)
    tabs = loaded["tabs"]
    assert isinstance(tabs, TabbedPane)
    assert [title for title, _child in tabs.tabs] == ["First tab", "Second tab"]
    assert tabs.page_background(loaded["tab-two"]) == "#224466"
    assert isinstance(loaded["split"], SplitPane)
    assert isinstance(loaded["scroll"], ScrollPane)
    assert isinstance(loaded["table"], Table)
    assert isinstance(loaded["tree"], TreeView)
    assert isinstance(loaded["paint"], PaintSurface)
    rich = loaded["rich"]
    assert isinstance(rich, RichTextPane)
    assert rich.text == "Rich text"


def test_menus_images_and_universal_events(tmp_path: Path) -> None:
    """Resolve relative images, attach menus, and route key/mouse handlers."""
    (tmp_path / "logo.svg").write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16"/>',
        encoding="utf-8",
    )
    calls: list[str] = []
    source = """
[config.app]
entry-window = "main"
[resources.icons]
logo = "logo.svg"
[commands.open]
text = "&Open"
[menu-bars.main]
menus = ["file"]
[menus.file]
text = "&File"
items = ["open", "-"]
[widgets.main]
type = "Window"
menu-bar = "main"
icon = "logo"
children = ["picture", "field"]
[widgets.picture]
type = "ImageLabel"
image = "logo"
[widgets.field]
type = "TextField"
[widgets.field.events]
key = "key"
mouse = "mouse"
"""

    loaded = TomlUILoader().loads(
        source,
        filename=str(tmp_path / "ui.toml"),
        handlers={
            "open": lambda _event: calls.append("open"),
            "key": lambda _event: calls.append("key"),
            "mouse": lambda _event: calls.append("mouse"),
        },
    )

    root = loaded.root
    assert isinstance(root, Frame)
    assert root.icon is not None
    assert root.menu_bar is loaded.menu_bars["main"]
    picture = loaded["picture"]
    assert isinstance(picture, ImageLabel)
    assert picture.image is loaded.resources.image("logo")
    menu_item = loaded.menu_bars["main"].menus[0].items[0]
    assert menu_item is not None
    menu_item.trigger_action()
    loaded["field"].emit_key_event(65, "A")
    loaded["field"].emit_mouse_event(1, 2)
    assert calls == ["open", "key", "mouse"]
