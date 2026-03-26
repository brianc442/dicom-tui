from __future__ import annotations
from pathlib import Path

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, RadioButton, RadioSet

from ..exporter import default_output_path, export_csv, export_json


class ExportModal(ModalScreen[None]):
    """Modal for configuring and triggering a metadata export."""

    DEFAULT_CSS = """
    ExportModal {
        align: center middle;
    }
    ExportModal > Vertical {
        width: 60;
        height: auto;
        border: solid $primary;
        padding: 1 2;
        background: $surface;
    }
    """

    def __init__(
        self,
        all_files: list[Path],
        current_file: Path | None,
        active_tags: list[str],
    ) -> None:
        super().__init__()
        self._all_files = all_files
        self._current_file = current_file
        self._active_tags = active_tags

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label("Export scope:")
            with RadioSet(id="scope"):
                yield RadioButton("Current file", value=True, id="scope-current")
                yield RadioButton("All files in directory", id="scope-all")
            yield Label("Format:")
            with RadioSet(id="format"):
                yield RadioButton("CSV", value=True, id="fmt-csv")
                yield RadioButton("JSON", id="fmt-json")
            yield Label("Output path:")
            yield Input(
                value=str(default_output_path("csv")),
                id="output-path",
            )
            yield Label("", id="error-label", classes="error")
            yield Button("Export", variant="primary", id="confirm")
            yield Button("Cancel", id="cancel")

    def on_radio_set_changed(self, event: RadioSet.Changed) -> None:
        # Keep output path extension in sync with format selection
        if event.radio_set.id == "format":
            ext = "json" if event.index == 1 else "csv"
            current = self.query_one("#output-path", Input).value
            if current.endswith(".csv") or current.endswith(".json"):
                base = current.rsplit(".", 1)[0]
                self.query_one("#output-path", Input).value = f"{base}.{ext}"

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel":
            self.dismiss(None)
        elif event.button.id == "confirm":
            self._do_export()

    def on_key(self, event) -> None:
        if event.key == "escape":
            self.dismiss(None)

    def _do_export(self) -> None:
        scope_radio = self.query_one("#scope", RadioSet)
        fmt_radio = self.query_one("#format", RadioSet)
        output = Path(self.query_one("#output-path", Input).value.strip())

        use_all = scope_radio.pressed_index == 1
        use_json = fmt_radio.pressed_index == 1

        files = self._all_files if use_all else (
            [self._current_file] if self._current_file else []
        )
        if not files:
            self.query_one("#error-label", Label).update("No file selected.")
            return

        try:
            if use_json:
                export_json(files, self._active_tags, output)
            else:
                export_csv(files, self._active_tags, output)
            self.app.notify(f"Export saved to {output}")
            self.dismiss(None)
        except Exception as exc:
            self.query_one("#error-label", Label).update(f"Export failed: {exc}")
