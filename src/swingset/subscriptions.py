"""Disposable weak subscriptions used by models and framework services."""

from __future__ import annotations

import inspect
import weakref
from collections.abc import Callable
from dataclasses import dataclass
from typing import Self


@dataclass(slots=True)
class Subscription:
    """A single disposable listener registration."""

    _dispose_callback: Callable[[], None] | None

    @property
    def disposed(self) -> bool:
        """Return whether this subscription was already disposed."""
        return self._dispose_callback is None

    def dispose(self) -> None:
        """Dispose this subscription once."""
        callback = self._dispose_callback
        if callback is None:
            return
        self._dispose_callback = None
        callback()

    def __enter__(self) -> Self:
        """Return self for context-manager usage."""
        return self

    def __exit__(self, *_args: object) -> None:
        """Dispose the subscription when leaving a context."""
        self.dispose()


class _ListenerRef[T]:
    def __init__(self, callback: Callable[[T], None]) -> None:
        self._strong: Callable[[T], None] | None = None
        self._weak: weakref.WeakMethod[Callable[[T], None]] | None = None
        if (
            inspect.ismethod(callback)
            and getattr(callback, "__self__", None) is not None
        ):
            self._weak = weakref.WeakMethod(callback)
        else:
            self._strong = callback

    def get(self) -> Callable[[T], None] | None:
        if self._strong is not None:
            return self._strong
        if self._weak is None:
            return None
        return self._weak()

    def matches(self, callback: Callable[[T], None]) -> bool:
        return self.get() == callback


class Signal[T]:
    """Minimal observer signal with weak bound-method listeners."""

    def __init__(self) -> None:
        """Create an empty listener list."""
        self._listeners: list[_ListenerRef[T]] = []

    def subscribe(self, callback: Callable[[T], None]) -> Subscription:
        """Register a listener and return its disposable token."""
        reference = _ListenerRef(callback)
        self._listeners.append(reference)

        def dispose() -> None:
            if reference in self._listeners:
                self._listeners.remove(reference)

        return Subscription(dispose)

    def unsubscribe(self, callback: Callable[[T], None]) -> None:
        """Remove all listener registrations matching callback."""
        self._listeners = [
            item for item in self._listeners if not item.matches(callback)
        ]

    def emit(self, value: T) -> None:
        """Notify live listeners and prune collected bound methods."""
        alive: list[_ListenerRef[T]] = []
        for reference in self._listeners:
            listener = reference.get()
            if listener is None:
                continue
            alive.append(reference)
            listener(value)
        self._listeners = alive
