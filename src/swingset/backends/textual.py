"""Textual/Rich terminal backend implemented through typed peers."""

from __future__ import annotations

import contextlib
import math
import queue
import threading
from collections.abc import Callable
from typing import TYPE_CHECKING
from typing import cast

from textual.app import App as TextualApp
from textual.containers import Container as TextualContainer
from textual.containers import ScrollableContainer
from textual.widgets import Button as TextualButton
from textual.widgets import Checkbox as TextualCheckbox
from textual.widgets import DataTable
from textual.widgets import Input
from textual.widgets import Label as TextualLabel
from textual.widgets import ListItem
from textual.widgets import ListView
from textual.widgets import ProgressBar as TextualProgressBar
from textual.widgets import Select
from textual.widgets import Static
from textual.widgets import TextArea as TextualTextArea
from textual.widgets import Tree

import swingset.core as swingset_core
import swingset.widgets as swingset_widgets
from swingset.core import Component
from swingset.geometry import Rect
from swingset.geometry import Size
from swingset.models import ModelEvent
from swingset.peers import BooleanPeer
from swingset.peers import ComponentPeer
from swingset.peers import IntValuePeer
from swingset.peers import PasswordPeer
from swingset.peers import RichTextPeer
from swingset.peers import SelectionPeer
from swingset.peers import WindowPeer
from swingset.theme import ColorInput
from swingset.theme import Theme
from swingset.theme import resolve_color
from swingset.widgets import Button
from swingset.widgets import CheckBox
from swingset.widgets import ComboBox
from swingset.widgets import ListBox
from swingset.widgets import ProgressBar
from swingset.widgets import Slider
from swingset.widgets import TabbedPane
from swingset.widgets import Table
from swingset.widgets import TextArea
from swingset.widgets import TreeNode
from swingset.widgets import TreeView

from .base import Backend
from .base import Capability

_CELL_WIDTH = 8
_CELL_HEIGHT = 10


def _logical_rect_to_cells(bounds: Rect) -> Rect:
    return Rect(
        bounds.x // _CELL_WIDTH,
        bounds.y // _CELL_HEIGHT,
        max(1, math.ceil(bounds.width / _CELL_WIDTH)),
        max(1, math.ceil(bounds.height / _CELL_HEIGHT)),
    )


def _cell_size_to_logical(size: Size) -> Size:
    return Size(size.width * _CELL_WIDTH, size.height * _CELL_HEIGHT)


if TYPE_CHECKING:
    from typing import Protocol

    import textual.widget

    class _OffsetDocument(Protocol):
        def get_index_from_location(self, location: tuple[int, int]) -> int: ...

        def get_location_from_index(self, index: int) -> tuple[int, int]: ...


class _HostApp(TextualApp[None]):
    CSS = """
    Screen { layout: vertical; }
    .swingset-window { border: round $accent; padding: 0 1; }
    .swingset-status { dock: bottom; height: 1; }
    .swingset-toolbar { height: auto; }
    """

    def __init__(self, backend: TextualBackend) -> None:
        super().__init__()
        self.backend = backend

    def on_mount(self) -> None:
        self.backend.on_app_mounted()


