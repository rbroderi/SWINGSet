"""Backend discovery with explicit diagnostics and graceful fallback."""

from __future__ import annotations

import importlib.util
import os
import sys
import warnings
from collections.abc import Callable
from dataclasses import dataclass
from dataclasses import field
from importlib import import_module
from typing import Final
from typing import Protocol
from typing import cast
from typing import runtime_checkable

from swingset.context import UIContext

from .base import Backend
from .base import BackendUnavailableError
from .base import Capability


@runtime_checkable
class _TkRoot(Protocol):
    def withdraw(self) -> None:
        """Hide the probe window."""
        ...

    def destroy(self) -> None:
        """Destroy the probe window."""
        ...


def _import_error(module_name: str) -> Exception | None:
    try:
        import_module(module_name)
    except (ImportError, OSError) as exc:
        return exc
    return None


def _import_backend_type(
    module_name: str,
    class_name: str,
) -> tuple[type[Backend] | None, Exception | None]:
    try:
        module = import_module(module_name)
    except (ImportError, OSError) as exc:
        return None, exc
    candidate = getattr(module, class_name, None)
    if not isinstance(candidate, type) or not issubclass(candidate, Backend):
        msg = f"{module_name}.{class_name} is not a Backend subclass"
        return None, TypeError(msg)
    return candidate, None


_TKINTER_IMPORT_ERROR: Final = _import_error("tkinter")
TkinterBackend, _TKINTER_BACKEND_IMPORT_ERROR = _import_backend_type(
    "swingset.backends.tkinter",
    "TkinterBackend",
)
TextualBackend, _TEXTUAL_IMPORT_ERROR = _import_backend_type(
    "swingset.backends.textual",
    "TextualBackend",
)
Win32Backend, _WIN32_IMPORT_ERROR = _import_backend_type(
    "swingset.backends.win32",
    "Win32Backend",
)

_AUTO: Final = "auto"
_VALID: Final = frozenset({_AUTO, "win32", "tkinter", "textual"})


@dataclass(frozen=True, slots=True)
class BackendAttempt:
    """One backend selection attempt for diagnostics."""

    name: str
    selected: bool
    reason: str


@dataclass(frozen=True, slots=True)
class BackendInfo:
    """Current backend selection and fallback history."""

    requested: str
    active: str
    attempts: tuple[BackendAttempt, ...]


@dataclass(slots=True)
class _RuntimeState:
    """Mutable backend runtime state owned by this module."""

    backend_name: str = os.environ.get("SWINGSET_BACKEND", _AUTO).lower()
    context: UIContext | None = None
    attempts: list[BackendAttempt] = field(default_factory=list)


_STATE = _RuntimeState()


def configure(name: str) -> None:
    """Set backend preference; expected environmental failures may fall through."""
    normalized = name.lower().strip()
    if normalized not in _VALID:
        msg = f"unknown backend {name!r}; expected auto, win32, tkinter, or textual"
        raise ValueError(msg)
    _STATE.backend_name = normalized
    _STATE.context = None
    _STATE.attempts.clear()


def _tkinter_probe() -> None:
    if importlib.util.find_spec("tkinter") is None:
        msg = "tkinter is not installed"
        raise BackendUnavailableError(msg)
    if _TKINTER_IMPORT_ERROR is not None:
        msg = "tkinter import failed"
        raise BackendUnavailableError(msg) from _TKINTER_IMPORT_ERROR
    if sys.platform in {"win32", "darwin"}:
        return
    if not (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")):
        msg = "no graphical display is configured"
        raise BackendUnavailableError(msg)
    module = import_module("tkinter")
    root_factory = cast("Callable[[], _TkRoot]", module.Tk)
    tcl_error = cast("type[Exception]", module.TclError)
    try:
        root = root_factory()
        root.withdraw()
        root.destroy()
    except (OSError, tcl_error) as exc:
        msg = f"graphical display probe failed: {exc}"
        raise BackendUnavailableError(msg) from exc


def _candidate_names() -> tuple[str, ...]:
    if _STATE.backend_name == _AUTO:
        if sys.platform == "win32":
            return "win32", "tkinter", "textual"
        return "tkinter", "textual", "win32"
    normal = ("win32", "tkinter", "textual")
    return (
        _STATE.backend_name,
        *(name for name in normal if name != _STATE.backend_name),
    )


def _load_backend(name: str) -> Backend:
    if name == "win32":
        if sys.platform != "win32":
            msg = "Win32 is only available on Windows"
            raise BackendUnavailableError(msg)
        if Win32Backend is None:
            details = _WIN32_IMPORT_ERROR
            msg = f"Win32 dependencies unavailable: {details}"
            raise BackendUnavailableError(msg) from details
        return Win32Backend()
    if name == "tkinter":
        _tkinter_probe()
        if TkinterBackend is None:
            details = _TKINTER_BACKEND_IMPORT_ERROR
            msg = f"Tkinter backend unavailable: {details}"
            raise BackendUnavailableError(msg) from details
        return TkinterBackend()
    if name == "textual":
        if importlib.util.find_spec("textual") is None:
            msg = "Textual is not installed"
            raise BackendUnavailableError(msg)
        if TextualBackend is None:
            details = _TEXTUAL_IMPORT_ERROR
            msg = f"Textual backend unavailable: {details}"
            raise BackendUnavailableError(msg) from details
        return TextualBackend()
    msg = f"unsupported backend {name!r}"
    raise BackendUnavailableError(msg)


def get_context() -> UIContext:
    """Return the selected context, falling back only for expected unavailability."""
    if _STATE.context is not None:
        return _STATE.context
    _STATE.attempts.clear()
    for name in _candidate_names():
        try:
            backend = _load_backend(name)
        except BackendUnavailableError as exc:
            _STATE.attempts.append(
                BackendAttempt(name, selected=False, reason=str(exc))
            )
            continue
        if name == "tkinter" and _STATE.backend_name != "tkinter":
            warnings.warn(
                "Tkinter was selected as a fallback; configure "
                "backend='tkinter' to select it explicitly.",
                RuntimeWarning,
                stacklevel=2,
            )
        _STATE.attempts.append(BackendAttempt(name, selected=True, reason="selected"))
        _STATE.context = UIContext(backend)
        return _STATE.context
    reasons = "; ".join(f"{item.name}: {item.reason}" for item in _STATE.attempts)
    msg = f"no SWINGSet backend is available ({reasons})"
    raise BackendUnavailableError(msg)


def selected_name() -> str:
    """Return the active backend name."""
    return get_context().backend.name


def supports(capability: Capability) -> bool:
    """Return whether the active backend supports a capability."""
    return get_context().backend.supports(capability)


def backend_info() -> BackendInfo:
    """Return backend selection details and fallback attempts."""
    context = get_context()
    return BackendInfo(
        _STATE.backend_name,
        context.backend.name,
        tuple(_STATE.attempts),
    )
