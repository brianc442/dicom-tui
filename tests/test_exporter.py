import csv
import json
import re
from pathlib import Path

import pytest
from tests.conftest import make_minimal_dicom
from src.dicom_reader import DicomStudy
from src.exporter import export_csv, export_json, default_output_path


TAGS = ["PatientName", "Modality", "StudyDate"]


def _make_study(path: Path) -> DicomStudy:
    """Wrap a single DICOM file path as a DicomStudy for testing."""
    return DicomStudy(
        display_name=path.name,
        root_path=path,
        representative=path,
        is_dir=False,
    )


def test_export_csv_creates_file(tmp_path):
    p = make_minimal_dicom(tmp_path / "scan.dcm")
    out = tmp_path / "out.csv"
    export_csv([_make_study(p)], TAGS, out)
    assert out.exists()


def test_export_csv_header_row(tmp_path):
    p = make_minimal_dicom(tmp_path / "scan.dcm")
    out = tmp_path / "out.csv"
    export_csv([_make_study(p)], TAGS, out)
    with open(out, newline="") as f:
        reader = csv.DictReader(f)
        assert set(reader.fieldnames) == {"file", "PatientName", "Modality", "StudyDate"}


def test_export_csv_data_row(tmp_path):
    p = make_minimal_dicom(tmp_path / "scan.dcm")
    out = tmp_path / "out.csv"
    export_csv([_make_study(p)], TAGS, out)
    with open(out, newline="") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 1
    assert rows[0]["file"] == "scan.dcm"
    assert rows[0]["PatientName"] == "Test^Patient"
    assert rows[0]["Modality"] == "CT"


def test_export_csv_missing_tag_is_empty(tmp_path):
    p = make_minimal_dicom(tmp_path / "scan.dcm")
    out = tmp_path / "out.csv"
    export_csv([_make_study(p)], ["PatientName", "NonExistentTag"], out)
    with open(out, newline="") as f:
        rows = list(csv.DictReader(f))
    assert rows[0]["NonExistentTag"] == ""


def test_export_csv_multiple_studies(tmp_path):
    files = [make_minimal_dicom(tmp_path / f"scan{i}.dcm") for i in range(3)]
    out = tmp_path / "out.csv"
    export_csv([_make_study(p) for p in files], TAGS, out)
    with open(out, newline="") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 3


def test_export_csv_uses_display_name_as_file_column(tmp_path):
    p = make_minimal_dicom(tmp_path / "slice001")
    study = DicomStudy(
        display_name="PCH0053_20260203_125047",
        root_path=tmp_path / "PCH0053_20260203_125047",
        representative=p,
        is_dir=True,
    )
    out = tmp_path / "out.csv"
    export_csv([study], TAGS, out)
    with open(out, newline="") as f:
        rows = list(csv.DictReader(f))
    assert rows[0]["file"] == "PCH0053_20260203_125047"


def test_export_json_creates_file(tmp_path):
    p = make_minimal_dicom(tmp_path / "scan.dcm")
    out = tmp_path / "out.json"
    export_json([_make_study(p)], TAGS, out)
    assert out.exists()


def test_export_json_structure(tmp_path):
    p = make_minimal_dicom(tmp_path / "scan.dcm")
    out = tmp_path / "out.json"
    export_json([_make_study(p)], TAGS, out)
    records = json.loads(out.read_text())
    assert isinstance(records, list)
    assert len(records) == 1
    assert records[0]["file"] == "scan.dcm"
    assert records[0]["PatientName"] == "Test^Patient"
    assert records[0]["Modality"] == "CT"


def test_export_json_missing_tag_is_empty_string(tmp_path):
    p = make_minimal_dicom(tmp_path / "scan.dcm")
    out = tmp_path / "out.json"
    export_json([_make_study(p)], ["PatientName", "NonExistentTag"], out)
    records = json.loads(out.read_text())
    assert records[0]["NonExistentTag"] == ""


def test_export_json_uses_display_name_as_file_column(tmp_path):
    p = make_minimal_dicom(tmp_path / "slice001")
    study = DicomStudy(
        display_name="LEON LUIS-001-2026.03.07",
        root_path=tmp_path / "LEON LUIS-001",
        representative=p,
        is_dir=True,
    )
    out = tmp_path / "out.json"
    export_json([study], TAGS, out)
    records = json.loads(out.read_text())
    assert records[0]["file"] == "LEON LUIS-001-2026.03.07"


def test_default_output_path_csv():
    path = default_output_path("csv")
    assert path.suffix == ".csv"
    assert re.match(r"dicom_export_\d{8}_\d{6}\.csv", path.name)


def test_default_output_path_json():
    path = default_output_path("json")
    assert path.suffix == ".json"