class TextualPeer(ComponentPeer):
    """Common Textual peer behavior."""

    def __init__(
        self,
        backend: TextualBackend,
        component: Component,
        widget: textual.widget.Widget,
    ) -> None:
        """Initialize the instance."""
        super().__init__(component)
        self.backend = backend
        self.widget = widget

    @property
    def native(self) -> object:
        """Return the native."""
        return self.widget

    @property
    def text(self) -> str:
        """Return the text."""
        if isinstance(self.widget, Input):
            return self.widget.value
        if isinstance(self.widget, TextualTextArea):
            return self.widget.text
        return self.component.snapshot_text()

    @text.setter
    def text(self, value: str) -> None:
        """Set the text."""
        if isinstance(self.widget, Input):
            self.widget.value = value
        elif isinstance(self.widget, TextualTextArea):
            self.widget.text = value
        elif isinstance(self.widget, (TextualButton, TextualCheckbox)):
            self.widget.label = value
        elif isinstance(self.widget, Static):
            self.widget.update(value)

    def destroy(self) -> None:
        """Update destroy."""
        remove = getattr(self.widget, "remove", None)
        if callable(remove):
            remove()

    def set_visible(self, *, visible: bool) -> None:
        """Set visible."""
        with contextlib.suppress(AttributeError):
            self.widget.display = visible

    def set_enabled(self, *, enabled: bool) -> None:
        """Set enabled."""
        with contextlib.suppress(AttributeError):
            self.widget.disabled = not enabled

    def set_bounds(self, bounds: Rect) -> None:
        """Set bounds."""
        cells = _logical_rect_to_cells(bounds)
        try:
            self.widget.styles.position = "absolute"
            self.widget.styles.offset = (max(0, cells.x), max(0, cells.y))
            self.widget.styles.width = cells.width
            self.widget.styles.height = cells.height
        except AttributeError, ValueError:
            pass

    def client_size(self) -> Size:
        """Return client size."""
        try:
            size = self.widget.content_size
            if size.width > 0 and size.height > 0:
                return _cell_size_to_logical(Size(size.width, size.height))
        except AttributeError:
            pass
        return self.component.size

    def focus(self) -> None:
        """Move keyboard focus to the native component."""
        focus = getattr(self.widget, "focus", None)
        if callable(focus):
            focus()

    def set_font(self, face: str, size: int, *, bold: bool) -> None:
        # Terminal font family/point size is controlled by the terminal emulator.
        """Set font."""
        del face, size, bold

    def _color(self, color: ColorInput) -> str:
        red, green, blue, alpha = resolve_color(color, self.backend.theme)
        return f"rgba({red},{green},{blue},{alpha / 255:.3f})"

    def set_foreground(self, color: ColorInput | None) -> None:
        """Apply a resolved Textual foreground color."""
        self.widget.styles.color = self._color(color or "foreground")

    def set_background(self, color: ColorInput | None) -> None:
        """Apply a resolved Textual background color."""
        self.widget.styles.background = self._color(color or "background")

    def set_tooltip(self, text: str | None) -> None:
        """Set Textual's built-in widget tooltip."""
        self.widget.tooltip = text

    def apply_theme(self, theme: Theme) -> None:
        """Update apply theme."""
        self.backend.apply_theme(theme)


class TextualWindowPeer(TextualPeer, WindowPeer):
    """Peer implementation for window components."""

    def destroy(self) -> None:
        """Update destroy."""
        super().destroy()
        self.backend.window_closed()


class TextualButtonPeer(TextualPeer):
    """Peer implementation for button components."""

    def refresh(self) -> None:
        """Refresh native state from component state."""
        control = cast("Button", self.component)
        fallback = None if control.image is None else control.image.fallback
        text = control.snapshot_text()
        label = text if not fallback else f"{fallback} {text}".strip()
        cast("TextualButton", self.widget).label = label


class TextualImagePeer(TextualPeer):
    """Peer implementation for image components."""

    def refresh(self) -> None:
        """Refresh native state from component state."""
        image = getattr(self.component, "image", None)
        fallback = None if image is None else image.fallback
        text = (
            self.component.snapshot_text()
            if not fallback
            else f"{fallback} {self.component.snapshot_text()}".strip()
        )
        cast("Static", self.widget).update(text)


class TextualPasswordPeer(TextualPeer, PasswordPeer):
    """Textual masked-input peer."""

    def set_revealed(self, *, revealed: bool) -> None:
        """Toggle Textual input masking."""
        cast("Input", self.widget).password = not revealed

    def apply_theme(self, theme: Theme) -> None:
        """Apply theme and retain the portable reveal state."""
        super().apply_theme(theme)
        control = cast("swingset_widgets.PasswordField", self.component)
        self.set_revealed(revealed=control.revealed)


