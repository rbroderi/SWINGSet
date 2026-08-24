"""Backend-neutral components built around typed peers and explicit context."""

from __future__ import annotations

from collections.abc import Callable
from collections.abc import Iterator
from dataclasses import dataclass
from typing import TYPE_CHECKING
from typing import Protocol
from typing import Self
from typing import cast
from typing import runtime_checkable

from .context import UIContext
from .context import current_context
from .events import KeyEvent
from .events import MouseEvent
from .geometry import Point
from .geometry import Rect
from .geometry import Size
from .lifecycle import ComponentState
from .peers import ComponentPeer
from .peers import WindowPeer
from .richtext import RichTextSpan
from .richtext import RichTextStyle
from .richtext import StyledText
from .richtext import parse_commonmark
from .subscriptions import Subscription
from .theme import ColorInput

if TYPE_CHECKING:
    import swingset.menu

type MouseListener = Callable[[MouseEvent["Component"]], None]
type KeyListener = Callable[[KeyEvent["Component"]], None]

_UNBOUNDED_SIZE = Size(2_147_483_647, 2_147_483_647)


def _clamp_size(value: Size, minimum: Size, maximum: Size) -> Size:
    return Size(
        max(minimum.width, min(value.width, maximum.width)),
        max(minimum.height, min(value.height, maximum.height)),
    )


@runtime_checkable
class LayoutManager(Protocol):
    """Protocol implemented by portable layout strategies."""

    def layout(self, container: Container) -> None:
        """Lay out one container."""

    def preferred_size(self, container: Container) -> Size:
        """Measure the preferred size of one container."""
        ...

    def minimum_size(self, container: Container) -> Size:
        """Measure the minimum usable size of one container."""
        ...

    def maximum_size(self, container: Container) -> Size:
        """Measure the maximum useful size of one container."""
        ...


