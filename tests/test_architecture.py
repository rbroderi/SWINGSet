"""Architecture and compatibility tests for core SWINGSet contracts."""

import gc
import threading
import warnings
import weakref
from collections.abc import Callable
from unittest.mock import patch

import pytest

import swingset
from swingset import Backend
from swingset import Button
from swingset import Capability
from swingset import CellChanged
from swingset import Component
from swingset import ComponentPeer
from swingset import ComponentState
from swingset import Frame
from swingset import Graphics
from swingset import Insert
from swingset import Label
from swingset import ListModel
from swingset import MessageBox
from swingset import MessageButtons
from swingset import MessageResult
from swingset import NullComponentPeer
from swingset import PaintEvent
from swingset import PaintSurface
from swingset import Panel
from swingset import Point
from swingset import RadioButton
from swingset import RadioGroup
from swingset import Rect
from swingset import Size
from swingset import TableModel
from swingset import Theme
from swingset import Timer
from swingset import UIContext
from swingset import UnsupportedComponentError
from swingset import palette_for
from swingset.backends import runtime


class FakePeer(ComponentPeer):
    """Test peer capturing lifecycle and geometry calls."""

    def __init__(self, component: Component) -> None:
        """Initialize test tracking state for a component peer."""
        super().__init__(component)
        self._native = object()
        self.destroyed = False
        self.last_bounds = component.bounds

    @property
    def native(self) -> object:
        """Return the fake native handle."""
        return self._native

    def destroy(self) -> None:
        """Record that destruction was requested."""
        self.destroyed = True

    def set_bounds(self, bounds: Rect) -> None:
        """Record the latest bounds forwarded to the peer."""
        self.last_bounds = bounds

    def client_size(self) -> Size:
        """Report the component's current logical size."""
        return self.component.size


class FakeBackend(Backend):
    """Minimal backend used to exercise architecture contracts."""

    name = "fake"
    capabilities = frozenset({Capability.TABLE})

    def install_factories(self) -> None:
        """Register fake peers for generic components."""
        self.register_peer(Component, lambda component, _parent: FakePeer(component))

    def initialize(self) -> None:
        """No-op backend initialization for tests."""
        return

    def run(self, startup: Callable[[], object] | None = None) -> None:
        """Execute startup immediately in the test thread."""
        if startup is not None:
            startup()

    def call_soon(self, callback: Callable[[], object]) -> None:
        """Run callbacks immediately for deterministic tests."""
        callback()

    def trigger_idle(self) -> None:
        """Emit an idle event for deterministic tests."""
        self._emit_idle()


class FakeTkinterBackend(FakeBackend):
    """Fake backend carrying Tkinter's runtime selection name."""

    name = "tkinter"


class FakeDialogBackend(FakeBackend):
    """Fake backend recording portable dialog delegation."""

    def show_message(
        self,
        owner: object | None,
        title: str,
        message: str,
        buttons: str,
        icon: str,
    ) -> str:
        """Return a deterministic result after validating forwarded options."""
        del owner, icon
        assert title == "Question"
        assert message == "Continue?"
        assert buttons == "yes_no"
        return "yes"

    def choose_color(
        self,
        owner: object | None,
        initial: tuple[int, int, int],
    ) -> tuple[int, int, int] | None:
        """Return a deterministic color after validating delegation."""
        del owner
        assert initial == (10, 20, 30)
        return 30, 20, 10

    def choose_font(
        self,
        owner: object | None,
        initial: tuple[str, int, bool, bool],
    ) -> tuple[str, int, bool, bool] | None:
        """Return a deterministic font after validating delegation."""
        del owner
        assert initial == ("Segoe UI", 9, False, False)
        return "Consolas", 11, True, False

    def choose_page_setup(
        self,
        owner: object | None,
        margins: tuple[int, int, int, int],
    ) -> tuple[int, int, int, int] | None:
        """Return deterministic margins after validating delegation."""
        del owner
        assert margins == (1000, 1000, 1000, 1000)
        return 500, 600, 700, 800

    def choose_print(
        self,
        owner: object | None,
        pages: tuple[int, int],
        copies: int,
    ) -> tuple[int, int, int] | None:
        """Return deterministic print settings after validating delegation."""
        expected_copies = 2
        del owner
        assert pages == (1, 3)
        assert copies == expected_copies
        return 2, 3, 4