class TextualRichTextPeer(TextualPeer, RichTextPeer):
    """Plain terminal fallback retaining portable rich-text source spans."""

    def selection_range(self) -> tuple[int, int]:
        """Return Textual row/column selection as character offsets."""
        area = cast("TextualTextArea", self.widget)
        selection = area.selection
        document = cast("_OffsetDocument", area.document)
        return (
            document.get_index_from_location(selection.start),
            document.get_index_from_location(selection.end),
        )

    def set_selection_range(self, start: int, end: int) -> None:
        """Select Textual text from portable character offsets."""
        area = cast("TextualTextArea", self.widget)
        selection_type = type(area.selection)
        document = cast("_OffsetDocument", area.document)
        area.selection = selection_type(
            document.get_location_from_index(start),
            document.get_location_from_index(end),
        )

    def apply_styles(self) -> None:
        """Retain spans for GUI backends while displaying plain terminal text."""
        return


class TextualSpinnerPeer(TextualPeer, IntValuePeer):
    """Integer-input fallback for a spinner."""

    @property
    def value(self) -> int:
        """Return the valid integer input value."""
        try:
            return int(cast("Input", self.widget).value)
        except ValueError:
            return cast("swingset_widgets.Spinner", self.component).initial_value()

    @value.setter
    def value(self, value: int) -> None:
        cast("Input", self.widget).value = str(value)


class TextualScrollPeer(TextualPeer):
    """Textual scrollable-container peer."""

    def refresh(self) -> None:
        """Synchronize the terminal viewport offset."""
        super().refresh()
        x, y = cast("swingset_widgets.ScrollPane", self.component).scroll_position
        cast("ScrollableContainer", self.widget).scroll_to(x, y, animate=False)


class TextualCheckPeer(TextualPeer, BooleanPeer):
    """Peer implementation for check components."""

    @property
    def selected(self) -> bool:
        """Return the selected."""
        return cast("TextualCheckbox", self.widget).value

    @selected.setter
    def selected(self, value: bool) -> None:
        """Set the selected."""
        cast("TextualCheckbox", self.widget).value = value

    def refresh(self) -> None:
        """Refresh native state from component state."""
        self.selected = cast("CheckBox", self.component).selected


class TextualComboPeer(TextualPeer, SelectionPeer):
    """Peer implementation for combo components."""

    @property
    def selected_index(self) -> int:
        """Return the selected index."""
        value = cast("Select[object]", self.widget).value
        if value is Select.NULL:
            return -1
        try:
            return int(str(value))
        except ValueError:
            return -1

    @selected_index.setter
    def selected_index(self, index: int) -> None:
        """Set the selected index."""
        select = cast("Select[object]", self.widget)
        select.value = Select.NULL if index < 0 else str(index)

    def refresh(self) -> None:
        """Refresh native state from component state."""
        component = cast("ComboBox[object]", self.component)
        select = cast("Select[object]", self.widget)
        select.set_options(
            [(str(item), str(index)) for index, item in enumerate(component.model)],
        )
        self.selected_index = component.model.selected_index

    def on_model_event(self, event: ModelEvent) -> None:
        """Handle a model event update."""
        del event
        self.refresh()


class TextualListPeer(TextualPeer, SelectionPeer):
    """Peer implementation for list components."""

    @property
    def selected_index(self) -> int:
        """Return the selected index."""
        value = getattr(cast("ListView", self.widget), "index", None)
        return -1 if value is None else int(value)

    @selected_index.setter
    def selected_index(self, index: int) -> None:
        """Set the selected index."""
        if index >= 0:
            cast("ListView", self.widget).index = index

    def refresh(self) -> None:
        """Refresh native state from component state."""
        component = cast("ListBox[object]", self.component)
        view = cast("ListView", self.widget)
        view.clear()
        view.extend([ListItem(TextualLabel(str(item))) for item in component.model])

    def on_model_event(self, event: ModelEvent) -> None:
        """Handle a model event update."""
        del event
        self.refresh()


