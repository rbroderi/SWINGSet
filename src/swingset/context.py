"""Explicit application context replacing hidden backend service lookup."""

from __future__ import annotations

import threading
from collections.abc import Callable
from collections.abc import Generator
from concurrent.futures import Future
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from dataclasses import field
from typing import TYPE_CHECKING
from typing import Protocol
from typing import runtime_checkable
from weakref import WeakSet

from .theme import Theme

if TYPE_CHECKING:
    import swingset.backends.base


@runtime_checkable
class ThemeAwareWindow(Protocol):
    """Window capability required by the context registry."""

    def handle_theme_changed(self) -> None:
        """Apply the context's current theme."""


class Dispatcher:
    """Backend-independent UI-thread scheduler."""

    def __init__(self, backend: swingset.backends.base.Backend) -> None:
        """Initialize a dispatcher backed by one runtime backend."""
        self._backend = backend
        self._thread_id: int | None = None

    def enter_ui_thread(self) -> None:
        """Mark the current thread as the active UI thread."""
        self._thread_id = threading.get_ident()

    def leave_ui_thread(self) -> None:
        """Clear the active UI thread marker."""
        self._thread_id = None

    def is_ui_thread(self) -> bool:
        """Return whether the current thread is the active UI thread."""
        return self._thread_id == threading.get_ident()

    def require_ui_thread(self) -> None:
        """Reject cross-thread access while a UI event loop is active."""
        if self._thread_id is not None and not self.is_ui_thread():
            msg = "mounted UI state may only be accessed from the UI thread"
            raise RuntimeError(msg)

    def invoke_later(self, callback: Callable[[], object]) -> None:
        """Schedule a callback to run on the backend event queue."""
        self._backend.call_soon(callback)

    def submit[T](self, callback: Callable[[], T]) -> Future[T]:
        """Schedule work and return a future that resolves with its result."""
        future: Future[T] = Future()

        def wrapped() -> None:
            if future.cancelled():
                return
            try:
                result = callback()
            except BaseException as exc:
                if isinstance(exc, (KeyboardInterrupt, SystemExit, GeneratorExit)):
                    raise
                future.set_exception(exc)
            else:
                future.set_result(result)

        self.invoke_later(wrapped)
        return future


class WindowRegistry:
    """Per-context top-level window lifecycle registry."""

    def __init__(self) -> None:
        """Create empty weak sets for known and mounted windows."""
        self._windows: WeakSet[ThemeAwareWindow] = WeakSet()
        self._mounted: WeakSet[ThemeAwareWindow] = WeakSet()

    def remember(self, window: ThemeAwareWindow) -> None:
        """Track a window for future lifecycle and theme updates."""
        self._windows.add(window)

    def mounted(self, window: ThemeAwareWindow) -> None:
        """Mark a window as mounted and visible to the runtime."""
        self._windows.add(window)
        self._mounted.add(window)

    def unmounted(self, window: ThemeAwareWindow) -> None:
        """Mark a window as no longer mounted."""
        self._mounted.discard(window)

    @property
    def open_count(self) -> int:
        """Return the number of currently mounted windows."""
        return len(self._mounted)

    def refresh_themes(self) -> None:
        """Notify all tracked windows that theme state changed."""
        for window in tuple(self._windows):
            window.handle_theme_changed()


@dataclass(slots=True)
class ThemeService:
    """Theme intent owned by one UI context."""

    theme: Theme = Theme.SYSTEM

    def set(self, theme: Theme | str) -> None:
        """Set the current theme value for this context."""
        self.theme = Theme(theme)


@dataclass(slots=True)
class UIContext:
    """All runtime services a component tree needs."""

    backend: swingset.backends.base.Backend
    dispatcher: Dispatcher = field(init=False)
    theme: ThemeService = field(default_factory=ThemeService)
    windows: WindowRegistry = field(default_factory=WindowRegistry)

    def __post_init__(self) -> None:
        """Build runtime services derived from the selected backend."""
        self.dispatcher = Dispatcher(self.backend)


_current_context: ContextVar[UIContext | None] = ContextVar(
    "swingset_ui_context",
    default=None,
)


def current_context() -> UIContext | None:
    """Return the context dynamically injected by the application bootstrap."""
    return _current_context.get()


@contextmanager
def bind_context(context: UIContext) -> Generator[None]:
    """Bind a UIContext to the current execution context for component construction."""
    token = _current_context.set(context)
    try:
        yield
    finally:
        _current_context.reset(token)
