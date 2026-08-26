"""Native Win32 backend using pywin32 and typed component peers."""

from __future__ import annotations

import contextlib
import ctypes
import itertools
import queue
from collections.abc import Callable
from ctypes import wintypes
from dataclasses import dataclass
from typing import Any, Final, Protocol, cast
from uuid import UUID

import pythoncom
import win32api
import win32con
import win32gui
import win32gui_struct
import win32ui

import swingset.core as swingset_core
import swingset.drawing as swingset_drawing
import swingset.widgets as swingset_widgets
from swingset.core import Component
from swingset.drawing import Graphics, PaintSurface
from swingset.geometry import Point, Rect, Size
from swingset.imaging import ImageResource
from swingset.menu import MenuBar
from swingset.models import ModelEvent
from swingset.peers import (
    BooleanPeer,
    ComponentPeer,
    IntValuePeer,
    PaintPeer,
    PasswordPeer,
    RichTextPeer,
    SelectionPeer,
    WindowPeer,
)
from swingset.theme import ColorInput, Dpi, Theme, resolve_color
from swingset.widgets import (
    Button,
    CheckBox,
    ComboBox,
    ListBox,
    ProgressBar,
    RadioButton,
    Slider,
    TabbedPane,
    Table,
    TreeNode,
    TreeView,
)

from .base import Backend, Capability
from .win32_imaging import NativeImageHandle, render_bitmap, render_icon
from .win32_support import Win32Dpi, Win32Theme

_CLASS_NAME: Final = "SWINGSetWindow"
_ids = itertools.count(1_000)
_ERROR_CLASS_ALREADY_EXISTS: Final = 1410
_WORD_MASK_16: Final = 0xFFFF
_WORD_SIGN_BIT_16: Final = 0x8000
_SIGNED_WORD_BASE_16: Final = 0x10000
_MAX_UNICODE_CODEPOINT: Final = 0x10FFFF
_WM_DPICHANGED: Final = 0x02E0
_TCIF_TEXT: Final = 0x0001
_CLSCTX_INPROC_SERVER: Final = 0x1
_FOS_PICKFOLDERS: Final = 0x20
_FOS_FORCEFILESYSTEM: Final = 0x40
_FOS_PATHMUSTEXIST: Final = 0x800
_SIGDN_FILESYSPATH: Final = 0x80058000
_ERROR_CANCELLED: Final = 0x800704C7
_PSD_MARGINS: Final = 0x0002
_PSD_INTHOUSANDTHSOFINCHES: Final = 0x0004
_PD_PAGENUMS: Final = 0x0002
_PD_USEDEVMODECOPIESANDCOLLATE: Final = 0x00040000
_FW_BOLD: Final = 700
_UDM_SETRANGE32: Final = win32con.WM_USER + 111
_UDM_SETPOS32: Final = win32con.WM_USER + 113
_UDM_GETPOS32: Final = win32con.WM_USER + 114
_UDN_DELTAPOS: Final = -722
_EM_SETCHARFORMAT: Final = win32con.WM_USER + 68
_SCF_SELECTION: Final = 0x0001
_CFM_BOLD: Final = 0x00000001
_CFM_ITALIC: Final = 0x00000002
_CFM_UNDERLINE: Final = 0x00000004
_CFM_BACKCOLOR: Final = 0x04000000
_CFM_COLOR: Final = 0x40000000
_CFM_FACE: Final = 0x20000000
_CFM_SIZE: Final = 0x80000000
_CFE_AUTOBACKCOLOR: Final = _CFM_BACKCOLOR
_CFE_AUTOCOLOR: Final = _CFM_COLOR
_TTM_ADDTOOLW: Final = win32con.WM_USER + 50
_TTF_IDISHWND: Final = 0x0001
_TTF_SUBCLASS: Final = 0x0010
_CONTROL_COLOR_MESSAGES: Final = frozenset(
    {
        win32con.WM_CTLCOLORBTN,
        win32con.WM_CTLCOLOREDIT,
        win32con.WM_CTLCOLORLISTBOX,
        win32con.WM_CTLCOLORSTATIC,
    }
)
_set_window_text = cast("Callable[[int, str], None]", win32gui.SetWindowText)
_append_menu = cast(
    "Callable[[int, int, int, str], None]",
    win32gui.AppendMenu,
)
_send_text_message = cast(
    "Callable[[int, int, int, str], int]",
    win32gui.SendMessage,
)
_set_scroll_info = cast(
    "Callable[[int, int, tuple[int, int, int, int, int, int], bool], int]",
    win32gui.SetScrollInfo,
)
_invalidate_rect = cast(
    "Callable[[int, tuple[int, int, int, int] | None, bool], None]",
    win32gui.InvalidateRect,
)


class _GUID(ctypes.Structure):
    _fields_ = [
        ("data1", wintypes.DWORD),
        ("data2", wintypes.WORD),
        ("data3", wintypes.WORD),
        ("data4", wintypes.BYTE * 8),
    ]

    @classmethod
    def from_string(cls, value: str) -> _GUID:
        """Create a Windows GUID from its canonical string representation."""
        return cls.from_buffer_copy(UUID(value).bytes_le)


_CLSID_FILE_OPEN_DIALOG: Final = _GUID.from_string(
    "dc1c5a9c-e88a-4dde-a5a1-60f82a20aef7"
)
_IID_FILE_OPEN_DIALOG: Final = _GUID.from_string("d57c7288-d4ad-4768-be02-9d969532d960")


def _com_method(
    interface: ctypes.c_void_p,
    index: int,
    result_type: Any,
    *argument_types: Any,
) -> Callable[..., int]:
    vtable = ctypes.cast(
        interface,
        ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p)),
    ).contents
    prototype = ctypes.WINFUNCTYPE(
        result_type,
        ctypes.c_void_p,
        *argument_types,
    )
    return cast("Callable[..., int]", prototype(vtable[index]))


def _release_com(interface: ctypes.c_void_p) -> None:
    _com_method(interface, 2, wintypes.ULONG)(interface)


def _modern_folder_dialog(owner: int, title: str) -> str | None:
    ole32 = ctypes.OleDLL("ole32")
    co_create_instance = ole32.CoCreateInstance
    co_create_instance.argtypes = [
        ctypes.POINTER(_GUID),
        ctypes.c_void_p,
        wintypes.DWORD,
        ctypes.POINTER(_GUID),
        ctypes.POINTER(ctypes.c_void_p),
    ]
    co_create_instance.restype = ctypes.c_long
    ole32.CoTaskMemFree.argtypes = [ctypes.c_void_p]
    ole32.CoTaskMemFree.restype = None

    dialog = ctypes.c_void_p()
    pythoncom.CoInitialize()
    try:
        result = co_create_instance(
            ctypes.byref(_CLSID_FILE_OPEN_DIALOG),
            None,
            _CLSCTX_INPROC_SERVER,
            ctypes.byref(_IID_FILE_OPEN_DIALOG),
            ctypes.byref(dialog),
        )
        if result < 0:
            raise ctypes.WinError(result)
        try:
            set_options = _com_method(
                dialog,
                9,
                ctypes.c_long,
                wintypes.DWORD,
            )
            options = _FOS_PICKFOLDERS | _FOS_FORCEFILESYSTEM | _FOS_PATHMUSTEXIST
            if (result := set_options(dialog, options)) < 0:
                raise ctypes.WinError(result)
            set_title = _com_method(
                dialog,
                17,
                ctypes.c_long,
                wintypes.LPCWSTR,
            )
            if (result := set_title(dialog, title)) < 0:
                raise ctypes.WinError(result)
            show = _com_method(dialog, 3, ctypes.c_long, wintypes.HWND)
            result = show(dialog, owner)
            if result & 0xFFFFFFFF == _ERROR_CANCELLED:
                return None
            if result < 0:
                raise ctypes.WinError(result)

            item = ctypes.c_void_p()
            get_result = _com_method(
                dialog,
                20,
                ctypes.c_long,
                ctypes.POINTER(ctypes.c_void_p),
            )
            if (result := get_result(dialog, ctypes.byref(item))) < 0:
                raise ctypes.WinError(result)
            try:
                path_pointer = ctypes.c_void_p()
                get_display_name = _com_method(
                    item,
                    5,
                    ctypes.c_long,
                    wintypes.DWORD,
                    ctypes.POINTER(ctypes.c_void_p),
                )
                result = get_display_name(
                    item,
                    _SIGDN_FILESYSPATH,
                    ctypes.byref(path_pointer),
                )
                if result < 0:
                    raise ctypes.WinError(result)
                try:
                    return ctypes.wstring_at(path_pointer)
                finally:
                    ole32.CoTaskMemFree(path_pointer)
            finally:
                _release_com(item)
        finally:
            _release_com(dialog)
    finally:
        pythoncom.CoUninitialize()


class _NativeFileDialog(Protocol):
    def SetOFNTitle(self, title: str) -> None:
        """Mirror pywin32's native method name."""
        ...

    def SetOFNInitialDir(self, directory: str) -> None:
        """Mirror pywin32's native method name."""
        ...

    def DoModal(self) -> int:
        """Mirror pywin32's native method name."""
        ...

    def GetPathName(self) -> str:
        """Mirror pywin32's native method name."""
        ...


class _NativeColorDialog(Protocol):
    def DoModal(self) -> int:
        """Mirror pywin32's native method name."""
        ...

    def GetColor(self) -> int:
        """Mirror pywin32's native method name."""
        ...


class _NativeFontDialog(Protocol):
    def DoModal(self) -> int:
        """Mirror pywin32's native method name."""
        ...

    def GetFaceName(self) -> str:
        """Mirror pywin32's native method name."""
        ...

    def GetSize(self) -> int:
        """Mirror pywin32's native method name."""
        ...

    def GetWeight(self) -> int:
        """Mirror pywin32's native method name."""
        ...

    def GetCurrentFont(self) -> dict[str, object]:
        """Mirror pywin32's native method name."""
        ...


class _LogFont(Protocol):
    lfHeight: int
    lfWeight: int
    lfCharSet: int
    lfFaceName: str


class _WindowClass(Protocol):
    hInstance: int
    lpszClassName: str
    lpfnWndProc: Callable[[int, int, int, int], int]
    hCursor: int
    hbrBackground: int


class _TCITEMW(ctypes.Structure):
    _fields_ = [
        ("mask", wintypes.UINT),
        ("dwState", wintypes.DWORD),
        ("dwStateMask", wintypes.DWORD),
        ("pszText", wintypes.LPWSTR),
        ("cchTextMax", ctypes.c_int),
        ("iImage", ctypes.c_int),
        ("lParam", wintypes.LPARAM),
    ]


class _PAINTSTRUCT(ctypes.Structure):
    _fields_ = [
        ("hdc", wintypes.HDC),
        ("fErase", wintypes.BOOL),
        ("rcPaint", wintypes.RECT),
        ("fRestore", wintypes.BOOL),
        ("fIncUpdate", wintypes.BOOL),
        ("rgbReserved", wintypes.BYTE * 32),
    ]


class _TOOLINFOW(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.UINT),
        ("uFlags", wintypes.UINT),
        ("hwnd", wintypes.HWND),
        ("uId", ctypes.c_size_t),
        ("rect", wintypes.RECT),
        ("hinst", wintypes.HINSTANCE),
        ("lpszText", wintypes.LPWSTR),
        ("lParam", wintypes.LPARAM),
        ("lpReserved", ctypes.c_void_p),
    ]


