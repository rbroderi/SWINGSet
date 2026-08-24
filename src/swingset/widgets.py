"""Backend-neutral Pythonic widgets backed by typed peer capabilities."""

from __future__ import annotations

from collections.abc import Callable
from collections.abc import Iterable
from collections.abc import Iterator
from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import override

from .backends.base import Capability
from .core import Component
from .core import Container
from .events import ActionEvent
from .events import ItemEvent
from .events import ListSelectionEvent
from .geometry import Size
from .imaging import ImageResource
from .layout import FlowLayout
from .models import ComboBoxModel
from .models import ListModel
from .models import ModelEvent
from .models import TableModel
from .peers import BooleanPeer
from .peers import IntValuePeer
from .peers import PasswordPeer
from .peers import RichTextPeer
from .peers import SelectionPeer
from .richtext import RichTextSpan as RichTextSpan
from .richtext import RichTextStyle as RichTextStyle
from .theme import ColorInput

type ActionListener = Callable[[ActionEvent["Button"]], None]


class Label(Component):
    """Single-line text label."""

    def __init__(self, text: str = "") -> None:
        """Initialize a label with text-based default width."""
        super().__init__(text)
        self.width = max(80, len(text) * 8)


class ImageLabel(Label):
    """Label displaying a portable image resource when the backend can."""

    def __init__(self, image: ImageResource | None = None, text: str = "") -> None:
        """Initialize an image label with optional image and text."""
        super().__init__(text)
        self._image = image
        if image is not None:
            self.size = Size(*image.logical_size)

    @property
    def image(self) -> ImageResource | None:
        """Return the current image resource."""
        return self._image

    @image.setter
    def image(self, value: ImageResource | None) -> None:
        self._image = value
        self.refresh()


class Button(Component):
    """Push button with typed action callbacks."""

    def __init__(self, text: str = "", image: ImageResource | None = None) -> None:
        """Initialize a button with optional text and image."""
        super().__init__(text)
        self.size = Size(max(90, len(text) * 8 + 24), 28)
        self._listeners: list[ActionListener] = []
        self._image = image

    @property
    def image(self) -> ImageResource | None:
        """Return the current button image resource."""
        return self._image

    @image.setter
    def image(self, value: ImageResource | None) -> None:
        self._image = value
        self.refresh()

    def on_click(self, listener: ActionListener) -> ActionListener:
        """Register a click listener and return it."""
        self._listeners.append(listener)
        return listener

    def _emit_action(self) -> None:
        event = ActionEvent[Button](self, self.text)
        for listener in tuple(self._listeners):
            listener(event)

    def trigger_action(self) -> None:
        """Notify click listeners about an invoked action."""
        self._emit_action()


class TextField(Component):
    """Single-line editable text field."""

    def __init__(self, text: str = "", columns: int = 20) -> None:
        """Initialize a single-line text field."""
        super().__init__(text)
        self.columns = columns
        self.size = Size(max(80, columns * 8), 24)


class TextArea(TextField):
    """Multiline editable text area."""

    def __init__(self, text: str = "", rows: int = 6, columns: int = 30) -> None:
        """Initialize a multiline text area."""
        super().__init__(text, columns)
        self.rows = rows
        self.size = Size(max(160, columns * 8), max(80, rows * 20))


class PasswordField(TextField):
    """Single-line text field whose contents are masked by default."""

    def __init__(
        self,
        text: str = "",
        columns: int = 20,
        *,
        revealed: bool = False,
    ) -> None:
        """Initialize a password field with optional initial reveal state."""
        super().__init__(text, columns)
        self._revealed = revealed

    @property
    def revealed(self) -> bool:
        """Return whether the underlying text is currently visible."""
        return self._revealed

    @revealed.setter
    def revealed(self, value: bool) -> None:
        self._revealed = value
        peer = self.peer
        if isinstance(peer, PasswordPeer) and self.created:
            peer.set_revealed(revealed=value)