class Component:
    """Portable half of the component/peer Bridge."""

    allow_null_peer = False

    def __init__(self, text: str = "") -> None:
        """Initialize component state before mounting."""
        self.parent: Container | None = None
        self._context: UIContext | None = None
        self._peer: ComponentPeer | None = None
        self._state = ComponentState.NEW
        self._bounds = Rect(0, 0, 100, 24)
        self._preferred_size = self._bounds.size
        self._preferred_size_override: Size | None = None
        self._minimum_size_override: Size | None = None
        self._maximum_size_override: Size | None = None
        self._text = text
        self._visible = True
        self._enabled = True
        self._tooltip: str | None = None
        self._foreground: ColorInput | None = None
        self._background: ColorInput | None = None
        self._styles: list[RichTextSpan] = []
        self._mouse_listeners: list[MouseListener] = []
        self._key_listeners: list[KeyListener] = []
        self._font_request: tuple[str, int, bool] | None = None
        self._subscriptions: list[Subscription] = []

    @property
    def context(self) -> UIContext | None:
        """Return the explicit runtime context once attached/mounted."""
        return self._context

    def _require_ui_thread(self) -> None:
        if self.created and self._context is not None:
            self._context.dispatcher.require_ui_thread()

    @property
    def peer(self) -> ComponentPeer | None:
        """Return the typed backend peer."""
        self._require_ui_thread()
        return self._peer

    @property
    def state(self) -> ComponentState:
        """Return the current lifecycle state."""
        return self._state

    @property
    def created(self) -> bool:
        """Return whether the component is mounted with a live peer."""
        return self._state is ComponentState.MOUNTED and self._peer is not None

    @property
    def text(self) -> str:
        """Return component text, synchronizing from the peer when mounted."""
        self._require_ui_thread()
        if self._peer is not None and self.created:
            self._text = self._peer.text
        return self._text

    def snapshot_text(self) -> str:
        """Return cached text without pulling from the peer."""
        return self._text

    @text.setter
    def text(self, value: str) -> None:
        self._require_ui_thread()
        self._text = value
        self._styles.clear()
        if self._peer is not None and self.created:
            self._peer.text = self._text
            self._peer.apply_text_styles()

    @property
    def visible(self) -> bool:
        """Return whether the component should be visible."""
        return self._visible

    @visible.setter
    def visible(self, value: bool) -> None:
        self._require_ui_thread()
        changed = self._visible != value
        self._visible = value
        if self._peer is not None and self.created:
            self._peer.set_visible(visible=self._visible)
        if changed:
            self.revalidate()

    @property
    def enabled(self) -> bool:
        """Return whether the component is enabled."""
        return self._enabled

    @enabled.setter
    def enabled(self, value: bool) -> None:
        self._require_ui_thread()
        self._enabled = value
        if self._peer is not None and self.created:
            self._peer.set_enabled(enabled=self._enabled)

    @property
    def tooltip(self) -> str | None:
        """Return text shown when the pointer rests over this component."""
        return self._tooltip

    @tooltip.setter
    def tooltip(self, value: str | None) -> None:
        self._require_ui_thread()
        self._tooltip = value
        if self._peer is not None and self.created:
            self._peer.set_tooltip(value)

    @property
    def foreground(self) -> ColorInput | None:
        """Return the requested foreground color, or the theme default."""
        return self._foreground

    @foreground.setter
    def foreground(self, value: ColorInput | None) -> None:
        self._require_ui_thread()
        self._foreground = value
        if self._peer is not None and self.created:
            self._peer.set_foreground(value)

    @property
    def background(self) -> ColorInput | None:
        """Return the requested background color, or the theme default."""
        return self._background

    @background.setter
    def background(self, value: ColorInput | None) -> None:
        self._require_ui_thread()
        self._background = value
        if self._peer is not None and self.created:
            self._peer.set_background(value)

    @property
    def styles(self) -> tuple[RichTextSpan, ...]:
        """Return portable character-format spans in insertion order."""
        return tuple(self._styles)

    def add_style(
        self,
        start: int,
        end: int,
        style: RichTextStyle,
    ) -> RichTextSpan:
        """Apply a style to a valid half-open character range."""
        self._require_ui_thread()
        if start < 0 or end <= start or end > len(self.snapshot_text()):
            msg = "text style range is outside the current text"
            raise ValueError(msg)
        span = RichTextSpan(start, end, style)
        self._styles.append(span)
        if self._peer is not None and self.created:
            self._peer.apply_text_styles()
        return span

    def clear_styles(self) -> None:
        """Remove all character formatting spans."""
        self._require_ui_thread()
        self._styles.clear()
        if self._peer is not None and self.created:
            self._peer.apply_text_styles()

    def set_styled_text(self, value: StyledText) -> Self:
        """Replace text and character-format spans atomically."""
        self._require_ui_thread()
        self._text = value.text
        self._styles = list(value.spans)
        if self._peer is not None and self.created:
            self._peer.text = self._text
            self._peer.apply_text_styles()
        return self

    def set_markdown(self, source: str) -> Self:
        """Parse CommonMark and replace this component's styled text."""
        return self.set_styled_text(parse_commonmark(source))

    @property
    def x(self) -> int:
        """Return the x-coordinate of component bounds."""
        return self._bounds.x

    @x.setter
    def x(self, value: int) -> None:
        self.set_location(value, self.y)

    @property
    def y(self) -> int:
        """Return the y-coordinate of component bounds."""
        return self._bounds.y

    @y.setter
    def y(self, value: int) -> None:
        self.set_location(self.x, value)

    @property
    def width(self) -> int:
        """Return component width."""
        return self._bounds.width

    @width.setter
    def width(self, value: int) -> None:
        self.set_size(value, self.height)

    @property
    def height(self) -> int:
        """Return component height."""
        return self._bounds.height

    @height.setter
    def height(self, value: int) -> None:
        self.set_size(self.width, value)

    @property
    def location(self) -> Point:
        """Return component location as a point."""
        return self._bounds.location

    @location.setter
    def location(self, value: Point) -> None:
        self.set_location(value.x, value.y)

    @property
    def size(self) -> Size:
        """Return component size."""
        return self._bounds.size

    @size.setter
    def size(self, value: Size) -> None:
        self.set_size(value.width, value.height)

    @property
    def preferred_size(self) -> Size:
        """Return the natural size requested by this component."""
        requested = self._preferred_size_override or self._preferred_size
        return _clamp_size(requested, self.minimum_size, self.maximum_size)

    @preferred_size.setter
    def preferred_size(self, value: Size) -> None:
        self._require_ui_thread()
        self._preferred_size_override = value
        self.revalidate()

    def clear_preferred_size(self) -> None:
        """Clear an explicit preferred-size override."""
        self._require_ui_thread()
        self._preferred_size_override = None
        self.revalidate()

    @property
    def minimum_size(self) -> Size:
        """Return the smallest usable size requested by this component."""
        return self._minimum_size_override or Size()

    def _set_minimum_size(self, value: Size) -> None:
        self._require_ui_thread()
        if value.width < 0 or value.height < 0:
            msg = "minimum size must not be negative"
            raise ValueError(msg)
        if (
            value.width > self.maximum_size.width
            or value.height > self.maximum_size.height
        ):
            msg = "minimum size must not exceed maximum size"
            raise ValueError(msg)
        self._minimum_size_override = value
        self.revalidate()

    @minimum_size.setter
    def minimum_size(self, value: Size) -> None:
        self._set_minimum_size(value)

    def clear_minimum_size(self) -> None:
        """Clear an explicit minimum-size override."""
        self._require_ui_thread()
        self._minimum_size_override = None
        self.revalidate()

    @property
    def maximum_size(self) -> Size:
        """Return the largest useful size requested by this component."""
        return self._maximum_size_override or _UNBOUNDED_SIZE

    def _set_maximum_size(self, value: Size) -> None:
        self._require_ui_thread()
        if (
            value.width < self.minimum_size.width
            or value.height < self.minimum_size.height
        ):
            msg = "maximum size must not be smaller than minimum size"
            raise ValueError(msg)
        self._maximum_size_override = value
        self.revalidate()

    @maximum_size.setter
    def maximum_size(self, value: Size) -> None:
        self._set_maximum_size(value)

    def clear_maximum_size(self) -> None:
        """Clear an explicit maximum-size override."""
        self._require_ui_thread()
        self._maximum_size_override = None
        self.revalidate()

    @property
    def bounds(self) -> Rect:
        """Return component bounds rectangle."""
        return self._bounds

    @bounds.setter
    def bounds(self, value: Rect) -> None:
        self.set_bounds(value.x, value.y, value.width, value.height)

    @property
    def dpi(self) -> int:
        """Return effective DPI from peer or the default value."""
        return 96 if self._peer is None else self._peer.dpi

    def _attach_context(self, context: UIContext) -> None:
        if self._context is not None and self._context is not context:
            msg = "a component cannot move between live UI contexts"
            raise RuntimeError(msg)
        self._context = context

    def attach_context(self, context: UIContext) -> None:
        """Bind this component to a runtime context once."""
        self._attach_context(context)

    def _synchronize_peer(self) -> None:
        peer = self._peer
        if peer is None:
            return
        peer.text = self._text
        peer.set_bounds(self._bounds)
        peer.set_enabled(enabled=self._enabled)
        peer.set_visible(visible=self._visible)
        peer.set_tooltip(self._tooltip)
        peer.set_foreground(self._foreground)
        peer.set_background(self._background)
        if self._context is not None:
            peer.apply_theme(self._context.theme.theme)
        if self._font_request is not None:
            face, size, bold = self._font_request
            peer.set_font(face, size, bold=bold)
        peer.refresh()
        peer.apply_text_styles()

    def _mount(self, parent: Container | None = None) -> None:
        if self._state is ComponentState.MOUNTED:
            return
        if self._state in {ComponentState.MOUNTING, ComponentState.DESTROYING}:
            msg = f"cannot mount component while {self._state.name.lower()}"
            raise RuntimeError(
                msg,
            )
        if self._state is ComponentState.DESTROYED:
            msg_0 = "destroyed components cannot be remounted"
            raise RuntimeError(msg_0)
        if parent is not None:
            if parent.context is None:
                msg = "parent must have a UI context before mounting children"
                raise RuntimeError(
                    msg,
                )
            self._attach_context(parent.context)
        if self._context is None:
            msg = "top-level components require an explicit UIContext"
            raise RuntimeError(msg)
        self._state = ComponentState.MOUNTING
        parent_peer = None if parent is None else parent.peer
        self._peer = self._context.backend.create_peer(self, parent_peer)
        try:
            self._synchronize_peer()
        except Exception:
            self._peer.destroy()
            self._peer = None
            self._state = ComponentState.NEW
            raise
        self._state = ComponentState.MOUNTED

    def mount(self, parent: Container | None = None) -> None:
        """Mount this component and create its backend peer."""
        self._mount(parent)

    def _on_size_changed(self) -> None:
        return

    def set_bounds(
        self,
        x: int,
        y: int,
        width: int,
        height: int,
    ) -> Self:
        """Set bounds and push them to the peer when mounted."""
        self._require_ui_thread()
        previous_size = self._bounds.size
        self._bounds = Rect(x, y, max(0, width), max(0, height))
        if self._peer is not None and self.created:
            self._peer.set_bounds(self._bounds)
        if self._bounds.size != previous_size:
            self._on_size_changed()
        return self

    def set_location(self, x: int, y: int) -> Self:
        """Set location while preserving current size."""
        return self.set_bounds(x, y, self.width, self.height)

    def set_size(self, width: int, height: int) -> Self:
        """Set size while preserving current location."""
        resolved = Size(max(0, width), max(0, height))
        self._preferred_size = resolved
        self.set_bounds(self.x, self.y, resolved.width, resolved.height)
        self.revalidate()
        return self

    def revalidate(self) -> None:
        """Invalidate and synchronously validate the containing layout tree."""
        if self.parent is None:
            return
        self.parent.invalidate_layout()
        self.parent.validate_layout_tree()

    def set_font(
        self,
        face: str = "Segoe UI",
        size: int = 9,
        *,
        bold: bool = False,
    ) -> Self:
        """Store a font request and apply it when mounted."""
        self._require_ui_thread()
        self._font_request = (face, size, bold)
        if self._peer is not None and self.created:
            self._peer.set_font(face, size, bold=bold)
        return self

    def on_mouse(self, listener: MouseListener) -> MouseListener:
        """Register a mouse-event listener and return it."""
        self._mouse_listeners.append(listener)
        return listener

    def on_key(self, listener: KeyListener) -> KeyListener:
        """Register a key-event listener and return it."""
        self._key_listeners.append(listener)
        return listener

    def _emit_mouse(
        self,
        x: int,
        y: int,
        button: int = 0,
        wheel_delta: int = 0,
    ) -> None:
        event = MouseEvent[Component](self, x, y, button, wheel_delta)
        for listener in tuple(self._mouse_listeners):
            listener(event)

    def emit_mouse_event(
        self,
        x: int,
        y: int,
        button: int = 0,
        wheel_delta: int = 0,
    ) -> None:
        """Publish a backend mouse event to registered listeners."""
        self._emit_mouse(x, y, button, wheel_delta)

    def _emit_key(self, key_code: int, char: str | None = None) -> None:
        event = KeyEvent[Component](self, key_code, char)
        for listener in tuple(self._key_listeners):
            listener(event)

    def emit_key_event(self, key_code: int, char: str | None = None) -> None:
        """Publish a backend key event to registered listeners."""
        self._emit_key(key_code, char)

    def _track_subscription(self, subscription: Subscription) -> Subscription:
        self._subscriptions.append(subscription)
        return subscription

    def focus(self) -> None:
        """Request focus from the backend peer when mounted."""
        self._require_ui_thread()
        if self._peer is not None and self.created:
            self._peer.focus()

    def refresh(self) -> None:
        """Ask the backend peer to refresh visual state."""
        self._require_ui_thread()
        if self._peer is not None and self.created:
            self._peer.refresh()

    def _on_dpi_changed(self) -> None:
        self.refresh()

    def handle_dpi_changed(self) -> None:
        """Handle a backend DPI-change notification."""
        self._on_dpi_changed()

    def _on_theme_changed(self) -> None:
        if self._peer is not None and self.created and self._context is not None:
            self._peer.apply_theme(self._context.theme.theme)
            self._peer.refresh()

    def handle_theme_changed(self) -> None:
        """Handle a theme-change notification from the active context."""
        self._on_theme_changed()

    def destroy(self) -> None:
        """Dispose subscriptions and destroy the backend peer."""
        self._require_ui_thread()
        if self._state in {ComponentState.NEW, ComponentState.DESTROYED}:
            if self._state is ComponentState.NEW:
                self._state = ComponentState.DESTROYED
            return
        if self._state is ComponentState.DESTROYING:
            return
        self._state = ComponentState.DESTROYING
        for subscription in tuple(self._subscriptions):
            subscription.dispose()
        self._subscriptions.clear()
        peer = self._peer
        self._peer = None
        if peer is not None:
            peer.destroy()
        self._state = ComponentState.DESTROYED


