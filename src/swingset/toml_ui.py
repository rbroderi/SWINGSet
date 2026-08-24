"""Backend-independent TOML front end for constructing SWINGSet interfaces."""

# Validation deliberately constructs contextual messages at each failure site.
# ruff: noqa: EM101, EM102, TRY003

from __future__ import annotations

import difflib
import tomllib
from collections.abc import Callable
from collections.abc import Mapping
from collections.abc import Sequence
from dataclasses import dataclass
from dataclasses import field
from pathlib import Path
from types import MappingProxyType
from typing import Self

from .core import Component
from .core import Container
from .core import Window
from .drawing import PaintSurface
from .imaging import ImageResource
from .imaging import load_image
from .layout import BorderLayout
from .layout import BoxAxis
from .layout import BoxLayout
from .layout import CardLayout
from .layout import Fill
from .layout import FlowAlignment
from .layout import FlowLayout
from .layout import GridBagConstraints
from .layout import GridBagLayout
from .layout import GridLayout
from .menu import Menu
from .menu import MenuBar
from .theme import ColorInput
from .widgets import Button
from .widgets import CheckBox
from .widgets import ComboBox
from .widgets import GroupBox
from .widgets import ImageLabel
from .widgets import Label
from .widgets import ListBox
from .widgets import Panel
from .widgets import PasswordField
from .widgets import ProgressBar
from .widgets import RadioButton
from .widgets import RadioGroup
from .widgets import RichTextPane
from .widgets import ScrollPane
from .widgets import Separator
from .widgets import SeparatorOrientation
from .widgets import Slider
from .widgets import Spinner
from .widgets import SplitOrientation
from .widgets import SplitPane
from .widgets import StatusBar
from .widgets import TabbedPane
from .widgets import Table
from .widgets import TextArea
from .widgets import TextField
from .widgets import ToolBar
from .widgets import TreeNode
from .widgets import TreeView
from .windows import Dialog
from .windows import Frame

type TomlValue = str | int | float | bool | list[TomlValue] | dict[str, TomlValue]
type WidgetFactory = Callable[[Mapping[str, object]], Component]
type EventHandler = Callable[[object], None]

_RESERVED_WIDGET_KEYS = frozenset(
    {
        "type",
        "id",
        "styles",
        "children",
        "style",
        "bind",
        "events",
        "command",
        "constraint",
        "tab-title",
        "tab-background",
        "group-id",
        "menu-bar",
    },
)
_UNSUPPORTED_STYLE_STATES = frozenset(
    {"hover", "focus", "disabled", "checked", "selected", "error", "active"},
)
_RGB_COMPONENT_COUNT = 3


class TomlUIError(ValueError):
    """Validation error tied to a source file and TOML table path."""

    def __init__(
        self,
        message: str,
        *,
        filename: str = "<toml>",
        table_path: str = "",
        property_name: str | None = None,
    ) -> None:
        """Initialize a contextual validation error."""
        location = filename
        if table_path:
            location += f": [{table_path}]"
        if property_name is not None:
            location += f" property {property_name!r}"
        super().__init__(f"{location}: {message}")
        self.filename = filename
        self.table_path = table_path
        self.property_name = property_name


@dataclass(frozen=True, slots=True)
class BindingSpec:
    """Binding between one widget property and one model path."""

    property_name: str
    model_path: str


@dataclass(frozen=True, slots=True)
class StyleSpec:
    """Named reusable style before inheritance and theme resolution."""

    name: str
    extends: tuple[str, ...] = ()
    properties: Mapping[str, object] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class CommandSpec:
    """Declarative command presentation metadata."""

    name: str
    text: str | None = None
    icon: str | None = None
    shortcut: str | None = None
    tooltip: str | None = None


@dataclass(frozen=True, slots=True)
class WidgetSpec:
    """Backend-independent widget description parsed from TOML."""

    registry_name: str
    type_name: str
    public_id: str | None = None
    properties: Mapping[str, object] = field(default_factory=dict)
    style_names: tuple[str, ...] = ()
    local_style: Mapping[str, object] = field(default_factory=dict)
    bindings: Mapping[str, BindingSpec] = field(default_factory=dict)
    events: Mapping[str, str] = field(default_factory=dict)
    children: tuple[str, ...] = ()
    command: str | None = None
    constraint: object | None = None
    tab_title: str | None = None
    tab_background: ColorInput | None = None
    group_id: str | None = None
    menu_bar: str | None = None


class ResourceRegistry:
    """Logical resource names mapped to source paths."""

    def __init__(
        self,
        resources: Mapping[str, str] | None = None,
        *,
        base_path: Path | None = None,
    ) -> None:
        """Initialize resource aliases."""
        self._resources = dict(resources or {})
        self._base_path = base_path
        self._images: dict[str, ImageResource] = {}

    def resolve(self, name: str) -> str:
        """Resolve a logical resource name."""
        try:
            return self._resources[name]
        except KeyError as error:
            raise KeyError(f"unknown resource {name!r}") from error

    def image(self, name: str) -> ImageResource:
        """Load and cache a logical image resource."""
        cached = self._images.get(name)
        if cached is not None:
            return cached
        path = Path(self.resolve(name))
        if not path.is_absolute() and self._base_path is not None:
            path = self._base_path / path
        image = load_image(path)
        self._images[name] = image
        return image

    def __contains__(self, name: object) -> bool:
        """Return whether a logical resource name is registered."""
        return name in self._resources


class ThemeRegistry:
    """Semantic theme values referenced by ``$name``."""

    def __init__(self, values: Mapping[str, object] | None = None) -> None:
        """Initialize semantic values."""
        self._values = dict(values or {})

    def resolve(self, value: object) -> object:
        """Resolve a theme reference while preserving native TOML values."""
        if not isinstance(value, str) or not value.startswith("$"):
            return value
        name = value[1:]
        try:
            return self._values[name]
        except KeyError as error:
            raise KeyError(f"unknown theme value {name!r}") from error


