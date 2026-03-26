from __future__ import annotations
from pathlib import Path

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label


class DirectoryModal(ModalScreen[Path | None]):
    """Modal for changing the current directory."""

    DEFAULT_CSS = """
    DirectoryModal {
        align: center middle;
    }
    DirectoryModal > Vertical {
        width: 60;
        height: auto;
        border: solid $primary;
        padding: 1 2;
        background: $surface;
    }
    """

    def __init__(self, current_dir: Path) -> None:
        super().__init__()
        self._current_dir = current_dir

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label("Enter directory path:")
            yield Input(value=str(self._current_dir), id="path-input")
            yield Label("", id="error-label", classes="error")
            yield Button("Open", variant="primary", id="confirm")
            yield Button("Cancel", id="cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel":
            self.dismiss(None)
        elif event.button.id == "confirm":
            self._try_confirm()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        # Handles Enter key while the Input widget has focus
        self._try_confirm()

    def on_key(self, event) -> None:
        if event.key == "escape":
            self.dismiss(None)

    def _try_confirm(self) -> None:
        path_str = self.query_one("#path-input", Input).value.strip()
        path = Path(path_str)
        if path.is_dir():
            self.dismiss(path)
        else:
            self.query_one("#error-label", Label).update(
                f"Not a valid directory: {path_str}"
            )
