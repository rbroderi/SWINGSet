"""A complete portable WordPad-style rich-text editor."""

from __future__ import annotations

import json
from collections.abc import Callable
from collections.abc import Mapping
from pathlib import Path

from swingset import ActionEvent
from swingset import App
from swingset import BorderLayout
from swingset import BoxAxis
from swingset import BoxLayout
from swingset import Button
from swingset import Capability
from swingset import ColorInput
from swingset import ComboBox
from swingset import FileFilter
from swingset import Frame
from swingset import Label
from swingset import Menu
from swingset import MenuBar
from swingset import MenuItem
from swingset import MessageBox
from swingset import MessageIcon
from swingset import OpenFileDialog
from swingset import Panel
from swingset import RichTextPane
from swingset import RichTextSpan
from swingset import RichTextStyle
from swingset import SaveFileDialog
from swingset import Size
from swingset import Spinner
from swingset import StatusBar
from swingset import StyledText
from swingset import TextField
from swingset import Theme
from swingset import ToolBar

_DOCUMENT_FILTERS = (
    FileFilter("SWINGSet documents", "*.swingdoc"),
    FileFilter("Markdown files", "*.md"),
    FileFilter("Text files", "*.txt"),
    FileFilter("All files", "*.*"),
)
_RGB_COMPONENT_COUNT = 3
_RGBA_COMPONENT_COUNT = 4


def _encode_color(value: ColorInput | None) -> str | list[int] | None:
    return list(value) if isinstance(value, tuple) else value


def _decode_color(value: object) -> ColorInput | None:
    if value is None or isinstance(value, str):
        return value
    if (
        isinstance(value, list)
        and len(value) in {_RGB_COMPONENT_COUNT, _RGBA_COMPONENT_COUNT}
        and all(isinstance(item, int) for item in value)
    ):
        components = tuple(value)
        if len(components) == _RGB_COMPONENT_COUNT:
            return components[0], components[1], components[2]
        return components[0], components[1], components[2], components[3]
    msg = "invalid color in SWINGSet document"
    raise ValueError(msg)


def _document_json(editor: RichTextPane) -> str:
    text = editor.text
    document = {
        "version": 1,
        "text": text,
        "styles": [
            {
                "start": span.start,
                "end": span.end,
                "bold": span.style.bold,
                "italic": span.style.italic,
                "underline": span.style.underline,
                "foreground": _encode_color(span.style.foreground),
                "background": _encode_color(span.style.background),
                "font-family": span.style.font_family,
                "font-size": span.style.font_size,
            }
            for span in editor.styles
            if span.end <= len(text)
        ],
    }
    return json.dumps(document, indent=2)


def _styled_document(source: str) -> StyledText:
    raw: object = json.loads(source)
    if not isinstance(raw, Mapping):
        msg = "SWINGSet document root must be an object"
        raise TypeError(msg)
    text = raw.get("text")
    styles = raw.get("styles", [])
    if not isinstance(text, str) or not isinstance(styles, list):
        msg = "SWINGSet document requires text and styles"
        raise TypeError(msg)
    spans: list[RichTextSpan] = []
    for item in styles:
        if not isinstance(item, Mapping):
            msg = "SWINGSet document styles must be objects"
            raise TypeError(msg)
        start = item.get("start")
        end = item.get("end")
        if not isinstance(start, int) or not isinstance(end, int):
            msg = "SWINGSet document style ranges must be integers"
            raise TypeError(msg)
        if start < 0 or end <= start or end > len(text):
            msg = "SWINGSet document style range is outside the text"
            raise ValueError(msg)
        font_family = item.get("font-family")
        font_size = item.get("font-size")
        if font_family is not None and not isinstance(font_family, str):
            msg = "SWINGSet document font family must be text"
            raise TypeError(msg)
        if font_size is not None and not isinstance(font_size, int):
            msg = "SWINGSet document font size must be an integer"
            raise TypeError(msg)
        spans.append(
            RichTextSpan(
                start,
                end,
                RichTextStyle(
                    bold=bool(item.get("bold", False)),
                    italic=bool(item.get("italic", False)),
                    underline=bool(item.get("underline", False)),
                    foreground=_decode_color(item.get("foreground")),
                    background=_decode_color(item.get("background")),
                    font_family=font_family,
                    font_size=font_size,
                ),
            ),
        )
    return StyledText(text, tuple(spans))