class FakeGraphics(Graphics):
    """No-op graphics implementation for paint-event contract tests."""

    def draw_line(
        self,
        start: Point,
        end: Point,
        *,
        color: swingset.ColorInput = "foreground",
        width: int = 1,
    ) -> None:
        """Accept a line operation."""
        del start, end, color, width

    def draw_rectangle(
        self,
        bounds: Rect,
        *,
        color: swingset.ColorInput = "foreground",
        width: int = 1,
    ) -> None:
        """Accept a rectangle operation."""
        del bounds, color, width

    def fill_rectangle(
        self,
        bounds: Rect,
        *,
        color: swingset.ColorInput = "background",
    ) -> None:
        """Accept a fill operation."""
        del bounds, color

    def draw_text(
        self,
        text: str,
        x: int,
        y: int,
        *,
        color: swingset.ColorInput = "foreground",
    ) -> None:
        """Accept a text operation."""
        del text, x, y, color


def _assert_destroyed(component: Component) -> None:
    assert component.state is ComponentState.DESTROYED


def _size_attribute_name() -> str:
    return "size"


def test_peer_bridge_and_lifecycle() -> None:
    """Components mount, forward bounds, and dispose through peers."""
    context = UIContext(FakeBackend())
    frame = Frame("Test", context=context)
    child = frame.add(Button("Go"))
    frame.visible = True
    assert frame.state is ComponentState.MOUNTED
    assert child.state is ComponentState.MOUNTED
    peer = child.peer
    assert isinstance(peer, FakePeer)
    child.bounds = Rect(1, 2, 30, 40)
    assert peer.last_bounds == Rect(1, 2, 30, 40)
    assert context.windows.open_count == 1
    frame.dispose()
    _assert_destroyed(frame)
    _assert_destroyed(child)
    assert context.windows.open_count == 0


def test_active_dispatcher_enforces_mounted_ui_thread_confinement() -> None:
    """Mounted peer state rejects workers while unmounted construction remains legal."""
    context = UIContext(FakeBackend())
    frame = Frame(context=context)
    button = frame.add(Button("Original"))
    failures: list[RuntimeError] = []
    constructed: list[str] = []

    context.dispatcher.enter_ui_thread()
    try:
        frame.visible = True

        def worker() -> None:
            constructed.append(Button("Worker").snapshot_text())
            try:
                button.text = "Changed"
            except RuntimeError as error:
                failures.append(error)

        thread = threading.Thread(target=worker)
        thread.start()
        thread.join()

        assert constructed == ["Worker"]
        assert len(failures) == 1
        assert "UI thread" in str(failures[0])
        assert button.snapshot_text() == "Original"
        frame.destroy()
    finally:
        context.dispatcher.leave_ui_thread()


def test_box_layout_stacks_children_and_fills_cross_axis() -> None:
    """BoxLayout keeps preferred major sizes and fills the cross axis."""
    frame = Frame(context=UIContext(FakeBackend()))
    frame.size = Size(300, 180)
    frame.layout = swingset.BoxLayout(swingset.BoxAxis.Y, gap=6)
    first = frame.add(Button("First"))
    second = frame.add(Button("Second"))

    frame.visible = True

    assert first.bounds == Rect(0, 0, 300, 28)
    assert second.bounds == Rect(0, 34, 300, 28)