class _CHARFORMAT2W(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.UINT),
        ("dwMask", wintypes.DWORD),
        ("dwEffects", wintypes.DWORD),
        ("yHeight", wintypes.LONG),
        ("yOffset", wintypes.LONG),
        ("crTextColor", wintypes.DWORD),
        ("bCharSet", wintypes.BYTE),
        ("bPitchAndFamily", wintypes.BYTE),
        ("szFaceName", wintypes.WCHAR * 32),
        ("wWeight", wintypes.WORD),
        ("sSpacing", ctypes.c_short),
        ("crBackColor", wintypes.DWORD),
        ("lcid", wintypes.DWORD),
        ("dwReserved", wintypes.DWORD),
        ("sStyle", ctypes.c_short),
        ("wKerning", wintypes.WORD),
        ("bUnderlineType", wintypes.BYTE),
        ("bAnimation", wintypes.BYTE),
        ("bRevAuthor", wintypes.BYTE),
        ("bReserved1", wintypes.BYTE),
    ]


class _PAGESETUPDLGW(ctypes.Structure):
    _fields_ = [
        ("lStructSize", wintypes.DWORD),
        ("hwndOwner", wintypes.HWND),
        ("hDevMode", wintypes.HGLOBAL),
        ("hDevNames", wintypes.HGLOBAL),
        ("Flags", wintypes.DWORD),
        ("ptPaperSize", wintypes.POINT),
        ("rtMinMargin", wintypes.RECT),
        ("rtMargin", wintypes.RECT),
        ("hInstance", wintypes.HINSTANCE),
        ("lCustData", wintypes.LPARAM),
        ("lpfnPageSetupHook", ctypes.c_void_p),
        ("lpfnPagePaintHook", ctypes.c_void_p),
        ("lpPageSetupTemplateName", wintypes.LPCWSTR),
        ("hPageSetupTemplate", wintypes.HGLOBAL),
    ]


class _PRINTDLGW(ctypes.Structure):
    _fields_ = [
        ("lStructSize", wintypes.DWORD),
        ("hwndOwner", wintypes.HWND),
        ("hDevMode", wintypes.HGLOBAL),
        ("hDevNames", wintypes.HGLOBAL),
        ("hDC", wintypes.HDC),
        ("Flags", wintypes.DWORD),
        ("nFromPage", wintypes.WORD),
        ("nToPage", wintypes.WORD),
        ("nMinPage", wintypes.WORD),
        ("nMaxPage", wintypes.WORD),
        ("nCopies", wintypes.WORD),
        ("hInstance", wintypes.HINSTANCE),
        ("lCustData", wintypes.LPARAM),
        ("lpfnPrintHook", ctypes.c_void_p),
        ("lpfnSetupHook", ctypes.c_void_p),
        ("lpPrintTemplateName", wintypes.LPCWSTR),
        ("lpSetupTemplateName", wintypes.LPCWSTR),
        ("hPrintTemplate", wintypes.HGLOBAL),
        ("hSetupTemplate", wintypes.HGLOBAL),
    ]


TCM_FIRST: Final = 0x1300
TCM_INSERTITEM: Final = TCM_FIRST + 62


def _insert_tab(hwnd: int, index: int, title: str) -> None:
    buffer = ctypes.create_unicode_buffer(title)
    item = _TCITEMW(
        mask=_TCIF_TEXT,
        pszText=ctypes.cast(buffer, wintypes.LPWSTR),
        cchTextMax=len(title),
    )
    ctypes.windll.user32.SendMessageW(hwnd, TCM_INSERTITEM, index, ctypes.byref(item))


_MOUSE_MESSAGES: Final = frozenset(
    {
        win32con.WM_MOUSEMOVE,
        win32con.WM_LBUTTONDOWN,
        win32con.WM_LBUTTONUP,
        win32con.WM_RBUTTONDOWN,
        win32con.WM_RBUTTONUP,
        win32con.WM_MBUTTONDOWN,
        win32con.WM_MBUTTONUP,
        win32con.WM_MOUSEWHEEL,
    },
)
_KEY_MESSAGES: Final = frozenset(
    {win32con.WM_KEYDOWN, win32con.WM_KEYUP, win32con.WM_CHAR}
)
_MOUSE_BUTTON_BY_MESSAGE: Final = {
    win32con.WM_LBUTTONDOWN: 1,
    win32con.WM_LBUTTONUP: 1,
    win32con.WM_RBUTTONDOWN: 2,
    win32con.WM_RBUTTONUP: 2,
    win32con.WM_MBUTTONDOWN: 3,
    win32con.WM_MBUTTONUP: 3,
}

CB_ADDSTRING: Final = 0x0143
CB_RESETCONTENT: Final = 0x014B
CB_GETCURSEL: Final = 0x0147
CB_SETCURSEL: Final = 0x014E
CBN_SELCHANGE: Final = 1
LB_ADDSTRING: Final = 0x0180
LB_RESETCONTENT: Final = 0x0184
LB_GETCURSEL: Final = 0x0188
LB_SETCURSEL: Final = 0x0186
LBN_SELCHANGE: Final = 1
LVM_FIRST: Final = 0x1000
LVM_DELETEALLITEMS: Final = LVM_FIRST + 9
LVM_INSERTCOLUMN: Final = LVM_FIRST + 97
LVM_INSERTITEM: Final = LVM_FIRST + 77
LVM_SETITEMTEXT: Final = LVM_FIRST + 116
LVM_DELETECOLUMN: Final = LVM_FIRST + 28
LVM_SETEXTENDEDLISTVIEWSTYLE: Final = LVM_FIRST + 54
LVS_REPORT: Final = 0x0001
LVS_SHOWSELALWAYS: Final = 0x0008
LVS_EX_FULLROWSELECT: Final = 0x20
TCM_GETCURSEL: Final = TCM_FIRST + 11
TCM_SETCURSEL: Final = TCM_FIRST + 12
TCM_ADJUSTRECT: Final = TCM_FIRST + 40
TCN_SELCHANGE: Final = -551
PBM_SETRANGE32: Final = win32con.WM_USER + 6
PBM_SETPOS: Final = win32con.WM_USER + 2
TBM_GETPOS: Final = win32con.WM_USER
TBM_SETPOS: Final = win32con.WM_USER + 5
TBM_SETRANGEMIN: Final = win32con.WM_USER + 7
TBM_SETRANGEMAX: Final = win32con.WM_USER + 8
SB_SETTEXTW: Final = win32con.WM_USER + 11
TV_FIRST: Final = 0x1100
TVM_DELETEITEM: Final = TV_FIRST + 1
TVM_INSERTITEMW: Final = TV_FIRST + 50
TVI_ROOT: Final = 0xFFFF0000
TVI_LAST: Final = 0xFFFF0002
TVIF_TEXT: Final = 0x0001


@dataclass(frozen=True, slots=True)
class Win32CreateSpec:
    """Native window creation parameters for one peer instance."""

    parent_peer: ComponentPeer | None
    class_name: str
    style: int
    ex_style: int = 0
    text: str | None = None
    top_level: bool = False


class NMHDR(ctypes.Structure):
    """NMHDR."""

    _fields_ = [
        ("hwndFrom", wintypes.HWND),
        ("idFrom", ctypes.c_size_t),
        ("code", ctypes.c_int),
    ]


class TVITEMW(ctypes.Structure):
    """TVITEMW."""

    _fields_ = [
        ("mask", wintypes.UINT),
        ("hItem", wintypes.HANDLE),
        ("state", wintypes.UINT),
        ("stateMask", wintypes.UINT),
        ("pszText", wintypes.LPWSTR),
        ("cchTextMax", ctypes.c_int),
        ("iImage", ctypes.c_int),
        ("iSelectedImage", ctypes.c_int),
        ("cChildren", ctypes.c_int),
        ("lParam", wintypes.LPARAM),
    ]


class TVINSERTSTRUCTW(ctypes.Structure):
    """TVINSERTSTRUCTW."""

    _fields_ = [
        ("hParent", wintypes.HANDLE),
        ("hInsertAfter", wintypes.HANDLE),
        ("item", TVITEMW),
    ]


