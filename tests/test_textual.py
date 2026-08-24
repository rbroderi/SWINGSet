"""Textual backend geometry tests."""

from textual.widgets import Static

from swingset import Component
from swingset import Rect
from swingset import Size
from swingset.backends.textual import TextualBackend
from swingset.backends.textual import TextualPeer
from swingset.backends.textual import _cell_size_to_logical
from swingset.backends.textual import _logical_rect_to_cells

EXPECTED_CELL_WIDTH = 11
EXPECTED_CELL_HEIGHT = 5


def test_logical_bounds_convert_to_terminal_cells() -> None:
    """Map backend-neutral pixel geometry to terminal columns and rows."""
    assert _logical_rect_to_cells(Rect(16, 40, 81, 41)) == Rect(2, 4, 11, 5)


def test_terminal_client_size_converts_to_logical_pixels() -> None:
    """Return terminal client dimensions in backend-neutral logical units."""
    assert _cell_size_to_logical(Size(80, 24)) == Size(640, 240)


def test_textual_bounds_use_absolute_cell_geometry() -> None:
    """Exclude SWINGSet-managed children from Textual's normal layout flow."""
    widget = Static()
    peer = TextualPeer(TextualBackend(headless=True), Component(), widget)

    peer.set_bounds(Rect(16, 40, 81, 41))

    assert widget.styles.position == "absolute"
    assert (widget.styles.offset.x.value, widget.styles.offset.y.value) == (2, 4)
    assert widget.styles.width.value == EXPECTED_CELL_WIDTH
    assert widget.styles.height.value == EXPECTED_CELL_HEIGHT
