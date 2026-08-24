"""Tkinter/ttk backend implemented as typed component peers."""

from __future__ import annotations

import contextlib
import queue
import threading
import tkinter as tk
from collections.abc import Callable
from io import BytesIO
from tkinter import font as tkfont
from tkinter import ttk
from typing import cast

from PIL import Image as PillowImage
from PIL import ImageTk

import swingset.core as swingset_core
import swingset.widgets as swingset_widgets
from swingset.core import Component
from swingset.geometry import Rect
from swingset.geometry import Size
from swingset.imaging import ImageResource
from swingset.menu import Menu
from swingset.menu import MenuBar
from swingset.models import CellChanged
from swingset.models import Insert
from swingset.models import ModelEvent
from swingset.models import Remove
from swingset.models import Reset
from swingset.models import RowInserted
from swingset.models import RowRemoved
from swingset.peers import BooleanPeer
from swingset.peers import ComponentPeer
from swingset.peers import IntValuePeer
from swingset.peers import PasswordPeer
from swingset.peers import RichTextPeer
from swingset.peers import SelectionPeer
from swingset.peers import WindowPeer
from swingset.theme import ColorInput
from swingset.theme import Theme
from swingset.theme import resolve_color
from swingset.widgets import Button
from swingset.widgets import CheckBox
from swingset.widgets import ComboBox
from swingset.widgets import ListBox
from swingset.widgets import ProgressBar
from swingset.widgets import Slider
from swingset.widgets import SplitPane
from swingset.widgets import TabbedPane
from swingset.widgets import Table
from swingset.widgets import TreeNode
from swingset.widgets import TreeView

from .base import Backend
from .base import Capability


def _set_icon_photo(window: tk.Toplevel, photo: ImageTk.PhotoImage) -> None:
    set_icon = cast("Callable[[bool, str], None]", window.iconphoto)
    default = True
    set_icon(default, str(photo))


