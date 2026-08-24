"""Typed observable models with granular change events and disposable subscriptions."""

from __future__ import annotations

from collections.abc import Callable
from collections.abc import Iterable
from collections.abc import Iterator
from collections.abc import Sequence
from dataclasses import dataclass

from .subscriptions import Signal
from .subscriptions import Subscription

Cell = object


@dataclass(frozen=True, slots=True)
class ModelEvent:
    """Base event emitted by observable data models."""

    source: ObservableModel


@dataclass(frozen=True, slots=True)
class Reset(ModelEvent):
    """The model should be considered fully replaced."""


@dataclass(frozen=True, slots=True)
class Insert(ModelEvent):
    """A contiguous item range was inserted."""

    index: int
    count: int = 1


@dataclass(frozen=True, slots=True)
class Remove(ModelEvent):
    """A contiguous item range was removed."""

    index: int
    count: int = 1


@dataclass(frozen=True, slots=True)
class Replace(ModelEvent):
    """A contiguous item range was replaced."""

    index: int
    count: int = 1


@dataclass(frozen=True, slots=True)
class SelectionChanged(ModelEvent):
    """A single-selection model changed its selected index or selected item."""

    previous: int
    current: int


@dataclass(frozen=True, slots=True)
class CellChanged(ModelEvent):
    """One table cell changed."""

    row: int
    column: int
    previous: Cell
    current: Cell


@dataclass(frozen=True, slots=True)
class RowInserted(ModelEvent):
    """One table row was inserted."""

    index: int
    values: tuple[Cell, ...]


@dataclass(frozen=True, slots=True)
class RowRemoved(ModelEvent):
    """One table row was removed."""

    index: int
    values: tuple[Cell, ...]


ModelListener = Callable[[ModelEvent], None]


class ObservableModel:
    """Base model using weak/disposable Observer subscriptions."""

    def __init__(self) -> None:
        """Initialize the model event signal."""
        self._changes: Signal[ModelEvent] = Signal()

    def subscribe(self, listener: ModelListener) -> Subscription:
        """Subscribe to typed model deltas and return a disposable registration."""
        return self._changes.subscribe(listener)

    def _emit(self, event: ModelEvent) -> None:
        self._changes.emit(event)


class ListModel[T](ObservableModel):
    """Mutable observable sequence for list-like controls."""

    def add(self, item: T) -> None:
        """Append one item and emit an insert event."""
        index = len(self._items)
        self._items.append(item)
        self._emit(Insert(self, index))

    append = add

    def __init__(self, items: Iterable[T] = ()) -> None:
        """Create a list model from initial items."""
        super().__init__()
        self._items = list(items)

    def get(self, index: int) -> T:
        """Return the item at an index."""
        return self._items[index]

    def insert(self, index: int, item: T) -> None:
        """Insert one item at an index and emit an event."""
        self._items.insert(index, item)
        self._emit(Insert(self, index))

    def extend(self, items: Iterable[T]) -> None:
        """Append many items and emit one contiguous insert event."""
        values = list(items)
        if not values:
            return
        index = len(self._items)
        self._items.extend(values)
        self._emit(Insert(self, index, len(values)))

    def remove(self, item: T) -> None:
        """Remove the first matching item and emit a remove event."""
        index = self._items.index(item)
        self._items.remove(item)
        self._emit(Remove(self, index))

    def pop(self, index: int = -1) -> T:
        """Remove and return an item by index and emit a remove event."""
        resolved = index if index >= 0 else len(self._items) + index
        value = self._items.pop(index)
        self._emit(Remove(self, resolved))
        return value

    def replace(self, index: int, item: T) -> None:
        """Replace one item and emit a replace event."""
        self._items[index] = item
        self._emit(Replace(self, index))

    def clear(self) -> None:
        """Clear all items and emit a reset event when needed."""
        if not self._items:
            return
        self._items.clear()
        self._emit(Reset(self))

    def set_items(self, items: Iterable[T]) -> None:
        """Replace all items from an iterable and emit a reset event."""
        self._items[:] = items
        self._emit(Reset(self))

    def to_list(self) -> list[T]:
        """Return a shallow copy of current items."""
        return self._items.copy()

    def __getitem__(self, index: int) -> T:
        """Return the item at an index."""
        return self._items[index]

    def __iter__(self) -> Iterator[T]:
        """Iterate over items in order."""
        return iter(self._items)

    def __len__(self) -> int:
        """Return the number of items."""
        return len(self._items)