def _suggest(value: str, choices: Mapping[str, object]) -> str:
    matches = difflib.get_close_matches(value, choices, n=1)
    return "" if not matches else f". Did you mean {matches[0]!r}?"


class StyleRegistry:
    """Style storage and deterministic inheritance resolver."""

    def __init__(
        self,
        styles: Mapping[str, StyleSpec] | None = None,
        defaults: Mapping[str, Mapping[str, object]] | None = None,
    ) -> None:
        """Initialize named styles and widget type defaults."""
        self._styles = dict(styles or {})
        self._defaults = {name: dict(value) for name, value in (defaults or {}).items()}

    def _resolve_named(self, name: str, trail: tuple[str, ...]) -> dict[str, object]:
        if name in trail:
            cycle = " -> ".join((*trail, name))
            raise TomlUIError(f"circular style inheritance: {cycle}")
        try:
            style = self._styles[name]
        except KeyError as error:
            suggestion = _suggest(name, self._styles)
            raise TomlUIError(f"unknown style {name!r}{suggestion}") from error
        resolved: dict[str, object] = {}
        for parent in style.extends:
            resolved.update(self._resolve_named(parent, (*trail, name)))
        resolved.update(style.properties)
        return resolved

    def resolve_named(self, name: str) -> dict[str, object]:
        """Resolve one style, including inherited styles left to right."""
        return self._resolve_named(name, ())

    def resolve(
        self,
        type_name: str,
        style_names: Sequence[str],
        local_style: Mapping[str, object],
        theme: ThemeRegistry,
    ) -> dict[str, object]:
        """Resolve defaults, named styles, local overrides, and theme values."""
        resolved = dict(self._defaults.get(type_name, {}))
        for name in style_names:
            resolved.update(self.resolve_named(name))
        resolved.update(local_style)
        return {name: theme.resolve(value) for name, value in resolved.items()}


def _string(properties: Mapping[str, object], name: str, default: str = "") -> str:
    value = properties.get(name, default)
    if not isinstance(value, str):
        raise TypeError(f"property {name!r} must be a string")
    return value


def _integer(properties: Mapping[str, object], name: str, default: int) -> int:
    value = properties.get(name, default)
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"property {name!r} must be an integer")
    return value


def _number(properties: Mapping[str, object], name: str, default: float) -> float:
    value = properties.get(name, default)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"property {name!r} must be numeric")
    return float(value)


def _boolean(
    properties: Mapping[str, object],
    name: str,
    *,
    default: bool = False,
) -> bool:
    value = properties.get(name, default)
    if not isinstance(value, bool):
        raise TypeError(f"property {name!r} must be a boolean")
    return value


def _box_panel(properties: Mapping[str, object], axis: BoxAxis) -> Panel:
    panel = Panel()
    panel.layout = BoxLayout(axis, _integer(properties, "gap", 8))
    return panel


def _grid_panel(properties: Mapping[str, object]) -> Panel:
    panel = Panel()
    panel.layout = GridLayout(
        rows=_integer(properties, "rows", 0),
        cols=_integer(properties, "columns", 1),
        hgap=_integer(properties, "horizontal-gap", _integer(properties, "gap", 4)),
        vgap=_integer(properties, "vertical-gap", _integer(properties, "gap", 4)),
    )
    return panel


def _flow_panel(properties: Mapping[str, object]) -> Panel:
    panel = Panel()
    alignment = {
        "left": FlowAlignment.LEFT,
        "center": FlowAlignment.CENTER,
        "right": FlowAlignment.RIGHT,
    }.get(_string(properties, "alignment", "left"))
    if alignment is None:
        raise ValueError("alignment must be left, center, or right")
    panel.layout = FlowLayout(
        alignment,
        _integer(properties, "horizontal-gap", _integer(properties, "gap", 8)),
        _integer(properties, "vertical-gap", _integer(properties, "gap", 8)),
    )
    return panel


def _border_panel(properties: Mapping[str, object]) -> Panel:
    panel = Panel()
    panel.layout = BorderLayout(
        _integer(properties, "horizontal-gap", _integer(properties, "gap", 4)),
        _integer(properties, "vertical-gap", _integer(properties, "gap", 4)),
    )
    return panel


def _card_panel(_properties: Mapping[str, object]) -> Panel:
    panel = Panel()
    panel.layout = CardLayout()
    return panel


def _grid_bag_panel(_properties: Mapping[str, object]) -> Panel:
    panel = Panel()
    panel.layout = GridBagLayout()
    return panel


def _frame(properties: Mapping[str, object]) -> Frame:
    return Frame(_string(properties, "title"))


def _table(properties: Mapping[str, object]) -> Table:
    rows = properties.get("rows", [])
    columns = properties.get("columns", [])
    if not isinstance(rows, list) or any(not isinstance(row, list) for row in rows):
        raise TypeError("property 'rows' must be an array of arrays")
    if not isinstance(columns, list) or any(
        not isinstance(column, str) for column in columns
    ):
        raise TypeError("property 'columns' must be an array of strings")
    return Table(rows, columns)


def _tree_node(value: object) -> TreeNode:
    if isinstance(value, str):
        return TreeNode(value)
    if not isinstance(value, Mapping):
        raise TypeError("tree node must be a string or table")
    text = value.get("text")
    children = value.get("children", [])
    if not isinstance(text, str) or not isinstance(children, list):
        raise TypeError("tree node requires string text and array children")
    return TreeNode(text, (_tree_node(child) for child in children))


def _tree_view(properties: Mapping[str, object]) -> TreeView:
    nodes = properties.get("nodes", [])
    if not isinstance(nodes, list):
        raise TypeError("property 'nodes' must be an array")
    return TreeView(_tree_node(node) for node in nodes)