class TkPeer(ComponentPeer):
    """Common ttk peer mechanics."""

    def _mouse_event(self, event: tk.Event[tk.Misc]) -> None:
        button = int(getattr(event, "num", 0) or 0)
        wheel = int(getattr(event, "delta", 0) or 0)
        self.component.emit_mouse_event(event.x, event.y, button, wheel)

    def _key_event(self, event: tk.Event[tk.Misc]) -> None:
        char = event.char or None
        self.component.emit_key_event(event.keycode, char)

    def _bind_input(self) -> None:
        try:
            self.widget.bind("<Motion>", self._mouse_event, add="+")
            self.widget.bind("<ButtonPress>", self._mouse_event, add="+")
            self.widget.bind("<ButtonRelease>", self._mouse_event, add="+")
            self.widget.bind("<MouseWheel>", self._mouse_event, add="+")
            self.widget.bind("<KeyPress>", self._key_event, add="+")
            self.widget.bind("<KeyRelease>", self._key_event, add="+")
        except tk.TclError:
            pass

    def __init__(
        self,
        backend: TkinterBackend,
        component: Component,
        widget: tk.Widget | tk.Toplevel,
    ) -> None:
        """Initialize the instance."""
        super().__init__(component)
        self.backend = backend
        self.widget = widget
        self._managed_by_parent = False
        self._photo: ImageTk.PhotoImage | None = None
        self._tooltip_window: tk.Toplevel | None = None
        self._tooltip_text: str | None = None
        self._color_style_name: str | None = None
        self._bind_input()

    @property
    def native(self) -> object:
        """Return the native."""
        return self.widget

    @property
    def dpi(self) -> int:
        """Return the dpi."""
        try:
            return max(96, round(self.widget.winfo_fpixels("1i")))
        except tk.TclError:
            return 96

    @property
    def text(self) -> str:
        """Return the text."""
        try:
            value = self.widget.cget("text")
        except tk.TclError:
            return self.component.snapshot_text()
        return str(value)

    def manage_with_parent(self) -> None:
        """Mark this peer as parent-managed for geometry ownership."""
        self._managed_by_parent = True

    @text.setter
    def text(self, value: str) -> None:
        """Set the text."""
        with contextlib.suppress(tk.TclError):
            self.widget.configure({"text": value})

    def _hide_tooltip(self, _event: object | None = None) -> None:
        del _event
        if self._tooltip_window is not None:
            with contextlib.suppress(tk.TclError):
                self._tooltip_window.destroy()
            self._tooltip_window = None

    def destroy(self) -> None:
        """Update destroy."""
        self._hide_tooltip()
        with contextlib.suppress(tk.TclError):
            self.widget.destroy()

    def set_visible(self, *, visible: bool) -> None:
        """Set visible."""
        if isinstance(self.widget, tk.Toplevel):
            with contextlib.suppress(tk.TclError):
                self.widget.deiconify() if visible else self.widget.withdraw()
            return
        if self._managed_by_parent:
            return
        try:
            if visible:
                self.set_bounds(self.component.bounds)
            else:
                self.widget.place_forget()
        except tk.TclError:
            pass

    def set_enabled(self, *, enabled: bool) -> None:
        """Set enabled."""
        try:
            if isinstance(self.widget, ttk.Widget):
                self.widget.state(["!disabled"] if enabled else ["disabled"])
            else:
                self.widget.configure(
                    {"state": tk.NORMAL if enabled else tk.DISABLED},
                )
        except tk.TclError:
            pass

    def set_bounds(self, bounds: Rect) -> None:
        """Set bounds."""
        if isinstance(self.widget, tk.Toplevel):
            xpart = "" if bounds.x < 0 or bounds.y < 0 else f"+{bounds.x}+{bounds.y}"
            with contextlib.suppress(tk.TclError):
                self.widget.geometry(f"{bounds.width}x{bounds.height}{xpart}")
            return
        if self._managed_by_parent:
            return
        with contextlib.suppress(tk.TclError):
            self.widget.place(
                x=bounds.x,
                y=bounds.y,
                width=bounds.width,
                height=bounds.height,
            )

    def client_size(self) -> Size:
        """Return client size."""
        try:
            self.widget.update_idletasks()
            width = self.widget.winfo_width()
            height = self.widget.winfo_height()
            if width > 1 and height > 1:
                return Size(width, height)
        except tk.TclError:
            pass
        return self.component.size

    def focus(self) -> None:
        """Move keyboard focus to the native component."""
        with contextlib.suppress(tk.TclError):
            self.widget.focus_set()

    def set_font(self, face: str, size: int, *, bold: bool) -> None:
        """Set font."""
        try:
            font = tkfont.Font(
                family=face,
                size=size,
                weight="bold" if bold else "normal",
            )
            self.widget.configure({"font": font})
            self.backend.keep_resource(self.component, font)
        except tk.TclError:
            pass

    def _set_color(self, option: str, color: ColorInput) -> None:
        red, green, blue, _alpha = resolve_color(color, self.backend.theme)
        value = f"#{red:02x}{green:02x}{blue:02x}"
        with contextlib.suppress(tk.TclError):
            if isinstance(self.widget, ttk.Widget):
                if self._color_style_name is None:
                    base_style = (
                        str(self.widget.cget("style")) or self.widget.winfo_class()
                    )
                    self._color_style_name = f"SWINGSet{id(self)}.{base_style}"
                    self.widget.configure({"style": self._color_style_name})
                options = {option: value}
                if option == "background":
                    options["fieldbackground"] = value
                ttk.Style(self.widget).configure(self._color_style_name, **options)
            else:
                self.widget.configure({option: value})

    def set_foreground(self, color: ColorInput | None) -> None:
        """Apply a resolved text color to Tk and ttk widgets."""
        self._set_color("foreground", color or "foreground")

    def set_background(self, color: ColorInput | None) -> None:
        """Apply a resolved fill color to Tk and ttk widgets."""
        self._set_color("background", color or "background")

    def _show_tooltip(self, _event: object) -> None:
        if not self._tooltip_text or self._tooltip_window is not None:
            return
        window = tk.Toplevel(self.widget)
        override_redirect = True
        window.wm_overrideredirect(override_redirect)
        window.wm_geometry(
            f"+{self.widget.winfo_pointerx() + 12}+{self.widget.winfo_pointery() + 18}"
        )
        ttk.Label(window, text=self._tooltip_text, padding=(6, 3)).pack()
        self._tooltip_window = window

    def set_tooltip(self, text: str | None) -> None:
        """Bind a small native hover window to this widget."""
        self._hide_tooltip()
        self._tooltip_text = text
        with contextlib.suppress(tk.TclError):
            self.widget.unbind("<Enter>")
            self.widget.unbind("<Leave>")
            if text:
                self.widget.bind("<Enter>", self._show_tooltip, add="+")
                self.widget.bind("<Leave>", self._hide_tooltip, add="+")

    def apply_theme(self, theme: Theme) -> None:
        """Update apply theme."""
        self.backend.apply_theme(theme)

    def attach_child(self, child: ComponentPeer) -> None:
        """Update attach child."""
        del child

    def _set_image(self, image: ImageResource | None) -> None:
        if image is None:
            self._photo = None
            with contextlib.suppress(tk.TclError):
                self.widget.configure({"image": ""})
            return
        frame = image.rasterize(dpi=self.dpi, theme=self.backend.theme)
        with PillowImage.open(BytesIO(frame.png)) as source:
            self._photo = ImageTk.PhotoImage(source.convert("RGBA"))
        with contextlib.suppress(tk.TclError):
            self.widget.configure({"image": self._photo})