class Win32Peer(ComponentPeer):
    """Common HWND peer with input subclassing and logical DPI scaling."""

    def __init__(
        self,
        backend: Win32Backend,
        component: Component,
        create_spec: Win32CreateSpec,
    ) -> None:
        """Initialize the instance."""
        super().__init__(component)
        self.backend = backend
        self._font: int | None = None
        self._image: NativeImageHandle | None = None
        self._tooltip_hwnd: int | None = None
        self._tooltip_text: ctypes.Array[ctypes.c_wchar] | None = None
        parent_peer = create_spec.parent_peer
        parent_hwnd = parent_peer.hwnd if isinstance(parent_peer, Win32Peer) else 0
        module = win32api.GetModuleHandle(None)
        dpi = (
            Win32Dpi.system()
            if create_spec.top_level
            else (
                parent_peer.dpi
                if isinstance(parent_peer, Win32Peer)
                else Win32Dpi.system()
            )
        )
        x = (
            win32con.CW_USEDEFAULT
            if create_spec.top_level and component.x < 0
            else Dpi.scale(component.x, dpi)
        )
        y = (
            win32con.CW_USEDEFAULT
            if create_spec.top_level and component.y < 0
            else Dpi.scale(component.y, dpi)
        )
        self.hwnd = int(
            win32gui.CreateWindowEx(
                create_spec.ex_style,
                create_spec.class_name,
                component.snapshot_text()
                if create_spec.text is None
                else create_spec.text,
                create_spec.style,
                x,
                y,
                Dpi.scale(component.width, dpi),
                Dpi.scale(component.height, dpi),
                parent_hwnd,
                0 if create_spec.top_level else next(_ids),
                module,
                None,
            ),
        )
        backend.register_hwnd(self)
        if not create_spec.top_level and create_spec.class_name != _CLASS_NAME:
            backend.subclass_control(self)

    @property
    def native(self) -> object:
        """Return the native."""
        return self.hwnd

    @property
    def dpi(self) -> int:
        """Return the dpi."""
        return Win32Dpi.for_window(self.hwnd)

    @property
    def text(self) -> str:
        """Return the text."""
        try:
            return win32gui.GetWindowText(self.hwnd)
        except win32gui.error:
            return self.component.snapshot_text()

    @text.setter
    def text(self, value: str) -> None:
        """Set the text."""
        with contextlib.suppress(win32gui.error):
            _set_window_text(self.hwnd, value)

    def destroy(self) -> None:
        """Update destroy."""
        self.backend.unregister_hwnd(self.hwnd)
        if self._tooltip_hwnd is not None:
            with contextlib.suppress(win32gui.error):
                win32gui.DestroyWindow(self._tooltip_hwnd)
            self._tooltip_hwnd = None
            self._tooltip_text = None
        if self._image is not None:
            self._image.close()
            self._image = None
        if self._font is not None:
            with contextlib.suppress(win32gui.error):
                win32gui.DeleteObject(self._font)
            self._font = None
        with contextlib.suppress(win32gui.error):
            win32gui.DestroyWindow(self.hwnd)

    def set_visible(self, *, visible: bool) -> None:
        """Set visible."""
        with contextlib.suppress(win32gui.error):
            win32gui.ShowWindow(
                self.hwnd,
                win32con.SW_SHOW if visible else win32con.SW_HIDE,
            )

    def set_enabled(self, *, enabled: bool) -> None:
        """Set enabled."""
        with contextlib.suppress(win32gui.error):
            win32gui.EnableWindow(self.hwnd, enabled)

    def set_bounds(self, bounds: Rect) -> None:
        """Set bounds."""
        dpi = self.dpi
        x = 0 if bounds.x < 0 else Dpi.scale(bounds.x, dpi)
        y = 0 if bounds.y < 0 else Dpi.scale(bounds.y, dpi)
        repaint = True
        with contextlib.suppress(win32gui.error):
            win32gui.MoveWindow(
                self.hwnd,
                x,
                y,
                Dpi.scale(bounds.width, dpi),
                Dpi.scale(bounds.height, dpi),
                repaint,
            )

    def client_size(self) -> Size:
        """Return client size."""
        try:
            left, top, right, bottom = win32gui.GetClientRect(self.hwnd)
        except win32gui.error:
            return self.component.size
        del left, top
        dpi = self.dpi
        return Size(Dpi.unscale(right, dpi), Dpi.unscale(bottom, dpi))

    def focus(self) -> None:
        """Move keyboard focus to the native component."""
        with contextlib.suppress(win32gui.error):
            win32gui.SetFocus(self.hwnd)

    def set_font(self, face: str, size: int, *, bold: bool) -> None:
        """Set font."""
        height = -Dpi.scale(round(size * 96 / 72), self.dpi)
        native_log_font = win32gui.LOGFONT()
        log_font = cast("_LogFont", native_log_font)
        log_font.lfHeight = height
        log_font.lfWeight = 700 if bold else 400
        log_font.lfCharSet = win32con.DEFAULT_CHARSET
        log_font.lfFaceName = face
        font = int(win32gui.CreateFontIndirect(native_log_font))
        previous = self._font
        self._font = font
        win32gui.SendMessage(self.hwnd, win32con.WM_SETFONT, font, 1)
        if previous is not None:
            with contextlib.suppress(win32gui.error):
                win32gui.DeleteObject(previous)

    def set_tooltip(self, text: str | None) -> None:
        """Create or replace a native common-controls tooltip."""
        if self._tooltip_hwnd is not None:
            with contextlib.suppress(win32gui.error):
                win32gui.DestroyWindow(self._tooltip_hwnd)
            self._tooltip_hwnd = None
            self._tooltip_text = None
        if not text:
            return
        tooltip = int(
            win32gui.CreateWindowEx(
                win32con.WS_EX_TOPMOST,
                "tooltips_class32",
                "",
                win32con.WS_POPUP,
                0,
                0,
                0,
                0,
                self.hwnd,
                0,
                win32api.GetModuleHandle(None),
                None,
            )
        )
        buffer = ctypes.create_unicode_buffer(text)
        info = _TOOLINFOW(
            cbSize=ctypes.sizeof(_TOOLINFOW),
            uFlags=_TTF_IDISHWND | _TTF_SUBCLASS,
            hwnd=self.hwnd,
            uId=self.hwnd,
            lpszText=ctypes.cast(buffer, wintypes.LPWSTR),
        )
        ctypes.windll.user32.SendMessageW(
            tooltip,
            _TTM_ADDTOOLW,
            0,
            ctypes.byref(info),
        )
        self._tooltip_hwnd = tooltip
        self._tooltip_text = buffer

    def _invalidate_color(self) -> None:
        erase = True
        _invalidate_rect(self.hwnd, None, erase)

    def set_foreground(self, color: ColorInput | None) -> None:
        """Request repainting with the component foreground override."""
        del color
        self._invalidate_color()

    def set_background(self, color: ColorInput | None) -> None:
        """Request repainting with the component background override."""
        del color
        self._invalidate_color()

    def apply_theme(self, theme: Theme) -> None:
        """Update apply theme."""
        self.backend.theme = theme
        Win32Theme.apply(self.hwnd, theme)
        if theme is Theme.CLASSIC:
            self.set_font("MS Shell Dlg", 8, bold=False)
        else:
            self.set_font("Segoe UI", 9, bold=False)

    def on_command(self, notify: int) -> None:
        """Handle a native command notification."""
        del notify

    def on_notify(self, code: int, source_hwnd: int) -> None:
        """Handle a native notification message."""
        del code, source_hwnd

    def on_scroll(self) -> None:
        """Handle scroll events."""
        return

    def on_scroll_message(self, message: int, command: int, position: int) -> None:
        """Handle a scrollbar message owned by this peer."""
        del message, command, position

    def on_paint(self) -> bool:
        """Handle custom painting when implemented by a specialized peer."""
        return False

    def _replace_image(self, image: NativeImageHandle | None) -> None:
        previous = self._image
        self._image = image
        if previous is not None:
            previous.close()


class Win32WindowPeer(Win32Peer, WindowPeer):
    """Peer implementation for window components."""

    def __init__(
        self,
        backend: Win32Backend,
        component: Component,
        parent_peer: ComponentPeer | None,
    ) -> None:
        """Initialize the instance."""
        super().__init__(
            backend,
            component,
            Win32CreateSpec(
                parent_peer=parent_peer,
                class_name=_CLASS_NAME,
                style=win32con.WS_OVERLAPPEDWINDOW,
                top_level=True,
            ),
        )
        self._menu_handle: int | None = None
        self.apply_theme(backend.theme)
        backend.window_opened()

    def destroy(self) -> None:
        """Update destroy."""
        super().destroy()
        self.backend.window_closed()

    def apply_theme(self, theme: Theme) -> None:
        """Update apply theme."""
        self.backend.theme = theme
        Win32Theme.apply(self.hwnd, theme, window=True)

    def set_menu(self, menu_bar: MenuBar | None) -> None:
        """Set menu."""
        if self._menu_handle is not None:
            with contextlib.suppress(win32gui.error):
                cast("Callable[[int], None]", win32gui.DestroyMenu)(
                    self._menu_handle,
                )
            self._menu_handle = None
        self.backend.clear_menu_commands(self.hwnd)
        if menu_bar is None:
            win32gui.SetMenu(self.hwnd, 0)
            return
        menu_handle = win32gui.CreateMenu()
        for menu in menu_bar.menus:
            popup = win32gui.CreatePopupMenu()
            for item in menu.items:
                if item is None:
                    _append_menu(popup, win32con.MF_SEPARATOR, 0, "")
                    continue
                flags = win32con.MF_STRING | (0 if item.enabled else win32con.MF_GRAYED)
                _append_menu(popup, flags, item.id, item.text)
                self.backend.register_menu_command(
                    self.hwnd,
                    item.id,
                    item.trigger_action,
                )
            _append_menu(menu_handle, win32con.MF_POPUP, popup, menu.text)
        win32gui.SetMenu(self.hwnd, menu_handle)
        win32gui.DrawMenuBar(self.hwnd)
        self._menu_handle = menu_handle

    def set_icon(self, image: ImageResource | None) -> None:
        """Set icon."""
        if image is None:
            return
        native = render_icon(image, dpi=self.dpi, theme=self.backend.theme)
        self._replace_image(native)
        win32gui.SendMessage(
            self.hwnd,
            win32con.WM_SETICON,
            win32con.ICON_BIG,
            native.handle,
        )
        win32gui.SendMessage(
            self.hwnd,
            win32con.WM_SETICON,
            win32con.ICON_SMALL,
            native.handle,
        )


class Win32PanelPeer(Win32Peer):
    """Peer implementation for panel components."""

    def __init__(
        self,
        backend: Win32Backend,
        component: Component,
        parent_peer: ComponentPeer | None,
    ) -> None:
        """Initialize the instance."""
        super().__init__(
            backend,
            component,
            Win32CreateSpec(
                parent_peer=parent_peer,
                class_name=_CLASS_NAME,
                style=win32con.WS_CHILD
                | win32con.WS_VISIBLE
                | win32con.WS_CLIPCHILDREN,
                text="",
            ),
        )


class Win32ScrollPeer(Win32PanelPeer):
    """Clipped panel with native horizontal and vertical scrollbars."""

    def __init__(
        self,
        backend: Win32Backend,
        component: Component,
        parent_peer: ComponentPeer | None,
    ) -> None:
        """Create a clipped native panel with both scrollbar styles."""
        Win32Peer.__init__(
            self,
            backend,
            component,
            Win32CreateSpec(
                parent_peer=parent_peer,
                class_name=_CLASS_NAME,
                style=win32con.WS_CHILD
                | win32con.WS_VISIBLE
                | win32con.WS_CLIPCHILDREN
                | win32con.WS_HSCROLL
                | win32con.WS_VSCROLL,
                text="",
            ),
        )
        self._content_peer: Win32Peer | None = None

    def attach_child(self, child: ComponentPeer) -> None:
        """Remember the child whose native position represents scrolling."""
        if isinstance(child, Win32Peer):
            self._content_peer = child

    def _set_scroll_info(self, bar: int, position: int, extent: int, page: int) -> None:
        redraw = True
        _set_scroll_info(
            self.hwnd,
            bar,
            (
                win32con.SIF_ALL,
                0,
                max(0, extent - 1),
                max(0, page),
                position,
                0,
            ),
            redraw,
        )

    def refresh(self) -> None:
        """Synchronize scrollbar ranges and the content window position."""
        super().refresh()
        pane = cast("swingset_widgets.ScrollPane", self.component)
        content = pane.content
        if content is None:
            return
        width, height = self.client_size()
        x, y = pane.scroll_position
        self._set_scroll_info(win32con.SB_HORZ, x, content.width, width)
        self._set_scroll_info(win32con.SB_VERT, y, content.height, height)
        if self._content_peer is not None:
            repaint = True
            win32gui.MoveWindow(
                self._content_peer.hwnd,
                -Dpi.scale(x, self.dpi),
                -Dpi.scale(y, self.dpi),
                Dpi.scale(content.width, self.dpi),
                Dpi.scale(content.height, self.dpi),
                repaint,
            )

    def on_scroll_message(self, message: int, command: int, position: int) -> None:
        """Translate a native scrollbar command into a portable offset."""
        pane = cast("swingset_widgets.ScrollPane", self.component)
        horizontal = message == win32con.WM_HSCROLL
        x, y = pane.scroll_position
        current = x if horizontal else y
        client_size = self.client_size()
        page = client_size.width if horizontal else client_size.height
        if command == win32con.SB_LINEUP:
            current -= 16
        elif command == win32con.SB_LINEDOWN:
            current += 16
        elif command == win32con.SB_PAGEUP:
            current -= page
        elif command == win32con.SB_PAGEDOWN:
            current += page
        elif command in {win32con.SB_THUMBPOSITION, win32con.SB_THUMBTRACK}:
            current = position
        pane.scroll_to(current if horizontal else x, y if horizontal else current)


