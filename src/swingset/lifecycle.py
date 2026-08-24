"""Component lifecycle states."""

from __future__ import annotations

from enum import Enum
from enum import auto


class ComponentState(Enum):
    """Explicit lifecycle state for a UI component."""

    NEW = auto()
    MOUNTING = auto()
    MOUNTED = auto()
    DESTROYING = auto()
    DESTROYED = auto()
