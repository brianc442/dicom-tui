import csv
import json
import re
from pathlib import Path
import pytest
from tests.conftest import make_minimal_dicom
from src.exporter import export_csv, export_json, default_output_path


TAGS = ["PatientName", "Modality", "StudyDate"]


def test_export_csv_creates_file(tmp_path):
    p = make_minimal_dicom(tmp_path / "scan.dcm")
    out = tmp_path / "out.csv"
    export_csv([p], TAGS, out)
    assert out.exists()


def test_export_csv_header_row(tmp_path):
    p = make_minimal_dicom(tmp_path / "scan.dcm")
    out = tmp_path / "out.csv"
    export_csv([p], TAGS, out)
    with open(out, newline="") as f:
        reader = csv.DictReader(f)
        assert set(reader.fieldnames) == {"file", "PatientName", "Modality", "StudyDate"}


def test_export_csv_data_row(tmp_path):
    p = make_minimal_dicom(tmp_path / "scan.dcm")
    out = tmp_path / "out.csv"
    export_csv([p], TAGS, out)
    with open(out, newline="") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 1
    assert rows[0]["file"] == "scan.dcm"
    assert rows[0]["PatientName"] == "Test^Patient"
    assert rows[0]["Modality"] == "CT"


def test_export_csv_missing_tag_is_empty(tmp_path):
    p = make_minimal_dicom(tmp_path / "scan.dcm")
    out = tmp_path / "out.csv"
    export_csv([p], ["PatientName", "NonExistentTag"], out)
    with open(out, newline="") as f:
        rows = list(csv.DictReader(f))
    assert rows[0]["NonExistentTag"] == ""


def test_export_csv_multiple_files(tmp_path):
    files = [make_minimal_dicom(tmp_path / f"scan{i}.dcm") for i in range(3)]
    out = tmp_path / "out.csv"
    export_csv(files, TAGS, out)
    with open(out, newline="") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 3


def test_export_json_creates_file(tmp_path):
    p = make_minimal_dicom(tmp_path / "scan.dcm")
    out = tmp_path / "out.json"
    export_json([p], TAGS, out)
    assert out.exists()


def test_export_json_structure(tmp_path):
    p = make_minimal_dicom(tmp_path / "scan.dcm")
    out = tmp_path / "out.json"
    export_json([p], TAGS, out)
    records = json.loads(out.read_text())
    assert isinstance(records, list)
    assert len(records) == 1
    assert records[0]["file"] == "scan.dcm"
    assert records[0]["PatientName"] == "Test^Patient"
    assert records[0]["Modality"] == "CT"


def test_export_json_missing_tag_is_empty_string(tmp_path):
    p = make_minimal_dicom(tmp_path / "scan.dcm")
    out = tmp_path / "out.json"
    export_json([p], ["PatientName", "NonExistentTag"], out)
    records = json.loads(out.read_text())
    assert records[0]["NonExistentTag"] == ""


def test_default_output_path_csv():
    path = default_output_path("csv")
    assert path.suffix == ".csv"
    assert re.match(r"dicom_export_\d{8}_\d{6}\.csv", path.name)


def test_default_output_path_json():
    path = default_output_path("json")
    assert path.suffix == ".json"
