from __future__ import annotations
from pathlib import Path

from textual.app import ComposeResult
from textual.message import Message
from textual.widget import Widget
from textual.widgets import Label, ListItem, ListView

from ..dicom_reader import (
    DicomStudy,
    INLINE_TAGS,
    build_inline_summary,
    filter_tags,
    find_representative,
    load_tags,
)


class FileListPanel(Widget):
    """Middle panel — scrollable list of DICOM studies in the selected directory."""

    DEFAULT_CSS = """
    FileListPanel #scan-status {
        display: none;
        color: $warning;
        padding: 0 1;
    }
    FileListPanel .study-name {
        color: $text;
    }
    FileListPanel .study-meta {
        color: $text-muted;
        padding-left: 2;
        text-style: dim;
    }
    """

    class FileSelected(Message):
        """Posted when the user highlights a different study."""

        def __init__(self, study: DicomStudy) -> None:
            super().__init__()
            self.study = study

    def __init__(self) -> None:
        super().__init__()
        self._study_map: dict[int, DicomStudy] = {}
        self._scan_id: int = 0
        self._item_map: dict[int, ListItem] = {}

    def compose(self) -> ComposeResult:
        yield Label("", id="scan-status")
        yield ListView()

    @property
    def studies(self) -> list[DicomStudy]:
        """Current list of confirmed DICOM studies in alphabetical order."""
        return [self._study_map[cid] for cid in sorted(self._study_map.keys())]

    def scan(self, path: Path) -> None:
        """Start a background scan of immediate children of `path`.

        Each immediate child that contains at least one DICOM file (anywhere
        in its subtree) becomes one study entry. Supersedes any in-flight scan.
        """
        self._scan_id += 1
        current_id = self._scan_id
        self._study_map = {}
        self._item_map = {}

        list_view = self.query_one(ListView)
        list_view.clear()

        status = self.query_one("#scan-status", Label)
        status.update("Scanning\u2026 (0 found)")
        status.display = True

        def _do_scan() -> None:
            candidate_id = 0
            try:
                children = sorted(path.iterdir(), key=lambda p: p.name.lower())
            except OSError:
                self.app.call_from_thread(self._on_scan_done, current_id)
                return

            for child in children:
                cid = candidate_id
                candidate_id += 1
                self.app.call_from_thread(
                    self._on_candidate_found, cid, child, current_id
                )
                representative = find_representative(child)
                if representative is None:
                    self.app.call_from_thread(
                        self._on_candidate_no_dicom, cid, current_id
                    )
                    continue
                study = DicomStudy(
                    display_name=child.name,
                    root_path=child,
                    representative=representative,
                    is_dir=child.is_dir(),
                )
                inline_tags = filter_tags(load_tags(representative), INLINE_TAGS)
                summary = build_inline_summary(inline_tags)
                self.app.call_from_thread(
                    self._on_study_ready, cid, study, summary, current_id
                )
            self.app.call_from_thread(self._on_scan_done, current_id)

        self.run_worker(_do_scan, thread=True, exit_on_error=False)

    def _on_candidate_found(
        self, candidate_id: int, child: Path, scan_id: int
    ) -> None:
        if scan_id != self._scan_id:
            return
        icon = "\U0001f4c2" if child.is_dir() else "\U0001f4c4"
        item = ListItem(
            Label(f"{icon} {child.name}", classes="study-name"),
            Label("loading\u2026", classes="study-meta"),
        )
        self._item_map[candidate_id] = item
        self.query_one(ListView).append(item)
        self.query_one("#scan-status", Label).update(
            f"Scanning\u2026 ({len(self._item_map)} found)"
        )

    def _on_candidate_no_dicom(self, candidate_id: int, scan_id: int) -> None:
        if scan_id != self._scan_id:
            return
        item = self._item_map.pop(candidate_id, None)
        if item is not None:
            item.remove()
            self.query_one("#scan-status", Label).update(
                f"Scanning\u2026 ({len(self._item_map)} found)"
            )

    def _on_study_ready(
        self,
        candidate_id: int,
        study: DicomStudy,
        summary: str,
        scan_id: int,
    ) -> None:
        if scan_id != self._scan_id:
            return
        self._study_map[candidate_id] = study
        item = self._item_map.get(candidate_id)
        if item is not None:
            item.query_one(".study-meta", Label).update(summary)

    def _on_scan_done(self, scan_id: int) -> None:
        if scan_id != self._scan_id:
            return
        status = self.query_one("#scan-status", Label)
        status.display = False
        if not self._study_map:
            self.query_one(ListView).append(
                ListItem(Label("No DICOM studies found"))
            )

    def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
        idx = self.query_one(ListView).index
        if idx is None:
            return
        visible_ids = sorted(self._item_map.keys())
        if 0 <= idx < len(visible_ids):
            study = self._study_map.get(visible_ids[idx])
            if study is not None:
                self.post_message(self.FileSelected(study))
