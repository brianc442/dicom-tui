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
async def test_scan_shows_one_entry_per_folder_study(tmp_path):
    study_dir = tmp_path / "study1"
    study_dir.mkdir()
    make_minimal_dicom(study_dir / "Slice0001")

    app = ScanTestApp()
    async with app.run_test() as pilot:
        panel = app.query_one(FileListPanel)
        panel.scan(tmp_path)
        await pilot.pause(1.0)
        assert len(panel.studies) == 1
        assert panel.studies[0].display_name == "study1"
        assert panel.studies[0].is_dir is True


@pytest.mark.asyncio
async def test_scan_shows_one_entry_per_standalone_dcm(tmp_path):
    make_minimal_dicom(tmp_path / "export.dcm")

    app = ScanTestApp()
    async with app.run_test() as pilot:
        panel = app.query_one(FileListPanel)
        panel.scan(tmp_path)
        await pilot.pause(1.0)
        assert len(panel.studies) == 1
        assert panel.studies[0].display_name == "export.dcm"
        assert panel.studies[0].is_dir is False


@pytest.mark.asyncio
async def test_scan_handles_deeply_nested_study(tmp_path):
    study_dir = tmp_path / "study1"
    deep = study_dir / "a" / "b" / "c"
    deep.mkdir(parents=True)
    make_minimal_dicom(deep / "00001DCM")

    app = ScanTestApp()
    async with app.run_test() as pilot:
        panel = app.query_one(FileListPanel)
        panel.scan(tmp_path)
        await pilot.pause(1.0)
        assert len(panel.studies) == 1
        assert panel.studies[0].display_name == "study1"


@pytest.mark.asyncio
async def test_scan_skips_non_dicom_folders(tmp_path):
    not_a_study = tmp_path / "not_a_study"
    not_a_study.mkdir()
    (not_a_study / "readme.txt").write_text("hello")

    app = ScanTestApp()
    async with app.run_test() as pilot:
        panel = app.query_one(FileListPanel)
        panel.scan(tmp_path)
        await pilot.pause(1.0)
        assert panel.studies == []


@pytest.mark.asyncio
async def test_scan_empty_directory(tmp_path):
    app = ScanTestApp()
    async with app.run_test() as pilot:
        panel = app.query_one(FileListPanel)
        panel.scan(tmp_path)
        await pilot.pause(1.0)
        assert panel.studies == []


@pytest.mark.asyncio
async def test_scan_mixed_folders_and_files(tmp_path):
    # One folder study + one standalone file study
    folder_study = tmp_path / "folder_study"
    folder_study.mkdir()
    make_minimal_dicom(folder_study / "Slice0001")
    make_minimal_dicom(tmp_path / "standalone.dcm")
    # One non-DICOM folder (should be excluded)
    empty_dir = tmp_path / "empty_dir"
    empty_dir.mkdir()

    app = ScanTestApp()
    async with app.run_test() as pilot:
        panel = app.query_one(FileListPanel)
        panel.scan(tmp_path)
        await pilot.pause(1.0)
        assert len(panel.studies) == 2
        names = {s.display_name for s in panel.studies}
        assert names == {"folder_study", "standalone.dcm"}


@pytest.mark.asyncio
async def test_scan_second_call_supersedes_first(tmp_path):
    dir1 = tmp_path / "dir1"
    dir1.mkdir()
    dir2 = tmp_path / "dir2"
    dir2.mkdir()
    study_a = dir1 / "study_a"
    study_a.mkdir()
    make_minimal_dicom(study_a / "Slice0001")
    study_b = dir2 / "study_b"
    study_b.mkdir()
    make_minimal_dicom(study_b / "Slice0001")

    app = ScanTestApp()
    async with app.run_test() as pilot:
        panel = app.query_one(FileListPanel)
        panel.scan(dir1)
        panel.scan(dir2)
        await pilot.pause(1.0)
        names = {s.display_name for s in panel.studies}
        assert "study_b" in names
        assert "study_a" not in names
