"""Typed access to Windows executable version-resource strings."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from importlib import import_module
from pathlib import Path
from typing import Protocol
from typing import cast
from typing import runtime_checkable


@runtime_checkable
class _VersionApi(Protocol):
    def GetFileVersionInfo(self, filename: str, sub_block: str) -> object:  # noqa: N802
        """Mirror pywin32's native function name."""
        ...


@dataclass(frozen=True, slots=True)
class WindowsVersionInfo:
    """Common string fields from a Windows VERSIONINFO resource."""

    path: Path
    company_name: str | None = None
    file_description: str | None = None
    file_version: str | None = None
    product_name: str | None = None
    product_version: str | None = None


def _query_string(
    api: _VersionApi,
    filename: str,
    language: int,
    code_page: int,
    name: str,
) -> str | None:
    block = f"\\StringFileInfo\\{language:04x}{code_page:04x}\\{name}"
    try:
        value = api.GetFileVersionInfo(filename, block)
    except OSError:
        return None
    return value if isinstance(value, str) and value else None


def read_windows_version_info(path: str | Path | None = None) -> WindowsVersionInfo:
    """Read common string fields from a Windows executable or DLL resource."""
    file_path = Path(sys.executable if path is None else path).resolve()
    api = cast("_VersionApi", import_module("win32api"))
    translations = cast(
        "list[tuple[int, int]]",
        api.GetFileVersionInfo(str(file_path), r"\VarFileInfo\Translation"),
    )
    language, code_page = translations[0]

    def query(name: str) -> str | None:
        return _query_string(api, str(file_path), language, code_page, name)

    return WindowsVersionInfo(
        path=file_path,
        company_name=query("CompanyName"),
        file_description=query("FileDescription"),
        file_version=query("FileVersion"),
        product_name=query("ProductName"),
        product_version=query("ProductVersion"),
    )