class RichTextPane(TextArea):
    """Editable multiline text with portable character style spans."""

    def __init__(
        self,
        text: str = "",
        rows: int = 8,
        columns: int = 40,
        *,
        editable: bool = True,
    ) -> None:
        """Initialize rich text and its editable state."""
        super().__init__(text, rows, columns)
        self.editable = editable
        self._selection_range = (0, 0)

    @property
    def selection_range(self) -> tuple[int, int]:
        """Return the selected half-open character range."""
        peer = self.peer
        if isinstance(peer, RichTextPeer) and self.created:
            self._selection_range = peer.selection_range()
        return self._selection_range

    @selection_range.setter
    def selection_range(self, value: tuple[int, int]) -> None:
        start, end = value
        if start < 0 or end < start or end > len(self.snapshot_text()):
            msg = "selection range is outside the current text"
            raise ValueError(msg)
        self._selection_range = value
        peer = self.peer
        if isinstance(peer, RichTextPeer) and self.created:
            peer.set_selection_range(start, end)

    def initial_selection_range(self) -> tuple[int, int]:
        """Return the requested selection before peer synchronization."""
        return self._selection_range

    def apply_style_to_selection(
        self,
        style: RichTextStyle,
    ) -> RichTextSpan | None:
        """Apply a portable style to the current non-empty selection."""
        self.text
        start, end = self.selection_range
        if start == end:
            return None
        span = self.add_style(start, end, style)
        self.selection_range = (start, end)
        return span


class CheckBox(Button):
    """Boolean checkbox with a strongly typed peer contract."""

    def __init__(self, text: str = "", *, selected: bool = False) -> None:
        """Initialize a checkbox with initial checked state."""
        super().__init__(text)
        self._selected = selected

    @property
    def selected(self) -> bool:
        """Return the checkbox state, syncing from peer when mounted."""
        peer = self.peer
        if isinstance(peer, BooleanPeer) and self.created:
            self._selected = peer.selected
        return self._selected

    def _apply_selected(self, *, selected: bool) -> None:
        self._selected = selected
        peer = self.peer
        if isinstance(peer, BooleanPeer) and self.created:
            peer.selected = self._selected

    @selected.setter
    def selected(self, value: bool) -> None:
        self._apply_selected(selected=value)


class RadioGroup:
    """Mutually exclusive collection of radio buttons."""

    def __init__(self) -> None:
        """Initialize an empty group."""
        self._buttons: list[RadioButton] = []

    @property
    def selected(self) -> RadioButton | None:
        """Return the selected button, if any."""
        return next((button for button in self._buttons if button.selected), None)

    def add(self, button: RadioButton) -> RadioButton:
        """Add a button to this group."""
        previous_group = button.group
        if previous_group is not None and previous_group is not self:
            previous_group.remove(button)
        if button not in self._buttons:
            self._buttons.append(button)
            button.set_group_membership(self)
            if button.selected:
                self.select(button)
        return button

    def remove(self, button: RadioButton) -> RadioButton:
        """Remove a button from this group."""
        if button not in self._buttons:
            msg = "radio button is not a member of this group"
            raise ValueError(msg)
        self._buttons.remove(button)
        if button.group is self:
            button.set_group_membership(None)
        return button

    def clear(self) -> None:
        """Detach every button from this group."""
        for button in tuple(self._buttons):
            self.remove(button)

    def select(self, selected: RadioButton) -> None:
        """Select one member and clear every other member."""
        for button in self._buttons:
            button.set_selected_from_group(selected=button is selected)


class RadioButton(CheckBox):
    """Boolean control participating in a mutually exclusive radio group."""

    def __init__(
        self,
        text: str = "",
        *,
        group: RadioGroup | None = None,
        selected: bool = False,
    ) -> None:
        """Initialize a radio button and optionally join a group."""
        super().__init__(text, selected=selected)
        self._group: RadioGroup | None = None
        if group is not None:
            group.add(self)

    @property
    def group(self) -> RadioGroup | None:
        """Return this button's mutual-exclusion group."""
        return self._group

    def set_group_membership(self, value: RadioGroup | None) -> None:
        """Update the owning group without recursively changing membership."""
        self._group = value

    @group.setter
    def group(self, value: RadioGroup | None) -> None:
        if value is self._group:
            return
        if value is None:
            if self._group is not None:
                self._group.remove(self)
            return
        value.add(self)

    @CheckBox.selected.setter
    @override
    def selected(self, value: bool) -> None:
        """Select this button and clear its group peers."""
        if value and self._group is not None:
            self._group.select(self)
            return
        self._apply_selected(selected=value)

    def set_selected_from_group(self, *, selected: bool) -> None:
        """Apply selection as part of one atomic group update."""
        self._apply_selected(selected=selected)

    def notify_selected(self) -> None:
        """Handle selection reported by the native peer."""
        self.selected = True