@dataclass(slots=True)
class ChildSlot:
    """Named child metadata replacing opaque child tuples."""

    component: Component
    constraint: object | None = None


class Container(Component):
    """Portable component capable of owning child components."""

    def __init__(self, text: str = "") -> None:
        """Initialize an empty container with optional text."""
        super().__init__(text)
        self.children: list[ChildSlot] = []
        self._layout: LayoutManager | None = None
        self._layout_valid = False

    def _mount(self, parent: Container | None = None) -> None:
        if self.created:
            return
        super()._mount(parent)
        for slot in self.children:
            slot.component.mount(self)
        self.do_layout()
        self.refresh()

    @property
    def layout(self) -> LayoutManager | None:
        """Return the active layout manager, if any."""
        return self._layout

    @layout.setter
    def layout(self, value: LayoutManager | None) -> None:
        self._layout = value
        self.invalidate_layout()
        self.validate_layout_tree()

    @property
    def preferred_size(self) -> Size:
        """Measure children through the active layout manager."""
        if self._preferred_size_override is not None:
            requested = self._preferred_size_override
        elif self._layout is not None and self.children:
            requested = self._layout.preferred_size(self)
        else:
            requested = self._preferred_size
        return _clamp_size(requested, self.minimum_size, self.maximum_size)

    @preferred_size.setter
    def preferred_size(self, value: Size) -> None:
        self._preferred_size_override = value
        self.revalidate()

    @property
    def minimum_size(self) -> Size:
        """Measure the minimum usable size of this container."""
        if self._minimum_size_override is not None:
            return self._minimum_size_override
        if self._layout is not None and self.children:
            return self._layout.minimum_size(self)
        return Size()

    @minimum_size.setter
    def minimum_size(self, value: Size) -> None:
        self._set_minimum_size(value)

    @property
    def maximum_size(self) -> Size:
        """Measure the maximum useful size of this container."""
        if self._maximum_size_override is not None:
            return self._maximum_size_override
        if self._layout is not None and self.children:
            return self._layout.maximum_size(self)
        return _UNBOUNDED_SIZE

    @maximum_size.setter
    def maximum_size(self, value: Size) -> None:
        self._set_maximum_size(value)

    def add[TComponent: Component](
        self,
        component: TComponent,
        constraint: object | None = None,
    ) -> TComponent:
        """Add a child component with an optional layout constraint."""
        self._require_ui_thread()
        if any(slot.component is component for slot in self.children):
            msg = "component is already a child of this container"
            raise ValueError(msg)
        if component.parent is not None and component.parent is not self:
            msg = "component already belongs to another container"
            raise ValueError(msg)
        if component.state is not ComponentState.NEW:
            msg = "only new components can be added to a container"
            raise RuntimeError(msg)
        component.parent = self
        self.children.append(ChildSlot(component, constraint))
        self.invalidate_layout()
        if self.context is not None:
            component.attach_context(self.context)
        if self.created:
            component.mount(self)
            self.validate_layout_tree()
            self.refresh()
        return component

    def remove(self, component: Component) -> Component:
        """Remove a child component and destroy it."""
        self._require_ui_thread()
        slot = next(
            (item for item in self.children if item.component is component),
            None,
        )
        if slot is None:
            msg = "component is not a child of this container"
            raise ValueError(msg)
        self.children.remove(slot)
        component.destroy()
        component.parent = None
        self.invalidate_layout()
        self.validate_layout_tree()
        self.refresh()
        return component

    def client_size(self) -> Size:
        """Return drawable client size from peer or logical size."""
        if self._peer is None or not self.created:
            return self.size
        return self._peer.client_size()

    def do_layout(self) -> None:
        """Run layout manager if available and mounted."""
        if self._layout is not None and self.created:
            self._layout.layout(self)
        self._layout_valid = True

    def invalidate_layout(self) -> None:
        """Invalidate this container and every ancestor layout."""
        self._layout_valid = False
        if self.parent is not None:
            self.parent.invalidate_layout()

    def validate_layout_tree(self) -> None:
        """Lay out invalid containers from this node down."""
        if not self.created:
            return
        if not self._layout_valid:
            self.do_layout()
        for slot in self.children:
            child = slot.component
            if isinstance(child, Container):
                child.validate_layout_tree()

    def invalidate_layout_tree(self) -> None:
        """Invalidate this container and every descendant layout."""
        self._layout_valid = False
        for slot in self.children:
            child = slot.component
            if isinstance(child, Container):
                child.invalidate_layout_tree()

    def _on_size_changed(self) -> None:
        self.invalidate_layout()
        self.validate_layout_tree()

    def handle_native_resize(self) -> None:
        """Recompute layout after a backend reports a client-size change."""
        self.invalidate_layout_tree()
        self.validate_layout_tree()

    def _on_dpi_changed(self) -> None:
        super()._on_dpi_changed()
        for slot in self.children:
            slot.component.handle_dpi_changed()
        self.do_layout()

    def _on_theme_changed(self) -> None:
        super()._on_theme_changed()
        for slot in self.children:
            slot.component.handle_theme_changed()

    def destroy(self) -> None:
        """Destroy child components before destroying this container."""
        for slot in tuple(self.children):
            slot.component.destroy()
        super().destroy()

    def __iter__(self) -> Iterator[Component]:
        """Iterate over child components in insertion order."""
        return (slot.component for slot in self.children)


