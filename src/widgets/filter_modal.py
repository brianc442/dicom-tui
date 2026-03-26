from __future__ import annotations
from pathlib import Path

from textual.app import ComposeResult
from textual.containers import ScrollableContainer, Vertical
from textual.widgets import Button, Checkbox, Label

from ..config import save_config
from ._base_modal import EscapeModal


class FilterModal(EscapeModal[list[str] | None]):
    """Modal for selecting which tags to display, with optional save-to-config."""

    DEFAULT_CSS = EscapeModal.DEFAULT_CSS + """
    FilterModal > Vertical {
        width: 50;
        height: 80%;
    }
    FilterModal ScrollableContainer {
        height: 1fr;
        border: solid $panel;
    }
    """

    def __init__(
        self,
        all_tags: list[str],
        active_include: list[str],
        config_path: Path | None,
    ) -> None:
        super().__init__()
        self._all_tags = all_tags
        self._active_set = set(active_include)
        self._config_path = config_path

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label("Select tags to display:")
            with ScrollableContainer():
                for i, tag in enumerate(self._all_tags):
                    yield Checkbox(
                        tag,
                        value=tag in self._active_set,
                        id=f"tag-{i}",
                    )
            yield Checkbox("Save selection to config", value=False, id="save-to-config")
            yield Button("Apply", variant="primary", id="confirm")
            yield Button("Cancel", id="cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel":
            self.dismiss(None)
        elif event.button.id == "confirm":
            include = [
                tag
                for i, tag in enumerate(self._all_tags)
                if self.query_one(f"#tag-{i}", Checkbox).value
            ]
            if self.query_one("#save-to-config", Checkbox).value:
                target = self._config_path or Path("config.toml")
                save_config(target, include)
            self.dismiss(include)