class ComboBoxModel[T](ListModel[T]):
    """List model with a single selected index."""

    def add(self, item: T) -> None:
        """Append an item and establish selection when the model was empty."""
        self.insert(len(self._items), item)

    append = add

    def __init__(self, items: Iterable[T] = ()) -> None:
        """Create a single-selection model with optional initial items."""
        super().__init__(items)
        self.selected_index = 0 if self._items else -1

    @property
    def selected_item(self) -> T | None:
        """Return the currently selected item or None."""
        if 0 <= self.selected_index < len(self._items):
            return self._items[self.selected_index]
        return None

    def get_selected_item(self) -> T | None:
        """Return the currently selected item or None."""
        return self.selected_item

    def set_selected_index(self, index: int) -> None:
        """Update the selected index and emit a selection event."""
        if index < -1 or index >= len(self._items):
            raise IndexError(index)
        previous = self.selected_index
        if previous == index:
            return
        self.selected_index = index
        self._emit(SelectionChanged(self, previous, index))

    def insert(self, index: int, item: T) -> None:
        """Insert an item while preserving the selected item."""
        resolved = max(0, min(index, len(self._items)))
        previous = self.selected_index
        super().insert(index, item)
        if previous == -1:
            self.selected_index = 0
            self._emit(SelectionChanged(self, previous, self.selected_index))
        elif previous >= resolved:
            self.selected_index = previous + 1
            self._emit(SelectionChanged(self, previous, self.selected_index))

    def extend(self, items: Iterable[T]) -> None:
        """Append items and establish selection when the model was empty."""
        previous = self.selected_index
        super().extend(items)
        if previous == -1 and self._items:
            self.selected_index = 0
            self._emit(SelectionChanged(self, previous, self.selected_index))

    def remove(self, item: T) -> None:
        """Remove the first matching item and repair selection."""
        self.pop(self._items.index(item))

    def pop(self, index: int = -1) -> T:
        """Remove an item and keep selection valid."""
        resolved = index if index >= 0 else len(self._items) + index
        previous = self.selected_index
        value = super().pop(index)
        if previous > resolved:
            self.selected_index = previous - 1
        elif previous == resolved:
            self.selected_index = min(resolved, len(self._items) - 1)
        if self.selected_index != previous:
            self._emit(SelectionChanged(self, previous, self.selected_index))
        return value

    def set_items(self, items: Iterable[T]) -> None:
        """Replace all items and establish a valid default selection."""
        previous = self.selected_index
        super().set_items(items)
        self.selected_index = 0 if self._items else -1
        if self.selected_index != previous:
            self._emit(SelectionChanged(self, previous, self.selected_index))

    def replace(self, index: int, item: T) -> None:
        """Replace an item and report selected-item identity changes."""
        resolved = index if index >= 0 else len(self._items) + index
        super().replace(index, item)
        if resolved == self.selected_index:
            self._emit(
                SelectionChanged(self, self.selected_index, self.selected_index),
            )

    def clear(self) -> None:
        """Clear items and reset selection to no selection."""
        previous = self.selected_index
        super().clear()
        self.selected_index = -1
        if previous != -1:
            self._emit(SelectionChanged(self, previous, -1))


class TableModel(ObservableModel):
    """Observable two-dimensional table model with cell/row deltas."""

    def add_row(self, row: Sequence[Cell]) -> None:
        """Append a row and emit a row-inserted event."""
        values = list(row)
        index = len(self.rows)
        self.rows.append(values)
        self._emit(RowInserted(self, index, tuple(values)))

    append = add_row

    def __init__(
        self,
        rows: Iterable[Sequence[Cell]] = (),
        columns: Iterable[str] = (),
    ) -> None:
        """Create a table model from initial rows and column labels."""
        super().__init__()
        self.columns = list(columns)
        self.rows = [list(row) for row in rows]

    @property
    def row_count(self) -> int:
        """Return the number of rows."""
        return len(self.rows)

    @property
    def column_count(self) -> int:
        """Return the number of columns."""
        return len(self.columns)

    def get_value_at(self, row: int, column: int) -> Cell:
        """Return the value at row and column."""
        return self.rows[row][column]

    def set_value_at(self, value: Cell, row: int, column: int) -> None:
        """Set one cell value and emit a cell-changed event."""
        previous = self.rows[row][column]
        self.rows[row][column] = value
        self._emit(CellChanged(self, row, column, previous, value))

    def insert_row(self, index: int, row: Sequence[Cell]) -> None:
        """Insert a row at an index and emit a row-inserted event."""
        values = list(row)
        self.rows.insert(index, values)
        self._emit(RowInserted(self, index, tuple(values)))

    def remove_row(self, index: int) -> list[Cell]:
        """Remove and return a row at an index, emitting a row-removed event."""
        values = self.rows.pop(index)
        self._emit(RowRemoved(self, index, tuple(values)))
        return values

    def set_columns(self, columns: Iterable[str]) -> None:
        """Replace column labels and emit a reset event."""
        self.columns[:] = columns
        self._emit(Reset(self))

    def clear(self) -> None:
        """Clear all rows and emit a reset event when needed."""
        if not self.rows:
            return
        self.rows.clear()
        self._emit(Reset(self))

    def __getitem__(self, index: int) -> list[Cell]:
        """Return the row at an index."""
        return self.rows[index]

    def __iter__(self) -> Iterator[list[Cell]]:
        """Iterate over rows in order."""
        return iter(self.rows)

    def __len__(self) -> int:
        """Return the number of rows."""
        return len(self.rows)