def _items(properties: Mapping[str, object]) -> Sequence[object]:
    value = properties.get("items", [])
    if not isinstance(value, list):
        raise TypeError("property 'items' must be an array")
    return value


def _range_widget(
    component_type: type[ProgressBar | Slider],
    properties: Mapping[str, object],
) -> ProgressBar | Slider:
    return component_type(
        _integer(properties, "minimum", 0),
        _integer(properties, "maximum", 100),
        _integer(properties, "value", 0),
    )


class WidgetRegistry:
    """Extensible mapping from declarative type names to factories."""

    def __init__(
        self,
        factories: Mapping[str, WidgetFactory] | None = None,
    ) -> None:
        """Initialize an empty widget registry."""
        self._factories = dict(factories or {})

    def register(self, type_name: str, factory: WidgetFactory) -> None:
        """Register or replace a widget factory."""
        self._factories[type_name] = factory

    def resolve(self, type_name: str) -> WidgetFactory:
        """Resolve a widget factory with a spelling suggestion on failure."""
        try:
            return self._factories[type_name]
        except KeyError as error:
            suggestion = _suggest(type_name, self._factories)
            raise TomlUIError(
                f"unknown widget type {type_name!r}{suggestion}",
            ) from error

    def copy(self) -> Self:
        """Return an independently extensible copy."""
        return type(self)(self._factories)

    @classmethod
    def defaults(cls) -> Self:
        """Return the built-in Phase 1 widget and layout registry."""
        registry = cls()
        registry.register("Window", _frame)
        registry.register("Frame", _frame)
        registry.register(
            "Dialog",
            lambda props: Dialog(
                title=_string(props, "title"),
                modal=_boolean(props, "modal"),
            ),
        )
        registry.register("Label", lambda props: Label(_string(props, "text")))
        registry.register(
            "ImageLabel",
            lambda props: ImageLabel(text=_string(props, "text")),
        )
        registry.register("Button", lambda props: Button(_string(props, "text")))
        registry.register(
            "TextField",
            lambda props: TextField(
                _string(props, "text"),
                _integer(props, "columns", 20),
            ),
        )
        registry.register(
            "CheckBox",
            lambda props: CheckBox(
                _string(props, "text"),
                selected=_boolean(props, "selected"),
            ),
        )
        registry.register(
            "RadioButton",
            lambda props: RadioButton(
                _string(props, "text"),
                selected=_boolean(props, "selected"),
            ),
        )
        registry.register(
            "TextArea",
            lambda props: TextArea(
                _string(props, "text"),
                _integer(props, "rows", 6),
                _integer(props, "columns", 30),
            ),
        )
        registry.register(
            "PasswordField",
            lambda props: PasswordField(
                _string(props, "text"),
                _integer(props, "columns", 20),
                revealed=_boolean(props, "revealed"),
            ),
        )
        registry.register(
            "RichTextPane",
            lambda props: RichTextPane(
                _string(props, "text"),
                _integer(props, "rows", 8),
                _integer(props, "columns", 40),
                editable=_boolean(props, "editable", default=True),
            ),
        )
        registry.register("ComboBox", lambda props: ComboBox(_items(props)))
        registry.register("ListBox", lambda props: ListBox(_items(props)))
        registry.register(
            "ProgressBar", lambda props: _range_widget(ProgressBar, props)
        )
        registry.register("Slider", lambda props: _range_widget(Slider, props))
        registry.register(
            "Spinner",
            lambda props: Spinner(
                _integer(props, "minimum", 0),
                _integer(props, "maximum", 100),
                _integer(props, "value", 0),
                _integer(props, "step", 1),
            ),
        )
        registry.register(
            "Separator",
            lambda props: Separator(
                SeparatorOrientation(_string(props, "orientation", "horizontal")),
            ),
        )
        registry.register("Panel", lambda _props: Panel())
        registry.register("GroupBox", lambda props: GroupBox(_string(props, "title")))
        registry.register("TabbedPane", lambda _props: TabbedPane())
        registry.register(
            "SplitPane",
            lambda props: SplitPane(
                SplitOrientation(_string(props, "orientation", "horizontal")),
                divider_location=_number(props, "divider-location", 0.5),
            ),
        )
        registry.register("ScrollPane", lambda _props: ScrollPane())
        registry.register("ToolBar", lambda _props: ToolBar())
        registry.register("StatusBar", lambda props: StatusBar(_string(props, "text")))
        registry.register("Table", _table)
        registry.register("TreeView", _tree_view)
        registry.register(
            "PaintSurface",
            lambda props: PaintSurface(
                _integer(props, "width", 320),
                _integer(props, "height", 200),
            ),
        )
        registry.register("VBox", lambda props: _box_panel(props, BoxAxis.Y))
        registry.register("HBox", lambda props: _box_panel(props, BoxAxis.X))
        registry.register("Grid", _grid_panel)
        registry.register("Flow", _flow_panel)
        registry.register("FlowLayout", _flow_panel)
        registry.register("Border", _border_panel)
        registry.register("BorderLayout", _border_panel)
        registry.register("Card", _card_panel)
        registry.register("CardLayout", _card_panel)
        registry.register("GridBag", _grid_bag_panel)
        registry.register("GridBagLayout", _grid_bag_panel)
        return registry


def _python_name(name: str) -> str:
    return name.replace("-", "_")


def _read_path(root: object, path: str) -> object:
    current = root
    for name in path.split("."):
        if isinstance(current, Mapping):
            current = current[name]
        else:
            current = getattr(current, name)
    return current