class _WordPad:
    @staticmethod
    def _button_action(
        action: Callable[[], None],
    ) -> Callable[[ActionEvent[Button]], None]:
        def invoke(_event: ActionEvent[Button]) -> None:
            action()

        return invoke

    @staticmethod
    def _menu_action(
        action: Callable[[], None],
    ) -> Callable[[ActionEvent[MenuItem]], None]:
        def invoke(_event: ActionEvent[MenuItem]) -> None:
            action()

        return invoke

    def _add_menu_item(
        self,
        menu: Menu,
        text: str,
        action: Callable[[], None],
    ) -> MenuItem:
        return menu.add(text, self._menu_action(action))

    def _add_toolbar_button(
        self,
        toolbar: ToolBar,
        text: str,
        action: Callable[[], None],
        width: int,
    ) -> Button:
        button = toolbar.add_button(text, self._button_action(action))
        button.width = width
        return button

    def _build_command_bar(self) -> None:
        self._add_toolbar_button(self.command_bar, "New", self.new_document, 64)
        self._add_toolbar_button(self.command_bar, "Open", self.open_document, 64)
        self._add_toolbar_button(self.command_bar, "Save", self.save_document, 64)
        find_label = self.command_bar.add(Label("Find"))
        find_label.width = 36
        self.find_field.width = 150
        self.command_bar.add(self.find_field)
        self._add_toolbar_button(self.command_bar, "Next", self.find_next, 60)

    def _build_format_bar(self) -> None:
        font_label = self.format_bar.add(Label("Font"))
        font_label.width = 36
        self.fonts.width = 130
        self.format_bar.add(self.fonts)
        self.font_size.width = 64
        self.format_bar.add(self.font_size)
        self._add_toolbar_button(self.format_bar, "Apply", self.apply_font, 60)
        self._add_toolbar_button(
            self.format_bar,
            "B",
            lambda: self.apply_selection_style(RichTextStyle(bold=True)),
            36,
        )
        self._add_toolbar_button(
            self.format_bar,
            "I",
            lambda: self.apply_selection_style(RichTextStyle(italic=True)),
            36,
        )
        self._add_toolbar_button(
            self.format_bar,
            "U",
            lambda: self.apply_selection_style(RichTextStyle(underline=True)),
            36,
        )
        self.colors.width = 120
        self.format_bar.add(self.colors)
        self._add_toolbar_button(self.format_bar, "Color", self.apply_color, 60)
        self._add_toolbar_button(
            self.format_bar,
            "Clear styles",
            self.clear_formatting,
            96,
        )

    def _build_menu(self) -> None:
        menu_bar = MenuBar()
        file_menu = menu_bar.add(Menu("&File"))
        self._add_menu_item(file_menu, "&New", self.new_document)
        self._add_menu_item(file_menu, "&Open...", self.open_document)
        self._add_menu_item(file_menu, "&Save", self.save_document)
        self._add_menu_item(file_menu, "Save &As...", self.save_document_as)
        file_menu.add_separator()
        self._add_menu_item(file_menu, "E&xit", self.frame.dispose)

        edit_menu = menu_bar.add(Menu("&Edit"))
        self._add_menu_item(edit_menu, "Select &All", self.select_all)
        self._add_menu_item(edit_menu, "&Find Next", self.find_next)
        self._add_menu_item(edit_menu, "Clear &Formatting", self.clear_formatting)

        format_menu = menu_bar.add(Menu("F&ormat"))
        self._add_menu_item(
            format_menu,
            "&Bold",
            lambda: self.apply_selection_style(RichTextStyle(bold=True)),
        )
        self._add_menu_item(
            format_menu,
            "&Italic",
            lambda: self.apply_selection_style(RichTextStyle(italic=True)),
        )
        self._add_menu_item(
            format_menu,
            "&Underline",
            lambda: self.apply_selection_style(RichTextStyle(underline=True)),
        )
        format_menu.add_separator()
        self._add_menu_item(
            format_menu,
            "Light theme",
            lambda: self.set_theme(Theme.LIGHT),
        )
        self._add_menu_item(
            format_menu,
            "Dark theme",
            lambda: self.set_theme(Theme.DARK),
        )
        self._add_menu_item(
            format_menu,
            "Classic theme",
            lambda: self.set_theme(Theme.CLASSIC),
        )

        help_menu = menu_bar.add(Menu("&Help"))
        self._add_menu_item(help_menu, "&About", self.show_about)
        self.frame.menu_bar = menu_bar

    def _update_status(self, message: str) -> None:
        text = self.editor.text
        start, end = self.editor.selection_range
        self.status.text = (
            f"{message}   |   {len(text.split())} words   |   {len(text)} characters"
            f"   |   selection {start}:{end}"
        )

    def _load_welcome_document(self) -> None:
        self.editor.set_markdown(
            "# SWINGSet WordPad\n\n"
            "A portable rich-text editor built from ordinary SWINGSet components.\n\n"
            "- Select text, then use **B**, *I*, U, or Color.\n"
            "- Open Markdown or text files.\n"
            "- Save rich documents as `.swingdoc`.\n\n"
            "Try the Find box, font controls, themes, menus, and native dialogs.",
        )
        heading_end = len("SWINGSet WordPad")
        self.editor.add_style(
            0,
            heading_end,
            RichTextStyle(bold=True, foreground="accent"),
        )
        self.editor.selection_range = (0, 0)
        self._update_status("Welcome")

    def __init__(self) -> None:
        self.frame = Frame("Untitled - SWINGSet WordPad")
        self.frame.size = Size(1040, 700)
        self.frame.minimum_size = Size(760, 500)
        self.current_path: Path | None = None

        chrome = self.frame.add(Panel(), BorderLayout.NORTH)
        chrome.layout = BoxLayout(BoxAxis.Y, gap=2)
        chrome.height = 76
        self.command_bar = chrome.add(ToolBar())
        self.format_bar = chrome.add(ToolBar())

        self.editor = self.frame.add(
            RichTextPane(rows=28, columns=100),
            BorderLayout.CENTER,
        )
        self.editor.background = "background"
        self.editor.foreground = "foreground"
        self.status = self.frame.add(StatusBar("Ready"), BorderLayout.SOUTH)

        self.find_field = TextField(columns=14)
        self.fonts = ComboBox(["Segoe UI", "Georgia", "Consolas"])
        self.font_size = Spinner(minimum=8, maximum=48, value=11)
        self.colors = ComboBox(["foreground", "accent", "#b42318", "#087a55"])

        self._build_command_bar()
        self._build_format_bar()
        self._build_menu()
        self._load_welcome_document()

    def _notify(self, message: str, *, error: bool = False) -> None:
        self._update_status(message)
        if App.supports(Capability.MESSAGE_DIALOGS):
            MessageBox.show(
                message,
                "SWINGSet WordPad",
                icon=MessageIcon.ERROR if error else MessageIcon.INFORMATION,
                owner=self.frame,
            )

    def _set_path(self, path: Path | None) -> None:
        self.current_path = path
        name = "Untitled" if path is None else path.name
        self.frame.title = f"{name} - SWINGSet WordPad"

    def new_document(self) -> None:
        self.editor.text = ""
        self.editor.selection_range = (0, 0)
        self._set_path(None)
        self._update_status("New document")
        self.editor.focus()

    def open_document(self) -> None:
        if not App.supports(Capability.FILE_DIALOGS):
            self._notify("The active backend does not provide file dialogs.")
            return
        path = OpenFileDialog(title="Open document", filters=_DOCUMENT_FILTERS).show(
            self.frame,
        )
        if path is None:
            return
        try:
            source = path.read_text(encoding="utf-8")
            if path.suffix.lower() == ".swingdoc":
                self.editor.set_styled_text(_styled_document(source))
            elif path.suffix.lower() in {".md", ".markdown"}:
                self.editor.set_markdown(source)
            else:
                self.editor.text = source
        except (OSError, UnicodeError, TypeError, ValueError) as error:
            self._notify(f"Could not open {path.name}: {error}", error=True)
            return
        self.editor.selection_range = (0, 0)
        self._set_path(path)
        self._update_status(f"Opened {path.name}")

    def _write_document(self, path: Path) -> None:
        try:
            content = (
                _document_json(self.editor)
                if path.suffix.lower() == ".swingdoc"
                else self.editor.text
            )
            path.write_text(content, encoding="utf-8")
        except (OSError, UnicodeError) as error:
            self._notify(f"Could not save {path.name}: {error}", error=True)
            return
        self._set_path(path)
        self._update_status(f"Saved {path.name}")

    def save_document(self) -> None:
        if self.current_path is None:
            self.save_document_as()
            return
        self._write_document(self.current_path)

    def save_document_as(self) -> None:
        if not App.supports(Capability.FILE_DIALOGS):
            self._notify("The active backend does not provide file dialogs.")
            return
        path = SaveFileDialog(title="Save document", filters=_DOCUMENT_FILTERS).show(
            self.frame,
        )
        if path is not None:
            self._write_document(path)

    def select_all(self) -> None:
        text = self.editor.text
        self.editor.selection_range = (0, len(text))
        self._update_status("Selected all")
        self.editor.focus()

    def find_next(self) -> None:
        query = self.find_field.text
        if not query:
            self._update_status("Enter text to find")
            return
        text = self.editor.text
        _start, selection_end = self.editor.selection_range
        index = text.casefold().find(query.casefold(), selection_end)
        if index < 0:
            index = text.casefold().find(query.casefold())
        if index < 0:
            self._update_status(f'No match for "{query}"')
            return
        self.editor.selection_range = (index, index + len(query))
        self._update_status(f'Found "{query}"')
        self.editor.focus()

    def apply_selection_style(self, style: RichTextStyle) -> None:
        if self.editor.apply_style_to_selection(style) is None:
            self._update_status("Select text before applying formatting")
            return
        self._update_status("Formatted selection")
        self.editor.focus()

    def apply_color(self) -> None:
        color = self.colors.selected_item or "foreground"
        self.apply_selection_style(RichTextStyle(foreground=color))

    def clear_formatting(self) -> None:
        self.editor.clear_styles()
        self._update_status("Cleared document formatting")
        self.editor.focus()

    def apply_font(self) -> None:
        face = self.fonts.selected_item or "Segoe UI"
        self.apply_selection_style(
            RichTextStyle(font_family=face, font_size=self.font_size.value),
        )

    def set_theme(self, theme: Theme) -> None:
        App.set_theme(theme)
        self._update_status(f"Theme: {theme.value}")

    def show_about(self) -> None:
        self._notify(
            "SWINGSet WordPad demonstrates portable menus, toolbars, dialogs, "
            "layouts, themes, rich selections, styled spans, and file I/O.",
        )

    def show(self) -> None:
        self.frame.visible = True
        self.editor.focus()


def build() -> None:
    """Build and show the complete WordPad example."""
    _WordPad().show()


if __name__ == "__main__":
    App.configure(backend="auto")
    App.run(build)