def test_layout_measurement_pack_and_recursive_resize() -> None:
    """Preferred measurement packs windows and nested layouts follow resize."""
    frame = Frame(context=UIContext(FakeBackend()))
    frame.layout = swingset.BoxLayout(swingset.BoxAxis.Y, gap=6)
    first = frame.add(Button("First"))
    second = frame.add(Button("Second"))

    frame.pack()
    assert frame.size == Size(90, 62)
    frame.visible = True
    assert first.bounds == Rect(0, 0, 90, 28)
    assert second.bounds == Rect(0, 34, 90, 28)

    outer = Frame(context=UIContext(FakeBackend()))
    content = outer.add(Panel())
    content.layout = swingset.BoxLayout(swingset.BoxAxis.Y)
    child = content.add(Button("Nested"))
    initial_width = 300
    resized_width = 420
    outer.size = Size(initial_width, 180)
    outer.visible = True
    assert content.bounds == Rect(0, 0, 300, 180)
    assert child.bounds.width == initial_width

    outer.size = Size(resized_width, 240)
    assert content.bounds == Rect(0, 0, 420, 240)
    assert child.bounds.width == resized_width

    child.bounds = Rect(0, 0, 1, 1)
    outer.handle_native_resize()
    assert child.bounds.width == resized_width


@pytest.mark.parametrize(
    "layout",
    [
        swingset.FlowLayout(hgap=0, vgap=0),
        swingset.BoxLayout(gap=0),
        swingset.CardLayout(),
        swingset.BorderLayout(hgap=0, vgap=0),
        swingset.GridLayout(rows=1, cols=1, hgap=0, vgap=0),
        swingset.GridBagLayout(),
    ],
)
def test_layouts_measure_minimum_preferred_and_maximum_sizes(
    layout: swingset.LayoutManager,
) -> None:
    """Every built-in layout measures all three component size contracts."""
    frame = Frame(context=UIContext(FakeBackend()))
    frame.layout = layout
    child = frame.add(Button("Measured"))
    child.minimum_size = Size(40, 20)
    child.preferred_size = Size(80, 40)
    child.maximum_size = Size(160, 80)

    minimum = frame.minimum_size
    preferred = frame.preferred_size
    maximum = frame.maximum_size

    assert minimum.width <= preferred.width <= maximum.width
    assert minimum.height <= preferred.height <= maximum.height


def test_size_constraints_validate_clamp_and_pack() -> None:
    """Component size overrides remain coherent and constrain window packing."""
    frame = Frame(context=UIContext(FakeBackend()))
    child = frame.add(Button("Constrained"))
    child.minimum_size = Size(140, 36)
    child.maximum_size = Size(180, 60)
    child.preferred_size = Size(100, 100)

    assert child.preferred_size == Size(140, 60)
    frame.pack()
    assert frame.size == Size(140, 60)
    with pytest.raises(ValueError, match="smaller than minimum"):
        child.maximum_size = Size(120, 30)


def test_card_layout_switches_named_cards() -> None:
    """CardLayout sizes one named card and hides all other cards."""
    frame = Frame(context=UIContext(FakeBackend()))
    frame.size = Size(320, 200)
    layout = swingset.CardLayout()
    frame.layout = layout
    first = frame.add(Panel(), "first")
    second = frame.add(Panel(), "second")
    frame.visible = True

    layout.show(frame, "second")

    assert not first.visible
    assert second.visible
    assert second.bounds == Rect(0, 0, 320, 200)
    assert layout.selected_name == "second"


def test_grid_bag_layout_honors_fill_constraint() -> None:
    """GridBagLayout preserves preferred height for horizontal-only fill."""
    frame = Frame(context=UIContext(FakeBackend()))
    frame.size = Size(300, 180)
    frame.layout = swingset.GridBagLayout()
    child = frame.add(
        Button("Horizontal"),
        swingset.GridBagConstraints(
            weightx=1.0,
            weighty=1.0,
            fill=swingset.Fill.HORIZONTAL,
            inset=10,
        ),
    )

    frame.visible = True

    assert child.bounds == Rect(10, 76, 280, 28)


def test_spinner_clamps_steps_and_notifies() -> None:
    """Spinner enforces its range and emits effective value changes."""
    spinner = swingset.Spinner(minimum=0, maximum=10, value=8, step=3)
    received: list[int] = []
    spinner.on_change(received.append)

    spinner.increment()
    spinner.decrement()

    expected_value = 7
    assert spinner.value == expected_value
    assert received == [10, expected_value]