@dataclass(slots=True)
class LoadedUI:
    """Parsed registries and one constructed, backend-neutral UI tree."""

    root: Component
    widgets: Mapping[str, Component]
    ids: Mapping[str, Component]
    specs: Mapping[str, WidgetSpec]
    config: Mapping[str, object]
    resources: ResourceRegistry
    theme: ThemeRegistry
    styles: StyleRegistry
    commands: Mapping[str, CommandSpec]
    menu_bars: Mapping[str, MenuBar]
    resolved_styles: Mapping[str, Mapping[str, object]]
    ignored_styles: Mapping[str, tuple[str, ...]]

    def widget(self, registry_name: str) -> Component:
        """Look up a widget by its TOML registry name."""
        try:
            return self.widgets[registry_name]
        except KeyError as error:
            raise KeyError(f"unknown widget {registry_name!r}") from error

    def by_id(self, public_id: str) -> Component:
        """Look up a widget by its explicitly declared public ID."""
        try:
            return self.ids[public_id]
        except KeyError as error:
            raise KeyError(f"unknown widget id {public_id!r}") from error

    def apply_bindings(self, model: object) -> None:
        """Apply current model values to declared widget properties."""
        for name, spec in self.specs.items():
            component = self.widgets[name]
            for binding in spec.bindings.values():
                value = _read_path(model, binding.model_path)
                setattr(component, _python_name(binding.property_name), value)

    def __getitem__(self, registry_name: str) -> Component:
        """Look up a widget by registry name."""
        return self.widget(registry_name)


