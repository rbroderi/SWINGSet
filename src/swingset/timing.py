"""Portable repeating timers dispatched onto the active UI thread."""

from __future__ import annotations

import threading
from collections.abc import Callable
from typing import Self

from .context import UIContext
from .context import current_context


class Timer:
    """Cancellable timer whose callback always runs on the UI thread."""

    def __init__(
        self,
        interval_ms: int,
        callback: Callable[[], object],
        *,
        repeat: bool = True,
        context: UIContext | None = None,
    ) -> None:
        """Configure a timer without starting it."""
        if interval_ms <= 0:
            msg = "timer interval must be greater than zero"
            raise ValueError(msg)
        self.interval_ms = interval_ms
        self.callback = callback
        self.repeat = repeat
        self._context = context
        self._native_timer: threading.Timer | None = None
        self._running = False

    @property
    def running(self) -> bool:
        """Return whether this timer is scheduled."""
        return self._running

    def _schedule(self) -> None:
        native_timer = threading.Timer(self.interval_ms / 1000, self._queue_tick)
        native_timer.daemon = True
        self._native_timer = native_timer
        native_timer.start()

    def start(self) -> None:
        """Start or restart the timer."""
        self.stop()
        if self._context is None:
            self._context = current_context()
        if self._context is None:
            msg = "timers require an active UI context"
            raise RuntimeError(msg)
        self._running = True
        self._schedule()

    def stop(self) -> None:
        """Cancel any scheduled callback."""
        self._running = False
        native_timer = self._native_timer
        self._native_timer = None
        if native_timer is not None:
            native_timer.cancel()

    def _queue_tick(self) -> None:
        context = self._context
        if self._running and context is not None:
            context.backend.call_soon(self._tick)

    def _tick(self) -> None:
        if not self._running:
            return
        self.callback()
        if self.repeat and self._running:
            self._schedule()
        else:
            self._running = False
            self._native_timer = None

    def __enter__(self) -> Self:
        """Start the timer for a managed lifetime."""
        self.start()
        return self

    def __exit__(self, *_exc_info: object) -> None:
        """Stop the timer at the end of a managed lifetime."""
        self.stop()
