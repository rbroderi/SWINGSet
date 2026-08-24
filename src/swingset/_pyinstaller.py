"""PyInstaller integration for SWINGSet dependencies."""

from pathlib import Path


def get_hook_dirs() -> list[str]:
    """Return the directory containing SWINGSet's PyInstaller hooks."""
    return [str(Path(__file__).with_name("_pyinstaller_hooks"))]
