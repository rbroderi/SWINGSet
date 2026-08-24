"""Switch between named pages managed by CardLayout."""

from swingset import App
from swingset import BorderLayout
from swingset import Button
from swingset import CardLayout
from swingset import Frame
from swingset import Label
from swingset import Panel
from swingset import Size


def card(title: str, detail: str) -> Panel:
    """Create one card page."""
    page = Panel()
    page.add(Label(title).set_font(size=16, bold=True))
    page.add(Label(detail))
    return page


def build() -> None:
    """Build the CardLayout example."""
    frame = Frame("CardLayout example")
    frame.size = Size(500, 320)
    frame.layout = BorderLayout(vgap=8)

    cards = Panel()
    card_layout = CardLayout()
    cards.layout = card_layout
    cards.add(card("Welcome", "This is the first named card."), "welcome")
    cards.add(card("Profile", "This page could contain account fields."), "profile")
    cards.add(card("Finish", "The final card completes the sequence."), "finish")
    frame.add(cards, BorderLayout.CENTER)

    navigation = Panel()
    navigation.height = 42
    previous = navigation.add(Button("Previous"))
    next_card = navigation.add(Button("Next"))
    previous.on_click(lambda _event: card_layout.previous(cards))
    next_card.on_click(lambda _event: card_layout.next(cards))
    frame.add(navigation, BorderLayout.SOUTH)
    frame.visible = True


def build_toml() -> str:
    """Return the backend-independent TOML form of this example."""
    return """[config.app]
entry-window = "main"
[widgets.main]
type = "Window"
title = "Card Layout"
children = ["cards"]
[widgets.cards]
type = "CardLayout"
children = ["first", "second"]
[widgets.first]
type = "Label"
text = "First card"
constraint = "first"
[widgets.second]
type = "Label"
text = "Second card"
constraint = "second"
"""


if __name__ == "__main__":
    App.configure(backend="win32")
    App.run(build)