class TkWindowPeer(TkPeer, WindowPeer):
    """Tk top-level window peer."""

    def _resized(self, event: tk.Event[tk.Misc]) -> None:
        if event.widget is self.widget:
            cast("swingset_core.Container", self.component).handle_native_resize()

    def _close_requested(self) -> None:
        callback = getattr(self.component, "_request_close", None)
        if callable(callback):
            callback()
        else:
            self.component.destroy()

    def __init__(
        self,
        backend: TkinterBackend,
        component: Component,
        parent_peer: ComponentPeer | None,
    ) -> None:
        """Initialize the instance."""
        owner = parent_peer.native if isinstance(parent_peer, TkPeer) else backend.root
        master = owner if isinstance(owner, tk.Misc) else backend.root
        window = tk.Toplevel(master)
        super().__init__(backend, component, window)
        window.protocol("WM_DELETE_WINDOW", self._close_requested)
        window.bind("<Configure>", self._resized, add="+")

    @property
    def text(self) -> str:
        """Return the text."""
        window = cast("tk.Toplevel", self.widget)
        try:
            return window.title()
        except tk.TclError:
            return self.component.snapshot_text()

    @text.setter
    def text(self, value: str) -> None:
        """Set the text."""
        with contextlib.suppress(tk.TclError):
            cast("tk.Toplevel", self.widget).title(value)

    def destroy(self) -> None:
        """Update destroy."""
        super().destroy()
        self.backend.window_closed()

    def set_enabled(self, *, enabled: bool) -> None:
        # Tk has no fully portable window-level disabled state.
        """Set enabled."""
        with contextlib.suppress(tk.TclError):
            cast("tk.Toplevel", self.widget).attributes("-disabled", not enabled)

    def _build_menu(self, parent: tk.Menu, description: Menu) -> tk.Menu:
        menu = tk.Menu(parent, tearoff=False)
        for item in description.items:
            if item is None:
                menu.add_separator()
                continue
            menu.add_command(
                label=item.text,
                state=tk.NORMAL if item.enabled else tk.DISABLED,
                command=item.trigger_action,
            )
        return menu

    def set_menu(self, menu_bar: MenuBar | None) -> None:
        """Set menu."""
        window = cast("tk.Toplevel", self.widget)
        if menu_bar is None:
            with contextlib.suppress(tk.TclError):
                window.configure({"menu": ""})
            return
        menu = tk.Menu(window, tearoff=False)
        for top in menu_bar.menus:
            submenu = self._build_menu(menu, top)
            menu.add_cascade(label=top.text, menu=submenu)
        window.configure(menu=menu)
        self.backend.keep_resource(self.component, menu)

    def set_icon(self, image: ImageResource | None) -> None:
        """Set icon."""
        if image is None:
            return
        frame = image.rasterize(dpi=self.dpi, theme=self.backend.theme)
        with PillowImage.open(BytesIO(frame.png)) as source:
            photo = ImageTk.PhotoImage(source.convert("RGBA"))
        try:
            _set_icon_photo(cast("tk.Toplevel", self.widget), photo)
            self.backend.keep_resource(self.component, photo)
        except tk.TclError:
            pass


class TkContainerPeer(TkPeer):
    """Normal ttk container peer."""


class TkLabelPeer(TkPeer):
    """ttk label peer."""


class TkImageLabelPeer(TkLabelPeer):
    """Peer implementation for image label components."""

    def refresh(self) -> None:
        """Refresh native state from component state."""
        image = getattr(self.component, "image", None)
        self._set_image(image)


class TkButtonPeer(TkPeer):
    """Peer implementation for button components."""

    def refresh(self) -> None:
        """Refresh native state from component state."""
        image = getattr(self.component, "image", None)
        self._set_image(image)
        if image is not None:
            with contextlib.suppress(tk.TclError):
                self.widget.configure({"compound": tk.LEFT})


class TkCheckBoxPeer(TkPeer, BooleanPeer):
    """Peer implementation for check box components."""

    def __init__(
        self,
        backend: TkinterBackend,
        component: Component,
        widget: tk.Widget | tk.Toplevel,
        variable: tk.BooleanVar,
    ) -> None:
        """Initialize the instance."""
        super().__init__(backend, component, widget)
        self.variable = variable

    @property
    def selected(self) -> bool:
        """Return the selected."""
        return self.variable.get()

    @selected.setter
    def selected(self, value: bool) -> None:
        """Set the selected."""
        self.variable.set(value)

    def refresh(self) -> None:
        """Refresh native state from component state."""
        self.selected = cast("CheckBox", self.component).selected


class TkEntryPeer(TkPeer):
    """Peer implementation for entry components."""

    @property
    def text(self) -> str:
        """Return the text."""
        try:
            return cast("ttk.Entry", self.widget).get()
        except tk.TclError:
            return self.component.snapshot_text()

    @text.setter
    def text(self, value: str) -> None:
        """Set the text."""
        entry = cast("ttk.Entry", self.widget)
        try:
            entry.delete(0, tk.END)
            entry.insert(0, value)
        except tk.TclError:
            pass


class TkTextAreaPeer(TkPeer):
    """Peer implementation for text area components."""

    @property
    def text(self) -> str:
        """Return the text."""
        try:
            return cast("tk.Text", self.widget).get("1.0", "end-1c")
        except tk.TclError:
            return self.component.snapshot_text()

    @text.setter
    def text(self, value: str) -> None:
        """Set the text."""
        area = cast("tk.Text", self.widget)
        try:
            area.delete("1.0", tk.END)
            area.insert("1.0", value)
        except tk.TclError:
            pass


class TkPasswordPeer(TkEntryPeer, PasswordPeer):
    """Masked ttk entry peer."""

    def set_revealed(self, *, revealed: bool) -> None:
        """Toggle the entry's masking character."""
        with contextlib.suppress(tk.TclError):
            self.widget.configure({"show": "" if revealed else "●"})

    def refresh(self) -> None:
        """Synchronize text and reveal state."""
        super().refresh()
        control = cast("swingset_widgets.PasswordField", self.component)
        self.set_revealed(revealed=control.revealed)