class Window(Container):
    """Top-level window with per-context lifecycle tracking."""

    def __init__(self, title: str = "", *, context: UIContext | None = None) -> None:
        """Initialize a top-level window bound to an optional context."""
        super().__init__(title)
        self._bounds = Rect(-1, -1, 640, 480)
        self._menu_bar = None
        self._pack_on_mount = False
        resolved_context = context if context is not None else current_context()
        if resolved_context is not None:
            self._attach_context(resolved_context)
            resolved_context.windows.remember(self)

    def _ensure_context(self) -> UIContext:
        if self._context is None:
            resolved_context = current_context()
            if resolved_context is None:
                msg = (
                    "top-level windows must be created inside App.run/App.run_async "
                    "or receive context=App.context() explicitly"
                )
                raise RuntimeError(msg)
            self._attach_context(resolved_context)
        context = cast("UIContext", self._context)
        context.windows.remember(self)
        return context

    def _mount(self, parent: Container | None = None) -> None:
        self._ensure_context()
        super()._mount(parent)
        peer = self._peer
        if isinstance(peer, WindowPeer):
            peer.set_menu(self._menu_bar)
        if self._pack_on_mount:
            self.pack()

    def pack(self) -> None:
        """Resize this window to the preferred size of its content."""
        preferred = self.preferred_size
        if self.created:
            client = self.client_size()
            preferred = Size(
                preferred.width + max(0, self.width - client.width),
                preferred.height + max(0, self.height - client.height),
            )
        else:
            self._pack_on_mount = True
        self.set_size(preferred.width, preferred.height)

    @Component.visible.setter
    def visible(self, value: object) -> None:
        """Show or hide the window, mounting it lazily when shown."""
        visible = bool(value)
        self._visible = visible
        if not visible and self._state is ComponentState.NEW and self._context is None:
            return
        context = self._ensure_context()
        if visible and self._state is ComponentState.NEW:
            self._mount(None)
            context.windows.mounted(self)
        if self._peer is not None and self.created:
            self._peer.set_visible(visible=self._visible)

    @property
    def title(self) -> str:
        """Return the window title."""
        return self.text

    @title.setter
    def title(self, value: str) -> None:
        self.text = value

    @property
    def menu_bar(self) -> swingset.menu.MenuBar | None:
        """Return the currently attached menu bar."""
        return self._menu_bar

    @menu_bar.setter
    def menu_bar(self, value: swingset.menu.MenuBar | None) -> None:
        self._menu_bar = value
        peer = self._peer
        if isinstance(peer, WindowPeer) and self.created:
            peer.set_menu(value)

    def _request_close(self) -> None:
        self.dispose()

    def destroy(self) -> None:
        """Destroy the window and release mounted-window tracking."""
        context = self._context
        was_created = self.created
        super().destroy()
        if was_created and context is not None:
            context.windows.unmounted(self)

    def dispose(self) -> None:
        """Destroy the window and update mounted-window tracking."""
        self.destroy()
