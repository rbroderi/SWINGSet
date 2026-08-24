"""Backend contracts and runtime selection."""

from .base import Backend as Backend
from .base import BackendUnavailableError as BackendUnavailableError
from .base import Capability as Capability
from .base import UnsupportedComponentError as UnsupportedComponentError
from .runtime import BackendAttempt as BackendAttempt
from .runtime import BackendInfo as BackendInfo
from .runtime import backend_info as backend_info
from .runtime import configure as configure
from .runtime import get_context as get_context
from .runtime import selected_name as selected_name
from .runtime import supports as supports
