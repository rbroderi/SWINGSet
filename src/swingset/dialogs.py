"""Portable facades for native message and file dialogs."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from .backends.base import Backend
from .context import current_context
from .core import Window


class MessageButtons(StrEnum):
    """Supported native message-box button groups."""

    OK = "ok"
    OK_CANCEL = "ok_cancel"
    YES_NO = "yes_no"
    YES_NO_CANCEL = "yes_no_cancel"


class MessageIcon(StrEnum):
    """Supported native message-box icons."""

    NONE = "none"
    INFORMATION = "information"
    WARNING = "warning"
    ERROR = "error"
    QUESTION = "question"


class MessageResult(StrEnum):
    """Portable result returned by a message box."""

    OK = "ok"
    CANCEL = "cancel"
    YES = "yes"
    NO = "no"


@dataclass(frozen=True, slots=True)
class FileFilter:
    """One display name and wildcard pattern for a file dialog."""

    name: str
    pattern: str


@dataclass(frozen=True, slots=True)
class FontSpec:
    """Portable font selection returned by a native font dialog."""

    face: str = "Segoe UI"
    size: int = 9
    bold: bool = False
    italic: bool = False


@dataclass(frozen=True, slots=True)
class PageMargins:
    """Page margins in thousandths of an inch."""

    left: int = 1000
    top: int = 1000
    right: int = 1000
    bottom: int = 1000


@dataclass(frozen=True, slots=True)
class PrintSettings:
    """Page range and copy count selected by a print dialog."""

    from_page: int = 1
    to_page: int = 1
    copies: int = 1


def _backend_and_owner(owner: Window | None) -> tuple[Backend, object | None]:
    context = None if owner is None else owner.context
    if context is None:
        context = current_context()
    if context is None:
        msg = "dialogs require an active UI context"
        raise RuntimeError(msg)
    peer = None if owner is None else owner.peer
    native_owner = None if peer is None else peer.native
    return context.backend, native_owner


class MessageBox:
    """Native modal message-box service."""

    @staticmethod
    def show(
        message: str,
        title: str = "Message",
        *,
        buttons: MessageButtons = MessageButtons.OK,
        icon: MessageIcon = MessageIcon.NONE,
        owner: Window | None = None,
    ) -> MessageResult:
        """Show a native message box and return the selected result."""
        backend, native_owner = _backend_and_owner(owner)
        result = backend.show_message(
            native_owner,
            title,
            message,
            buttons.value,
            icon.value,
        )
        return MessageResult(result)


@dataclass(slots=True)
class OpenFileDialog:
    """Native open-file dialog configuration."""

    title: str = "Open"
    filters: tuple[FileFilter, ...] = ()
    initial_directory: Path | None = None

    def show(self, owner: Window | None = None) -> Path | None:
        """Show the dialog and return the selected path, or None on cancellation."""
        backend, native_owner = _backend_and_owner(owner)
        result = backend.choose_file(
            native_owner,
            self.title,
            tuple((item.name, item.pattern) for item in self.filters),
            None if self.initial_directory is None else str(self.initial_directory),
            save=False,
        )
        return None if result is None else Path(result)


@dataclass(slots=True)
class SaveFileDialog:
    """Native save-file dialog configuration."""

    title: str = "Save As"
    filters: tuple[FileFilter, ...] = ()
    initial_directory: Path | None = None

    def show(self, owner: Window | None = None) -> Path | None:
        """Show the dialog and return the selected path, or None on cancellation."""
        backend, native_owner = _backend_and_owner(owner)
        result = backend.choose_file(
            native_owner,
            self.title,
            tuple((item.name, item.pattern) for item in self.filters),
            None if self.initial_directory is None else str(self.initial_directory),
            save=True,
        )
        return None if result is None else Path(result)


@dataclass(slots=True)
class FolderBrowserDialog:
    """Native folder-selection dialog configuration."""

    title: str = "Select Folder"

    def show(self, owner: Window | None = None) -> Path | None:
        """Show the dialog and return the selected folder, or None on cancellation."""
        backend, native_owner = _backend_and_owner(owner)
        result = backend.choose_folder(native_owner, self.title)
        return None if result is None else Path(result)


@dataclass(slots=True)
class ColorDialog:
    """Native color-selection dialog configuration."""

    color: tuple[int, int, int] = (0, 0, 0)

    def show(self, owner: Window | None = None) -> tuple[int, int, int] | None:
        """Show the dialog and return an RGB color, or None on cancellation."""
        backend, native_owner = _backend_and_owner(owner)
        return backend.choose_color(native_owner, self.color)


@dataclass(slots=True)
class FontDialog:
    """Native font-selection dialog configuration."""

    font: FontSpec = FontSpec()

    def show(self, owner: Window | None = None) -> FontSpec | None:
        """Show the dialog and return a font, or None on cancellation."""
        backend, native_owner = _backend_and_owner(owner)
        result = backend.choose_font(
            native_owner,
            (self.font.face, self.font.size, self.font.bold, self.font.italic),
        )
        return None if result is None else FontSpec(*result)


@dataclass(slots=True)
class PageSetupDialog:
    """Native page-setup dialog configuration."""

    margins: PageMargins = PageMargins()

    def show(self, owner: Window | None = None) -> PageMargins | None:
        """Show the dialog and return margins, or None on cancellation."""
        backend, native_owner = _backend_and_owner(owner)
        result = backend.choose_page_setup(
            native_owner,
            (
                self.margins.left,
                self.margins.top,
                self.margins.right,
                self.margins.bottom,
            ),
        )
        return None if result is None else PageMargins(*result)


@dataclass(slots=True)
class PrintDialog:
    """Native print-dialog configuration."""

    settings: PrintSettings = PrintSettings()

    def show(self, owner: Window | None = None) -> PrintSettings | None:
        """Show the dialog and return print settings, or None on cancellation."""
        backend, native_owner = _backend_and_owner(owner)
        result = backend.choose_print(
            native_owner,
            (self.settings.from_page, self.settings.to_page),
            self.settings.copies,
        )
        return None if result is None else PrintSettings(*result)