class Win32Graphics(Graphics):
    """Short-lived GDI graphics context for one paint event."""

    def __init__(self, hdc: int, dpi: int, theme: Theme) -> None:
        """Bind one paint DC and its logical coordinate system."""
        self._hdc = hdc
        self._dpi = dpi
        self._theme = theme

    def _color_ref(self, color: ColorInput) -> int:
        red, green, blue, _alpha = resolve_color(color, self._theme)
        return red | (green << 8) | (blue << 16)

    def draw_line(
        self,
        start: Point,
        end: Point,
        *,
        color: ColorInput = "foreground",
        width: int = 1,
    ) -> None:
        """Draw one GDI line."""
        pen = ctypes.windll.gdi32.CreatePen(
            win32con.PS_SOLID,
            Dpi.scale(width, self._dpi),
            self._color_ref(color),
        )
        previous = ctypes.windll.gdi32.SelectObject(self._hdc, pen)
        try:
            ctypes.windll.gdi32.MoveToEx(
                self._hdc,
                Dpi.scale(start.x, self._dpi),
                Dpi.scale(start.y, self._dpi),
                None,
            )
            ctypes.windll.gdi32.LineTo(
                self._hdc,
                Dpi.scale(end.x, self._dpi),
                Dpi.scale(end.y, self._dpi),
            )
        finally:
            ctypes.windll.gdi32.SelectObject(self._hdc, previous)
            ctypes.windll.gdi32.DeleteObject(pen)

    def draw_rectangle(
        self,
        bounds: Rect,
        *,
        color: ColorInput = "foreground",
        width: int = 1,
    ) -> None:
        """Draw one unfilled GDI rectangle."""
        pen = ctypes.windll.gdi32.CreatePen(
            win32con.PS_SOLID,
            Dpi.scale(width, self._dpi),
            self._color_ref(color),
        )
        previous_pen = ctypes.windll.gdi32.SelectObject(self._hdc, pen)
        null_brush = ctypes.windll.gdi32.GetStockObject(win32con.NULL_BRUSH)
        previous_brush = ctypes.windll.gdi32.SelectObject(self._hdc, null_brush)
        try:
            ctypes.windll.gdi32.Rectangle(
                self._hdc,
                Dpi.scale(bounds.x, self._dpi),
                Dpi.scale(bounds.y, self._dpi),
                Dpi.scale(bounds.x + bounds.width, self._dpi),
                Dpi.scale(bounds.y + bounds.height, self._dpi),
            )
        finally:
            ctypes.windll.gdi32.SelectObject(self._hdc, previous_brush)
            ctypes.windll.gdi32.SelectObject(self._hdc, previous_pen)
            ctypes.windll.gdi32.DeleteObject(pen)

    def fill_rectangle(
        self,
        bounds: Rect,
        *,
        color: ColorInput = "background",
    ) -> None:
        """Fill one GDI rectangle."""
        native_rect = wintypes.RECT(
            Dpi.scale(bounds.x, self._dpi),
            Dpi.scale(bounds.y, self._dpi),
            Dpi.scale(bounds.x + bounds.width, self._dpi),
            Dpi.scale(bounds.y + bounds.height, self._dpi),
        )
        brush = ctypes.windll.gdi32.CreateSolidBrush(self._color_ref(color))
        try:
            ctypes.windll.user32.FillRect(
                self._hdc,
                ctypes.byref(native_rect),
                brush,
            )
        finally:
            ctypes.windll.gdi32.DeleteObject(brush)

    def draw_text(
        self,
        text: str,
        x: int,
        y: int,
        *,
        color: ColorInput = "foreground",
    ) -> None:
        """Draw transparent GDI text."""
        previous_color = ctypes.windll.gdi32.SetTextColor(
            self._hdc,
            self._color_ref(color),
        )
        previous_mode = ctypes.windll.gdi32.SetBkMode(
            self._hdc,
            win32con.TRANSPARENT,
        )
        try:
            ctypes.windll.gdi32.TextOutW(
                self._hdc,
                Dpi.scale(x, self._dpi),
                Dpi.scale(y, self._dpi),
                text,
                len(text),
            )
        finally:
            ctypes.windll.gdi32.SetBkMode(self._hdc, previous_mode)
            ctypes.windll.gdi32.SetTextColor(self._hdc, previous_color)


class Win32PaintPeer(Win32Peer, PaintPeer):
    """Peer implementation for native GDI paint surfaces."""

    def __init__(
        self,
        backend: Win32Backend,
        component: Component,
        parent: ComponentPeer | None,
    ) -> None:
        """Create a child HWND that receives WM_PAINT."""
        super().__init__(
            backend,
            component,
            Win32CreateSpec(
                parent_peer=parent,
                class_name=_CLASS_NAME,
                style=win32con.WS_CHILD | win32con.WS_VISIBLE,
                text="",
            ),
        )

    def invalidate(self) -> None:
        """Invalidate the complete native surface."""
        invalidate_rect = cast(
            "Callable[[int, tuple[int, int, int, int], bool], None]",
            win32gui.InvalidateRect,
        )
        invalidate_rect(
            self.hwnd,
            win32gui.GetClientRect(self.hwnd),
            True,
        )

    def on_paint(self) -> bool:
        """Dispatch one scoped GDI paint event."""
        paint = _PAINTSTRUCT()
        hdc = int(ctypes.windll.user32.BeginPaint(self.hwnd, ctypes.byref(paint)))
        try:
            dpi = self.dpi
            clip = Rect(
                Dpi.unscale(paint.rcPaint.left, dpi),
                Dpi.unscale(paint.rcPaint.top, dpi),
                Dpi.unscale(paint.rcPaint.right - paint.rcPaint.left, dpi),
                Dpi.unscale(paint.rcPaint.bottom - paint.rcPaint.top, dpi),
            )
            cast("PaintSurface", self.component).dispatch_paint(
                Win32Graphics(hdc, dpi, self.backend.theme),
                clip,
            )
        finally:
            ctypes.windll.user32.EndPaint(self.hwnd, ctypes.byref(paint))
        return True


class Win32LabelPeer(Win32Peer):
    """Peer implementation for label components."""

    def __init__(
        self,
        backend: Win32Backend,
        component: Component,
        parent: ComponentPeer | None,
    ) -> None:
        """Initialize the instance."""
        super().__init__(
            backend,
            component,
            Win32CreateSpec(
                parent_peer=parent,
                class_name="STATIC",
                style=win32con.WS_CHILD | win32con.WS_VISIBLE,
            ),
        )


class Win32ImagePeer(Win32LabelPeer):
    """Peer implementation for image components."""

    def refresh(self) -> None:
        """Refresh native state from component state."""
        image = getattr(self.component, "image", None)
        if image is None:
            return
        native = render_bitmap(image, dpi=self.dpi, theme=self.backend.theme)
        self._replace_image(native)
        win32gui.SendMessage(
            self.hwnd,
            win32con.STM_SETIMAGE,
            win32con.IMAGE_BITMAP,
            native.handle,
        )


class Win32ButtonPeer(Win32Peer):
    """Peer implementation for button components."""

    def __init__(
        self,
        backend: Win32Backend,
        component: Component,
        parent: ComponentPeer | None,
    ) -> None:
        """Initialize the instance."""
        super().__init__(
            backend,
            component,
            Win32CreateSpec(
                parent_peer=parent,
                class_name="BUTTON",
                style=win32con.WS_CHILD
                | win32con.WS_VISIBLE
                | win32con.WS_TABSTOP
                | win32con.BS_PUSHBUTTON,
            ),
        )

    def on_command(self, notify: int) -> None:
        """Handle a native command notification."""
        if notify == win32con.BN_CLICKED:
            cast("Button", self.component).trigger_action()

    def refresh(self) -> None:
        """Refresh native state from component state."""
        image = getattr(self.component, "image", None)
        if image is None:
            return
        native = render_bitmap(image, dpi=self.dpi, theme=self.backend.theme)
        self._replace_image(native)
        win32gui.SendMessage(
            self.hwnd,
            win32con.BM_SETIMAGE,
            win32con.IMAGE_BITMAP,
            native.handle,
        )


class Win32CheckPeer(Win32ButtonPeer, BooleanPeer):
    """Peer implementation for check components."""

    def __init__(
        self,
        backend: Win32Backend,
        component: Component,
        parent: ComponentPeer | None,
    ) -> None:
        """Initialize the instance."""
        Win32Peer.__init__(
            self,
            backend,
            component,
            Win32CreateSpec(
                parent_peer=parent,
                class_name="BUTTON",
                style=win32con.WS_CHILD
                | win32con.WS_VISIBLE
                | win32con.WS_TABSTOP
                | win32con.BS_AUTOCHECKBOX,
            ),
        )

    @property
    def selected(self) -> bool:
        """Return the selected."""
        return bool(win32gui.SendMessage(self.hwnd, win32con.BM_GETCHECK, 0, 0))

    @selected.setter
    def selected(self, value: bool) -> None:
        """Set the selected."""
        state = win32con.BST_CHECKED if value else win32con.BST_UNCHECKED
        win32gui.SendMessage(self.hwnd, win32con.BM_SETCHECK, state, 0)

    def refresh(self) -> None:
        """Refresh native state from component state."""
        self.selected = cast("CheckBox", self.component).selected


class Win32RadioPeer(Win32CheckPeer):
    """Peer implementation for native auto-radio buttons."""

    def __init__(
        self,
        backend: Win32Backend,
        component: Component,
        parent: ComponentPeer | None,
    ) -> None:
        """Create a native radio button."""
        Win32Peer.__init__(
            self,
            backend,
            component,
            Win32CreateSpec(
                parent_peer=parent,
                class_name="BUTTON",
                style=win32con.WS_CHILD
                | win32con.WS_VISIBLE
                | win32con.WS_TABSTOP
                | win32con.BS_AUTORADIOBUTTON,
            ),
        )

    def on_command(self, notify: int) -> None:
        """Synchronize the portable group after a native click."""
        if notify == win32con.BN_CLICKED:
            component = cast("RadioButton", self.component)
            component.notify_selected()
            component.trigger_action()


class Win32GroupBoxPeer(Win32Peer):
    """Peer implementation for native labeled group boxes."""

    def __init__(
        self,
        backend: Win32Backend,
        component: Component,
        parent: ComponentPeer | None,
    ) -> None:
        """Create a native group-box container."""
        super().__init__(
            backend,
            component,
            Win32CreateSpec(
                parent_peer=parent,
                class_name="BUTTON",
                style=win32con.WS_CHILD
                | win32con.WS_VISIBLE
                | win32con.WS_CLIPCHILDREN
                | win32con.BS_GROUPBOX,
            ),
        )


class Win32EditPeer(Win32Peer):
    """Peer implementation for edit components."""

    def __init__(
        self,
        backend: Win32Backend,
        component: Component,
        parent: ComponentPeer | None,
        *,
        multiline: bool = False,
        password: bool = False,
    ) -> None:
        """Initialize the instance."""
        style = (
            win32con.WS_CHILD
            | win32con.WS_VISIBLE
            | win32con.WS_TABSTOP
            | win32con.WS_BORDER
        )
        if multiline:
            style |= (
                win32con.WS_VSCROLL | win32con.ES_MULTILINE | win32con.ES_AUTOVSCROLL
            )
        else:
            style |= win32con.ES_AUTOHSCROLL
        if password:
            style |= win32con.ES_PASSWORD
        super().__init__(
            backend,
            component,
            Win32CreateSpec(parent_peer=parent, class_name="EDIT", style=style),
        )


class Win32PasswordPeer(Win32EditPeer, PasswordPeer):
    """Native masked edit control."""

    def __init__(
        self,
        backend: Win32Backend,
        component: Component,
        parent: ComponentPeer | None,
    ) -> None:
        """Create a native password edit control."""
        super().__init__(backend, component, parent, password=True)

    def set_revealed(self, *, revealed: bool) -> None:
        """Toggle the native edit control's password character."""
        win32gui.SendMessage(
            self.hwnd,
            win32con.EM_SETPASSWORDCHAR,
            0 if revealed else 0x25CF,
            0,
        )
        erase = True
        _invalidate_rect(self.hwnd, None, erase)

    def refresh(self) -> None:
        """Synchronize text and reveal state."""
        super().refresh()
        control = cast("swingset_widgets.PasswordField", self.component)
        self.set_revealed(revealed=control.revealed)


