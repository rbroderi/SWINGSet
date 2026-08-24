"""Small backend contract plus type-driven peer registry."""

from __future__ import annotations

from abc import ABC
from abc import abstractmethod
from collections.abc import Callable
from enum import StrEnum

from swingset.core import Component
from swingset.peers import ComponentPeer
from swingset.peers import NullComponentPeer

type PeerFactory = Callable[["Component", ComponentPeer | None], ComponentPeer]


class Capability(StrEnum):
    """Optional features a backend can truthfully advertise."""

    DARK_MODE = "dark_mode"
    NATIVE_DARK_MODE = "native_dark_mode"
    SVG = "svg"
    WINDOW_ICON = "window_icon"
    MENUS = "menus"
    TABLE = "table"
    TREE = "tree"
    TABS = "tabs"
    COLORED_TAB_PAGES = "colored_tab_pages"
    SPLIT_PANE = "split_pane"
    SCROLL_PANE = "scroll_pane"
    TOOLBAR = "toolbar"
    STATUS_BAR = "status_bar"
    DPI_AWARE = "dpi_aware"
    TERMINAL_UI = "terminal_ui"
    RICH_TEXT = "rich_text"
    TOOLTIPS = "tooltips"
    CLASSIC_THEME = "classic_theme"
    MESSAGE_DIALOGS = "message_dialogs"
    FILE_DIALOGS = "file_dialogs"
    NATIVE_COMMON_DIALOGS = "native_common_dialogs"
    CUSTOM_PAINT = "custom_paint"


class BackendUnavailableError(RuntimeError):
    """Expected environment/dependency failure that permits graceful fallback."""


class UnsupportedComponentError(RuntimeError):
    """A component requires a peer but the selected backend has no registration."""


class Backend(ABC):
    """Minimal event-loop and peer-factory backend abstraction."""

    name: str
    capabilities: frozenset[Capability] = frozenset()
    _peer_factories: dict[type[Component], PeerFactory]

    def __init__(self) -> None:
        """Initialize the instance."""
        self._peer_factories = {}
        self._factories_installed = False
        self._idle_listeners: list[Callable[[], object]] = []

    def supports(self, capability: Capability) -> bool:
        """Return supports."""
        return capability in self.capabilities

    def _ensure_factories(self) -> None:
        if self._factories_installed:
            return
        self.install_factories()
        self._factories_installed = True

    def supports_component(self, component_type: type[Component]) -> bool:
        """Return whether a component type resolves to a registered peer."""
        self._ensure_factories()
        return any(
            candidate in self._peer_factories for candidate in component_type.__mro__
        )

    def on_idle(self, listener: Callable[[], object]) -> Callable[[], object]:
        """Register an application-idle listener and return it."""
        self._idle_listeners.append(listener)
        return listener

    def _emit_idle(self) -> None:
        for listener in tuple(self._idle_listeners):
            listener()

    def register_peer(
        self,
        component_type: type[Component],
        factory: PeerFactory,
    ) -> None:
        """Register a peer factory by portable component class."""
        self._peer_factories[component_type] = factory

    def create_peer(
        self,
        component: Component,
        parent_peer: ComponentPeer | None,
    ) -> ComponentPeer:
        """Create a peer using MRO-aware type registration, never string RTTI."""
        self._ensure_factories()
        for component_type in type(component).__mro__:
            factory = self._peer_factories.get(component_type)
            if factory is not None:
                peer = factory(component, parent_peer)
                if parent_peer is not None:
                    parent_peer.attach_child(peer)
                return peer
        if component.allow_null_peer:
            return NullComponentPeer(component)
        msg = f"{self.name} has no peer registered for {type(component).__name__}"
        raise UnsupportedComponentError(msg)

    @abstractmethod
    def install_factories(self) -> None:
        """Register backend peer factories."""

    @abstractmethod
    def initialize(self) -> None:
        """Initialize backend process/thread state."""

    @abstractmethod
    def run(self, startup: Callable[[], object] | None = None) -> None:
        """Run the event loop until application shutdown."""

    @abstractmethod
    def call_soon(self, callback: Callable[[], object]) -> None:
        """Schedule a callback on the backend UI thread."""

    def show_message(
        self,
        owner: object | None,
        title: str,
        message: str,
        buttons: str,
        icon: str,
    ) -> str:
        """Show a native message box when supported."""
        del owner, title, message, buttons, icon
        msg = f"{self.name} does not support native message dialogs"
        raise UnsupportedComponentError(msg)

    def choose_file(
        self,
        owner: object | None,
        title: str,
        filters: tuple[tuple[str, str], ...],
        initial_directory: str | None,
        *,
        save: bool,
    ) -> str | None:
        """Show a native open/save file dialog when supported."""
        del owner, title, filters, initial_directory, save
        msg = f"{self.name} does not support native file dialogs"
        raise UnsupportedComponentError(msg)

    def choose_folder(self, owner: object | None, title: str) -> str | None:
        """Show a native folder browser when supported."""
        del owner, title
        msg = f"{self.name} does not support native folder dialogs"
        raise UnsupportedComponentError(msg)

    def choose_color(
        self,
        owner: object | None,
        initial: tuple[int, int, int],
    ) -> tuple[int, int, int] | None:
        """Show a native color dialog when supported."""
        del owner, initial
        msg = f"{self.name} does not support native color dialogs"
        raise UnsupportedComponentError(msg)

    def choose_font(
        self,
        owner: object | None,
        initial: tuple[str, int, bool, bool],
    ) -> tuple[str, int, bool, bool] | None:
        """Show a native font dialog when supported."""
        del owner, initial
        msg = f"{self.name} does not support native font dialogs"
        raise UnsupportedComponentError(msg)

    def choose_page_setup(
        self,
        owner: object | None,
        margins: tuple[int, int, int, int],
    ) -> tuple[int, int, int, int] | None:
        """Show a native page-setup dialog when supported."""
        del owner, margins
        msg = f"{self.name} does not support native page-setup dialogs"
        raise UnsupportedComponentError(msg)

    def choose_print(
        self,
        owner: object | None,
        pages: tuple[int, int],
        copies: int,
    ) -> tuple[int, int, int] | None:
        """Show a native print dialog when supported."""
        del owner, pages, copies
        msg = f"{self.name} does not support native print dialogs"
        raise UnsupportedComponentError(msg)