class ComboBox[T](Component):
    """Typed drop-down backed by a ComboBoxModel."""

    def _on_model_event(self, event: ModelEvent) -> None:
        peer = self.peer
        if peer is not None and self.created:
            peer.on_model_event(event)

    def __init__(
        self,
        items: Iterable[T] = (),
        model: ComboBoxModel[T] | None = None,
    ) -> None:
        """Initialize a combo box with items or a provided model."""
        super().__init__("")
        self.size = Size(160, 28)
        self.model = model if model is not None else ComboBoxModel(items)
        self._listeners: list[Callable[[ItemEvent[ComboBox[T], T]], None]] = []
        self._track_subscription(self.model.subscribe(self._on_model_event))

    @property
    def selected_index(self) -> int:
        """Return the selected index."""
        peer = self.peer
        if isinstance(peer, SelectionPeer) and self.created:
            index = peer.selected_index
            if index != self.model.selected_index and -1 <= index < len(self.model):
                self.model.set_selected_index(index)
        return self.model.selected_index

    @selected_index.setter
    def selected_index(self, index: int) -> None:
        self.model.set_selected_index(index)
        peer = self.peer
        if isinstance(peer, SelectionPeer) and self.created:
            peer.selected_index = index

    @property
    def selected_item(self) -> T | None:
        """Return the selected item or None."""
        index = self.selected_index
        return self.model[index] if 0 <= index < len(self.model) else None

    def on_change(
        self,
        listener: Callable[[ItemEvent[ComboBox[T], T]], None],
    ) -> Callable[[ItemEvent[ComboBox[T], T]], None]:
        """Register a selection-change listener and return it."""
        self._listeners.append(listener)
        return listener

    def _emit_selection(self, index: int) -> None:
        if -1 <= index < len(self.model) and index != self.model.selected_index:
            self.model.set_selected_index(index)
        event = ItemEvent[ComboBox[T], T](self, self.selected_item, selected=True)
        for listener in tuple(self._listeners):
            listener(event)

    def notify_selection(self, index: int) -> None:
        """Handle a backend-reported selection change."""
        self._emit_selection(index)

    def __iter__(self) -> Iterator[T]:
        """Iterate over model items."""
        return iter(self.model)


class ListBox[T](Component):
    """Single-selection list backed by a ListModel."""

    def _on_model_event(self, event: ModelEvent) -> None:
        peer = self.peer
        if peer is not None and self.created:
            peer.on_model_event(event)

    def __init__(
        self,
        items: Iterable[T] = (),
        model: ListModel[T] | None = None,
    ) -> None:
        """Initialize a list box with items or a provided model."""
        super().__init__("")
        self.size = Size(180, 130)
        self.model = model if model is not None else ListModel(items)
        self._selected_index = -1
        self._listeners: list[Callable[[ListSelectionEvent[ListBox[T]]], None]] = []
        self._track_subscription(self.model.subscribe(self._on_model_event))

    @property
    def selected_index(self) -> int:
        """Return the selected row index."""
        peer = self.peer
        if isinstance(peer, SelectionPeer) and self.created:
            self._selected_index = peer.selected_index
        return self._selected_index

    @selected_index.setter
    def selected_index(self, index: int) -> None:
        self._selected_index = index
        peer = self.peer
        if isinstance(peer, SelectionPeer) and self.created:
            peer.selected_index = self._selected_index

    def initial_selected_index(self) -> int:
        """Return the requested selection index before peer synchronization."""
        return self._selected_index

    @property
    def selected_value(self) -> T | None:
        """Return the selected value or None."""
        index = self.selected_index
        return self.model[index] if 0 <= index < len(self.model) else None

    def on_select(
        self,
        listener: Callable[[ListSelectionEvent[ListBox[T]]], None],
    ) -> Callable[[ListSelectionEvent[ListBox[T]]], None]:
        """Register a list-selection listener and return it."""
        self._listeners.append(listener)
        return listener

    def _emit_selection(self, index: int) -> None:
        self._selected_index = index
        event = ListSelectionEvent[ListBox[T]](self, index)
        for listener in tuple(self._listeners):
            listener(event)

    def notify_selection(self, index: int) -> None:
        """Handle a backend-reported list selection."""
        self._emit_selection(index)

    def __iter__(self) -> Iterator[T]:
        """Iterate over model items."""
        return iter(self.model)