def test_scroll_pane_clamps_and_positions_content() -> None:
    """ScrollPane moves oversized content within its clipped viewport."""
    content = Panel()
    content.size = Size(500, 400)
    pane = swingset.ScrollPane(content)
    pane.size = Size(200, 150)
    frame = Frame(context=UIContext(FakeBackend()))
    frame.size = Size(200, 150)
    frame.add(pane)
    frame.visible = True

    pane.scroll_to(999, 999)

    assert pane.scroll_position == (300, 250)
    assert content.location == Point(-300, -250)


def test_password_tooltip_and_rich_text_portable_state() -> None:
    """New text components retain masking, tooltip, and formatting state."""
    password = swingset.PasswordField("secret")
    password.tooltip = "Required"
    rich_text = swingset.RichTextPane("Hello world")
    style = swingset.RichTextStyle(bold=True, foreground="accent")

    span = rich_text.add_style(0, 5, style)

    assert not password.revealed
    assert password.tooltip == "Required"
    assert span == swingset.RichTextSpan(0, 5, style)
    with pytest.raises(ValueError, match="outside"):
        rich_text.add_style(4, 99, style)


def test_panel_uses_flow_layout_by_default() -> None:
    """Panel children receive distinct left-to-right bounds when mounted."""
    context = UIContext(FakeBackend())
    frame = Frame("Test", context=context)
    panel = frame.add(Panel())
    first = panel.add(Label("First"))
    second = panel.add(Button("Second"))

    frame.visible = True

    assert first.x < second.x
    assert first.x + first.width <= second.x


def test_classic_theme_uses_windows_95_palette() -> None:
    """Classic theme exposes the expected gray face and navy accent colors."""
    palette = palette_for(Theme.CLASSIC)

    assert palette.background == (192, 192, 192, 255)
    assert palette.accent == (0, 0, 128, 255)


def test_radio_group_keeps_exactly_one_selection() -> None:
    """Selecting a radio button clears the other members of its group."""
    group = RadioGroup()
    first = RadioButton("First", group=group, selected=True)
    second = RadioButton("Second", group=group)

    second.selected = True

    assert not first.selected
    assert second.selected
    assert group.selected is second

    group.clear()
    assert first.group is None
    assert second.group is None
    assert group.selected is None


def test_tab_page_retains_requested_background() -> None:
    """Tabbed panes retain per-page color metadata for capable backends."""
    tabs = swingset.TabbedPane()
    page = swingset.Panel()

    tabs.add_tab("Red", page, background=(255, 0, 0))

    assert tabs.page_background(page) == (255, 0, 0)


def test_tabbed_pane_owns_and_mutates_complete_tab_records() -> None:
    """Tab metadata, selection, and child ownership remain synchronized."""
    tabs = swingset.TabbedPane()
    first = tabs.add_tab("First", swingset.Panel())
    second = tabs.add_tab("Second", swingset.Panel())

    tabs.selected_index = 1
    tabs.set_tab_title(second, "Renamed")
    tabs.set_tab_background(1, "accent")

    assert tabs.tabs == [("First", first), ("Renamed", second)]
    assert tabs.tab_title(1) == "Renamed"
    assert tabs.page_background(second) == "accent"
    assert tabs.remove_tab(0) is first
    assert tabs.selected_index == 0
    with pytest.raises(IndexError):
        tabs.selected_index = 1
    with pytest.raises(TypeError, match=r"add_tab\(\)"):
        tabs.add(swingset.Panel())


def test_current_interpreter_exposes_windows_version_info() -> None:
    """The selected Python executable has a readable Windows version resource."""
    info = swingset.read_windows_version_info()

    assert info.path.exists()
    assert info.file_version is not None