class TextualTablePeer(TextualPeer):
    """Peer implementation for table components."""

    def refresh(self) -> None:
        """Refresh native state from component state."""
        component = cast("Table", self.component)
        table = cast("DataTable[object]", self.widget)
        table.clear(columns=True)
        if component.model.columns:
            table.add_columns(*component.model.columns)
        if component.model.rows:
            table.add_rows(
                [tuple(str(value) for value in row) for row in component.model.rows],
            )

    def on_model_event(self, event: ModelEvent) -> None:
        """Handle a model event update."""
        del event
        self.refresh()


class TextualTreePeer(TextualPeer):
    """Peer implementation for tree components."""

    def _add_node(self, parent: object, node: TreeNode) -> None:
        add = getattr(parent, "add", None)
        if not callable(add):
            return
        target = add(node.text)
        for child in node:
            self._add_node(target, child)

    def refresh(self) -> None:
        """Refresh native state from component state."""
        component = cast("TreeView", self.component)
        tree = cast("Tree[object]", self.widget)
        tree.clear()
        for root in component.roots:
            self._add_node(tree.root, root)


class TextualTabPeer(TextualPeer, SelectionPeer):
    """Graceful terminal tab emulation using child visibility."""

    @property
    def selected_index(self) -> int:
        """Return the selected index."""
        return cast("TabbedPane", self.component).initial_selected_index()

    @selected_index.setter
    def selected_index(self, index: int) -> None:
        """Set the selected index."""
        cast("TabbedPane", self.component).sync_selected_index_from_peer(index)
        self.refresh()

    def refresh(self) -> None:
        """Refresh native state from component state."""
        component = cast("TabbedPane", self.component)
        selected = component.initial_selected_index()
        for index, (_title, child) in enumerate(component.tabs):
            if isinstance(child.peer, TextualPeer):
                child.peer.set_visible(visible=index == selected)


class TextualProgressPeer(TextualPeer, IntValuePeer):
    """Peer implementation for progress components."""

    @property
    def value(self) -> int:
        """Return the value."""
        return cast("ProgressBar", self.component).initial_value()

    @value.setter
    def value(self, value: int) -> None:
        """Set the value."""
        control = cast("ProgressBar", self.component)
        widget = cast("TextualProgressBar", self.widget)
        total = max(1, control.maximum - control.minimum)
        widget.update(total=total, progress=value - control.minimum)

    def refresh(self) -> None:
        """Refresh native state from component state."""
        self.value = cast("ProgressBar", self.component).initial_value()


class TextualSliderPeer(TextualPeer, IntValuePeer):
    """Peer implementation for slider components."""

    @property
    def value(self) -> int:
        """Return the value."""
        control = cast("Slider", self.component)
        value = cast("Input", self.widget).value
        try:
            return max(control.minimum, min(control.maximum, int(value)))
        except ValueError:
            return control.initial_value()

    @value.setter
    def value(self, value: int) -> None:
        """Set the value."""
        control = cast("Slider", self.component)
        resolved = max(control.minimum, min(control.maximum, value))
        cast("Input", self.widget).value = str(resolved)

    def refresh(self) -> None:
        """Refresh native state from component state."""
        self.value = cast("Slider", self.component).initial_value()


