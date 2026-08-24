"""Portable styled text and CommonMark conversion."""

from __future__ import annotations

from dataclasses import dataclass
from dataclasses import replace

from markdown_it import MarkdownIt
from markdown_it.token import Token  # noqa: TC002

from .theme import ColorInput


@dataclass(frozen=True, slots=True)
class RichTextStyle:
    """Portable character formatting for a rich-text span."""

    bold: bool = False
    italic: bool = False
    underline: bool = False
    foreground: ColorInput | None = None
    background: ColorInput | None = None
    font_family: str | None = None
    font_size: int | None = None

    def __post_init__(self) -> None:
        """Validate optional font attributes."""
        if self.font_size is not None and self.font_size <= 0:
            msg = "rich-text font size must be positive"
            raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class RichTextSpan:
    """Half-open character range with one formatting style."""

    start: int
    end: int
    style: RichTextStyle


@dataclass(frozen=True, slots=True)
class StyledText:
    """Plain display text paired with portable character-format spans."""

    text: str
    spans: tuple[RichTextSpan, ...] = ()


@dataclass(slots=True)
class _StyleState:
    bold: int = 0
    italic: int = 0
    underline: int = 0
    code: int = 0

    def style(self) -> RichTextStyle:
        return RichTextStyle(
            bold=self.bold > 0,
            italic=self.italic > 0,
            underline=self.underline > 0,
            background="muted" if self.code > 0 else None,
        )


def _code_style(style: RichTextStyle) -> RichTextStyle:
    return replace(style, background="muted")


def _append_segment(
    text: str,
    style: RichTextStyle,
    output: list[str],
    spans: list[RichTextSpan],
) -> None:
    if not text:
        return
    start = sum(len(part) for part in output)
    output.append(text)
    end = start + len(text)
    if style == RichTextStyle():
        return
    if spans and spans[-1].end == start and spans[-1].style == style:
        previous = spans[-1]
        spans[-1] = RichTextSpan(previous.start, end, style)
    else:
        spans.append(RichTextSpan(start, end, style))


def _append_inline(  # noqa: C901
    tokens: list[Token],
    output: list[str],
    spans: list[RichTextSpan],
    state: _StyleState,
) -> None:
    for token in tokens:
        if token.type == "strong_open":
            state.bold += 1
        elif token.type == "strong_close":
            state.bold -= 1
        elif token.type == "em_open":
            state.italic += 1
        elif token.type == "em_close":
            state.italic -= 1
        elif token.type == "link_open":
            state.underline += 1
        elif token.type == "link_close":
            state.underline -= 1
        elif token.type == "code_inline":
            _append_segment(token.content, _code_style(state.style()), output, spans)
        elif token.type in {"softbreak", "hardbreak"}:
            _append_segment("\n", state.style(), output, spans)
        elif token.type in {"text", "html_inline", "image"}:
            _append_segment(token.content, state.style(), output, spans)


def parse_commonmark(source: str) -> StyledText:  # noqa: C901, PLR0912
    """Parse CommonMark into plain text and merged portable style spans."""
    tokens = MarkdownIt("commonmark").parse(source)
    output: list[str] = []
    spans: list[RichTextSpan] = []
    state = _StyleState()
    block_started = False
    lists: list[tuple[str, int]] = []

    for token in tokens:
        if token.type == "heading_open":
            state.bold += 1
        elif token.type == "heading_close":
            state.bold -= 1
        elif token.type == "bullet_list_open":
            lists.append(("bullet", 1))
        elif token.type == "ordered_list_open":
            start = token.attrs.get("start", 1)
            lists.append(("ordered", start if isinstance(start, int) else 1))
        elif token.type in {"bullet_list_close", "ordered_list_close"}:
            lists.pop()
        elif token.type == "list_item_open":
            if block_started and output and not output[-1].endswith("\n"):
                output.append("\n")
            kind, number = lists[-1]
            prefix = "• " if kind == "bullet" else f"{number}. "
            output.append("  " * (len(lists) - 1) + prefix)
            lists[-1] = kind, number + 1
            block_started = False
        elif token.type == "inline":
            if block_started and output and not output[-1].endswith("\n"):
                output.append("\n")
            _append_inline(token.children or [], output, spans, state)
            block_started = True
        elif token.type in {"code_block", "fence"}:
            if block_started and output and not output[-1].endswith("\n"):
                output.append("\n")
            _append_segment(
                token.content.rstrip("\n"),
                _code_style(state.style()),
                output,
                spans,
            )
            block_started = True
        elif token.type == "hr":
            if output and not output[-1].endswith("\n"):
                output.append("\n")
            _append_segment("---", state.style(), output, spans)
            block_started = True

    return StyledText("".join(output).rstrip("\n"), tuple(spans))