class TkRichTextPeer(TkTextAreaPeer, RichTextPeer):
    """Tk text peer using tags for portable formatting spans."""

    @staticmethod
    def _color(value: swingset_widgets.ColorInput | None) -> str | None:
        if value is None:
            return None
        red, green, blue, _alpha = resolve_color(value)
        return f"#{red:02x}{green:02x}{blue:02x}"

    def apply_styles(self) -> None:
        """Translate portable spans into Tk text tags."""
        area = cast("tk.Text", self.widget)
        control = cast("swingset_widgets.RichTextPane", self.component)
        with contextlib.suppress(tk.TclError):
            for tag in area.tag_names():
                if tag.startswith("swingset-rich-"):
                    area.tag_delete(tag)
            for index, span in enumerate(control.styles):
                tag = f"swingset-rich-{index}"
                style = span.style
                font = tkfont.nametofont("TkDefaultFont").copy()
                if style.bold:
                    font.configure(weight="bold")
                if style.italic:
                    font.configure(slant="italic")
                if style.underline:
                    font.configure(underline=True)
                if style.font_family is not None:
                    font.configure(family=style.font_family)
                if style.font_size is not None:
                    font.configure(size=style.font_size)
                self.backend.keep_resource(self.component, font)
                foreground = self._color(style.foreground)
                background = self._color(style.background)
                area.tag_configure(
                    tag,
                    font=font,
                    foreground="" if foreground is None else foreground,
                    background="" if background is None else background,
                )
                area.tag_add(tag, f"1.0+{span.start}c", f"1.0+{span.end}c")

    def selection_range(self) -> tuple[int, int]:
        """Return the native Tk selection as character offsets."""
        area = cast("tk.Text", self.widget)
        try:
            start_count = area.count("1.0", "sel.first", "chars")
            end_count = area.count("1.0", "sel.last", "chars")
        except tk.TclError:
            return cast(
                "swingset_widgets.RichTextPane",
                self.component,
            ).initial_selection_range()
        if start_count is None or end_count is None:
            return cast(
                "swingset_widgets.RichTextPane",
                self.component,
            ).initial_selection_range()
        start = start_count[0]
        end = end_count[0]
        return start, end

    def set_selection_range(self, start: int, end: int) -> None:
        """Select native Tk text from portable character offsets."""
        area = cast("tk.Text", self.widget)
        with contextlib.suppress(tk.TclError):
            area.tag_remove(tk.SEL, "1.0", tk.END)
            area.tag_add(tk.SEL, f"1.0+{start}c", f"1.0+{end}c")

    def refresh(self) -> None:
        """Synchronize content, spans, and editable state."""
        area = cast("tk.Text", self.widget)
        control = cast("swingset_widgets.RichTextPane", self.component)
        with contextlib.suppress(tk.TclError):
            area.configure({"state": tk.NORMAL})
        super().refresh()
        self.apply_styles()
        start, end = control.initial_selection_range()
        self.set_selection_range(start, end)
        with contextlib.suppress(tk.TclError):
            area.configure({"state": tk.NORMAL if control.editable else tk.DISABLED})


class TkSpinnerPeer(TkPeer, IntValuePeer):
    """ttk spinbox integer-value peer."""

    @property
    def value(self) -> int:
        """Return the integer currently displayed by the spinbox."""
        try:
            return int(cast("ttk.Spinbox", self.widget).get())
        except tk.TclError, ValueError:
            return cast("swingset_widgets.Spinner", self.component).initial_value()

    @value.setter
    def value(self, value: int) -> None:
        spinbox = cast("ttk.Spinbox", self.widget)
        with contextlib.suppress(tk.TclError):
            spinbox.delete(0, tk.END)
            spinbox.insert(0, str(value))

    def refresh(self) -> None:
        """Synchronize the portable spinner value."""
        self.value = cast("swingset_widgets.Spinner", self.component).initial_value()