def test_message_box_delegates_to_active_backend() -> None:
    """MessageBox forwards portable options and converts the native result."""
    frame = Frame(context=UIContext(FakeDialogBackend()))

    result = MessageBox.show(
        "Continue?",
        "Question",
        buttons=MessageButtons.YES_NO,
        owner=frame,
    )

    assert result is MessageResult.YES


def test_native_common_dialogs_delegate_typed_values() -> None:
    """Common-dialog facades convert backend tuples into public value types."""
    frame = Frame(context=UIContext(FakeDialogBackend()))

    assert swingset.ColorDialog((10, 20, 30)).show(frame) == (30, 20, 10)
    assert swingset.FontDialog().show(frame) == swingset.FontSpec(
        "Consolas", 11, bold=True
    )
    assert swingset.PageSetupDialog().show(frame) == swingset.PageMargins(
        500, 600, 700, 800
    )
    assert swingset.PrintDialog(swingset.PrintSettings(1, 3, 2)).show(
        frame
    ) == swingset.PrintSettings(2, 3, 4)


def test_application_idle_listener_uses_active_backend() -> None:
    """App idle listeners are owned and dispatched by the active backend."""
    backend = FakeBackend()
    frame = Frame(context=UIContext(backend))
    received: list[str] = []

    backend.on_idle(lambda: received.append("idle"))
    backend.trigger_idle()

    assert frame.context is not None
    assert received == ["idle"]


def test_paint_surface_dispatches_scoped_event() -> None:
    """Paint listeners receive the source, graphics object, and clip rectangle."""
    surface = PaintSurface()
    received: list[PaintEvent] = []
    surface.on_paint(received.append)
    graphics = FakeGraphics()
    clip = Rect(1, 2, 30, 40)

    surface.dispatch_paint(graphics, clip)

    assert received == [PaintEvent(surface, graphics, clip)]


def test_timer_rejects_non_positive_intervals() -> None:
    """Timers require a positive scheduling interval."""
    for interval in (0, -1):
        try:
            Timer(interval, lambda: None)
        except ValueError:
            pass
        else:
            msg = "non-positive timer interval must be rejected"
            raise AssertionError(msg)


def test_implicit_tkinter_selection_warns() -> None:
    """Automatic Tkinter fallback reports that it was not explicitly selected."""
    runtime.configure("auto")
    try:
        with (
            patch.object(runtime, "_candidate_names", return_value=("tkinter",)),
            patch.object(runtime, "_load_backend", return_value=FakeTkinterBackend()),
            warnings.catch_warnings(record=True) as caught,
        ):
            warnings.simplefilter("always")
            runtime.get_context()
    finally:
        runtime.configure("auto")

    assert len(caught) == 1
    assert caught[0].category is RuntimeWarning
    assert "configure backend='tkinter'" in str(caught[0].message)


def test_explicit_tkinter_selection_does_not_warn() -> None:
    """Explicit Tkinter selection remains quiet."""
    runtime.configure("tkinter")
    try:
        with (
            patch.object(runtime, "_candidate_names", return_value=("tkinter",)),
            patch.object(runtime, "_load_backend", return_value=FakeTkinterBackend()),
            warnings.catch_warnings(record=True) as caught,
        ):
            warnings.simplefilter("always")
            runtime.get_context()
    finally:
        runtime.configure("auto")

    assert not caught


def test_models_publish_granular_events() -> None:
    """List and table models emit typed granular change events."""
    items = ListModel(["a"])
    item_events: list[object] = []
    subscription = items.subscribe(item_events.append)
    items.add("b")
    assert isinstance(item_events[-1], Insert)
    subscription.dispose()

    table = TableModel([[1]], ["value"])
    table_events: list[object] = []
    table.subscribe(table_events.append)
    table.set_value_at(2, 0, 0)
    assert isinstance(table_events[-1], CellChanged)