def _mapping(value: object, filename: str, path: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise TomlUIError("expected a table", filename=filename, table_path=path)
    return {str(name): item for name, item in value.items()}


def _parse_resources(value: object, filename: str) -> ResourceRegistry:
    tables = _mapping(value, filename, "resources")
    resources: dict[str, str] = {}
    for group_name, group_value in tables.items():
        group = _mapping(group_value, filename, f"resources.{group_name}")
        for name, path in group.items():
            if not isinstance(path, str):
                raise TomlUIError(
                    "resource path must be a string",
                    filename=filename,
                    table_path=f"resources.{group_name}",
                    property_name=name,
                )
            resources[name] = path
    base_path = None if filename.startswith("<") else Path(filename).parent
    return ResourceRegistry(resources, base_path=base_path)


def _parse_theme(value: object, filename: str) -> ThemeRegistry:
    theme = _mapping(value, filename, "theme")
    values: dict[str, object] = {}
    for group_name, group_value in theme.items():
        if isinstance(group_value, Mapping):
            for name, item in group_value.items():
                values[str(name)] = item
        else:
            values[group_name] = group_value
    return ThemeRegistry(values)


def _string_list(
    value: object,
    filename: str,
    path: str,
    property_name: str,
) -> tuple[str, ...]:
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise TomlUIError(
            "expected an array of strings",
            filename=filename,
            table_path=path,
            property_name=property_name,
        )
    return tuple(value)


def _parse_styles(value: object, filename: str) -> StyleRegistry:
    tables = _mapping(value, filename, "style")
    defaults: dict[str, Mapping[str, object]] = {}
    styles: dict[str, StyleSpec] = {}
    for name, raw_value in tables.items():
        table = _mapping(raw_value, filename, f"style.{name}")
        if name == "defaults":
            for type_name, default_value in table.items():
                defaults[type_name] = _mapping(
                    default_value,
                    filename,
                    f"style.defaults.{type_name}",
                )
            continue
        extends = _string_list(
            table.get("extends", []),
            filename,
            f"style.{name}",
            "extends",
        )
        unsupported_states = _UNSUPPORTED_STYLE_STATES.intersection(table)
        if unsupported_states:
            state = min(unsupported_states)
            raise TomlUIError(
                "runtime state styles are not supported",
                filename=filename,
                table_path=f"style.{name}.{state}",
            )
        properties = {key: item for key, item in table.items() if key != "extends"}
        styles[name] = StyleSpec(name, extends, properties)
    registry = StyleRegistry(styles, defaults)
    for name in styles:
        registry.resolve_named(name)
    return registry


def _optional_string(
    table: Mapping[str, object],
    name: str,
    filename: str,
    path: str,
) -> str | None:
    value = table.get(name)
    if value is not None and not isinstance(value, str):
        raise TomlUIError(
            "expected a string",
            filename=filename,
            table_path=path,
            property_name=name,
        )
    return value


def _parse_commands(value: object, filename: str) -> dict[str, CommandSpec]:
    tables = _mapping(value, filename, "commands")
    commands: dict[str, CommandSpec] = {}
    for name, raw_value in tables.items():
        table = _mapping(raw_value, filename, f"commands.{name}")
        commands[name] = CommandSpec(
            name=name,
            text=_optional_string(table, "text", filename, f"commands.{name}"),
            icon=_optional_string(table, "icon", filename, f"commands.{name}"),
            shortcut=_optional_string(table, "shortcut", filename, f"commands.{name}"),
            tooltip=_optional_string(table, "tooltip", filename, f"commands.{name}"),
        )
    return commands


def _parse_menu_bars(
    bar_value: object,
    menu_value: object,
    commands: Mapping[str, CommandSpec],
    handlers: Mapping[str, EventHandler],
    filename: str,
) -> dict[str, MenuBar]:
    bar_tables = _mapping(bar_value, filename, "menu-bars")
    menu_tables = _mapping(menu_value, filename, "menus")
    menu_bars: dict[str, MenuBar] = {}
    for bar_name, raw_bar in bar_tables.items():
        bar_path = f"menu-bars.{bar_name}"
        bar_table = _mapping(raw_bar, filename, bar_path)
        menu_names = _string_list(
            bar_table.get("menus", []), filename, bar_path, "menus"
        )
        menu_bar = MenuBar()
        for menu_name in menu_names:
            try:
                raw_menu = menu_tables[menu_name]
            except KeyError as error:
                raise TomlUIError(
                    f"unknown menu {menu_name!r}",
                    filename=filename,
                    table_path=bar_path,
                    property_name="menus",
                ) from error
            menu_path = f"menus.{menu_name}"
            menu_table = _mapping(raw_menu, filename, menu_path)
            text = _optional_string(menu_table, "text", filename, menu_path)
            menu = menu_bar.add(Menu(text or menu_name))
            for command_name in _string_list(
                menu_table.get("items", []), filename, menu_path, "items"
            ):
                if command_name == "-":
                    menu.add_separator()
                    continue
                try:
                    command = commands[command_name]
                    handler = handlers[command_name]
                except KeyError as error:
                    raise TomlUIError(
                        f"unknown or unhandled command {command_name!r}",
                        filename=filename,
                        table_path=menu_path,
                        property_name="items",
                    ) from error
                menu.add(command.text or command_name).on_click(handler)
        menu_bars[bar_name] = menu_bar
    return menu_bars


def _string_mapping(value: object, filename: str, path: str) -> dict[str, str]:
    table = _mapping(value, filename, path)
    result: dict[str, str] = {}
    for name, item in table.items():
        if not isinstance(item, str):
            raise TomlUIError(
                "expected a string",
                filename=filename,
                table_path=path,
                property_name=name,
            )
        result[name] = item
    return result


def _parse_bindings(
    value: object,
    type_name: str,
    filename: str,
    path: str,
) -> dict[str, BindingSpec]:
    if isinstance(value, str):
        primary_properties = {
            "CheckBox": "selected",
            "RadioButton": "selected",
            "ProgressBar": "value",
            "Slider": "value",
            "Spinner": "value",
        }
        property_name = primary_properties.get(type_name, "text")
        return {property_name: BindingSpec(property_name, value)}
    table = _string_mapping(value, filename, f"{path}.bind")
    return {name: BindingSpec(name, model_path) for name, model_path in table.items()}


def _style_color(value: object, name: str) -> ColorInput:
    if isinstance(value, str):
        return value
    if (
        isinstance(value, list)
        and len(value) in {3, 4}
        and all(isinstance(item, int) and not isinstance(item, bool) for item in value)
    ):
        if len(value) == _RGB_COMPONENT_COUNT:
            return value[0], value[1], value[2]
        return value[0], value[1], value[2], value[3]
    raise TomlUIError(
        f"style property {name!r} must be a color string or RGB/RGBA array"
    )


def _parse_widgets(value: object, filename: str) -> dict[str, WidgetSpec]:
    tables = _mapping(value, filename, "widgets")
    specs: dict[str, WidgetSpec] = {}
    for name, raw_value in tables.items():
        path = f"widgets.{name}"
        table = _mapping(raw_value, filename, path)
        type_name = table.get("type")
        if not isinstance(type_name, str) or not type_name:
            raise TomlUIError(
                "concrete widget requires a non-empty string type",
                filename=filename,
                table_path=path,
                property_name="type",
            )
        public_id = _optional_string(table, "id", filename, path)
        styles = _string_list(table.get("styles", []), filename, path, "styles")
        children = _string_list(table.get("children", []), filename, path, "children")
        local_style = _mapping(table.get("style", {}), filename, f"{path}.style")
        events = _string_mapping(table.get("events", {}), filename, f"{path}.events")
        bindings = _parse_bindings(
            table.get("bind", {}),
            type_name,
            filename,
            path,
        )
        command = _optional_string(table, "command", filename, path)
        tab_title = _optional_string(table, "tab-title", filename, path)
        tab_background_value = table.get("tab-background")
        tab_background = (
            None
            if tab_background_value is None
            else _style_color(tab_background_value, "tab-background")
        )
        group_id = _optional_string(table, "group-id", filename, path)
        menu_bar = _optional_string(table, "menu-bar", filename, path)
        properties = {
            key: item for key, item in table.items() if key not in _RESERVED_WIDGET_KEYS
        }
        specs[name] = WidgetSpec(
            registry_name=name,
            type_name=type_name,
            public_id=public_id,
            properties=properties,
            style_names=styles,
            local_style=local_style,
            bindings=bindings,
            events=events,
            children=children,
            command=command,
            constraint=table.get("constraint"),
            tab_title=tab_title,
            tab_background=tab_background,
            group_id=group_id,
            menu_bar=menu_bar,
        )
    return specs


def _validate_widget_cycles(specs: Mapping[str, WidgetSpec], filename: str) -> None:
    visited: set[str] = set()
    active: list[str] = []

    def visit(name: str) -> None:
        if name in active:
            start = active.index(name)
            cycle = " -> ".join((*active[start:], name))
            raise TomlUIError(f"circular widget hierarchy: {cycle}", filename=filename)
        if name in visited:
            return
        active.append(name)
        for child in specs[name].children:
            visit(child)
        active.pop()
        visited.add(name)

    for name in specs:
        visit(name)


def _validate_specs(  # noqa: C901
    specs: Mapping[str, WidgetSpec],
    styles: StyleRegistry,
    commands: Mapping[str, CommandSpec],
    registry: WidgetRegistry,
    filename: str,
) -> None:
    ids: dict[str, str] = {}
    parents: dict[str, str] = {}
    for name, spec in specs.items():
        path = f"widgets.{name}"
        try:
            registry.resolve(spec.type_name)
        except TomlUIError as error:
            raise TomlUIError(
                str(error),
                filename=filename,
                table_path=path,
            ) from error
        for style_name in spec.style_names:
            try:
                styles.resolve_named(style_name)
            except TomlUIError as error:
                raise TomlUIError(
                    str(error), filename=filename, table_path=path
                ) from error
        if spec.command is not None and spec.command not in commands:
            suggestion = _suggest(spec.command, commands)
            raise TomlUIError(
                f"unknown command {spec.command!r}{suggestion}",
                filename=filename,
                table_path=path,
                property_name="command",
            )
        if spec.public_id is not None:
            previous = ids.get(spec.public_id)
            if previous is not None:
                message = (
                    f"duplicate public id {spec.public_id!r}; "
                    f"first used by {previous!r}"
                )
                raise TomlUIError(
                    message,
                    filename=filename,
                    table_path=path,
                    property_name="id",
                )
            ids[spec.public_id] = name
        for child in spec.children:
            if child not in specs:
                suggestion = _suggest(child, specs)
                raise TomlUIError(
                    f"unknown widget reference {child!r}{suggestion}",
                    filename=filename,
                    table_path=path,
                    property_name="children",
                )
            previous_parent = parents.get(child)
            if previous_parent is not None and previous_parent != name:
                raise TomlUIError(
                    f"widget {child!r} has multiple parents",
                    filename=filename,
                    table_path=path,
                    property_name="children",
                )
            parents[child] = name
    _validate_widget_cycles(specs, filename)


def _entry_window(
    config: Mapping[str, object],
    specs: Mapping[str, WidgetSpec],
    filename: str,
) -> str:
    app = _mapping(config.get("app", {}), filename, "config.app")
    entry = app.get("entry-window")
    if not isinstance(entry, str) or not entry:
        raise TomlUIError(
            "entry-window must name a widget",
            filename=filename,
            table_path="config.app",
            property_name="entry-window",
        )
    if entry not in specs:
        suggestion = _suggest(entry, specs)
        raise TomlUIError(
            f"unknown widget reference {entry!r}{suggestion}",
            filename=filename,
            table_path="config.app",
            property_name="entry-window",
        )
    return entry


def _apply_properties(
    component: Component,
    properties: Mapping[str, object],
    filename: str,
    registry_name: str,
) -> None:
    constructor_properties = {
        "title",
        "text",
        "columns",
        "selected",
        "gap",
        "rows",
        "horizontal-gap",
        "vertical-gap",
        "minimum",
        "maximum",
        "value",
        "step",
        "items",
        "orientation",
        "revealed",
        "editable",
        "modal",
        "divider-location",
        "alignment",
        "nodes",
        "width",
        "height",
        "image",
        "icon",
    }
    for toml_name, value in properties.items():
        if toml_name in constructor_properties:
            continue
        if toml_name == "markdown":
            if not isinstance(value, str):
                raise TomlUIError(
                    "markdown must be a string",
                    filename=filename,
                    table_path=f"widgets.{registry_name}",
                    property_name=toml_name,
                )
            component.set_markdown(value)
            continue
        name = _python_name(toml_name)
        if not hasattr(component, name):
            raise TomlUIError(
                f"{type(component).__name__} has no property {toml_name!r}",
                filename=filename,
                table_path=f"widgets.{registry_name}",
                property_name=toml_name,
            )
        try:
            setattr(component, name, value)
        except (TypeError, ValueError) as error:
            raise TomlUIError(
                str(error),
                filename=filename,
                table_path=f"widgets.{registry_name}",
                property_name=toml_name,
            ) from error


def _apply_image_resources(
    component: Component,
    properties: Mapping[str, object],
    resources: ResourceRegistry,
    filename: str,
    registry_name: str,
) -> None:
    property_name = "icon" if isinstance(component, Window) else "image"
    value = properties.get(property_name)
    if value is None:
        return
    if not isinstance(value, str):
        raise TomlUIError(
            "image resource name must be a string",
            filename=filename,
            table_path=f"widgets.{registry_name}",
            property_name=property_name,
        )
    if not hasattr(component, property_name):
        raise TomlUIError(
            f"{type(component).__name__} has no property {property_name!r}",
            filename=filename,
            table_path=f"widgets.{registry_name}",
            property_name=property_name,
        )
    try:
        setattr(component, property_name, resources.image(value))
    except (KeyError, OSError, ValueError) as error:
        raise TomlUIError(
            str(error),
            filename=filename,
            table_path=f"widgets.{registry_name}",
            property_name=property_name,
        ) from error


def _apply_menu_bar(
    component: Component,
    spec: WidgetSpec,
    menu_bars: Mapping[str, MenuBar],
    filename: str,
) -> None:
    if spec.menu_bar is None:
        return
    if not isinstance(component, Window):
        raise TomlUIError(
            "menu-bar is only valid on windows",
            filename=filename,
            table_path=f"widgets.{spec.registry_name}",
            property_name="menu-bar",
        )
    try:
        component.menu_bar = menu_bars[spec.menu_bar]
    except KeyError as error:
        raise TomlUIError(
            f"unknown menu bar {spec.menu_bar!r}",
            filename=filename,
            table_path=f"widgets.{spec.registry_name}",
            property_name="menu-bar",
        ) from error


def _style_integer(style: Mapping[str, object], name: str, default: int) -> int:
    value = style.get(name, default)
    if isinstance(value, bool) or not isinstance(value, int):
        raise TomlUIError(f"style property {name!r} must be an integer")
    return value


def _constraint_integer(value: Mapping[object, object], name: str, default: int) -> int:
    item = value.get(name, default)
    if isinstance(item, bool) or not isinstance(item, int):
        raise TomlUIError(f"GridBag {name} must be an integer")
    return item


def _constraint_number(
    value: Mapping[object, object],
    name: str,
    default: float,
) -> float:
    item = value.get(name, default)
    if isinstance(item, bool) or not isinstance(item, (int, float)):
        raise TomlUIError(f"GridBag {name} must be numeric")
    return float(item)


def _child_constraint(spec: WidgetSpec) -> object | None:
    value = spec.constraint
    if not isinstance(value, Mapping):
        return value
    fill_value = value.get("fill", "both")
    if not isinstance(fill_value, str):
        raise TomlUIError("GridBag fill must be a string")
    try:
        fill = {
            "none": Fill.NONE,
            "horizontal": Fill.HORIZONTAL,
            "vertical": Fill.VERTICAL,
            "both": Fill.BOTH,
        }[fill_value.lower()]
    except KeyError as error:
        raise TomlUIError(
            "GridBag fill must be none, horizontal, vertical, or both"
        ) from error
    return GridBagConstraints(
        gridx=_constraint_integer(value, "gridx", 0),
        gridy=_constraint_integer(value, "gridy", 0),
        gridwidth=_constraint_integer(value, "gridwidth", 1),
        gridheight=_constraint_integer(value, "gridheight", 1),
        weightx=_constraint_number(value, "weightx", 0.0),
        weighty=_constraint_number(value, "weighty", 0.0),
        fill=fill,
        inset=_constraint_integer(value, "inset", 4),
    )


def _resolved_child_constraint(
    parent: Container,
    child_name: str,
    spec: WidgetSpec,
) -> object | None:
    constraint = _child_constraint(spec)
    if isinstance(parent.layout, CardLayout):
        return child_name if constraint is None else str(constraint)
    if isinstance(parent.layout, BorderLayout) and constraint is None:
        return BorderLayout.CENTER
    if isinstance(parent.layout, BorderLayout) and isinstance(constraint, str):
        regions = {
            "north": BorderLayout.NORTH,
            "south": BorderLayout.SOUTH,
            "east": BorderLayout.EAST,
            "west": BorderLayout.WEST,
            "center": BorderLayout.CENTER,
        }
        try:
            return regions[constraint.lower()]
        except KeyError as error:
            raise TomlUIError(
                "Border constraint must be north, south, east, west, or center"
            ) from error
    return constraint


def _split_children(
    children: Sequence[tuple[str, Component, WidgetSpec]],
    spec: WidgetSpec,
    filename: str,
) -> tuple[Component, Component]:
    try:
        (_, first, _), (_, second, _) = children
    except ValueError as error:
        raise TomlUIError(
            "SplitPane requires exactly two children",
            filename=filename,
            table_path=f"widgets.{spec.registry_name}",
            property_name="children",
        ) from error
    return first, second


def _attach_children(
    component: Component,
    spec: WidgetSpec,
    children: Sequence[tuple[str, Component, WidgetSpec]],
    theme: ThemeRegistry,
    filename: str,
) -> None:
    if isinstance(component, TabbedPane):
        for child_name, child, child_spec in children:
            background_value = child_spec.tab_background
            background = (
                None
                if background_value is None
                else _style_color(theme.resolve(background_value), "tab-background")
            )
            component.add_tab(
                child_spec.tab_title or child_name,
                child,
                background=background,
            )
        return
    if isinstance(component, ScrollPane):
        if len(children) != 1:
            raise TomlUIError(
                "ScrollPane requires exactly one child",
                filename=filename,
                table_path=f"widgets.{spec.registry_name}",
                property_name="children",
            )
        component.set_content(children[0][1])
        return
    if isinstance(component, SplitPane):
        first_child, second_child = _split_children(children, spec, filename)
        component.first = component.add(first_child)
        component.second = component.add(second_child)
        return
    if isinstance(component, Container):
        for child_name, child, child_spec in children:
            component.add(
                child,
                _resolved_child_constraint(component, child_name, child_spec),
            )
        return
    if children:
        raise TomlUIError(
            f"{spec.type_name} cannot contain children",
            filename=filename,
            table_path=f"widgets.{spec.registry_name}",
            property_name="children",
        )


def _apply_style(component: Component, style: Mapping[str, object]) -> tuple[str, ...]:
    supported = {
        "width",
        "height",
        "min-width",
        "min-height",
        "font-family",
        "font-size",
        "font-weight",
        "foreground",
        "background",
        "gap",
    }
    width = _style_integer(style, "width", component.width)
    height = _style_integer(style, "height", component.height)
    width = max(width, _style_integer(style, "min-width", 0))
    height = max(height, _style_integer(style, "min-height", 0))
    component.set_size(width, height)
    face = style.get("font-family", "Segoe UI")
    size = style.get("font-size", 9)
    weight = style.get("font-weight", "normal")
    if not isinstance(face, str):
        raise TomlUIError("font-family must be a string")
    if isinstance(size, bool) or not isinstance(size, int):
        raise TomlUIError("font-size must be an integer")
    if not isinstance(weight, str):
        raise TomlUIError("font-weight must be a string")
    if any(name in style for name in ("font-family", "font-size", "font-weight")):
        component.set_font(face, size, bold=weight == "bold")
    if "foreground" in style:
        component.foreground = _style_color(style["foreground"], "foreground")
    if "background" in style:
        component.background = _style_color(style["background"], "background")
    layout = component.layout if isinstance(component, Container) else None
    if "gap" in style and isinstance(layout, BoxLayout):
        layout.gap = _style_integer(style, "gap", layout.gap)
    return tuple(sorted(set(style) - supported))


def _wire_events(
    component: Component,
    spec: WidgetSpec,
    command: CommandSpec | None,
    handlers: Mapping[str, EventHandler],
    filename: str,
) -> None:
    events = dict(spec.events)
    if spec.command is not None:
        events.setdefault("click", spec.command)
    for event_name, handler_name in events.items():
        try:
            handler = handlers[handler_name]
        except KeyError as error:
            raise TomlUIError(
                f"no Python handler registered for {handler_name!r}",
                filename=filename,
                table_path=f"widgets.{spec.registry_name}.events",
                property_name=event_name,
            ) from error
        if event_name == "click" and isinstance(component, Button):
            component.on_click(handler)
        elif event_name == "key":
            component.on_key(handler)
        elif event_name == "mouse":
            component.on_mouse(handler)
        elif (event_name == "change" and isinstance(component, (Slider, Spinner))) or (
            event_name == "change" and isinstance(component, ComboBox)
        ):
            component.on_change(handler)
        elif event_name == "select" and isinstance(component, ListBox):
            component.on_select(handler)
        else:
            raise TomlUIError(
                f"event {event_name!r} is not supported by {spec.type_name}",
                filename=filename,
                table_path=f"widgets.{spec.registry_name}.events",
                property_name=event_name,
            )
    del command


class TomlUILoader:
    """Parse, validate, resolve, and build backend-neutral TOML interfaces."""

    def __init__(self, widget_registry: WidgetRegistry | None = None) -> None:
        """Initialize with built-ins or an application-provided registry."""
        self.widget_registry = (
            WidgetRegistry.defaults() if widget_registry is None else widget_registry
        )

    def load(
        self,
        path: str | Path,
        *,
        handlers: Mapping[str, EventHandler] | None = None,
    ) -> LoadedUI:
        """Load a UTF-8 TOML UI file."""
        source = Path(path)
        with source.open("rb") as stream:
            document = tomllib.load(stream)
        return self.loads(document, filename=str(source), handlers=handlers)

    def _build(  # noqa: PLR0913, PLR0917
        self,
        entry_name: str,
        specs: Mapping[str, WidgetSpec],
        config: Mapping[str, object],
        resources: ResourceRegistry,
        theme: ThemeRegistry,
        styles: StyleRegistry,
        commands: Mapping[str, CommandSpec],
        menu_bars: Mapping[str, MenuBar],
        handlers: Mapping[str, EventHandler],
        filename: str,
    ) -> LoadedUI:
        widgets: dict[str, Component] = {}
        ids: dict[str, Component] = {}
        resolved_styles: dict[str, Mapping[str, object]] = {}
        ignored_styles: dict[str, tuple[str, ...]] = {}
        radio_groups: dict[str, RadioGroup] = {}

        def construct(name: str) -> Component:
            existing = widgets.get(name)
            if existing is not None:
                return existing
            spec = specs[name]
            properties = dict(spec.properties)
            command = commands.get(spec.command) if spec.command is not None else None
            if command is not None:
                if command.text is not None:
                    properties.setdefault("text", command.text)
                if command.tooltip is not None:
                    properties.setdefault("tooltip", command.tooltip)
            try:
                component = self.widget_registry.resolve(spec.type_name)(properties)
            except (TypeError, ValueError) as error:
                raise TomlUIError(
                    str(error),
                    filename=filename,
                    table_path=f"widgets.{name}",
                ) from error
            _apply_properties(component, properties, filename, name)
            _apply_image_resources(component, properties, resources, filename, name)
            _apply_menu_bar(component, spec, menu_bars, filename)
            resolved = styles.resolve(
                spec.type_name,
                spec.style_names,
                spec.local_style,
                theme,
            )
            ignored_styles[name] = _apply_style(component, resolved)
            resolved_styles[name] = MappingProxyType(resolved)
            widgets[name] = component
            if isinstance(component, RadioButton) and spec.group_id is not None:
                radio_groups.setdefault(spec.group_id, RadioGroup()).add(component)
            if spec.public_id is not None:
                ids[spec.public_id] = component
            children = [
                (child_name, construct(child_name), specs[child_name])
                for child_name in spec.children
            ]
            _attach_children(component, spec, children, theme, filename)
            _wire_events(component, spec, command, handlers, filename)
            return component

        root = construct(entry_name)
        return LoadedUI(
            root=root,
            widgets=MappingProxyType(widgets),
            ids=MappingProxyType(ids),
            specs=MappingProxyType(dict(specs)),
            config=MappingProxyType(dict(config)),
            resources=resources,
            theme=theme,
            styles=styles,
            commands=MappingProxyType(dict(commands)),
            menu_bars=MappingProxyType(dict(menu_bars)),
            resolved_styles=MappingProxyType(resolved_styles),
            ignored_styles=MappingProxyType(ignored_styles),
        )

    def _compile(
        self,
        document: Mapping[str, object],
        *,
        filename: str,
        handlers: Mapping[str, EventHandler],
    ) -> LoadedUI:
        config = _mapping(document.get("config", {}), filename, "config")
        resources = _parse_resources(document.get("resources", {}), filename)
        theme = _parse_theme(document.get("theme", {}), filename)
        styles = _parse_styles(document.get("style", {}), filename)
        commands = _parse_commands(document.get("commands", {}), filename)
        menu_bars = _parse_menu_bars(
            document.get("menu-bars", {}),
            document.get("menus", {}),
            commands,
            handlers,
            filename,
        )
        specs = _parse_widgets(document.get("widgets", {}), filename)
        _validate_specs(specs, styles, commands, self.widget_registry, filename)
        entry_name = _entry_window(config, specs, filename)
        return self._build(
            entry_name,
            specs,
            config,
            resources,
            theme,
            styles,
            commands,
            menu_bars,
            handlers,
            filename,
        )

    def loads(
        self,
        source: str | bytes | Mapping[str, object],
        *,
        filename: str = "<toml>",
        handlers: Mapping[str, EventHandler] | None = None,
    ) -> LoadedUI:
        """Load TOML text, bytes, or an already parsed mapping."""
        if isinstance(source, str):
            document = tomllib.loads(source)
        elif isinstance(source, bytes):
            document = tomllib.loads(source.decode("utf-8"))
        else:
            document = dict(source)
        return self._compile(document, filename=filename, handlers=handlers or {})


def load_toml_ui(
    path: str | Path,
    *,
    handlers: Mapping[str, EventHandler] | None = None,
    widget_registry: WidgetRegistry | None = None,
) -> LoadedUI:
    """Load and build one backend-independent TOML UI document."""
    return TomlUILoader(widget_registry).load(path, handlers=handlers)