class Win32RichTextPeer(Win32Peer, RichTextPeer):
    """Native RichEdit control with portable character formatting spans."""

    def __init__(
        self,
        backend: Win32Backend,
        component: Component,
        parent: ComponentPeer | None,
    ) -> None:
        """Load RichEdit and create a multiline native control."""
        self._base_font_face = "Segoe UI"
        self._base_font_size = 9
        ctypes.windll.kernel32.LoadLibraryW("Msftedit.dll")
        super().__init__(
            backend,
            component,
            Win32CreateSpec(
                parent_peer=parent,
                class_name="RICHEDIT50W",
                style=win32con.WS_CHILD
                | win32con.WS_VISIBLE
                | win32con.WS_TABSTOP
                | win32con.WS_BORDER
                | win32con.WS_VSCROLL
                | win32con.ES_MULTILINE
                | win32con.ES_AUTOVSCROLL,
            ),
        )

    def _color_ref(self, color: ColorInput | None) -> int:
        if color is None:
            return 0
        red, green, blue, _alpha = resolve_color(color, self.backend.theme)
        return red | (green << 8) | (blue << 16)

    def _format(self, style: swingset_widgets.RichTextStyle) -> _CHARFORMAT2W:
        mask = 0
        effects = 0
        if style.bold:
            mask |= _CFM_BOLD
            effects |= _CFM_BOLD
        if style.italic:
            mask |= _CFM_ITALIC
            effects |= _CFM_ITALIC
        if style.underline:
            mask |= _CFM_UNDERLINE
            effects |= _CFM_UNDERLINE
        if style.foreground is not None:
            mask |= _CFM_COLOR
        if style.background is not None:
            mask |= _CFM_BACKCOLOR
        if style.font_family is not None:
            mask |= _CFM_FACE
        if style.font_size is not None:
            mask |= _CFM_SIZE
        native_format = _CHARFORMAT2W(
            cbSize=ctypes.sizeof(_CHARFORMAT2W),
            dwMask=mask,
            dwEffects=effects,
            yHeight=0 if style.font_size is None else style.font_size * 20,
            crTextColor=self._color_ref(style.foreground),
            crBackColor=self._color_ref(style.background),
        )
        if style.font_family is not None:
            native_format.szFaceName = style.font_family[:31]
        return native_format

    def _default_format(self) -> _CHARFORMAT2W:
        native_format = _CHARFORMAT2W(
            cbSize=ctypes.sizeof(_CHARFORMAT2W),
            dwMask=_CFM_BOLD
            | _CFM_ITALIC
            | _CFM_UNDERLINE
            | _CFM_COLOR
            | _CFM_BACKCOLOR
            | _CFM_FACE
            | _CFM_SIZE,
            dwEffects=_CFE_AUTOCOLOR | _CFE_AUTOBACKCOLOR,
            yHeight=self._base_font_size * 20,
        )
        native_format.szFaceName = self._base_font_face[:31]
        return native_format

    def apply_styles(self) -> None:
        """Reset and apply all portable character-format spans."""
        control = cast("swingset_widgets.RichTextPane", self.component)
        selection = self.selection_range()
        win32gui.SendMessage(self.hwnd, win32con.EM_SETSEL, 0, -1)
        default = self._default_format()
        win32gui.SendMessage(
            self.hwnd,
            _EM_SETCHARFORMAT,
            _SCF_SELECTION,
            ctypes.addressof(default),
        )
        for span in control.styles:
            win32gui.SendMessage(self.hwnd, win32con.EM_SETSEL, span.start, span.end)
            native_format = self._format(span.style)
            win32gui.SendMessage(
                self.hwnd,
                _EM_SETCHARFORMAT,
                _SCF_SELECTION,
                ctypes.addressof(native_format),
            )
        self.set_selection_range(*selection)

    def selection_range(self) -> tuple[int, int]:
        """Return the native RichEdit selection as character offsets."""
        start = ctypes.c_int()
        end = ctypes.c_int()
        ctypes.windll.user32.SendMessageW(
            self.hwnd,
            win32con.EM_GETSEL,
            ctypes.byref(start),
            ctypes.byref(end),
        )
        return start.value, end.value

    def set_selection_range(self, start: int, end: int) -> None:
        """Select native RichEdit text from portable character offsets."""
        win32gui.SendMessage(self.hwnd, win32con.EM_SETSEL, start, end)

    def set_font(self, face: str, size: int, *, bold: bool) -> None:
        """Apply face and point size to existing RichEdit characters."""
        self._base_font_face = face
        self._base_font_size = size
        super().set_font(face, size, bold=bold)
        selection = self.selection_range()
        win32gui.SendMessage(self.hwnd, win32con.EM_SETSEL, 0, -1)
        native_format = _CHARFORMAT2W(
            cbSize=ctypes.sizeof(_CHARFORMAT2W),
            dwMask=_CFM_FACE | _CFM_SIZE,
            yHeight=size * 20,
        )
        native_format.szFaceName = face[:31]
        win32gui.SendMessage(
            self.hwnd,
            _EM_SETCHARFORMAT,
            _SCF_SELECTION,
            ctypes.addressof(native_format),
        )
        self.set_selection_range(*selection)

    def refresh(self) -> None:
        """Synchronize text, editability, and rich formatting."""
        super().refresh()
        control = cast("swingset_widgets.RichTextPane", self.component)
        win32gui.SendMessage(
            self.hwnd,
            win32con.EM_SETREADONLY,
            not control.editable,
            0,
        )
        self.apply_styles()
        self.set_selection_range(*control.initial_selection_range())


class Win32SeparatorPeer(Win32Peer):
    """Native etched static separator."""

    def __init__(
        self,
        backend: Win32Backend,
        component: Component,
        parent: ComponentPeer | None,
    ) -> None:
        """Create an etched static control in the requested orientation."""
        control = cast("swingset_widgets.Separator", component)
        etched_style = (
            0x0010
            if control.orientation is swingset_widgets.SeparatorOrientation.HORIZONTAL
            else 0x0011
        )
        super().__init__(
            backend,
            component,
            Win32CreateSpec(
                parent_peer=parent,
                class_name="STATIC",
                style=win32con.WS_CHILD | win32con.WS_VISIBLE | etched_style,
                text="",
            ),
        )


class Win32SpinnerPeer(Win32EditPeer, IntValuePeer):
    """Numeric edit control with an attached native up-down control."""

    _UPDOWN_WIDTH = 18

    def __init__(
        self,
        backend: Win32Backend,
        component: Component,
        parent: ComponentPeer | None,
    ) -> None:
        """Create an edit buddy and attached common-controls up-down."""
        super().__init__(backend, component, parent)
        parent_hwnd = parent.hwnd if isinstance(parent, Win32Peer) else 0
        self.updown_hwnd = int(
            win32gui.CreateWindowEx(
                0,
                "msctls_updown32",
                "",
                win32con.WS_CHILD
                | win32con.WS_VISIBLE
                | win32con.WS_TABSTOP
                | 0x0002
                | 0x0020,
                0,
                0,
                0,
                0,
                parent_hwnd,
                next(_ids),
                win32api.GetModuleHandle(None),
                None,
            )
        )
        backend.register_auxiliary(self.updown_hwnd, self)
        win32gui.SendMessage(
            self.updown_hwnd,
            win32con.WM_USER + 105,
            self.hwnd,
            0,
        )

    def set_bounds(self, bounds: Rect) -> None:
        """Move the edit buddy and its up-down control as one component."""
        updown_width = min(self._UPDOWN_WIDTH, bounds.width)
        edit_width = max(0, bounds.width - updown_width)
        super().set_bounds(
            Rect(bounds.x, bounds.y, edit_width, bounds.height),
        )
        dpi = self.dpi
        repaint = True
        with contextlib.suppress(win32gui.error):
            win32gui.MoveWindow(
                self.updown_hwnd,
                Dpi.scale(bounds.x + edit_width, dpi),
                Dpi.scale(bounds.y, dpi),
                Dpi.scale(updown_width, dpi),
                Dpi.scale(bounds.height, dpi),
                repaint,
            )

    def set_visible(self, *, visible: bool) -> None:
        """Show or hide both native spinner windows."""
        super().set_visible(visible=visible)
        with contextlib.suppress(win32gui.error):
            win32gui.ShowWindow(
                self.updown_hwnd,
                win32con.SW_SHOW if visible else win32con.SW_HIDE,
            )

    def set_enabled(self, *, enabled: bool) -> None:
        """Enable or disable both native spinner windows."""
        super().set_enabled(enabled=enabled)
        with contextlib.suppress(win32gui.error):
            win32gui.EnableWindow(self.updown_hwnd, enabled)

    @property
    def value(self) -> int:
        """Return the native spinner value."""
        return win32gui.SendMessage(self.updown_hwnd, _UDM_GETPOS32, 0, 0)

    @value.setter
    def value(self, value: int) -> None:
        """Set the native spinner value."""
        win32gui.SendMessage(self.updown_hwnd, _UDM_SETPOS32, 0, value)

    def on_notify(self, code: int, source_hwnd: int) -> None:
        """Publish changes after the up-down control updates its buddy."""
        if source_hwnd == self.updown_hwnd and code == _UDN_DELTAPOS:
            control = cast("swingset_widgets.Spinner", self.component)
            self.backend.call_soon(lambda: control.notify_value_changed(self.value))

    def refresh(self) -> None:
        """Synchronize range, step-independent native position, and text."""
        control = cast("swingset_widgets.Spinner", self.component)
        super().refresh()
        win32gui.SendMessage(
            self.updown_hwnd,
            _UDM_SETRANGE32,
            control.minimum,
            control.maximum,
        )
        self.value = control.initial_value()

    def destroy(self) -> None:
        """Destroy the auxiliary up-down before its edit buddy."""
        self.backend.unregister_hwnd(self.updown_hwnd)
        with contextlib.suppress(win32gui.error):
            win32gui.DestroyWindow(self.updown_hwnd)
        super().destroy()


class Win32ComboPeer(Win32Peer, SelectionPeer):
    """Peer implementation for combo components."""

    def __init__(
        self,
        backend: Win32Backend,
        component: Component,
        parent: ComponentPeer | None,
    ) -> None:
        """Initialize the instance."""
        style = (
            win32con.WS_CHILD
            | win32con.WS_VISIBLE
            | win32con.WS_TABSTOP
            | win32con.WS_VSCROLL
            | 0x0003
        )
        super().__init__(
            backend,
            component,
            Win32CreateSpec(parent_peer=parent, class_name="COMBOBOX", style=style),
        )

    @property
    def selected_index(self) -> int:
        """Return the selected index."""
        return win32gui.SendMessage(self.hwnd, CB_GETCURSEL, 0, 0)

    @selected_index.setter
    def selected_index(self, index: int) -> None:
        """Set the selected index."""
        win32gui.SendMessage(self.hwnd, CB_SETCURSEL, index, 0)

    def on_command(self, notify: int) -> None:
        """Handle a native command notification."""
        if notify == CBN_SELCHANGE:
            cast("ComboBox[object]", self.component).notify_selection(
                self.selected_index,
            )

    def refresh(self) -> None:
        """Refresh native state from component state."""
        component = cast("ComboBox[object]", self.component)
        win32gui.SendMessage(self.hwnd, CB_RESETCONTENT, 0, 0)
        for item in component.model:
            _send_text_message(self.hwnd, CB_ADDSTRING, 0, str(item))
        self.selected_index = component.model.selected_index

    def on_model_event(self, event: ModelEvent) -> None:
        """Handle a model event update."""
        del event
        self.refresh()


