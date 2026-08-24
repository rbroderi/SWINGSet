"""Contract tests for runnable examples and their TOML forms."""

from __future__ import annotations

import importlib.util
import tomllib
from collections.abc import Mapping
from pathlib import Path
from typing import Protocol
from typing import cast

from swingset import TomlUILoader


class TomlExample(Protocol):
    """Runnable example module exposing its declarative form."""

    def build_toml(self) -> str:
        """Return the example's TOML document."""
        ...


def _load_module(path: Path, index: int) -> TomlExample:
    spec = importlib.util.spec_from_file_location(f"swingset_example_{index}", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return cast("TomlExample", module)


def _no_op(_event: object) -> None:
    pass


def _handler_names(document: Mapping[str, object]) -> set[str]:
    names: set[str] = set()
    commands = document.get("commands", {})
    if isinstance(commands, Mapping):
        names.update(str(name) for name in commands)
    widgets = document.get("widgets", {})
    if not isinstance(widgets, Mapping):
        return names
    for raw_widget in widgets.values():
        if not isinstance(raw_widget, Mapping):
            continue
        command = raw_widget.get("command")
        if isinstance(command, str):
            names.add(command)
        events = raw_widget.get("events", {})
        if isinstance(events, Mapping):
            names.update(str(name) for name in events.values())
    return names


def test_every_catalog_example_has_compilable_toml() -> None:
    """Import and compile the TOML form of every categorized catalog example."""
    root = Path(__file__).parents[1]
    examples_root = root / "examples"
    example_paths = sorted(
        path
        for path in examples_root.rglob("*.py")
        if path.name != "__init__.py" and path.parent != examples_root
    )
    assert example_paths

    for index, path in enumerate(example_paths):
        example = _load_module(path, index)
        toml_path = path.with_suffix(".toml")
        source = (
            toml_path.read_text(encoding="utf-8")
            if toml_path.exists()
            else example.build_toml()
        )
        document = tomllib.loads(source)
        handlers = dict.fromkeys(_handler_names(document), _no_op)
        TomlUILoader().loads(source, filename=str(path), handlers=handlers)
