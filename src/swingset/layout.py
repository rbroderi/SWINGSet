"""Backend-neutral layout strategies."""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass
from enum import IntEnum
from typing import TYPE_CHECKING

from .core import Component
from .core import Container
from .geometry import Size

if TYPE_CHECKING:
    from .core import Component


def _visible_children(container: Container) -> list[Component]:
    return [slot.component for slot in container.children if slot.component.visible]


class FlowAlignment(IntEnum):
    """Horizontal row alignment for FlowLayout."""

    LEFT = 0
    CENTER = 1
    RIGHT = 2


class FlowLayout:
    """Lay children left-to-right and wrap rows."""

    LEFT = FlowAlignment.LEFT
    CENTER = FlowAlignment.CENTER
    RIGHT = FlowAlignment.RIGHT

    def __init__(
        self,
        align: FlowAlignment = LEFT,
        hgap: int = 8,
        vgap: int = 8,
    ) -> None:
        """Configure alignment and horizontal/vertical gaps."""
        self.align = align
        self.hgap = hgap
        self.vgap = vgap

    def layout(self, container: Container) -> None:
        """Lay out the container's children."""
        if not container.created:
            return
        client_width, _height = container.client_size()
        row: list[Component] = []
        row_width = 0
        row_height = 0
        y = self.vgap

        def place(items: list[Component], width: int, ypos: int) -> None:
            if not items:
                return
            if self.align == self.LEFT:
                start = self.hgap
            elif self.align == self.CENTER:
                start = max(self.hgap, (client_width - width) // 2)
            else:
                start = max(self.hgap, client_width - width - self.hgap)
            x = start
            for child in items:
                child.set_bounds(x, ypos, child.width, child.height)
                x += child.width + self.hgap

        for slot in container.children:
            child = slot.component
            needed = child.width + (self.hgap if row else 0)
            if row and row_width + needed + self.hgap > client_width:
                place(row, row_width, y)
                y += row_height + self.vgap
                row = []
                row_width = 0
                row_height = 0
            row.append(child)
            row_width += child.width if len(row) == 1 else child.width + self.hgap
            row_height = max(row_height, child.height)
        place(row, row_width, y)

    def _measure(
        self,
        container: Container,
        measure: Callable[[Component], Size],
    ) -> Size:
        children = _visible_children(container)
        if not children:
            return Size(2 * self.hgap, 2 * self.vgap)
        sizes = [measure(child) for child in children]
        width = sum(size.width for size in sizes)
        width += self.hgap * (len(children) + 1)
        height = max(size.height for size in sizes)
        return Size(width, height + 2 * self.vgap)

    def preferred_size(self, container: Container) -> Size:
        """Measure one unwrapped row of child preferred sizes."""
        return self._measure(container, lambda child: child.preferred_size)

    def minimum_size(self, container: Container) -> Size:
        """Measure one unwrapped row of child minimum sizes."""
        return self._measure(container, lambda child: child.minimum_size)

    def maximum_size(self, container: Container) -> Size:
        """Measure one unwrapped row of child maximum sizes."""
        return self._measure(container, lambda child: child.maximum_size)


class BoxAxis(IntEnum):
    """Major axis used by BoxLayout."""

    X = 0
    Y = 1


class BoxLayout:
    """Lay children in one non-wrapping horizontal or vertical strip."""

    X_AXIS = BoxAxis.X
    Y_AXIS = BoxAxis.Y

    def __init__(self, axis: BoxAxis = Y_AXIS, gap: int = 8) -> None:
        """Configure the stacking axis and inter-component gap."""
        if gap < 0:
            msg = "gap must not be negative"
            raise ValueError(msg)
        self.axis = axis
        self.gap = gap

    def layout(self, container: Container) -> None:
        """Lay out visible children along the configured axis."""
        if not container.created:
            return
        width, height = container.client_size()
        position = 0
        for slot in container.children:
            child = slot.component
            if not child.visible:
                continue
            preferred = child.preferred_size
            if self.axis is self.X_AXIS:
                child.set_bounds(position, 0, preferred.width, height)
                position += preferred.width + self.gap
            else:
                child.set_bounds(0, position, width, preferred.height)
                position += preferred.height + self.gap

    def _measure(
        self,
        container: Container,
        measure: Callable[[Component], Size],
    ) -> Size:
        children = _visible_children(container)
        if not children:
            return Size()
        sizes = [measure(child) for child in children]
        gaps = self.gap * (len(children) - 1)
        if self.axis is self.X_AXIS:
            return Size(
                sum(size.width for size in sizes) + gaps,
                max(size.height for size in sizes),
            )
        return Size(
            max(size.width for size in sizes),
            sum(size.height for size in sizes) + gaps,
        )

    def preferred_size(self, container: Container) -> Size:
        """Measure children from preferred sizes along the major axis."""
        return self._measure(container, lambda child: child.preferred_size)

    def minimum_size(self, container: Container) -> Size:
        """Measure children from minimum sizes along the major axis."""
        return self._measure(container, lambda child: child.minimum_size)

    def maximum_size(self, container: Container) -> Size:
        """Measure children from maximum sizes along the major axis."""
        return self._measure(container, lambda child: child.maximum_size)


class CardLayout:
    """Stack named children and expose exactly one card at a time."""

    def __init__(self) -> None:
        """Initialize with the first card selected by default."""
        self._selected_name: str | None = None

    @staticmethod
    def _cards(container: Container) -> list[tuple[str, Component]]:
        return [
            (
                slot.constraint if isinstance(slot.constraint, str) else str(index),
                slot.component,
            )
            for index, slot in enumerate(container.children)
        ]

    @property
    def selected_name(self) -> str | None:
        """Return the selected card name, if any."""
        return self._selected_name

    def show(self, container: Container, name: str) -> None:
        """Select a named card and update the mounted container."""
        names = {card_name for card_name, _component in self._cards(container)}
        if name not in names:
            msg = f"unknown card: {name}"
            raise ValueError(msg)
        self._selected_name = name
        container.do_layout()

    def first(self, container: Container) -> None:
        """Select the first card."""
        cards = self._cards(container)
        if cards:
            self.show(container, cards[0][0])

    def _move(self, container: Container, offset: int) -> None:
        cards = self._cards(container)
        if not cards:
            return
        names = [name for name, _component in cards]
        selected_name = self._selected_name
        index = (
            names.index(selected_name)
            if selected_name is not None and selected_name in names
            else 0
        )
        self.show(container, names[(index + offset) % len(names)])

    def next(self, container: Container) -> None:
        """Select the card after the current card, wrapping at the end."""
        self._move(container, 1)

    def previous(self, container: Container) -> None:
        """Select the card before the current card, wrapping at the start."""
        self._move(container, -1)

    def layout(self, container: Container) -> None:
        """Fill the container with the selected card and hide the others."""
        if not container.created:
            return
        cards = self._cards(container)
        if not cards:
            self._selected_name = None
            return
        names = [name for name, _component in cards]
        if self._selected_name not in names:
            self._selected_name = names[0]
        width, height = container.client_size()
        for name, component in cards:
            selected = name == self._selected_name
            component.visible = selected
            if selected:
                component.set_bounds(0, 0, width, height)

    def _measure(
        self,
        container: Container,
        measure: Callable[[Component], Size],
    ) -> Size:
        cards = self._cards(container)
        if not cards:
            return Size()
        sizes = [measure(component) for _name, component in cards]
        return Size(
            max(size.width for size in sizes),
            max(size.height for size in sizes),
        )

    def preferred_size(self, container: Container) -> Size:
        """Measure the largest preferred card."""
        return self._measure(container, lambda child: child.preferred_size)

    def minimum_size(self, container: Container) -> Size:
        """Measure the largest minimum card."""
        return self._measure(container, lambda child: child.minimum_size)

    def maximum_size(self, container: Container) -> Size:
        """Measure the largest maximum card."""
        return self._measure(container, lambda child: child.maximum_size)


class BorderLayout:
    """Lay out up to five directional regions."""

    NORTH = "North"
    SOUTH = "South"
    EAST = "East"
    WEST = "West"
    CENTER = "Center"

    def __init__(self, hgap: int = 4, vgap: int = 4) -> None:
        """Configure horizontal and vertical region gaps."""
        self.hgap = hgap
        self.vgap = vgap

    def layout(self, container: Container) -> None:
        """Lay out directional children."""
        if not container.created:
            return
        width, height = container.client_size()
        x = y = 0
        right = width
        bottom = height
        mapping = {
            self.CENTER if slot.constraint is None else slot.constraint: slot.component
            for slot in container.children
        }
        north = mapping.get(self.NORTH)
        south = mapping.get(self.SOUTH)
        west = mapping.get(self.WEST)
        east = mapping.get(self.EAST)
        center = mapping.get(self.CENTER)
        if north is not None:
            north.set_bounds(0, 0, width, north.height)
            y += north.height + self.vgap
        if south is not None:
            south.set_bounds(0, height - south.height, width, south.height)
            bottom -= south.height + self.vgap
        if west is not None:
            west.set_bounds(0, y, west.width, max(0, bottom - y))
            x += west.width + self.hgap
        if east is not None:
            east.set_bounds(width - east.width, y, east.width, max(0, bottom - y))
            right -= east.width + self.hgap
        if center is not None:
            center.set_bounds(x, y, max(0, right - x), max(0, bottom - y))

    def _measure(
        self,
        container: Container,
        measure: Callable[[Component], Size],
    ) -> Size:
        mapping = {
            self.CENTER if slot.constraint is None else slot.constraint: slot.component
            for slot in container.children
            if slot.component.visible
        }
        north = mapping.get(self.NORTH)
        south = mapping.get(self.SOUTH)
        west = mapping.get(self.WEST)
        east = mapping.get(self.EAST)
        center = mapping.get(self.CENTER)
        middle = [item for item in (west, center, east) if item is not None]
        middle_sizes = [measure(item) for item in middle]
        middle_width = sum(size.width for size in middle_sizes)
        middle_width += self.hgap * max(0, len(middle) - 1)
        middle_height = max((size.height for size in middle_sizes), default=0)
        horizontal = [item for item in (north, south) if item is not None]
        horizontal_sizes = [measure(item) for item in horizontal]
        width = max([middle_width, *(size.width for size in horizontal_sizes)])
        heights = [size.height for size in horizontal_sizes]
        height = middle_height + sum(heights)
        if middle and north is not None:
            height += self.vgap
        if middle and south is not None:
            height += self.vgap
        if not middle and north is not None and south is not None:
            height += self.vgap
        return Size(width, height)

    def preferred_size(self, container: Container) -> Size:
        """Measure directional regions from preferred dimensions."""
        return self._measure(container, lambda child: child.preferred_size)

    def minimum_size(self, container: Container) -> Size:
        """Measure directional regions from minimum dimensions."""
        return self._measure(container, lambda child: child.minimum_size)

    def maximum_size(self, container: Container) -> Size:
        """Measure directional regions from maximum dimensions."""
        return self._measure(container, lambda child: child.maximum_size)


class GridLayout:
    """Lay children into equally sized grid cells."""

    def __init__(
        self,
        rows: int = 1,
        cols: int = 0,
        hgap: int = 4,
        vgap: int = 4,
    ) -> None:
        """Configure grid dimensions and inter-cell gaps."""
        self.rows = rows
        self.cols = cols
        self.hgap = hgap
        self.vgap = vgap

    def layout(self, container: Container) -> None:
        """Lay out the grid."""
        if not container.created:
            return
        children = [slot.component for slot in container.children]
        count = len(children)
        if count == 0:
            return
        rows = self.rows or math.ceil(count / self.cols)
        cols = self.cols or math.ceil(count / rows)
        width, height = container.client_size()
        cell_width = max(0, (width - (cols - 1) * self.hgap) // cols)
        cell_height = max(0, (height - (rows - 1) * self.vgap) // rows)
        for index, child in enumerate(children):
            row, col = divmod(index, cols)
            child.set_bounds(
                col * (cell_width + self.hgap),
                row * (cell_height + self.vgap),
                cell_width,
                cell_height,
            )

    def _measure(
        self,
        container: Container,
        measure: Callable[[Component], Size],
    ) -> Size:
        children = _visible_children(container)
        count = len(children)
        if count == 0:
            return Size()
        rows = self.rows or math.ceil(count / self.cols)
        cols = self.cols or math.ceil(count / rows)
        sizes = [measure(child) for child in children]
        cell_width = max(size.width for size in sizes)
        cell_height = max(size.height for size in sizes)
        return Size(
            cols * cell_width + (cols - 1) * self.hgap,
            rows * cell_height + (rows - 1) * self.vgap,
        )

    def preferred_size(self, container: Container) -> Size:
        """Measure equal cells from child preferred sizes."""
        return self._measure(container, lambda child: child.preferred_size)

    def minimum_size(self, container: Container) -> Size:
        """Measure equal cells from child minimum sizes."""
        return self._measure(container, lambda child: child.minimum_size)

    def maximum_size(self, container: Container) -> Size:
        """Measure equal cells from child maximum sizes."""
        return self._measure(container, lambda child: child.maximum_size)


class Fill(IntEnum):
    """GridBag fill behavior."""

    NONE = 0
    HORIZONTAL = 1
    VERTICAL = 2
    BOTH = 3


@dataclass(slots=True)
class GridBagConstraints:
    """Placement and weight metadata for GridBagLayout."""

    gridx: int = 0
    gridy: int = 0
    gridwidth: int = 1
    gridheight: int = 1
    weightx: float = 0.0
    weighty: float = 0.0
    fill: Fill = Fill.BOTH
    inset: int = 4

    NONE = Fill.NONE
    HORIZONTAL = Fill.HORIZONTAL
    VERTICAL = Fill.VERTICAL
    BOTH = Fill.BOTH


def _weighted_edges(total: int, weights: list[float]) -> list[int]:
    weight_sum = sum(weights)
    edges = [0]
    for weight in weights:
        edges.append(edges[-1] + round(total * weight / weight_sum))
    edges[-1] = total
    return edges


class GridBagLayout:
    """Pragmatic weighted grid inspired by Swing's GridBagLayout."""

    def layout(self, container: Container) -> None:
        """Lay out weighted cells."""
        if not container.created:
            return
        pairs = [
            (
                slot.component,
                slot.constraint
                if isinstance(slot.constraint, GridBagConstraints)
                else GridBagConstraints(),
            )
            for slot in container.children
        ]
        if not pairs:
            return
        cols = max(c.gridx + c.gridwidth for _, c in pairs)
        rows = max(c.gridy + c.gridheight for _, c in pairs)
        col_weights = [0.0] * cols
        row_weights = [0.0] * rows
        for _child, constraint in pairs:
            for index in range(
                constraint.gridx,
                constraint.gridx + constraint.gridwidth,
            ):
                col_weights[index] = max(
                    col_weights[index],
                    constraint.weightx / max(1, constraint.gridwidth),
                )
            for index in range(
                constraint.gridy,
                constraint.gridy + constraint.gridheight,
            ):
                row_weights[index] = max(
                    row_weights[index],
                    constraint.weighty / max(1, constraint.gridheight),
                )
        if not any(col_weights):
            col_weights = [1.0] * cols
        if not any(row_weights):
            row_weights = [1.0] * rows
        width, height = container.client_size()
        xs = _weighted_edges(width, col_weights)
        ys = _weighted_edges(height, row_weights)
        for child, constraint in pairs:
            left = xs[constraint.gridx]
            top = ys[constraint.gridy]
            right = xs[constraint.gridx + constraint.gridwidth]
            bottom = ys[constraint.gridy + constraint.gridheight]
            inset = constraint.inset
            available_width = max(0, right - left - 2 * inset)
            available_height = max(0, bottom - top - 2 * inset)
            fill_horizontal = constraint.fill in {Fill.HORIZONTAL, Fill.BOTH}
            fill_vertical = constraint.fill in {Fill.VERTICAL, Fill.BOTH}
            child_width = available_width if fill_horizontal else child.width
            child_height = available_height if fill_vertical else child.height
            child.set_bounds(
                left + inset + max(0, available_width - child_width) // 2,
                top + inset + max(0, available_height - child_height) // 2,
                min(child_width, available_width),
                min(child_height, available_height),
            )

    def _measure(
        self,
        container: Container,
        measure: Callable[[Component], Size],
    ) -> Size:
        pairs = [
            (
                slot.component,
                slot.constraint
                if isinstance(slot.constraint, GridBagConstraints)
                else GridBagConstraints(),
            )
            for slot in container.children
            if slot.component.visible
        ]
        if not pairs:
            return Size()
        cols = max(constraint.gridx + constraint.gridwidth for _, constraint in pairs)
        rows = max(constraint.gridy + constraint.gridheight for _, constraint in pairs)
        col_widths = [0] * cols
        row_heights = [0] * rows
        for child, constraint in pairs:
            child_size = measure(child)
            requested_width = math.ceil(
                (child_size.width + 2 * constraint.inset) / constraint.gridwidth
            )
            requested_height = math.ceil(
                (child_size.height + 2 * constraint.inset) / constraint.gridheight
            )
            for index in range(
                constraint.gridx,
                constraint.gridx + constraint.gridwidth,
            ):
                col_widths[index] = max(col_widths[index], requested_width)
            for index in range(
                constraint.gridy,
                constraint.gridy + constraint.gridheight,
            ):
                row_heights[index] = max(row_heights[index], requested_height)
        return Size(sum(col_widths), sum(row_heights))

    def preferred_size(self, container: Container) -> Size:
        """Measure weighted-grid cells from child preferred sizes."""
        return self._measure(container, lambda child: child.preferred_size)

    def minimum_size(self, container: Container) -> Size:
        """Measure weighted-grid cells from child minimum sizes."""
        return self._measure(container, lambda child: child.minimum_size)

    def maximum_size(self, container: Container) -> Size:
        """Measure weighted-grid cells from child maximum sizes."""
        return self._measure(container, lambda child: child.maximum_size)
