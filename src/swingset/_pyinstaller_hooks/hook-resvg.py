"""Collect metadata imported by resvg at runtime."""

from PyInstaller.utils.hooks import copy_metadata

datas = copy_metadata("resvg")
