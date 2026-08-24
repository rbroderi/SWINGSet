"""Cross-backend conformance tests for peer registration contracts."""

from __future__ import annotations

import importlib
from collections.abc import Callable
from collections.abc import Iterable
from typing import cast
from unittest.mock import patch

import pytest

from swingset import Backend
from swingset import BoxLayout
from swingset import Button
from swingset import Capability
from swingset import CheckBox
from swingset import ComboBox
from swingset import Component
from swingset import ComponentState
from swingset import Container
from swingset import Frame
from swingset import GroupBox
from swingset import ImageLabel
from swingset import Label
from swingset import ListBox
from swingset import Menu
from swingset import MenuBar
from swingset import PaintSurface
from swingset import Panel
from swingset import PasswordField
from swingset import ProgressBar
from swingset import RadioButton
from swingset import RichTextPane
from swingset import ScrollPane
from swingset import Separator
from swingset import Slider
from swingset import Spinner
from swingset import SplitPane
from swingset import StatusBar
from swingset import TabbedPane
from swingset import Table
from swingset import TextArea
from swingset import TextField
from swingset import ToolBar
from swingset import TreeView
from swingset import UIContext
from swingset import Window

_BACKENDS = (
    ("win32", "Win32Backend"),
    ("tkinter", "TkinterBackend"),
    ("textual", "TextualBackend"),
)
_REQUIRED_COMPONENTS: tuple[type[Component], ...] = (
    Window,
    Container,
    Panel,
    GroupBox,
    Button,
    CheckBox,
    RadioButton,
    Label,
    ImageLabel,
    TextField,
    TextArea,
    PasswordField,
    RichTextPane,
    ComboBox,
    ListBox,
    Table,
    TreeView,
    ProgressBar,
    Slider,
    Spinner,
    Separator,
    TabbedPane,
    SplitPane,
    ScrollPane,
    ToolBar,
    StatusBar,
)
_CAPABILITY_COMPONENTS: dict[Capability, type[Component]] = {
    Capability.TABLE: Table,
    Capability.TREE: TreeView,
    Capability.TABS: TabbedPane,
    Capability.SPLIT_PANE: SplitPane,
    Capability.SCROLL_PANE: ScrollPane,
    Capability.TOOLBAR: ToolBar,
    Capability.STATUS_BAR: StatusBar,
    Capability.RICH_TEXT: RichTextPane,
    Capability.CUSTOM_PAINT: PaintSurface,
}


def _load_backend(module_name: str, type_name: str) -> Backend:
    try:
        module = importlib.import_module(f"swingset.backends.{module_name}")
    except ImportError as error:
        pytest.skip(f"{module_name} backend dependencies unavailable: {error}")
    backend_type = cast("type[Backend]", getattr(module, type_name))
    if module_name == "textual":
        factory = cast("Callable[..., Backend]", backend_type)
        return factory(headless=True)
    return backend_type()


@pytest.mark.parametrize(("module_name", "type_name"), _BACKENDS)
def test_backend_resolves_standard_component_set(
    module_name: str,
    type_name: str,
) -> None:
    """Every backend resolves all required portable components through MRO."""
    backend = _load_backend(module_name, type_name)
    missing = [
        component_type.__name__
        for component_type in _REQUIRED_COMPONENTS
        if not backend.supports_component(component_type)
    ]
    assert missing == []


@pytest.mark.parametrize(("module_name", "type_name"), _BACKENDS)
def test_advertised_widget_capabilities_have_peers(
    module_name: str,
    type_name: str,
) -> None:
    """Advertised widget capabilities correspond to registered peers."""
    backend = _load_backend(module_name, type_name)
    advertised: Iterable[tuple[Capability, type[Component]]] = (
        (capability, component_type)
        for capability, component_type in _CAPABILITY_COMPONENTS.items()
        if backend.supports(capability)
    )
    missing = [
        capability.value
        for capability, component_type in advertised
        if not backend.supports_component(component_type)
    ]
    assert missing == []


def test_win32_folder_dialog_uses_modern_file_picker() -> None:
    """The Win32 folder browser delegates to the modern folder picker."""
    module = pytest.importorskip("swingset.backends.win32")
    backend = module.Win32Backend()

    with patch.object(
        module,
        "_modern_folder_dialog",
        return_value=r"C:\Selected",
    ) as picker:
        result = backend.choose_folder(None, "Select folder")

    assert result == r"C:\Selected"
    picker.assert_called_once_with(0, "Select folder")


@pytest.mark.parametrize(("module_name", "type_name"), _BACKENDS)
def test_real_backend_component_lifecycle(
    module_name: str,
    type_name: str,
) -> None:
    """Mount real peers and exercise events, models, styling, resize, and teardown."""
    backend = _load_backend(module_name, type_name)
    context = UIContext(backend)
    failures: list[Exception] = []
    completed: list[bool] = []
    destroyed: list[ComponentState] = []

    def probe() -> None:
        context.dispatcher.enter_ui_thread()
        frame = Frame("Conformance", context=context)
        try:
            frame.layout = BoxLayout(gap=0)
            button = frame.add(Button("Action"))
            combo = frame.add(ComboBox(["one"]))
            actions: list[str] = []
            button.on_click(lambda _event: actions.append("clicked"))
            menu_bar = MenuBar()
            file_menu = menu_bar.add(Menu("File"))
            file_menu.add("Action", lambda _event: actions.append("menu"))
            file_menu.add_separator()
            frame.menu_bar = menu_bar

            frame.visible = True
            button.trigger_action()
            file_menu.items[0].trigger_action() if file_menu.items[0] else None
            combo.model.add("two")
            button.text = "Updated"
            button.foreground = "accent"
            button.background = "background"
            button.tooltip = "Conformance tooltip"
            frame.set_size(360, 220)
            frame.handle_native_resize()

            assert actions == ["clicked", "menu"]
            assert button.peer is not None
            assert button.peer.text == "Updated"
            assert combo.model.to_list() == ["one", "two"]
            assert button.width == frame.client_size().width
            completed.append(True)
        except Exception as error:  # noqa: BLE001
            failures.append(error)
        finally:
            frame.destroy()
            destroyed.append(frame.state)
            context.dispatcher.leave_ui_thread()

    backend.run(probe)

    if failures:
        raise failures[0]
    assert completed == [True]
    assert destroyed == [ComponentState.DESTROYED]
    assert context.windows.open_count == 0