class TkScrollPeer(TkPeer):
    """Canvas viewport with native ttk scrollbars."""

    def __init__(
        self,
        backend: TkinterBackend,
        component: Component,
        canvas: tk.Canvas,
    ) -> None:
        """Create a canvas with horizontal and vertical scrollbars."""
        super().__init__(backend, component, canvas)
        self.horizontal = ttk.Scrollbar(
            canvas,
            orient=tk.HORIZONTAL,
            command=canvas.xview,
        )
        self.vertical = ttk.Scrollbar(canvas, orient=tk.VERTICAL, command=canvas.yview)
        canvas.configure(
            xscrollcommand=self.horizontal.set,
            yscrollcommand=self.vertical.set,
        )
        self._window: int | None = None

    def attach_child(self, child: ComponentPeer) -> None:
        """Embed the portable content widget into the canvas."""
        if not isinstance(child, TkPeer) or not isinstance(child.widget, tk.Widget):
            return
        child.manage_with_parent()
        content = cast("swingset_widgets.ScrollPane", self.component).content
        if content is None:
            return
        self._window = cast("tk.Canvas", self.widget).create_window(
            0,
            0,
            anchor=tk.NW,
            window=child.widget,
            width=content.width,
            height=content.height,
        )

    def set_bounds(self, bounds: Rect) -> None:
        """Size the canvas and overlay its native scrollbars."""
        super().set_bounds(bounds)
        scrollbar_size = 14
        with contextlib.suppress(tk.TclError):
            self.horizontal.place(
                x=0,
                y=max(0, bounds.height - scrollbar_size),
                width=max(0, bounds.width - scrollbar_size),
                height=scrollbar_size,
            )
            self.vertical.place(
                x=max(0, bounds.width - scrollbar_size),
                y=0,
                width=scrollbar_size,
                height=max(0, bounds.height - scrollbar_size),
            )

    def refresh(self) -> None:
        """Synchronize the scroll region and viewport offsets."""
        super().refresh()
        pane = cast("swingset_widgets.ScrollPane", self.component)
        content = pane.content
        if content is None:
            return
        canvas = cast("tk.Canvas", self.widget)
        x, y = pane.scroll_position
        with contextlib.suppress(tk.TclError):
            canvas.configure(scrollregion=(0, 0, content.width, content.height))
            canvas.xview_moveto(x / max(1, content.width))
            canvas.yview_moveto(y / max(1, content.height))


class TkComboPeer(TkPeer, SelectionPeer):
    """Peer implementation for combo components."""

    @property
    def selected_index(self) -> int:
        """Return the selected index."""
        try:
            return cast("ttk.Combobox", self.widget).current()
        except tk.TclError:
            return -1

    @selected_index.setter
    def selected_index(self, index: int) -> None:
        """Set the selected index."""
        with contextlib.suppress(tk.TclError):
            cast("ttk.Combobox", self.widget).current(index)

    def refresh(self) -> None:
        """Refresh native state from component state."""
        component = cast("ComboBox[object]", self.component)
        combo = cast("ttk.Combobox", self.widget)
        combo.configure(values=[str(item) for item in component.model])
        if component.model.selected_index >= 0:
            self.selected_index = component.model.selected_index

    def on_model_event(self, event: ModelEvent) -> None:
        """Handle a model event update."""
        del event
        self.refresh()


class TkListPeer(TkPeer, SelectionPeer):
    """Peer implementation for list components."""

    @property
    def selected_index(self) -> int:
        """Return the selected index."""
        try:
            selection = cast("tk.Listbox", self.widget).curselection()
        except tk.TclError:
            return -1
        return int(selection[0]) if selection else -1

    @selected_index.setter
    def selected_index(self, index: int) -> None:
        """Set the selected index."""
        listbox = cast("tk.Listbox", self.widget)
        try:
            listbox.selection_clear(0, tk.END)
            if index >= 0:
                listbox.selection_set(index)
                listbox.activate(index)
        except tk.TclError:
            pass

    def refresh(self) -> None:
        """Refresh native state from component state."""
        component = cast("ListBox[object]", self.component)
        listbox = cast("tk.Listbox", self.widget)
        listbox.delete(0, tk.END)
        for item in component.model:
            listbox.insert(tk.END, str(item))
        initial_index = component.initial_selected_index()
        if initial_index >= 0:
            self.selected_index = initial_index

    def on_model_event(self, event: ModelEvent) -> None:
        """Handle a model event update."""
        listbox = cast("tk.Listbox", self.widget)
        component = cast("ListBox[object]", self.component)
        try:
            if isinstance(event, Insert):
                for offset in range(event.count):
                    listbox.insert(
                        event.index + offset,
                        str(component.model[event.index + offset]),
                    )
                return
            if isinstance(event, Remove):
                listbox.delete(event.index, event.index + event.count - 1)
                return
        except tk.TclError:
            pass
        self.refresh()


class TkTablePeer(TkPeer):
    """Peer implementation for table components."""

    def refresh(self) -> None:
        """Refresh native state from component state."""
        component = cast("Table", self.component)
        tree = cast("ttk.Treeview", self.widget)
        tree.delete(*tree.get_children())
        tree.configure(
            columns=[str(index) for index in range(len(component.model.columns))],
        )
        tree["show"] = "headings"
        for index, title in enumerate(component.model.columns):
            column = str(index)
            tree.heading(column, text=title)
            tree.column(column, width=100, stretch=True)
        for row in component.model:
            tree.insert("", tk.END, values=[str(value) for value in row])

    def on_model_event(self, event: ModelEvent) -> None:
        """Handle a model event update."""
        tree = cast("ttk.Treeview", self.widget)
        component = cast("Table", self.component)
        try:
            if isinstance(event, CellChanged):
                items = tree.get_children()
                if event.row < len(items):
                    tree.item(
                        items[event.row],
                        values=[str(v) for v in component.model[event.row]],
                    )
                    return
            if isinstance(event, RowInserted):
                tree.insert("", event.index, values=[str(v) for v in event.values])
                return
            if isinstance(event, RowRemoved):
                items = tree.get_children()
                if event.index < len(items):
                    tree.delete(items[event.index])
                    return
            if isinstance(event, Reset):
                self.refresh()
                return
        except tk.TclError:
            pass
        self.refresh()