class Table(Component):
    """Two-dimensional table backed by a TableModel."""

    def _on_model_event(self, event: ModelEvent) -> None:
        peer = self.peer
        if peer is not None and self.created:
            peer.on_model_event(event)

    def __init__(
        self,
        rows: Iterable[Sequence[object]] = (),
        columns: Iterable[str] = (),
        model: TableModel | None = None,
    ) -> None:
        """Initialize a table with rows/columns or a provided model."""
        super().__init__("")
        self.size = Size(320, 180)
        self.model = model if model is not None else TableModel(rows, columns)
        self._track_subscription(self.model.subscribe(self._on_model_event))

    def __iter__(self) -> Iterator[list[object]]:
        """Iterate over table rows."""
        return iter(self.model)


class Panel(Container):
    """Generic grouping container."""

    def __init__(self) -> None:
        """Initialize a generic panel with default size."""
        super().__init__()
        self.size = Size(200, 120)
        self.layout = FlowLayout()


class GroupBox(Panel):
    """Labeled container rendered as a native grouping frame when available."""

    def __init__(self, title: str = "") -> None:
        """Initialize a group box with inset child placement."""
        super().__init__()
        self.text = title
        self.layout = FlowLayout(hgap=12, vgap=24)


@dataclass(slots=True)
class _TabMetadata:
    title: str
    background: ColorInput | None = None


