"""Cross-backend conformance tests for peer registration contracts."""

from __future__ import annotations

import importlib
from collections.abc import Callable, Iterable
from typing import cast
from unittest.mock import patch

import pytest
from swingset import (
    Backend,
    BoxLayout,
    Button,
    Capability,
    CheckBox,
    ComboBox,
    Component,
    ComponentState,
    Container,
    Frame,
    GroupBox,
    ImageLabel,
    Label,
    ListBox,
    Menu,
    MenuBar,
    PaintSurface,
    Panel,
    PasswordField,
    ProgressBar,
    RadioButton,
    RichTextPane,
    ScrollPane,
    Separator,
    Slider,
    Spinner,
    SplitPane,
    StatusBar,
    TabbedPane,
    Table,
    TextArea,
    TextField,
    ToolBar,
    TreeView,
    UIContext,
    Window,
)

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


def test_win32_scroll_peer_uses_native_scroll_info_tuple() -> None:
    """Pass pywin32 the positional SCROLLINFO representation it requires."""
    module = pytest.importorskip("swingset.backends.win32")
    peer = object.__new__(module.Win32ScrollPeer)
    peer.hwnd = 42

    with patch.object(module, "_set_scroll_info") as set_scroll_info:
        peer._set_scroll_info(module.win32con.SB_VERT, 7, 100, 20)

    set_scroll_info.assert_called_once_with(
        42,
        module.win32con.SB_VERT,
        (module.win32con.SIF_ALL, 0, 99, 20, 7, 0),
        True,
    )


def test_win32_text_update_repaints_immediately() -> None:
    """Flush text painting without waiting for another native window event."""
    module = pytest.importorskip("swingset.backends.win32")
    peer = object.__new__(module.Win32Peer)
    peer.hwnd = 42

    with (
        patch.object(module, "_set_window_text") as set_window_text,
        patch.object(module.win32gui, "UpdateWindow") as update_window,
    ):
        module.Win32Peer.text.__set__(peer, "live output")

    set_window_text.assert_called_once_with(42, "live output")
    update_window.assert_called_once_with(42)


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