class TextualBackend(Backend):
    """Terminal UI backend using Textual while preserving portable semantics."""

    name = "textual"
    capabilities = frozenset(
        {
            Capability.DARK_MODE,
            Capability.TABLE,
            Capability.TREE,
            Capability.TOOLBAR,
            Capability.STATUS_BAR,
            Capability.TERMINAL_UI,
            Capability.SCROLL_PANE,
            Capability.TOOLTIPS,
        },
    )

    def __init__(self, *, headless: bool = False) -> None:
        """Initialize the instance."""
        super().__init__()
        self._app: _HostApp | None = None
        self._queue: queue.Queue[Callable[[], object]] = queue.Queue()
        self._mounted = False
        self._thread_id: int | None = None
        self._windows = 0
        self.theme = Theme.SYSTEM
        self.headless = headless

    def _require_app(self) -> _HostApp:
        if self._app is None:
            msg = "Textual backend is not initialized"
            raise RuntimeError(msg)
        return self._app

    def _parent_widget(
        self,
        parent: ComponentPeer | None,
    ) -> textual.widget.Widget | None:
        return parent.widget if isinstance(parent, TextualPeer) else None

    def _mount(
        self,
        widget: textual.widget.Widget,
        parent: ComponentPeer | None,
    ) -> None:
        parent_widget = self._parent_widget(parent)
        if parent_widget is not None:
            parent_widget.mount(widget)
        else:
            self._require_app().mount(widget)

    def _peer(
        self,
        component: Component,
        parent: ComponentPeer | None,
        widget: textual.widget.Widget,
        peer_type: type[TextualPeer] = TextualPeer,
    ) -> ComponentPeer:
        self._mount(widget, parent)
        return peer_type(self, component, widget)

    def _window_factory(
        self,
        component: Component,
        parent: ComponentPeer | None,
    ) -> ComponentPeer:
        control = cast("swingset_core.Container", component)

        class ResizableWindow(TextualContainer):
            def on_resize(self, _event: object) -> None:
                control.handle_native_resize()

        self.initialize()
        self._windows += 1
        widget = ResizableWindow(classes="swingset-window")
        self._mount(widget, parent)
        return TextualWindowPeer(self, component, widget)

    def _container_factory(
        self,
        component: Component,
        parent: ComponentPeer | None,
    ) -> ComponentPeer:
        return self._peer(component, parent, TextualContainer())

    def _toolbar_factory(
        self,
        component: Component,
        parent: ComponentPeer | None,
    ) -> ComponentPeer:
        return self._peer(
            component,
            parent,
            TextualContainer(classes="swingset-toolbar"),
        )

    def _label_factory(
        self,
        component: Component,
        parent: ComponentPeer | None,
    ) -> ComponentPeer:
        return self._peer(component, parent, TextualLabel(component.snapshot_text()))

    def _status_factory(
        self,
        component: Component,
        parent: ComponentPeer | None,
    ) -> ComponentPeer:
        return self._peer(
            component,
            parent,
            Static(component.snapshot_text(), classes="swingset-status"),
        )

    def _image_factory(
        self,
        component: Component,
        parent: ComponentPeer | None,
    ) -> ComponentPeer:
        widget = Static(component.snapshot_text())
        self._mount(widget, parent)
        return TextualImagePeer(self, component, widget)

    def _button_factory(
        self,
        component: Component,
        parent: ComponentPeer | None,
    ) -> ComponentPeer:
        control = cast("Button", component)

        class ActionButton(TextualButton):
            def on_button_pressed(self, _event: TextualButton.Pressed) -> None:
                control.trigger_action()

        widget = ActionButton(component.snapshot_text())
        self._mount(widget, parent)
        return TextualButtonPeer(self, component, widget)

    def _checkbox_factory(
        self,
        component: Component,
        parent: ComponentPeer | None,
    ) -> ComponentPeer:
        control = cast("CheckBox", component)

        class ActionCheck(TextualCheckbox):
            def on_checkbox_changed(self, _event: TextualCheckbox.Changed) -> None:
                control.selected = self.value
                control.trigger_action()

        widget = ActionCheck(component.snapshot_text(), value=control.selected)
        self._mount(widget, parent)
        return TextualCheckPeer(self, component, widget)

    def _input_factory(
        self,
        component: Component,
        parent: ComponentPeer | None,
    ) -> ComponentPeer:
        return self._peer(component, parent, Input(value=component.snapshot_text()))

    def _password_factory(
        self,
        component: Component,
        parent: ComponentPeer | None,
    ) -> ComponentPeer:
        control = cast("swingset_widgets.PasswordField", component)
        widget = Input(
            value=control.snapshot_text(),
            password=not control.revealed,
        )
        return self._peer(component, parent, widget, TextualPasswordPeer)

    def _text_area_factory(
        self,
        component: Component,
        parent: ComponentPeer | None,
    ) -> ComponentPeer:
        control = cast("TextArea", component)
        return self._peer(
            component,
            parent,
            TextualTextArea(control.snapshot_text()),
        )

    def _rich_text_factory(
        self,
        component: Component,
        parent: ComponentPeer | None,
    ) -> ComponentPeer:
        control = cast("swingset_widgets.RichTextPane", component)
        widget = TextualTextArea(
            control.snapshot_text(),
            read_only=not control.editable,
        )
        peer = cast(
            "TextualRichTextPeer",
            self._peer(component, parent, widget, TextualRichTextPeer),
        )
        peer.set_selection_range(*control.initial_selection_range())
        return peer

    def _spinner_factory(
        self,
        component: Component,
        parent: ComponentPeer | None,
    ) -> ComponentPeer:
        control = cast("swingset_widgets.Spinner", component)

        class ActionSpinner(Input):
            def on_input_changed(self, event: Input.Changed) -> None:
                try:
                    value = int(event.value)
                except ValueError:
                    return
                control.notify_value_changed(
                    max(control.minimum, min(control.maximum, value))
                )

        widget = ActionSpinner(value=str(control.initial_value()), type="integer")
        return self._peer(component, parent, widget, TextualSpinnerPeer)

    def _separator_factory(
        self,
        component: Component,
        parent: ComponentPeer | None,
    ) -> ComponentPeer:
        control = cast("swingset_widgets.Separator", component)
        line = (
            "─"
            if control.orientation is swingset_widgets.SeparatorOrientation.HORIZONTAL
            else "│"
        )
        return self._peer(component, parent, Static(line))

    def _scroll_factory(
        self,
        component: Component,
        parent: ComponentPeer | None,
    ) -> ComponentPeer:
        return self._peer(
            component,
            parent,
            ScrollableContainer(),
            TextualScrollPeer,
        )

    def _combo_factory(
        self,
        component: Component,
        parent: ComponentPeer | None,
    ) -> ComponentPeer:
        control = cast("ComboBox[object]", component)

        class ActionSelect(Select[object]):
            def on_select_changed(self, _event: Select.Changed) -> None:
                value = self.value
                index = -1 if value is Select.NULL else int(str(value))
                control.notify_selection(index)

        options = [(str(item), str(index)) for index, item in enumerate(control.model)]
        widget = ActionSelect(options, allow_blank=True)
        self._mount(widget, parent)
        return TextualComboPeer(self, component, widget)

    def _list_factory(
        self,
        component: Component,
        parent: ComponentPeer | None,
    ) -> ComponentPeer:
        control = cast("ListBox[object]", component)

        class ActionList(ListView):
            def on_list_view_selected(self, event: ListView.Selected) -> None:
                index = self.index if self.index is not None else -1
                control.notify_selection(index)
                del event

        widget = ActionList(
            *[ListItem(TextualLabel(str(item))) for item in control.model],
        )
        self._mount(widget, parent)
        return TextualListPeer(self, component, widget)

    def _table_factory(
        self,
        component: Component,
        parent: ComponentPeer | None,
    ) -> ComponentPeer:
        return self._peer(component, parent, DataTable(), TextualTablePeer)

    def _tree_factory(
        self,
        component: Component,
        parent: ComponentPeer | None,
    ) -> ComponentPeer:
        return self._peer(component, parent, Tree("Root"), TextualTreePeer)

    def _tab_factory(
        self,
        component: Component,
        parent: ComponentPeer | None,
    ) -> ComponentPeer:
        return self._peer(component, parent, TextualContainer(), TextualTabPeer)

    def _progress_factory(
        self,
        component: Component,
        parent: ComponentPeer | None,
    ) -> ComponentPeer:
        control = cast("ProgressBar", component)
        widget = TextualProgressBar(total=max(1, control.maximum - control.minimum))
        self._mount(widget, parent)
        return TextualProgressPeer(self, component, widget)

    def _slider_factory(
        self,
        component: Component,
        parent: ComponentPeer | None,
    ) -> ComponentPeer:
        control = cast("Slider", component)

        class ActionSlider(Input):
            def on_input_changed(self, event: Input.Changed) -> None:
                try:
                    value = int(event.value)
                except ValueError:
                    return
                control.notify_value_changed(
                    max(control.minimum, min(control.maximum, value)),
                )

        widget = ActionSlider(
            value=str(control.initial_value()),
            type="integer",
        )
        self._mount(widget, parent)
        return TextualSliderPeer(self, component, widget)

    def _drain(self) -> None:
        while True:
            try:
                callback = self._queue.get_nowait()
            except queue.Empty:
                return
            callback()

    def on_app_mounted(self) -> None:
        """Mark the Textual app as mounted and run queued callbacks."""
        self._mounted = True
        self._drain()

    def install_factories(self) -> None:
        """Update install factories."""
        self.register_peer(swingset_core.Window, self._window_factory)
        self.register_peer(swingset_widgets.TabbedPane, self._tab_factory)
        self.register_peer(swingset_widgets.SplitPane, self._container_factory)
        self.register_peer(swingset_widgets.ScrollPane, self._scroll_factory)
        self.register_peer(swingset_widgets.ToolBar, self._toolbar_factory)
        self.register_peer(swingset_widgets.Panel, self._container_factory)
        self.register_peer(swingset_core.Container, self._container_factory)
        self.register_peer(swingset_widgets.CheckBox, self._checkbox_factory)
        self.register_peer(swingset_widgets.Button, self._button_factory)
        self.register_peer(swingset_widgets.ImageLabel, self._image_factory)
        self.register_peer(swingset_widgets.StatusBar, self._status_factory)
        self.register_peer(swingset_widgets.Label, self._label_factory)
        self.register_peer(swingset_widgets.PasswordField, self._password_factory)
        self.register_peer(swingset_widgets.RichTextPane, self._rich_text_factory)
        self.register_peer(swingset_widgets.Separator, self._separator_factory)
        self.register_peer(swingset_widgets.TextArea, self._text_area_factory)
        self.register_peer(swingset_widgets.TextField, self._input_factory)
        self.register_peer(swingset_widgets.ComboBox, self._combo_factory)
        self.register_peer(swingset_widgets.ListBox, self._list_factory)
        self.register_peer(swingset_widgets.Table, self._table_factory)
        self.register_peer(swingset_widgets.TreeView, self._tree_factory)
        self.register_peer(swingset_widgets.ProgressBar, self._progress_factory)
        self.register_peer(swingset_widgets.Slider, self._slider_factory)
        self.register_peer(swingset_widgets.Spinner, self._spinner_factory)

    def initialize(self) -> None:
        """Initialize backend resources."""
        if self._app is None:
            self._app = _HostApp(self)

    def run(self, startup: Callable[[], object] | None = None) -> None:
        """Run the backend event loop."""
        self.initialize()
        self._thread_id = threading.get_ident()
        if startup is not None:
            self._queue.put(startup)
        app = self._require_app()
        try:
            app.run(headless=self.headless)
        finally:
            self._thread_id = None
            self._mounted = False

    def call_soon(self, callback: Callable[[], object]) -> None:
        """Schedule a callback on the UI thread."""
        self._queue.put(callback)
        app = self._app
        if app is not None and self._mounted:
            if self._thread_id == threading.get_ident():
                app.call_later(self._drain)
            else:
                app.call_from_thread(self._drain)

    def window_closed(self) -> None:
        """Update window closed."""
        self._windows = max(0, self._windows - 1)
        if self._windows == 0 and self._app is not None:
            self._app.exit()

    def apply_theme(self, theme: Theme) -> None:
        """Update apply theme."""
        self.theme = theme
        app = self._app
        if app is not None and theme is not Theme.SYSTEM:
            app.theme = "textual-dark" if theme is Theme.DARK else "textual-light"