class TabbedPane(Panel):
    """Tabbed container with a typed SelectionPeer contract."""

    def __init__(self) -> None:
        """Initialize an empty tabbed pane."""
        super().__init__()
        self._selected_index = -1

    @property
    def tabs(self) -> list[tuple[str, Component]]:
        """Return tab titles and pages derived from child-slot metadata."""
        return [
            (metadata.title, slot.component)
            for slot in self.children
            if isinstance((metadata := slot.constraint), _TabMetadata)
        ]

    def _tab_slots(self) -> list[tuple[Component, _TabMetadata]]:
        return [
            (slot.component, metadata)
            for slot in self.children
            if isinstance((metadata := slot.constraint), _TabMetadata)
        ]

    def _tab_index(self, tab: int | Component) -> int:
        slots = self._tab_slots()
        if isinstance(tab, int):
            if tab < 0 or tab >= len(slots):
                raise IndexError(tab)
            return tab
        for index, (component, _metadata) in enumerate(slots):
            if component is tab:
                return index
        msg = "component is not a tab page"
        raise ValueError(msg)

    @property
    def selected_index(self) -> int:
        """Return the selected tab index."""
        peer = self.peer
        if isinstance(peer, SelectionPeer) and self.created:
            current = peer.selected_index
            if current >= 0:
                self._selected_index = current
        return self._selected_index

    @selected_index.setter
    def selected_index(self, index: int) -> None:
        if index < -1 or index >= len(self.tabs):
            raise IndexError(index)
        self._selected_index = index
        peer = self.peer
        if isinstance(peer, SelectionPeer) and self.created:
            peer.selected_index = self._selected_index

    def initial_selected_index(self) -> int:
        """Return the requested tab index before peer synchronization."""
        return self._selected_index

    def sync_selected_index_from_peer(self, index: int) -> None:
        """Record a backend tab selection without pushing it back to the peer."""
        if -1 <= index < len(self.tabs):
            self._selected_index = index

    @override
    def add[TComponent: Component](
        self,
        component: TComponent,
        constraint: object | None = None,
    ) -> TComponent:
        """Reject generic children so every page has complete tab metadata."""
        del component, constraint
        msg = "use add_tab() to add pages to a TabbedPane"
        raise TypeError(msg)

    def add_tab[T](
        self,
        title: str,
        component: T,
        *,
        background: ColorInput | None = None,
    ) -> T:
        """Add one tab and return the component."""
        if not isinstance(component, Component):
            msg = "tab component must be a Component"
            raise TypeError(msg)
        super().add(component, _TabMetadata(title, background))
        if self._selected_index == -1:
            self._selected_index = 0
        self.refresh()
        return component

    def remove_tab(self, tab: int | Component) -> Component:
        """Remove a tab by index or page and return its component."""
        component, _metadata = self._tab_slots()[self._tab_index(tab)]
        return self.remove(component)

    def tab_title(self, tab: int | Component) -> str:
        """Return a tab title by index or page."""
        _component, metadata = self._tab_slots()[self._tab_index(tab)]
        return metadata.title

    def set_tab_title(self, tab: int | Component, title: str) -> None:
        """Change a tab title and refresh its peer."""
        _component, metadata = self._tab_slots()[self._tab_index(tab)]
        metadata.title = title
        self.refresh()

    def set_tab_background(
        self,
        tab: int | Component,
        background: ColorInput | None,
    ) -> None:
        """Change a tab-page background and refresh its peer."""
        _component, metadata = self._tab_slots()[self._tab_index(tab)]
        metadata.background = background
        self.refresh()

    @override
    def remove(self, component: Component) -> Component:
        """Remove a tab page and its associated metadata."""
        index = self._tab_index(component)
        removed = super().remove(component)
        if not self.tabs:
            self._selected_index = -1
        elif self._selected_index > index:
            self._selected_index -= 1
        elif self._selected_index == index:
            self._selected_index = min(index, len(self.tabs) - 1)
        return removed

    def page_background(self, component: Component) -> ColorInput | None:
        """Return the requested background for one tab-page component."""
        try:
            _page, metadata = self._tab_slots()[self._tab_index(component)]
        except ValueError:
            return None
        return metadata.background

    def do_layout(self) -> None:
        """Refresh backend-driven tab layout when mounted."""
        if self.created:
            self.refresh()


class SplitOrientation(StrEnum):
    """Portable split-pane orientation."""

    HORIZONTAL = "horizontal"
    VERTICAL = "vertical"


class SplitPane(Panel):
    """Two-child split container with graceful portable emulation."""

    def __init__(
        self,
        orientation: SplitOrientation = SplitOrientation.HORIZONTAL,
        first: Component | None = None,
        second: Component | None = None,
        divider_location: float = 0.5,
    ) -> None:
        """Initialize a split pane with optional child components."""
        super().__init__()
        self.orientation = SplitOrientation(orientation)
        self._divider_location = divider_location
        self.first = first
        self.second = second
        if first is not None:
            self.add(first)
        if second is not None:
            self.add(second)

    @property
    def divider_location(self) -> float | int:
        """Return the divider position as ratio or absolute value."""
        return self._divider_location

    @divider_location.setter
    def divider_location(self, value: float) -> None:
        self._divider_location = value
        self.do_layout()

    def do_layout(self) -> None:
        """Lay out both panes or delegate to backend split capability."""
        if not self.created or self.first is None or self.second is None:
            return
        context = self.context
        if context is not None and context.backend.supports(Capability.SPLIT_PANE):
            self.refresh()
            return
        width, height = self.client_size()
        extent = width if self.orientation is SplitOrientation.HORIZONTAL else height
        position = (
            int(extent * self.divider_location)
            if isinstance(self.divider_location, float)
            else self.divider_location
        )
        if self.orientation is SplitOrientation.HORIZONTAL:
            self.first.set_bounds(0, 0, max(0, position - 2), height)
            self.second.set_bounds(
                position + 2,
                0,
                max(0, width - position - 2),
                height,
            )
        else:
            self.first.set_bounds(0, 0, width, max(0, position - 2))
            self.second.set_bounds(
                0,
                position + 2,
                width,
                max(0, height - position - 2),
            )