class TkTreePeer(TkPeer):
    """Peer implementation for tree components."""

    def _add_node(self, tree: ttk.Treeview, parent: str, node: TreeNode) -> None:
        item = tree.insert(parent, tk.END, text=node.text)
        for child in node:
            self._add_node(tree, item, child)

    def refresh(self) -> None:
        """Refresh native state from component state."""
        component = cast("TreeView", self.component)
        tree = cast("ttk.Treeview", self.widget)
        tree.delete(*tree.get_children())
        for node in component.roots:
            self._add_node(tree, "", node)


class TkTabPeer(TkPeer, SelectionPeer):
    """Peer implementation for tab components."""

    @property
    def selected_index(self) -> int:
        """Return the selected index."""
        notebook = cast("ttk.Notebook", self.widget)
        try:
            current = notebook.select()
            return int(notebook.index(current)) if current else -1
        except tk.TclError:
            return -1

    @selected_index.setter
    def selected_index(self, index: int) -> None:
        """Set the selected index."""
        with contextlib.suppress(tk.TclError):
            cast("ttk.Notebook", self.widget).select(index)

    def attach_child(self, child: ComponentPeer) -> None:
        """Update attach child."""
        if not isinstance(child, TkPeer):
            return
        child.manage_with_parent()
        component = cast("TabbedPane", self.component)
        title = next(
            (title for title, item in component.tabs if item is child.component),
            "Tab",
        )
        if isinstance(child.widget, tk.Widget):
            with contextlib.suppress(tk.TclError):
                cast("ttk.Notebook", self.widget).add(child.widget, text=title)

    def refresh(self) -> None:
        """Refresh native state from component state."""
        component = cast("TabbedPane", self.component)
        if component.tabs:
            self.selected_index = min(
                component.initial_selected_index(),
                len(component.tabs) - 1,
            )


class TkSplitPeer(TkPeer):
    """Peer implementation for split components."""

    def attach_child(self, child: ComponentPeer) -> None:
        """Update attach child."""
        if not isinstance(child, TkPeer):
            return
        child.manage_with_parent()
        if isinstance(child.widget, tk.Widget):
            with contextlib.suppress(tk.TclError):
                cast("ttk.Panedwindow", self.widget).add(child.widget, weight=1)


class TkIntValuePeer(TkPeer, IntValuePeer):
    """Peer implementation for int value components."""

    @property
    def value(self) -> int:
        """Return the value."""
        try:
            return int(float(self.widget.cget("value")))
        except tk.TclError, ValueError:
            return cast("ProgressBar", self.component).initial_value()

    @value.setter
    def value(self, value: int) -> None:
        """Set the value."""
        with contextlib.suppress(tk.TclError):
            self.widget.configure({"value": value})


class TkSliderPeer(TkPeer, IntValuePeer):
    """Peer implementation for slider components."""

    @property
    def value(self) -> int:
        """Return the value."""
        try:
            return round(cast("ttk.Scale", self.widget).get())
        except tk.TclError, ValueError:
            return cast("Slider", self.component).initial_value()

    @value.setter
    def value(self, value: int) -> None:
        """Set the value."""
        with contextlib.suppress(tk.TclError):
            cast("ttk.Scale", self.widget).set(value)

    def refresh(self) -> None:
        """Refresh native state from component state."""
        self.value = cast("Slider", self.component).initial_value()