class Win32ListPeer(Win32Peer, SelectionPeer):
    """Peer implementation for list components."""

    def __init__(
        self,
        backend: Win32Backend,
        component: Component,
        parent: ComponentPeer | None,
    ) -> None:
        """Initialize the instance."""
        style = (
            win32con.WS_CHILD
            | win32con.WS_VISIBLE
            | win32con.WS_TABSTOP
            | win32con.WS_BORDER
            | win32con.WS_VSCROLL
            | 0x0001
        )
        super().__init__(
            backend,
            component,
            Win32CreateSpec(parent_peer=parent, class_name="LISTBOX", style=style),
        )

    @property
    def selected_index(self) -> int:
        """Return the selected index."""
        return win32gui.SendMessage(self.hwnd, LB_GETCURSEL, 0, 0)

    @selected_index.setter
    def selected_index(self, index: int) -> None:
        """Set the selected index."""
        win32gui.SendMessage(self.hwnd, LB_SETCURSEL, index, 0)

    def on_command(self, notify: int) -> None:
        """Handle a native command notification."""
        if notify == LBN_SELCHANGE:
            cast("ListBox[object]", self.component).notify_selection(
                self.selected_index,
            )

    def refresh(self) -> None:
        """Refresh native state from component state."""
        component = cast("ListBox[object]", self.component)
        win32gui.SendMessage(self.hwnd, LB_RESETCONTENT, 0, 0)
        for item in component.model:
            _send_text_message(self.hwnd, LB_ADDSTRING, 0, str(item))
        initial_index = component.initial_selected_index()
        if initial_index >= 0:
            self.selected_index = initial_index

    def on_model_event(self, event: ModelEvent) -> None:
        """Handle a model event update."""
        del event
        self.refresh()


class Win32TablePeer(Win32Peer):
    """Peer implementation for table components."""

    def __init__(
        self,
        backend: Win32Backend,
        component: Component,
        parent: ComponentPeer | None,
    ) -> None:
        """Initialize the instance."""
        style = (
            win32con.WS_CHILD
            | win32con.WS_VISIBLE
            | win32con.WS_TABSTOP
            | win32con.WS_BORDER
            | LVS_REPORT
            | LVS_SHOWSELALWAYS
        )
        super().__init__(
            backend,
            component,
            Win32CreateSpec(
                parent_peer=parent, class_name="SysListView32", style=style
            ),
        )

    def refresh(self) -> None:
        """Refresh native state from component state."""
        component = cast("Table", self.component)
        win32gui.SendMessage(
            self.hwnd,
            LVM_SETEXTENDEDLISTVIEWSTYLE,
            LVS_EX_FULLROWSELECT,
            LVS_EX_FULLROWSELECT,
        )
        while win32gui.SendMessage(self.hwnd, LVM_DELETECOLUMN, 0, 0):
            pass
        for index, name in enumerate(component.model.columns):
            packed, _extra = win32gui_struct.PackLVCOLUMN(
                fmt=0x0001 | 0x0002 | 0x0004,
                cx=120,
                text=name,
                subItem=index,
            )
            win32gui.SendMessage(self.hwnd, LVM_INSERTCOLUMN, index, packed)
        win32gui.SendMessage(self.hwnd, LVM_DELETEALLITEMS, 0, 0)
        for row_index, row in enumerate(component.model.rows):
            first = str(row[0]) if row else ""
            packed, _extra = win32gui_struct.PackLVITEM(
                item=row_index,
                subItem=0,
                text=first,
            )
            win32gui.SendMessage(self.hwnd, LVM_INSERTITEM, 0, packed)
            for column_index, value in enumerate(row[1:], 1):
                packed, _extra = win32gui_struct.PackLVITEM(
                    item=row_index,
                    subItem=column_index,
                    text=str(value),
                )
                win32gui.SendMessage(self.hwnd, LVM_SETITEMTEXT, row_index, packed)

    def on_model_event(self, event: ModelEvent) -> None:
        """Handle a model event update."""
        del event
        self.refresh()


class Win32ProgressPeer(Win32Peer, IntValuePeer):
    """Peer implementation for progress components."""

    def __init__(
        self,
        backend: Win32Backend,
        component: Component,
        parent: ComponentPeer | None,
    ) -> None:
        """Initialize the instance."""
        super().__init__(
            backend,
            component,
            Win32CreateSpec(
                parent_peer=parent,
                class_name="msctls_progress32",
                style=win32con.WS_CHILD | win32con.WS_VISIBLE,
            ),
        )

    @property
    def value(self) -> int:
        """Return the value."""
        return cast("ProgressBar", self.component).initial_value()

    @value.setter
    def value(self, value: int) -> None:
        """Set the value."""
        win32gui.SendMessage(self.hwnd, PBM_SETPOS, value, 0)

    def refresh(self) -> None:
        """Refresh native state from component state."""
        control = cast("ProgressBar", self.component)
        win32gui.SendMessage(
            self.hwnd,
            PBM_SETRANGE32,
            control.minimum,
            control.maximum,
        )
        self.value = control.initial_value()


class Win32SliderPeer(Win32Peer, IntValuePeer):
    """Peer implementation for slider components."""

    def __init__(
        self,
        backend: Win32Backend,
        component: Component,
        parent: ComponentPeer | None,
    ) -> None:
        """Initialize the instance."""
        style = win32con.WS_CHILD | win32con.WS_VISIBLE | win32con.WS_TABSTOP
        super().__init__(
            backend,
            component,
            Win32CreateSpec(
                parent_peer=parent,
                class_name="msctls_trackbar32",
                style=style,
            ),
        )

    @property
    def value(self) -> int:
        """Return the value."""
        return win32gui.SendMessage(self.hwnd, TBM_GETPOS, 0, 0)

    @value.setter
    def value(self, value: int) -> None:
        """Set the value."""
        win32gui.SendMessage(self.hwnd, TBM_SETPOS, 1, value)

    def on_scroll(self) -> None:
        """Handle scroll events."""
        cast("Slider", self.component).notify_value_changed(self.value)

    def refresh(self) -> None:
        """Refresh native state from component state."""
        control = cast("Slider", self.component)
        win32gui.SendMessage(self.hwnd, TBM_SETRANGEMIN, 1, control.minimum)
        win32gui.SendMessage(self.hwnd, TBM_SETRANGEMAX, 1, control.maximum)
        self.value = control.initial_value()


class Win32StatusPeer(Win32LabelPeer):
    """Peer implementation for status components."""

    def __init__(
        self,
        backend: Win32Backend,
        component: Component,
        parent: ComponentPeer | None,
    ) -> None:
        """Initialize the instance."""
        Win32Peer.__init__(
            self,
            backend,
            component,
            Win32CreateSpec(
                parent_peer=parent,
                class_name="msctls_statusbar32",
                style=win32con.WS_CHILD | win32con.WS_VISIBLE,
            ),
        )

    @Win32Peer.text.setter
    def text(self, value: str) -> None:
        """Set the text."""
        _send_text_message(self.hwnd, SB_SETTEXTW, 0, value)


class Win32TreePeer(Win32Peer):
    """Peer implementation for tree components."""

    def __init__(
        self,
        backend: Win32Backend,
        component: Component,
        parent: ComponentPeer | None,
    ) -> None:
        """Initialize the instance."""
        style = (
            win32con.WS_CHILD
            | win32con.WS_VISIBLE
            | win32con.WS_TABSTOP
            | win32con.WS_BORDER
            | 0x0001
            | 0x0002
        )
        super().__init__(
            backend,
            component,
            Win32CreateSpec(
                parent_peer=parent, class_name="SysTreeView32", style=style
            ),
        )

    def _insert(self, node: TreeNode, parent: int) -> None:
        buffer = ctypes.create_unicode_buffer(node.text)
        item = TVITEMW(
            TVIF_TEXT,
            0,
            0,
            0,
            ctypes.cast(buffer, wintypes.LPWSTR),
            len(node.text),
            0,
            0,
            len(node.children),
            0,
        )
        structure = TVINSERTSTRUCTW(parent, TVI_LAST, item)
        handle = int(
            ctypes.windll.user32.SendMessageW(
                self.hwnd,
                TVM_INSERTITEMW,
                0,
                ctypes.byref(structure),
            ),
        )
        for child in node.children:
            self._insert(child, handle)

    def refresh(self) -> None:
        """Refresh native state from component state."""
        component = cast("TreeView", self.component)
        ctypes.windll.user32.SendMessageW(self.hwnd, TVM_DELETEITEM, 0, TVI_ROOT)
        for root in component.roots:
            self._insert(root, TVI_ROOT)


class Win32TabPeer(Win32PanelPeer, SelectionPeer):
    """Peer implementation for tab components."""

    def __init__(
        self,
        backend: Win32Backend,
        component: Component,
        parent: ComponentPeer | None,
    ) -> None:
        """Initialize the instance."""
        super().__init__(backend, component, parent)
        module = win32api.GetModuleHandle(None)
        self.tab_hwnd = int(
            win32gui.CreateWindowEx(
                0,
                "SysTabControl32",
                "",
                win32con.WS_CHILD | win32con.WS_VISIBLE | win32con.WS_TABSTOP,
                0,
                0,
                component.width,
                component.height,
                self.hwnd,
                next(_ids),
                module,
                None,
            ),
        )
        backend.register_auxiliary(self.tab_hwnd, self)

    @property
    def selected_index(self) -> int:
        """Return the selected index."""
        return win32gui.SendMessage(self.tab_hwnd, TCM_GETCURSEL, 0, 0)

    def _layout_children(self) -> None:
        component = cast("TabbedPane", self.component)
        size = self.client_size()
        repaint = True
        try:
            win32gui.MoveWindow(
                self.tab_hwnd,
                0,
                0,
                Dpi.scale(size.width, self.dpi),
                Dpi.scale(size.height, self.dpi),
                repaint,
            )
        except win32gui.error:
            return
        content = wintypes.RECT(
            0,
            0,
            Dpi.scale(size.width, self.dpi),
            Dpi.scale(size.height, self.dpi),
        )
        ctypes.windll.user32.SendMessageW(
            self.tab_hwnd,
            TCM_ADJUSTRECT,
            0,
            ctypes.byref(content),
        )
        left = Dpi.unscale(content.left, self.dpi)
        top = Dpi.unscale(content.top, self.dpi)
        width = Dpi.unscale(content.right - content.left, self.dpi)
        height = Dpi.unscale(content.bottom - content.top, self.dpi)
        for index, (_title, child) in enumerate(component.tabs):
            child.set_bounds(left, top, max(0, width), max(0, height))
            child.visible = index == component.initial_selected_index()

    @selected_index.setter
    def selected_index(self, index: int) -> None:
        """Set the selected index."""
        win32gui.SendMessage(self.tab_hwnd, TCM_SETCURSEL, index, 0)
        cast("TabbedPane", self.component).sync_selected_index_from_peer(index)
        self._layout_children()

    def refresh(self) -> None:
        """Refresh native state from component state."""
        component = cast("TabbedPane", self.component)
        with contextlib.suppress(win32gui.error):
            win32gui.DestroyWindow(self.tab_hwnd)
        module = win32api.GetModuleHandle(None)
        size = self.client_size()
        self.tab_hwnd = int(
            win32gui.CreateWindowEx(
                0,
                "SysTabControl32",
                "",
                win32con.WS_CHILD | win32con.WS_VISIBLE | win32con.WS_TABSTOP,
                0,
                0,
                Dpi.scale(size.width, self.dpi),
                Dpi.scale(size.height, self.dpi),
                self.hwnd,
                next(_ids),
                module,
                None,
            ),
        )
        self.backend.register_auxiliary(self.tab_hwnd, self)
        for index, (title, _child) in enumerate(component.tabs):
            _insert_tab(self.tab_hwnd, index, title)
        if component.tabs:
            self.selected_index = min(
                component.initial_selected_index(),
                len(component.tabs) - 1,
            )
        self._layout_children()

    def set_bounds(self, bounds: Rect) -> None:
        """Set bounds."""
        super().set_bounds(bounds)
        self._layout_children()

    def on_notify(self, code: int, source_hwnd: int) -> None:
        """Handle a native notification message."""
        if source_hwnd == self.tab_hwnd and code == TCN_SELCHANGE:
            cast("TabbedPane", self.component).sync_selected_index_from_peer(
                self.selected_index,
            )
            self._layout_children()


