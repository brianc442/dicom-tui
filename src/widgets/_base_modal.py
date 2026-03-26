from __future__ import annotations
from typing import TypeVar

from textual.screen import ModalScreen

_T = TypeVar("_T")


class EscapeModal(ModalScreen[_T]):
    """ModalScreen that dismisses with None on Escape."""

    DEFAULT_CSS = """
    EscapeModal {
        align: center middle;
    }
    EscapeModal > Vertical {
        border: solid $primary;
        padding: 1 2;
        background: $surface;
    }
    """

    def on_key(self, event) -> None:
        if event.key == "escape":
            self.dismiss(None)