class TkinterBackend(Backend):
    """Desktop fallback backend using Tk and themed ttk widgets."""

    name = "tkinter"
    capabilities = frozenset(
        {
            Capability.DARK_MODE,
            Capability.SVG,
            Capability.WINDOW_ICON,
            Capability.MENUS,
            Capability.TABLE,
            Capability.TREE,
            Capability.TABS,
            Capability.SPLIT_PANE,
            Capability.SCROLL_PANE,
            Capability.TOOLBAR,
            Capability.STATUS_BAR,
            Capability.DPI_AWARE,
            Capability.RICH_TEXT,
            Capability.TOOLTIPS,
        },
    )

    def __init__(self) -> None:
        """Initialize the instance."""
        super().__init__()
        self.root: tk.Tk | None = None
        self._queue: queue.Queue[Callable[[], object]] = queue.Queue()
        self._thread_id: int | None = None
        self._windows = 0
        self._resources: dict[int, list[object]] = {}
        self.theme = Theme.SYSTEM

    def _root(self) -> tk.Tk:
        if self.root is None:
            msg = "Tkinter backend is not initialized"
            raise RuntimeError(msg)
        return self.root

    def _master(self, parent_peer: ComponentPeer | None) -> tk.Misc:
        if isinstance(parent_peer, TkPeer):
            return parent_peer.widget
        return self._root()

    def _window_factory(
        self,
        component: Component,
        parent: ComponentPeer | None,
    ) -> ComponentPeer:
        self.initialize()
        self._windows += 1
        return TkWindowPeer(self, component, parent)

    def _container_factory(
        self,
        component: Component,
        parent: ComponentPeer | None,
    ) -> ComponentPeer:
        widget = ttk.Frame(self._master(parent))
        return TkContainerPeer(self, component, widget)

    def _label_factory(
        self,
        component: Component,
        parent: ComponentPeer | None,
    ) -> ComponentPeer:
        return TkLabelPeer(
            self,
            component,
            ttk.Label(self._master(parent), text=component.snapshot_text()),
        )

    def _image_label_factory(
        self,
        component: Component,
        parent: ComponentPeer | None,
    ) -> ComponentPeer:
        widget = ttk.Label(self._master(parent), text=component.snapshot_text())
        return TkImageLabelPeer(self, component, widget)

    def _button_factory(
        self,
        component: Component,
        parent: ComponentPeer | None,
    ) -> ComponentPeer:
        callback = cast("Button", component).trigger_action
        widget = ttk.Button(
            self._master(parent),
            text=component.snapshot_text(),
            command=callback,
        )
        return TkButtonPeer(self, component, widget)

    def _checkbox_factory(
        self,
        component: Component,
        parent: ComponentPeer | None,
    ) -> ComponentPeer:
        control = cast("CheckBox", component)
        variable = tk.BooleanVar(master=self._master(parent), value=control.selected)
        widget = ttk.Checkbutton(
            self._master(parent),
            text=control.snapshot_text(),
            variable=variable,
            command=control.trigger_action,
        )
        return TkCheckBoxPeer(self, component, widget, variable)

    def _entry_factory(
        self,
        component: Component,
        parent: ComponentPeer | None,
    ) -> ComponentPeer:
        widget = ttk.Entry(self._master(parent))
        return TkEntryPeer(self, component, widget)

    def _password_factory(
        self,
        component: Component,
        parent: ComponentPeer | None,
    ) -> ComponentPeer:
        widget = ttk.Entry(self._master(parent), show="●")
        return TkPasswordPeer(self, component, widget)

    def _text_area_factory(
        self,
        component: Component,
        parent: ComponentPeer | None,
    ) -> ComponentPeer:
        widget = tk.Text(self._master(parent), wrap=tk.WORD)
        return TkTextAreaPeer(self, component, widget)

    def _rich_text_factory(
        self,
        component: Component,
        parent: ComponentPeer | None,
    ) -> ComponentPeer:
        widget = tk.Text(self._master(parent), wrap=tk.WORD)
        return TkRichTextPeer(self, component, widget)

    def _spinner_factory(
        self,
        component: Component,
        parent: ComponentPeer | None,
    ) -> ComponentPeer:
        control = cast("swingset_widgets.Spinner", component)

        def changed() -> None:
            try:
                control.notify_value_changed(int(widget.get()))
            except tk.TclError, ValueError:
                return

        widget = ttk.Spinbox(
            self._master(parent),
            from_=control.minimum,
            to=control.maximum,
            increment=control.step,
            command=changed,
        )
        widget.bind("<Return>", lambda _event: changed())
        widget.bind("<FocusOut>", lambda _event: changed())
        return TkSpinnerPeer(self, component, widget)

    def _separator_factory(
        self,
        component: Component,
        parent: ComponentPeer | None,
    ) -> ComponentPeer:
        control = cast("swingset_widgets.Separator", component)
        orientation = (
            tk.HORIZONTAL
            if control.orientation is swingset_widgets.SeparatorOrientation.HORIZONTAL
            else tk.VERTICAL
        )
        return TkPeer(
            self,
            component,
            ttk.Separator(self._master(parent), orient=orientation),
        )

    def _scroll_factory(
        self,
        component: Component,
        parent: ComponentPeer | None,
    ) -> ComponentPeer:
        canvas = tk.Canvas(self._master(parent), highlightthickness=0)
        return TkScrollPeer(self, component, canvas)

    def _combo_factory(
        self,
        component: Component,
        parent: ComponentPeer | None,
    ) -> ComponentPeer:
        control = cast("ComboBox[object]", component)
        widget = ttk.Combobox(self._master(parent), state="readonly")
        peer = TkComboPeer(self, component, widget)
        widget.bind(
            "<<ComboboxSelected>>",
            lambda _event: control.notify_selection(peer.selected_index),
        )
        return peer

    def _list_factory(
        self,
        component: Component,
        parent: ComponentPeer | None,
    ) -> ComponentPeer:
        control = cast("ListBox[object]", component)
        widget = tk.Listbox(self._master(parent), exportselection=False)
        peer = TkListPeer(self, component, widget)
        widget.bind(
            "<<ListboxSelect>>",
            lambda _event: control.notify_selection(peer.selected_index),
        )
        return peer

    def _table_factory(
        self,
        component: Component,
        parent: ComponentPeer | None,
    ) -> ComponentPeer:
        return TkTablePeer(
            self,
            component,
            ttk.Treeview(self._master(parent), show="headings"),
        )

    def _tree_factory(
        self,
        component: Component,
        parent: ComponentPeer | None,
    ) -> ComponentPeer:
        return TkTreePeer(
            self,
            component,
            ttk.Treeview(self._master(parent), show="tree"),
        )

    def _tab_factory(
        self,
        component: Component,
        parent: ComponentPeer | None,
    ) -> ComponentPeer:
        notebook = ttk.Notebook(self._master(parent))
        control = cast("TabbedPane", component)
        peer = TkTabPeer(self, component, notebook)
        notebook.bind(
            "<<NotebookTabChanged>>",
            lambda _event: control.sync_selected_index_from_peer(peer.selected_index),
        )
        return peer

    def _split_factory(
        self,
        component: Component,
        parent: ComponentPeer | None,
    ) -> ComponentPeer:
        control = cast("SplitPane", component)
        orient = (
            tk.HORIZONTAL
            if control.orientation is swingset_widgets.SplitOrientation.HORIZONTAL
            else tk.VERTICAL
        )
        return TkSplitPeer(
            self,
            component,
            ttk.Panedwindow(self._master(parent), orient=orient),
        )

    def _progress_factory(
        self,
        component: Component,
        parent: ComponentPeer | None,
    ) -> ComponentPeer:
        control = cast("ProgressBar", component)
        widget = ttk.Progressbar(
            self._master(parent),
            mode="determinate",
            maximum=max(control.minimum + 1, control.maximum),
            value=control.initial_value(),
        )
        return TkIntValuePeer(self, component, widget)

    def _slider_factory(
        self,
        component: Component,
        parent: ComponentPeer | None,
    ) -> ComponentPeer:
        control = cast("Slider", component)

        def changed(value: str) -> None:
            control.notify_value_changed(round(float(value)))

        widget = ttk.Scale(
            self._master(parent),
            from_=control.minimum,
            to=control.maximum,
            command=changed,
        )
        return TkSliderPeer(self, component, widget)

    def install_factories(self) -> None:
        """Update install factories."""
        self.register_peer(swingset_core.Window, self._window_factory)
        self.register_peer(swingset_widgets.TabbedPane, self._tab_factory)
        self.register_peer(swingset_widgets.SplitPane, self._split_factory)
        self.register_peer(swingset_widgets.ScrollPane, self._scroll_factory)
        self.register_peer(swingset_widgets.ToolBar, self._container_factory)
        self.register_peer(swingset_widgets.Panel, self._container_factory)
        self.register_peer(swingset_core.Container, self._container_factory)
        self.register_peer(swingset_widgets.CheckBox, self._checkbox_factory)
        self.register_peer(swingset_widgets.Button, self._button_factory)
        self.register_peer(swingset_widgets.ImageLabel, self._image_label_factory)
        self.register_peer(swingset_widgets.StatusBar, self._label_factory)
        self.register_peer(swingset_widgets.Label, self._label_factory)
        self.register_peer(swingset_widgets.PasswordField, self._password_factory)
        self.register_peer(swingset_widgets.RichTextPane, self._rich_text_factory)
        self.register_peer(swingset_widgets.Separator, self._separator_factory)
        self.register_peer(swingset_widgets.TextArea, self._text_area_factory)
        self.register_peer(swingset_widgets.TextField, self._entry_factory)
        self.register_peer(swingset_widgets.ComboBox, self._combo_factory)
        self.register_peer(swingset_widgets.ListBox, self._list_factory)
        self.register_peer(swingset_widgets.Table, self._table_factory)
        self.register_peer(swingset_widgets.TreeView, self._tree_factory)
        self.register_peer(swingset_widgets.ProgressBar, self._progress_factory)
        self.register_peer(swingset_widgets.Slider, self._slider_factory)
        self.register_peer(swingset_widgets.Spinner, self._spinner_factory)

    def initialize(self) -> None:
        """Initialize backend resources."""
        if self.root is not None:
            return
        self.root = tk.Tk()
        self.root.withdraw()

    def _drain(self) -> None:
        while True:
            try:
                callback = self._queue.get_nowait()
            except queue.Empty:
                break
            callback()

    def run(self, startup: Callable[[], object] | None = None) -> None:
        """Run the backend event loop."""
        self.initialize()
        root = self._root()
        self._thread_id = threading.get_ident()
        root.after(0, self._drain)
        if startup is not None:
            self._queue.put(startup)
        try:
            root.mainloop()
        finally:
            self._thread_id = None

    def call_soon(self, callback: Callable[[], object]) -> None:
        """Schedule a callback on the UI thread."""
        self._queue.put(callback)
        root = self.root
        if root is not None:
            with contextlib.suppress(tk.TclError):
                root.after(0, self._drain)

    def keep_resource(self, component: Component, resource: object) -> None:
        """Update keep resource."""
        self._resources.setdefault(id(component), []).append(resource)

    def window_closed(self) -> None:
        """Update window closed."""
        self._windows = max(0, self._windows - 1)
        if self._windows == 0 and self.root is not None:
            with contextlib.suppress(tk.TclError):
                self.root.quit()

    def apply_theme(self, theme: Theme) -> None:
        """Update apply theme."""
        self.theme = theme
        root = self.root
        if root is None:
            return
        try:
            style = ttk.Style(root)
            # Best effort: use built-in themes; do not pretend this is native dark mode.
            if theme is Theme.LIGHT and "clam" in style.theme_names():
                style.theme_use("clam")
        except tk.TclError:
            pass