class Win32Backend(Backend):
    """Native Win32 event loop plus a registry of strongly typed peers."""

    name = "win32"
    capabilities = frozenset(
        {
            Capability.DARK_MODE,
            Capability.NATIVE_DARK_MODE,
            Capability.SVG,
            Capability.WINDOW_ICON,
            Capability.MENUS,
            Capability.TABLE,
            Capability.TREE,
            Capability.TABS,
            Capability.COLORED_TAB_PAGES,
            Capability.SCROLL_PANE,
            Capability.TOOLBAR,
            Capability.STATUS_BAR,
            Capability.DPI_AWARE,
            Capability.CLASSIC_THEME,
            Capability.MESSAGE_DIALOGS,
            Capability.FILE_DIALOGS,
            Capability.NATIVE_COMMON_DIALOGS,
            Capability.CUSTOM_PAINT,
            Capability.RICH_TEXT,
            Capability.TOOLTIPS,
        },
    )

    def __init__(self) -> None:
        """Initialize the instance."""
        super().__init__()
        self._registered = False
        self._queue: queue.Queue[Callable[[], object]] = queue.Queue()
        self._dispatch_hwnd: int | None = None
        self._dispatch_message = win32con.WM_APP + 41
        self._peers: dict[int, Win32Peer] = {}
        self._auxiliary: dict[int, Win32Peer] = {}
        self._old_procs: dict[int, int] = {}
        self._subclass_procs: dict[int, object] = {}
        self._menu_commands: dict[int, dict[int, Callable[[], object]]] = {}
        self._background_brushes: dict[int, int] = {}
        self._windows = 0
        self.theme = Theme.SYSTEM

    def _factory(
        self,
        peer_type: type[Win32Peer],
    ) -> Callable[[Component, ComponentPeer | None], ComponentPeer]:
        constructor = cast(
            "Callable[[Win32Backend, Component, ComponentPeer | None], ComponentPeer]",
            peer_type,
        )

        def create(component: Component, parent: ComponentPeer | None) -> ComponentPeer:
            self.initialize()
            return constructor(self, component, parent)

        return create

    def _edit_factory(
        self,
        *,
        multiline: bool,
    ) -> Callable[[Component, ComponentPeer | None], ComponentPeer]:
        def create(component: Component, parent: ComponentPeer | None) -> ComponentPeer:
            self.initialize()
            return Win32EditPeer(self, component, parent, multiline=multiline)

        return create

    def install_factories(self) -> None:
        """Update install factories."""
        self.register_peer(swingset_core.Window, self._factory(Win32WindowPeer))
        self.register_peer(swingset_drawing.PaintSurface, self._factory(Win32PaintPeer))
        self.register_peer(swingset_widgets.TabbedPane, self._factory(Win32TabPeer))
        self.register_peer(swingset_widgets.SplitPane, self._factory(Win32PanelPeer))
        self.register_peer(
            swingset_widgets.ScrollPane,
            self._factory(Win32ScrollPeer),
        )
        self.register_peer(swingset_widgets.ToolBar, self._factory(Win32PanelPeer))
        self.register_peer(swingset_widgets.GroupBox, self._factory(Win32GroupBoxPeer))
        self.register_peer(swingset_widgets.Panel, self._factory(Win32PanelPeer))
        self.register_peer(swingset_core.Container, self._factory(Win32PanelPeer))
        self.register_peer(swingset_widgets.RadioButton, self._factory(Win32RadioPeer))
        self.register_peer(swingset_widgets.CheckBox, self._factory(Win32CheckPeer))
        self.register_peer(swingset_widgets.Button, self._factory(Win32ButtonPeer))
        self.register_peer(swingset_widgets.ImageLabel, self._factory(Win32ImagePeer))
        self.register_peer(swingset_widgets.StatusBar, self._factory(Win32StatusPeer))
        self.register_peer(swingset_widgets.Label, self._factory(Win32LabelPeer))
        self.register_peer(
            swingset_widgets.PasswordField,
            self._factory(Win32PasswordPeer),
        )
        self.register_peer(
            swingset_widgets.RichTextPane,
            self._factory(Win32RichTextPeer),
        )
        self.register_peer(
            swingset_widgets.Separator,
            self._factory(Win32SeparatorPeer),
        )
        self.register_peer(
            swingset_widgets.TextArea, self._edit_factory(multiline=True)
        )
        self.register_peer(
            swingset_widgets.TextField, self._edit_factory(multiline=False)
        )
        self.register_peer(swingset_widgets.ComboBox, self._factory(Win32ComboPeer))
        self.register_peer(swingset_widgets.ListBox, self._factory(Win32ListPeer))
        self.register_peer(swingset_widgets.Table, self._factory(Win32TablePeer))
        self.register_peer(swingset_widgets.TreeView, self._factory(Win32TreePeer))
        self.register_peer(
            swingset_widgets.ProgressBar, self._factory(Win32ProgressPeer)
        )
        self.register_peer(swingset_widgets.Slider, self._factory(Win32SliderPeer))
        self.register_peer(
            swingset_widgets.Spinner,
            self._factory(Win32SpinnerPeer),
        )

    def _drain(self) -> None:
        while True:
            try:
                callback = self._queue.get_nowait()
            except queue.Empty:
                self._emit_idle()
                return
            callback()

    @staticmethod
    def _loword(value: int) -> int:
        return value & _WORD_MASK_16

    @staticmethod
    def _hiword(value: int) -> int:
        return (value >> 16) & _WORD_MASK_16

    @staticmethod
    def _default_wndproc(hwnd: int, message: int, wparam: int, lparam: int) -> int:
        return win32gui.DefWindowProc(hwnd, message, wparam, lparam)

    def _theme_color_ref(self, name: ColorInput) -> int:
        red, green, blue, _alpha = resolve_color(name, self.theme)
        return red | (green << 8) | (blue << 16)

    def _theme_background_brush(self, color_name: ColorInput = "background") -> int:
        color = self._theme_color_ref(color_name)
        brush = self._background_brushes.get(color)
        if brush is None:
            brush = int(ctypes.windll.gdi32.CreateSolidBrush(color))
            self._background_brushes[color] = brush
        return brush

    @staticmethod
    def _page_background(component: Component) -> ColorInput:
        current: Component | None = component
        while current is not None:
            if current.background is not None:
                return current.background
            parent = current.parent
            if isinstance(parent, TabbedPane):
                return parent.page_background(current) or "background"
            current = parent
        return "background"

    def _handle_control_color(
        self,
        message: int,
        hdc: int,
        component: Component,
    ) -> int | None:
        if message not in _CONTROL_COLOR_MESSAGES:
            return None
        background = self._page_background(component)
        foreground = component.foreground or "foreground"
        ctypes.windll.gdi32.SetTextColor(
            hdc,
            self._theme_color_ref(foreground),
        )
        ctypes.windll.gdi32.SetBkColor(
            hdc,
            self._theme_color_ref(background),
        )
        return self._theme_background_brush(background)

    def _erase_background(self, peer: Win32Peer, hdc: int) -> None:
        left, top, right, bottom = win32gui.GetClientRect(peer.hwnd)
        native_rect = wintypes.RECT(left, top, right, bottom)
        ctypes.windll.user32.FillRect(
            hdc,
            ctypes.byref(native_rect),
            self._theme_background_brush(self._page_background(peer.component)),
        )

    def _handle_size_message(self, peer: Win32Peer, message: int) -> bool:
        if message != win32con.WM_SIZE:
            return False
        if isinstance(peer.component, swingset_core.Container):
            peer.component.handle_native_resize()
        if isinstance(peer, Win32ScrollPeer):
            peer.refresh()
        return True

    def _handle_command_message(self, hwnd: int, wparam: int, lparam: int) -> bool:
        command_id = self._loword(wparam)
        notify = self._hiword(wparam)
        if lparam:
            child = self._peers.get(lparam)
            if child is not None:
                child.on_command(notify)
                return True
        callback = self._menu_commands.get(hwnd, {}).get(command_id)
        if callback is None:
            return False
        callback()
        return True

    def _handle_notify_message(self, lparam: int) -> bool:
        if not lparam:
            return False
        header = ctypes.cast(lparam, ctypes.POINTER(NMHDR)).contents
        source = int(header.hwndFrom)
        target = self._auxiliary.get(source)
        if target is None:
            return False
        target.on_notify(int(header.code), source)
        return True

    def _handle_scroll_message(
        self,
        peer: Win32Peer,
        message: int,
        wparam: int,
        lparam: int,
    ) -> bool:
        if not lparam:
            peer.on_scroll_message(message, self._loword(wparam), self._hiword(wparam))
            return isinstance(peer, Win32ScrollPeer)
        child = self._peers.get(lparam)
        if child is None:
            return False
        child.on_scroll()
        return True

    @staticmethod
    def _handle_close_message(peer: Win32Peer) -> None:
        close = getattr(peer.component, "_request_close", None)
        if callable(close):
            close()
            return
        peer.component.destroy()

    def _wndproc(self, hwnd: int, message: int, wparam: int, lparam: int) -> int:
        if hwnd == self._dispatch_hwnd and message == self._dispatch_message:
            self._drain()
            return 0
        peer = self._peers.get(hwnd)
        if peer is None:
            return self._default_wndproc(hwnd, message, wparam, lparam)

        control_brush = self._handle_control_color(message, wparam, peer.component)
        if control_brush is not None:
            return control_brush
        if message == win32con.WM_ERASEBKGND:
            self._erase_background(peer, wparam)
            return 1

        handled = message == win32con.WM_PAINT and peer.on_paint()
        handled = handled or self._handle_size_message(peer, message)
        handled = handled or (
            message == win32con.WM_COMMAND
            and self._handle_command_message(hwnd, wparam, lparam)
        )
        handled = handled or (
            message == win32con.WM_NOTIFY and self._handle_notify_message(lparam)
        )
        handled = handled or (
            message in {win32con.WM_HSCROLL, win32con.WM_VSCROLL}
            and self._handle_scroll_message(peer, message, wparam, lparam)
        )
        if message == _WM_DPICHANGED:
            peer.component.handle_dpi_changed()
        if message == win32con.WM_CLOSE:
            self._handle_close_message(peer)
            handled = True
        if handled:
            return 0
        return self._default_wndproc(hwnd, message, wparam, lparam)

    def initialize(self) -> None:
        """Initialize backend resources."""
        if self._registered:
            return
        Win32Dpi.enable()
        module = win32api.GetModuleHandle(None)
        native_window_class = win32gui.WNDCLASS()
        window_class = cast("_WindowClass", native_window_class)
        window_class.hInstance = module
        window_class.lpszClassName = _CLASS_NAME
        window_class.lpfnWndProc = self._wndproc
        window_class.hCursor = win32gui.LoadCursor(0, win32con.IDC_ARROW)
        window_class.hbrBackground = win32con.COLOR_WINDOW + 1
        try:
            win32gui.RegisterClass(native_window_class)
        except win32gui.error as exc:
            if getattr(exc, "winerror", None) != _ERROR_CLASS_ALREADY_EXISTS:
                raise
        self._registered = True
        self._dispatch_hwnd = int(
            win32gui.CreateWindowEx(
                0,
                _CLASS_NAME,
                "",
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                module,
                None,
            ),
        )

    def run(self, startup: Callable[[], object] | None = None) -> None:
        """Run the backend event loop."""
        self.initialize()
        if startup is not None:
            self.call_soon(startup)
        self._drain()
        win32gui.PumpMessages()

    def call_soon(self, callback: Callable[[], object]) -> None:
        """Schedule a callback on the UI thread."""
        self._queue.put(callback)
        if self._dispatch_hwnd is not None:
            win32gui.PostMessage(self._dispatch_hwnd, self._dispatch_message, 0, 0)

    @staticmethod
    def _owner_hwnd(owner: object | None) -> int:
        return owner if isinstance(owner, int) else 0

    def show_message(
        self,
        owner: object | None,
        title: str,
        message: str,
        buttons: str,
        icon: str,
    ) -> str:
        """Show a native Win32 message box."""
        button_flags = {
            "ok": win32con.MB_OK,
            "ok_cancel": win32con.MB_OKCANCEL,
            "yes_no": win32con.MB_YESNO,
            "yes_no_cancel": win32con.MB_YESNOCANCEL,
        }
        icon_flags = {
            "none": 0,
            "information": win32con.MB_ICONINFORMATION,
            "warning": win32con.MB_ICONWARNING,
            "error": win32con.MB_ICONERROR,
            "question": win32con.MB_ICONQUESTION,
        }
        result = win32gui.MessageBox(
            self._owner_hwnd(owner),
            message,
            title,
            button_flags[buttons] | icon_flags[icon],
        )
        return {
            win32con.IDOK: "ok",
            win32con.IDCANCEL: "cancel",
            win32con.IDYES: "yes",
            win32con.IDNO: "no",
        }[result]

    def choose_file(
        self,
        owner: object | None,
        title: str,
        filters: tuple[tuple[str, str], ...],
        initial_directory: str | None,
        *,
        save: bool,
    ) -> str | None:
        """Show a native Win32 open/save common dialog."""
        filter_text = "|".join(
            part
            for name, pattern in (filters or (("All files", "*.*"),))
            for part in (f"{name} ({pattern})", pattern)
        )
        flags = win32con.OFN_HIDEREADONLY | win32con.OFN_PATHMUSTEXIST
        flags |= win32con.OFN_OVERWRITEPROMPT if save else win32con.OFN_FILEMUSTEXIST
        parent = (
            None
            if not isinstance(owner, int)
            else win32ui.CreateWindowFromHandle(owner)
        )
        create_dialog = cast(
            "Callable[[int, str | None, str | None, int, str, object | None], object]",
            win32ui.CreateFileDialog,
        )
        dialog = cast(
            "_NativeFileDialog",
            create_dialog(
                0 if save else 1,
                None,
                None,
                flags,
                f"{filter_text}||",
                parent,
            ),
        )
        dialog.SetOFNTitle(title)
        if initial_directory is not None:
            dialog.SetOFNInitialDir(initial_directory)
        if dialog.DoModal() != win32con.IDOK:
            return None
        return dialog.GetPathName()

    def choose_folder(self, owner: object | None, title: str) -> str | None:
        """Show a native Win32 shell folder browser."""
        """Show the modern Windows file dialog configured for folder selection."""
        return _modern_folder_dialog(self._owner_hwnd(owner), title)

    @staticmethod
    def _dialog_parent(owner: object | None) -> object | None:
        if not isinstance(owner, int):
            return None
        return win32ui.CreateWindowFromHandle(owner)

    def choose_color(
        self,
        owner: object | None,
        initial: tuple[int, int, int],
    ) -> tuple[int, int, int] | None:
        """Show the Win32 color common dialog."""
        red, green, blue = initial
        color_ref = red | (green << 8) | (blue << 16)
        create_dialog = cast(
            "Callable[[int, int, object | None], object]",
            win32ui.CreateColorDialog,
        )
        dialog = cast(
            "_NativeColorDialog",
            create_dialog(color_ref, 0, self._dialog_parent(owner)),
        )
        if dialog.DoModal() != win32con.IDOK:
            return None
        selected = dialog.GetColor()
        return selected & 0xFF, (selected >> 8) & 0xFF, (selected >> 16) & 0xFF

    def choose_font(
        self,
        owner: object | None,
        initial: tuple[str, int, bool, bool],
    ) -> tuple[str, int, bool, bool] | None:
        """Show the Win32 font common dialog."""
        face, size, bold, italic = initial
        log_font: dict[str, object] = {
            "height": -(size * Dpi.BASE // 72),
            "weight": _FW_BOLD if bold else 400,
            "italic": italic,
            "name": face,
        }
        create_dialog = cast(
            "Callable[[dict[str, object], int, object | None, object | None], object]",
            win32ui.CreateFontDialog,
        )
        dialog = cast(
            "_NativeFontDialog",
            create_dialog(
                log_font,
                win32con.CF_EFFECTS | win32con.CF_SCREENFONTS,
                None,
                self._dialog_parent(owner),
            ),
        )
        if dialog.DoModal() != win32con.IDOK:
            return None
        current = dialog.GetCurrentFont()
        return (
            dialog.GetFaceName(),
            max(1, dialog.GetSize() // 10),
            dialog.GetWeight() >= _FW_BOLD,
            bool(current.get("italic", False)),
        )

    @staticmethod
    def _release_dialog_handles(*handles: int | None) -> None:
        for handle in handles:
            if handle:
                ctypes.windll.kernel32.GlobalFree(handle)

    def choose_page_setup(
        self,
        owner: object | None,
        margins: tuple[int, int, int, int],
    ) -> tuple[int, int, int, int] | None:
        """Show the Win32 page-setup common dialog."""
        left, top, right, bottom = margins
        setup = _PAGESETUPDLGW(
            lStructSize=ctypes.sizeof(_PAGESETUPDLGW),
            hwndOwner=self._owner_hwnd(owner),
            Flags=_PSD_MARGINS | _PSD_INTHOUSANDTHSOFINCHES,
            rtMargin=wintypes.RECT(left, top, right, bottom),
        )
        accepted = bool(ctypes.windll.comdlg32.PageSetupDlgW(ctypes.byref(setup)))
        self._release_dialog_handles(setup.hDevMode, setup.hDevNames)
        if not accepted:
            return None
        return (
            setup.rtMargin.left,
            setup.rtMargin.top,
            setup.rtMargin.right,
            setup.rtMargin.bottom,
        )

    def choose_print(
        self,
        owner: object | None,
        pages: tuple[int, int],
        copies: int,
    ) -> tuple[int, int, int] | None:
        """Show the Win32 print common dialog."""
        from_page, to_page = pages
        dialog = _PRINTDLGW(
            lStructSize=ctypes.sizeof(_PRINTDLGW),
            hwndOwner=self._owner_hwnd(owner),
            Flags=_PD_PAGENUMS | _PD_USEDEVMODECOPIESANDCOLLATE,
            nFromPage=from_page,
            nToPage=to_page,
            nMinPage=1,
            nMaxPage=max(1, to_page),
            nCopies=copies,
        )
        accepted = bool(ctypes.windll.comdlg32.PrintDlgW(ctypes.byref(dialog)))
        self._release_dialog_handles(dialog.hDevMode, dialog.hDevNames)
        if not accepted:
            return None
        return dialog.nFromPage, dialog.nToPage, dialog.nCopies

    def register_hwnd(self, peer: Win32Peer) -> None:
        """Update register hwnd."""
        self._peers[peer.hwnd] = peer

    def unregister_hwnd(self, hwnd: int) -> None:
        """Update unregister hwnd."""
        self._peers.pop(hwnd, None)
        self._auxiliary.pop(hwnd, None)
        self._old_procs.pop(hwnd, None)
        self._subclass_procs.pop(hwnd, None)

    def register_auxiliary(self, hwnd: int, peer: Win32Peer) -> None:
        """Update register auxiliary."""
        self._auxiliary[hwnd] = peer

    def window_opened(self) -> None:
        """Update window opened."""
        self._windows += 1

    def window_closed(self) -> None:
        """Update window closed."""
        self._windows = max(0, self._windows - 1)
        if self._windows == 0:
            win32gui.PostQuitMessage(0)

    def register_menu_command(
        self,
        hwnd: int,
        command: int,
        callback: Callable[[], object],
    ) -> None:
        """Update register menu command."""
        self._menu_commands.setdefault(hwnd, {})[command] = callback

    def clear_menu_commands(self, hwnd: int) -> None:
        """Update clear menu commands."""
        self._menu_commands.pop(hwnd, None)

    @staticmethod
    def _signed_word(value: int) -> int:
        word = value & _WORD_MASK_16
        if word & _WORD_SIGN_BIT_16:
            return word - _SIGNED_WORD_BASE_16
        return word

    @classmethod
    def _point_from_lparam(cls, lparam: int) -> tuple[int, int]:
        x = cls._signed_word(lparam)
        y = cls._signed_word(lparam >> 16)
        return x, y

    @staticmethod
    def _mouse_wheel_delta(message: int, wparam: int) -> int:
        if message != win32con.WM_MOUSEWHEEL:
            return 0
        return Win32Backend._signed_word(wparam >> 16)

    @staticmethod
    def _char_for_key_event(message: int, wparam: int) -> str | None:
        if message != win32con.WM_CHAR:
            return None
        if 0 <= wparam <= _MAX_UNICODE_CODEPOINT:
            return chr(wparam)
        return None

    def _dispatch_subclass_message(
        self,
        peer: Win32Peer,
        message: int,
        wparam: int,
        lparam: int,
    ) -> None:
        if message in _MOUSE_MESSAGES:
            x, y = self._point_from_lparam(lparam)
            button = _MOUSE_BUTTON_BY_MESSAGE.get(message, 0)
            wheel = self._mouse_wheel_delta(message, wparam)
            peer.component.emit_mouse_event(x, y, button, wheel)
            return
        if message in _KEY_MESSAGES:
            peer.component.emit_key_event(
                wparam, self._char_for_key_event(message, wparam)
            )

    def subclass_control(self, peer: Win32Peer) -> None:
        """Update subclass control."""

        def proc(window: int, message: int, wparam: int, lparam: int) -> int:
            control_brush = self._handle_control_color(
                message,
                wparam,
                peer.component,
            )
            if control_brush is not None:
                return control_brush
            self._dispatch_subclass_message(peer, message, wparam, lparam)
            old = self._old_procs.get(window)
            if old is None:
                return self._default_wndproc(window, message, wparam, lparam)
            return int(win32gui.CallWindowProc(old, window, message, wparam, lparam))

        try:
            old = int(win32gui.SetWindowLong(peer.hwnd, win32con.GWL_WNDPROC, proc))
        except win32gui.error:
            return
        self._old_procs[peer.hwnd] = old
        self._subclass_procs[peer.hwnd] = proc