class ProgressBar(Component):
    """Progress indicator using an IntValuePeer."""

    def __init__(self, minimum: int = 0, maximum: int = 100, value: int = 0) -> None:
        """Initialize a bounded integer progress indicator."""
        super().__init__("")
        self.minimum = minimum
        self.maximum = maximum
        self._value = value
        self.size = Size(180, 22)

    @property
    def value(self) -> int:
        """Return the current progress value."""
        return self._value

    @value.setter
    def value(self, value: int) -> None:
        self._value = max(self.minimum, min(self.maximum, value))
        peer = self.peer
        if isinstance(peer, IntValuePeer) and self.created:
            peer.value = self._value

    def initial_value(self) -> int:
        """Return the stored value for backend initialization."""
        return self._value


class Slider(Component):
    """Integer range slider using an IntValuePeer."""

    def __init__(self, minimum: int = 0, maximum: int = 100, value: int = 0) -> None:
        """Initialize an integer range slider."""
        super().__init__("")
        self.minimum = minimum
        self.maximum = maximum
        self._value = value
        self._listeners: list[Callable[[int], None]] = []
        self.size = Size(180, 32)

    @property
    def value(self) -> int:
        """Return the current slider value."""
        peer = self.peer
        if isinstance(peer, IntValuePeer) and self.created:
            self._value = peer.value
        return self._value

    @value.setter
    def value(self, value: int) -> None:
        self._value = max(self.minimum, min(self.maximum, value))
        peer = self.peer
        if isinstance(peer, IntValuePeer) and self.created:
            peer.value = self._value

    def initial_value(self) -> int:
        """Return the stored value for backend initialization."""
        return self._value

    def on_change(self, listener: Callable[[int], None]) -> Callable[[int], None]:
        """Register a value-change listener and return it."""
        self._listeners.append(listener)
        return listener

    def _emit_change(self, value: int) -> None:
        self._value = value
        for listener in tuple(self._listeners):
            listener(self._value)

    def notify_value_changed(self, value: int) -> None:
        """Handle a backend-reported slider value change."""
        self._emit_change(value)


class Spinner(Component):
    """Bounded integer input with increment and decrement actions."""

    def __init__(
        self,
        minimum: int = 0,
        maximum: int = 100,
        value: int = 0,
        step: int = 1,
    ) -> None:
        """Initialize a bounded spinner."""
        if maximum < minimum:
            msg = "maximum must not be less than minimum"
            raise ValueError(msg)
        if step <= 0:
            msg = "step must be positive"
            raise ValueError(msg)
        super().__init__("")
        self.minimum = minimum
        self.maximum = maximum
        self.step = step
        self._value = max(minimum, min(maximum, value))
        self._listeners: list[Callable[[int], None]] = []
        self.size = Size(100, 28)

    @property
    def value(self) -> int:
        """Return the current integer value."""
        peer = self.peer
        if isinstance(peer, IntValuePeer) and self.created:
            self._value = peer.value
        return self._value

    def _emit_change(self, value: int) -> None:
        self._value = max(self.minimum, min(self.maximum, value))
        for listener in tuple(self._listeners):
            listener(self._value)

    @value.setter
    def value(self, value: int) -> None:
        clamped = max(self.minimum, min(self.maximum, value))
        changed = clamped != self._value
        self._value = clamped
        peer = self.peer
        if isinstance(peer, IntValuePeer) and self.created:
            peer.value = clamped
        if changed:
            self._emit_change(clamped)

    def initial_value(self) -> int:
        """Return the stored value for backend initialization."""
        return self._value

    def increment(self) -> None:
        """Advance by one configured step."""
        self.value += self.step

    def decrement(self) -> None:
        """Move back by one configured step."""
        self.value -= self.step

    def on_change(self, listener: Callable[[int], None]) -> Callable[[int], None]:
        """Register a value-change listener and return it."""
        self._listeners.append(listener)
        return listener

    def notify_value_changed(self, value: int) -> None:
        """Handle a value change reported by the native peer."""
        self._emit_change(value)


class SeparatorOrientation(StrEnum):
    """Axis crossed by a separator line."""

    HORIZONTAL = "horizontal"
    VERTICAL = "vertical"


