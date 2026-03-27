from __future__ import annotations
from pathlib import Path

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Button, Input, Label, RadioButton, RadioSet

from ..dicom_reader import DicomStudy
from ..exporter import default_output_path, export_csv, export_json
from ._base_modal import EscapeModal


class ExportModal(EscapeModal[None]):
    """Modal for configuring and triggering a metadata export."""

    DEFAULT_CSS = EscapeModal.DEFAULT_CSS + """
    ExportModal > Vertical {
        width: 60;
        height: auto;
    }
    """

    def __init__(
        self,
        all_studies: list[DicomStudy],
        current_study: DicomStudy | None,
        active_tags: list[str],
    ) -> None:
        super().__init__()
        self._all_studies = all_studies
        self._current_study = current_study
        self._active_tags = active_tags

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label("Export scope:")
            with RadioSet(id="scope"):
                yield RadioButton("Current study", value=True, id="scope-current")
                yield RadioButton("All studies in directory", id="scope-all")
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
        if event.radio_set.id == "format":
            ext = "json" if event.index == 1 else "csv"
            current = self.query_one("#output-path", Input).value
            self.query_one("#output-path", Input).value = str(
                Path(current).with_suffix(f".{ext}")
            )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel":
            self.dismiss(None)
        elif event.button.id == "confirm":
            self._do_export()

    def _do_export(self) -> None:
        scope_radio = self.query_one("#scope", RadioSet)
        fmt_radio = self.query_one("#format", RadioSet)
        output = Path(self.query_one("#output-path", Input).value.strip())

        use_all = scope_radio.pressed_index == 1
        use_json = fmt_radio.pressed_index == 1

        studies = self._all_studies if use_all else (
            [self._current_study] if self._current_study else []
        )
        if not studies:
            self.query_one("#error-label", Label).update("No study selected.")
            return

        try:
            if use_json:
                export_json(studies, self._active_tags, output)
            else:
                export_csv(studies, self._active_tags, output)
            self.app.notify(f"Export saved to {output}")
            self.dismiss(None)
        except Exception as exc:
            self.query_one("#error-label", Label).update(f"Export failed: {exc}")
