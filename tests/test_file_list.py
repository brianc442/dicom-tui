from __future__ import annotations
import pytest
from pathlib import Path
from textual.app import App, ComposeResult
from tests.conftest import make_minimal_dicom
from src.widgets.file_list import FileListPanel


class ScanTestApp(App):
    def compose(self) -> ComposeResult:
        yield FileListPanel()


@pytest.mark.asyncio
async def test_scan_populates_files(tmp_path):
    make_minimal_dicom(tmp_path / "IM000001")
    make_minimal_dicom(tmp_path / "IM000002")
    (tmp_path / "notes.txt").write_text("not a dicom")

    app = ScanTestApp()
    async with app.run_test() as pilot:
        panel = app.query_one(FileListPanel)
        panel.scan(tmp_path)
        await pilot.pause(1.0)
        assert len(panel.files) == 2
        names = {p.name for p in panel.files}
        assert names == {"IM000001", "IM000002"}


@pytest.mark.asyncio
async def test_scan_empty_directory(tmp_path):
    app = ScanTestApp()
    async with app.run_test() as pilot:
        panel = app.query_one(FileListPanel)
        panel.scan(tmp_path)
        await pilot.pause(1.0)
        assert panel.files == []


@pytest.mark.asyncio
async def test_scan_second_call_supersedes_first(tmp_path):
    dir1 = tmp_path / "dir1"
    dir1.mkdir()
    dir2 = tmp_path / "dir2"
    dir2.mkdir()
    make_minimal_dicom(dir1 / "scan_a")
    make_minimal_dicom(dir2 / "scan_b")

    app = ScanTestApp()
    async with app.run_test() as pilot:
        panel = app.query_one(FileListPanel)
        panel.scan(dir1)
        panel.scan(dir2)   # immediately supersedes dir1 scan via scan_id
        await pilot.pause(1.0)
        names = {p.name for p in panel.files}
        assert "scan_b" in names
        assert "scan_a" not in names


@pytest.mark.asyncio
async def test_scan_recursive_finds_nested_dicoms(tmp_path):
    sub = tmp_path / "series"
    sub.mkdir()
    make_minimal_dicom(tmp_path / "root_scan")
    make_minimal_dicom(sub / "nested_scan")

    app = ScanTestApp()
    async with app.run_test() as pilot:
        panel = app.query_one(FileListPanel)
        panel.scan(tmp_path, recursive=True)
        await pilot.pause(1.0)
        names = {p.name for p in panel.files}
        assert "root_scan" in names
        assert "nested_scan" in names
