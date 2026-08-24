"""Application facade, explicit context access, and asyncio interoperability."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from collections.abc import Coroutine
from concurrent.futures import Future

from .backends import BackendInfo
from .backends import Capability
from .backends.runtime import backend_info
from .backends.runtime import configure
from .backends.runtime import get_context
from .backends.runtime import selected_name
from .backends.runtime import supports
from .context import UIContext
from .context import bind_context
from .theme import Theme


class UIThread:
    """Dispatch work through the current context without exposing backend mechanics."""

    @classmethod
    def is_ui_thread(cls) -> bool:
        """Return whether the current thread is the active UI thread."""
        return get_context().dispatcher.is_ui_thread()

    @classmethod
    def invoke_later(cls, callback: Callable[[], object]) -> None:
        """Schedule a callback to run on the UI thread."""
        get_context().dispatcher.invoke_later(callback)

    @classmethod
    def submit[T](cls, callback: Callable[[], T]) -> Future[T]:
        """Submit work to the UI thread and return a future for its result."""
        return get_context().dispatcher.submit(callback)

    @classmethod
    def invoke_and_wait[T](cls, callback: Callable[[], T]) -> T:
        """Run a callback on the UI thread and wait for the return value."""
        dispatcher = get_context().dispatcher
        if dispatcher.is_ui_thread():
            return callback()
        return dispatcher.submit(callback).result()

    @classmethod
    async def invoke_async[T](cls, callback: Callable[[], T]) -> T:
        """Await a callback executed on the UI thread."""
        return await asyncio.wrap_future(cls.submit(callback))

    @classmethod
    def run(cls, startup: Callable[[], object] | None = None) -> None:
        """Start the backend UI loop for the current context."""
        context = get_context()
        context.dispatcher.enter_ui_thread()
        try:
            with bind_context(context):
                context.backend.run(startup)
        finally:
            context.dispatcher.leave_ui_thread()

    @classmethod
    async def run_async(cls, startup: Callable[[], object] | None = None) -> None:
        """Run the UI loop in an executor and await completion."""
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, cls.run, startup)


class App:
    """High-level facade over a per-run UIContext."""

    invoke_later = UIThread.invoke_later
    invoke_and_wait = UIThread.invoke_and_wait
    invoke_async = UIThread.invoke_async
    is_ui_thread = UIThread.is_ui_thread
    run = UIThread.run
    run_async = UIThread.run_async

    @staticmethod
    def configure(*, backend: str = "auto") -> None:
        """Select which backend runtime to use."""
        configure(backend)

    @staticmethod
    def context() -> UIContext:
        """Return the explicit runtime context for advanced integration/testing."""
        return get_context()

    @staticmethod
    def backend_name() -> str:
        """Return the name of the selected backend."""
        return selected_name()

    @staticmethod
    def backend_info() -> BackendInfo:
        """Describe fallback attempts so graceful degradation remains debuggable."""
        return backend_info()

    @staticmethod
    def supports(capability: Capability) -> bool:
        """Return whether the current backend supports a capability."""
        return supports(capability)

    @staticmethod
    def on_idle(listener: Callable[[], object]) -> Callable[[], object]:
        """Register a listener invoked when the native event queue becomes idle."""
        return get_context().backend.on_idle(listener)

    @staticmethod
    def set_theme(theme: Theme | str) -> None:
        """Apply a theme to the current context and refresh open windows."""
        context = get_context()
        context.theme.set(theme)
        context.windows.refresh_themes()

    @staticmethod
    def create_task[T](coro: Coroutine[object, object, T]) -> asyncio.Task[T]:
        """Create an asyncio task on the running event loop."""
        return asyncio.get_running_loop().create_task(coro)