class Separator(Component):
    """Non-interactive horizontal or vertical dividing line."""

    def __init__(
        self,
        orientation: SeparatorOrientation = SeparatorOrientation.HORIZONTAL,
    ) -> None:
        """Initialize a separator with orientation-based preferred size."""
        super().__init__("")
        self.orientation = SeparatorOrientation(orientation)
        self.size = (
            Size(160, 2)
            if self.orientation is SeparatorOrientation.HORIZONTAL
            else Size(2, 80)
        )


class ScrollPane(Container):
    """Clipped viewport for one component larger than its visible extent."""

    def __init__(self, content: Component | None = None) -> None:
        """Initialize an optional viewport component and zero scroll offset."""
        super().__init__()
        self.size = Size(240, 180)
        self.content: Component | None = None
        self._scroll_x = 0
        self._scroll_y = 0
        if content is not None:
            self.set_content(content)

    @property
    def scroll_position(self) -> tuple[int, int]:
        """Return horizontal and vertical viewport offsets."""
        return self._scroll_x, self._scroll_y

    def set_content[T: Component](self, content: T) -> T:
        """Replace the viewport content and return it."""
        if self.content is not None:
            self.remove(self.content)
        self.content = content
        self.add(content)
        self.scroll_to(0, 0)
        return content

    def scroll_to(self, x: int, y: int) -> None:
        """Scroll to a clamped logical content offset."""
        content = self.content
        if content is None:
            self._scroll_x = self._scroll_y = 0
            return
        viewport = self.client_size()
        self._scroll_x = max(0, min(x, max(0, content.width - viewport.width)))
        self._scroll_y = max(0, min(y, max(0, content.height - viewport.height)))
        self.do_layout()
        self.refresh()

    def scroll_by(self, dx: int, dy: int) -> None:
        """Move the viewport relative to its current offset."""
        self.scroll_to(self._scroll_x + dx, self._scroll_y + dy)

    def do_layout(self) -> None:
        """Position content relative to the viewport offset."""
        if not self.created or self.content is None:
            return
        self.content.set_bounds(
            -self._scroll_x,
            -self._scroll_y,
            self.content.width,
            self.content.height,
        )


class StatusBar(Label):
    """Single-part status display."""

    def __init__(self, text: str = "") -> None:
        """Initialize a status bar with optional text."""
        super().__init__(text)
        self.height = 24


class ToolBar(Panel):
    """Toolbar composed from portable buttons."""

    def __init__(self) -> None:
        """Initialize a toolbar with compact flow layout."""
        super().__init__()
        self.height = 36
        self.layout = FlowLayout(hgap=2, vgap=3)

    def add_button(
        self,
        text: str,
        action: ActionListener | None = None,
        *,
        image: ImageResource | None = None,
    ) -> Button:
        """Create, optionally bind, and add a toolbar button."""
        button = Button(text, image=image)
        if action is not None:
            button.on_click(action)
        return self.add(button)


class TreeNode:
    """Portable logical tree node."""

    def __init__(self, text: str, children: Iterable[TreeNode] = ()) -> None:
        """Initialize a tree node with text and child nodes."""
        self.text = text
        self.children = list(children)

    def add(self, child: TreeNode | str) -> TreeNode:
        """Append and return a child node."""
        node = TreeNode(child) if isinstance(child, str) else child
        self.children.append(node)
        return node

    def __iter__(self) -> Iterator[TreeNode]:
        """Iterate over child nodes."""
        return iter(self.children)


class TreeView(Component):
    """Tree control populated from TreeNode objects."""

    def __init__(self, roots: Iterable[TreeNode] = ()) -> None:
        """Initialize a tree view from root nodes."""
        super().__init__("")
        self.roots = list(roots)
        self.size = Size(220, 180)

    def add(self, node: TreeNode | str) -> TreeNode:
        """Append and return a root node."""
        resolved = TreeNode(node) if isinstance(node, str) else node
        self.roots.append(resolved)
        self.refresh()
        return resolved

    def __iter__(self) -> Iterator[TreeNode]:
        """Iterate over root nodes."""
        return iter(self.roots)