def test_combo_box_model_repairs_selection_after_mutation() -> None:
    """List mutation preserves a valid selected item and index."""
    model = swingset.ComboBoxModel(["a", "b", "c"])
    model.set_selected_index(2)

    model.pop(0)
    assert model.selected_index == 1
    assert model.selected_item == "c"

    model.pop(1)
    assert model.selected_index == 0
    assert model.selected_item == "b"

    events: list[object] = []
    model.subscribe(events.append)
    model.replace(0, "replacement")
    assert isinstance(events[-1], swingset.SelectionChanged)
    assert model.selected_item == "replacement"

    empty = swingset.ComboBoxModel[str]()
    empty.add("first")
    assert empty.selected_index == 0


def test_component_ownership_rejects_invalid_mutation() -> None:
    """Containers, tabs, and radio groups retain one coherent owner."""
    panel = Panel()
    orphan = Button("orphan")
    with pytest.raises(ValueError, match="not a child"):
        panel.remove(orphan)
    assert orphan.state is ComponentState.NEW

    child = panel.add(Button("child"))
    with pytest.raises(ValueError, match="already a child"):
        panel.add(child)

    tabs = swingset.TabbedPane()
    page = tabs.add_tab("Page", Button("page"))
    tabs.remove(page)
    assert tabs.tabs == []
    assert list(tabs) == []

    button = RadioButton("choice", selected=True)
    first = RadioGroup()
    second = RadioGroup()
    first.add(button)
    second.add(button)
    assert first.selected is None
    assert second.selected is button
    assert button.group is second


def test_weak_subscription_does_not_retain_bound_listener() -> None:
    """Bound listeners are weakly referenced and can be collected."""
    model = ListModel(["a"])

    class Listener:
        def on_change(self, _event: object) -> None:
            return

    listener = Listener()
    reference = weakref.ref(listener)
    model.subscribe(listener.on_change)
    del listener
    gc.collect()
    assert reference() is None
    model.add("b")


def test_null_peer_is_explicit_opt_in() -> None:
    """Null peers are allowed only for components opting in explicitly."""

    class SparseBackend(FakeBackend):
        def install_factories(self) -> None:
            return

    class OptionalComponent(Component):
        allow_null_peer = True

    backend = SparseBackend()
    try:
        backend.create_peer(Component(), None)
    except UnsupportedComponentError:
        pass
    else:
        msg = "required components must not silently become null peers"
        raise AssertionError(msg)

    peer = backend.create_peer(OptionalComponent(), None)
    assert isinstance(peer, NullComponentPeer)


def test_historical_compatibility_api_is_removed() -> None:
    """Legacy Swing-style exports and aliases remain removed."""
    removed_exports = {
        "JButton",
        "JDialog",
        "JFrame",
        "JLabel",
        "JPanel",
        "SwingUtilities",
        "ThemeManager",
        "NativeControl",
        "SvgIcon",
        "Bitmap",
        "Icon",
    }
    for name in removed_exports:
        assert not hasattr(swingset, name)

    button_control = Button("Go")
    assert not hasattr(button_control, "setText")
    assert not hasattr(button_control, "getText")
    assert not hasattr(button_control, "addActionListener")
    assert not hasattr(button_control, "kind")
    assert not hasattr(button_control, "native")
    assert not hasattr(button_control, "hwnd")

    for old_backend_name in ("tk", "tui", "rich"):
        try:
            swingset.App.configure(backend=old_backend_name)
        except ValueError:
            pass
        else:
            msg = f"legacy backend alias {old_backend_name!r} must be rejected"
            raise AssertionError(
                msg,
            )


def test_geometry_properties_require_value_objects() -> None:
    """Geometry properties reject tuple assignment in favor of value objects."""
    component = Component()
    attribute = _size_attribute_name()

    try:
        setattr(component, attribute, (120, 30))
    except TypeError:
        pass
    else:
        msg = "tuple geometry must not be accepted"
        raise AssertionError(msg)


def test_menu_bar_runtime_annotation_resolves() -> None:
    """Menu bars remain assignable through Beartype's cyclic type reference."""
    frame = Frame()
    menu_bar = swingset.MenuBar()

    frame.menu_bar = menu_bar

    assert frame.menu_bar is menu_bar
