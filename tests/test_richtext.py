"""Portable component colors and CommonMark styled-text tests."""

import pytest

from swingset import Label
from swingset import RichTextPane
from swingset import RichTextStyle
from swingset import parse_commonmark


def test_parse_commonmark_nested_inline_styles() -> None:
    """Convert nested emphasis, links, and code into exact portable spans."""
    styled = parse_commonmark(
        "Hello **bold and *italic*** with [link](https://example.com) and `code`"
    )

    assert styled.text == "Hello bold and italic with link and code"
    bold_start = 6
    bold_end = 15
    assert styled.spans[0].start == bold_start
    assert styled.spans[0].end == bold_end
    assert styled.spans[0].style == RichTextStyle(bold=True)
    assert styled.spans[1].style == RichTextStyle(bold=True, italic=True)
    assert styled.spans[2].style == RichTextStyle(underline=True)
    assert styled.spans[3].style.background == "muted"


def test_component_markdown_and_colors() -> None:
    """Make styled text and semantic colors available to every component."""
    label = Label()
    label.foreground = "accent"
    label.background = (240, 240, 240)

    result = label.set_markdown("**Portable** *text*")

    assert result is label
    assert label.text == "Portable text"
    assert label.foreground == "accent"
    assert label.background == (240, 240, 240)
    expected_span_count = 2
    assert len(label.styles) == expected_span_count
    assert label.styles[0].style.bold
    assert label.styles[1].style.italic


def test_plain_text_replaces_styled_content() -> None:
    """Clear stale spans when plain component text replaces Markdown."""
    label = Label().set_markdown("**Styled**")

    label.text = "Plain"

    assert label.styles == ()


def test_rich_text_selection_applies_portable_style() -> None:
    """Apply formatting to a validated half-open editor selection."""
    pane = RichTextPane("Portable rich text")
    pane.selection_range = (9, 13)

    span = pane.apply_style_to_selection(RichTextStyle(bold=True, underline=True))

    assert span is not None
    assert (span.start, span.end) == (9, 13)
    assert span.style == RichTextStyle(bold=True, underline=True)
    with pytest.raises(ValueError, match="outside the current text"):
        pane.selection_range = (0, 99)


def test_rich_text_selection_supports_font_attributes() -> None:
    """Retain selection-scoped font family and point size portably."""
    font_size = 18
    pane = RichTextPane("Font selection")
    pane.selection_range = (0, 4)

    span = pane.apply_style_to_selection(
        RichTextStyle(font_family="Georgia", font_size=font_size),
    )

    assert span is not None
    assert span.style.font_family == "Georgia"
    assert span.style.font_size == font_size
    with pytest.raises(ValueError, match="must be positive"):
        RichTextStyle(font_size=0)


def test_commonmark_headings_and_lists() -> None:
    """Preserve useful block structure and heading emphasis."""
    styled = parse_commonmark("# Tasks\n\n- first\n- second\n\n3. third")

    assert styled.text == "Tasks\n• first\n• second\n3. third"
    assert styled.spans[0] == styled.spans[0].__class__(
        0,
        len("Tasks"),
        RichTextStyle(bold=True),
    )
