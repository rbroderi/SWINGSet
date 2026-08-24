# SWINGSet

SWINGSet is a typed, cross-platform UI toolkit for Python with native Win32,
Tkinter/ttk, and Textual/Rich backends.

The library is inspired by the feel of building interfaces with Java Swing:
applications are composed from familiar components, containers, layouts,
models, and events. The API is designed for Python, using properties,
snake_case methods, type hints, decorators, context-aware runtime services,
and Python data models instead of reproducing the Java API directly.

SWINGSet is currently alpha software and requires Python 3.14 or later.

## Installation

Install the package from PyPI:

```bash
python -m pip install swingset
```

Tkinter is provided by your Python installation when available. The Win32
backend is available on Windows, and the Textual backend provides a terminal
interface on supported platforms.

## Quick start

```python
from swingset import ActionEvent
from swingset import App
from swingset import BorderLayout
from swingset import Button
from swingset import Frame
from swingset import Label
from swingset import Panel
from swingset import Size


def build() -> None:
    frame = Frame("Hello, SWINGSet")
    frame.size = Size(480, 220)

    content = frame.add(Panel(), BorderLayout.CENTER)
    message = content.add(Label("Ready"))
    button = content.add(Button("Click me"))

    @button.on_click
    def clicked(_event: ActionEvent[Button]) -> None:
        message.text = f"Running on {App.backend_name()}"

    frame.visible = True


if __name__ == "__main__":
    App.configure(backend="auto")
    App.run(build)
```

With automatic backend selection, SWINGSet prefers Win32 on Windows and
Tkinter elsewhere, then falls back to another available backend when needed.
A backend can also be selected explicitly:

```python
App.configure(backend="win32")
App.configure(backend="tkinter")
App.configure(backend="textual")
```

## Features

- Typed components, events, models, geometry, and layout APIs
- Win32, Tkinter/ttk, and Textual/Rich backends
- Common controls, menus, toolbars, dialogs, tables, trees, and rich text
- `FlowLayout`, `BorderLayout`, `BoxLayout`, `GridLayout`, and `GridBagLayout`
- Light and dark themes with backend-neutral colors
- SVG and raster image resources
- Synchronous and `asyncio` application entry points
- Declarative TOML interfaces with Python event handlers
- Strict typing support through the included `py.typed` marker

## Layout and components

Components are assembled into a tree using `Container.add()`. Layout managers
measure and arrange that tree independently of the active backend:

```python
from swingset import BorderLayout
from swingset import Button
from swingset import Frame
from swingset import Label

frame = Frame("Layout example")
frame.add(Label("Status"), BorderLayout.SOUTH)
frame.add(Button("Continue"), BorderLayout.CENTER)
frame.pack()
```

Geometry uses immutable value objects such as `Point`, `Size`, and `Rect`.
Observable list, selection, combo-box, and table models can be shared with
controls without depending on a particular platform toolkit.

## TOML interfaces

Interfaces can also be declared in TOML and connected to Python handlers:

```toml
[config.app]
entry-window = "main"

[widgets.main]
type = "Window"
title = "TOML UI"
children = ["content"]

[widgets.content]
type = "VBox"
children = ["message", "save"]

[widgets.message]
type = "Label"
text = "Ready"

[widgets.save]
type = "Button"
text = "Save"

[widgets.save.events]
click = "save"
```

```python
from swingset import TomlUILoader

ui = TomlUILoader().load("interface.toml", handlers={"save": save})
window = ui.root
save_button = ui["save"]
```

See the [customer editor TOML](examples/Toml/customer_editor.toml) and its
[Python handlers](examples/Toml/customer_editor.py) for a complete example.

## Examples

The [examples directory](examples/README.md) contains focused demonstrations
of controls, layouts, dialogs, styling, menus, and complete applications.

From a source checkout, install the development dependencies and run an
example from the repository root:

```bash
uv sync --extra dev
uv run python examples/feature_showcase.py
uv run python examples/Controls/button.py
uv run python examples/Applications/wordpad.py
```

## Async applications

SWINGSet can run alongside an `asyncio` application:

```python
import asyncio

from swingset import App


async def main() -> None:
    await App.run_async(build)


asyncio.run(main())
```

Use `App.invoke_later()`, `App.invoke_and_wait()`, or
`await App.invoke_async()` to schedule work on the UI thread.

## Development

The project uses Ruff, BasedPyright, Pyrefly, and pytest. With the development
dependencies installed:

```bash
uv run ruff check .
uv run basedpyright
uv run pyrefly check
uv run pytest -q
```

The public API is exported from `swingset` and is fully type annotated.
