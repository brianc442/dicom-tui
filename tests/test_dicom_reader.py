from pathlib import Path
import pytest
from tests.conftest import make_minimal_dicom
from src.dicom_reader import (
    is_dicom,
    find_dicoms,
    load_tags,
    filter_tags,
    get_tag_id,
)
from src.dicom_reader import iter_dicoms


# --- is_dicom ---

def test_is_dicom_valid_file(tmp_path):
    p = make_minimal_dicom(tmp_path / "scan")
    assert is_dicom(p) is True


def test_is_dicom_valid_dcm_extension(tmp_path):
    p = make_minimal_dicom(tmp_path / "scan.dcm")
    assert is_dicom(p) is True


def test_is_dicom_non_dicom_file(tmp_path):
    p = tmp_path / "not_dicom.txt"
    p.write_bytes(b"hello world" * 20)
    assert is_dicom(p) is False


def test_is_dicom_too_short_file(tmp_path):
    p = tmp_path / "tiny"
    p.write_bytes(b"\x00" * 50)
    assert is_dicom(p) is False


def test_is_dicom_directory(tmp_path):
    assert is_dicom(tmp_path) is False


def test_is_dicom_extensionless_dicom(tmp_path):
    # DICOM files often have no extension
    p = make_minimal_dicom(tmp_path / "IM000001")
    assert is_dicom(p) is True


# --- find_dicoms ---

def test_find_dicoms_returns_dicom_files(tmp_path):
    make_minimal_dicom(tmp_path / "IM000001")
    make_minimal_dicom(tmp_path / "IM000002")
    (tmp_path / "notes.txt").write_text("not a dicom")
    result = find_dicoms(tmp_path)
    assert len(result) == 2
    names = [p.name for p in result]
    assert "IM000001" in names
    assert "IM000002" in names


def test_find_dicoms_empty_directory(tmp_path):
    assert find_dicoms(tmp_path) == []


def test_find_dicoms_skips_subdirectories(tmp_path):
    subdir = tmp_path / "subdir"
    subdir.mkdir()
    make_minimal_dicom(tmp_path / "IM000001")
    result = find_dicoms(tmp_path)
    assert len(result) == 1


def test_find_dicoms_includes_mixed_extensions(tmp_path):
    make_minimal_dicom(tmp_path / "scan.dcm")
    make_minimal_dicom(tmp_path / "scan_no_ext")
    (tmp_path / "image.jpg").write_bytes(b"\xff\xd8\xff" + b"\x00" * 200)
    result = find_dicoms(tmp_path)
    assert len(result) == 2


# --- load_tags ---

def test_load_tags_returns_dict(tmp_path):
    p = make_minimal_dicom(tmp_path / "test.dcm")
    tags = load_tags(p)
    assert isinstance(tags, dict)
    assert tags["PatientName"] == "Test^Patient"
    assert tags["Modality"] == "CT"
    assert tags["Rows"] == "512"


def test_load_tags_invalid_file_returns_empty(tmp_path):
    p = tmp_path / "bad.dcm"
    p.write_bytes(b"not a dicom file at all")
    tags = load_tags(p)
    assert tags == {}


def test_serialize_value_bytes():
    from src.dicom_reader import _serialize_value
    assert _serialize_value(b"\x00\x01\x02") == "<binary: 3 bytes>"


def test_serialize_value_multivalue():
    from src.dicom_reader import _serialize_value
    import pydicom.multival
    mv = pydicom.multival.MultiValue(str, ["a", "b", "c"])
    assert _serialize_value(mv) == "a \\ b \\ c"


def test_serialize_value_sequence():
    from src.dicom_reader import _serialize_value
    import pydicom.sequence
    import pydicom
    seq = pydicom.sequence.Sequence([pydicom.Dataset(), pydicom.Dataset()])
    assert _serialize_value(seq) == "<Sequence: 2 items>"


# --- filter_tags ---

def test_filter_tags_by_keyword(tmp_path):
    p = make_minimal_dicom(tmp_path / "test.dcm")
    all_tags = load_tags(p)
    filtered = filter_tags(all_tags, ["PatientName", "Modality"])
    assert set(filtered.keys()) == {"PatientName", "Modality"}


def test_filter_tags_by_tag_id(tmp_path):
    p = make_minimal_dicom(tmp_path / "test.dcm")
    all_tags = load_tags(p)
    # (0010,0010) = PatientName, (0008,0060) = Modality
    filtered = filter_tags(all_tags, ["(0010,0010)", "(0008,0060)"])
    assert "PatientName" in filtered
    assert "Modality" in filtered


def test_filter_tags_unknown_tag_skipped(tmp_path):
    p = make_minimal_dicom(tmp_path / "test.dcm")
    all_tags = load_tags(p)
    filtered = filter_tags(all_tags, ["NonExistentTag123"])
    assert filtered == {}


def test_filter_tags_empty_include_returns_empty():
    tags = {"PatientName": "John", "Modality": "CT"}
    assert filter_tags(tags, []) == {}


# --- get_tag_id ---

def test_get_tag_id_patient_name():
    assert get_tag_id("PatientName") == "(0010,0010)"  # all numeric, same upper/lower


def test_get_tag_id_modality():
    assert get_tag_id("Modality") == "(0008,0060)"  # all numeric, same upper/lower


def test_get_tag_id_hex_digits_are_lowercase():
    # PixelData is (7fe0,0010) — contains 'a'-'f' hex digits, universally in pydicom
    result = get_tag_id("PixelData")
    assert result == "(7fe0,0010)"


def test_get_tag_id_unknown_returns_empty():
    assert get_tag_id("NotARealKeyword") == ""


# --- iter_dicoms ---

def test_iter_dicoms_flat_yields_dicoms(tmp_path):
    make_minimal_dicom(tmp_path / "IM000001")
    make_minimal_dicom(tmp_path / "IM000002")
    (tmp_path / "notes.txt").write_text("not a dicom")
    result = list(iter_dicoms(tmp_path))
    assert len(result) == 2
    names = {p.name for p in result}
    assert names == {"IM000001", "IM000002"}


def test_iter_dicoms_flat_skips_subdirectories(tmp_path):
    subdir = tmp_path / "sub"
    subdir.mkdir()
    make_minimal_dicom(tmp_path / "IM000001")
    result = list(iter_dicoms(tmp_path))
    assert len(result) == 1
    assert result[0].name == "IM000001"


def test_iter_dicoms_recursive_descends_subdirs(tmp_path):
    sub = tmp_path / "series1"
    sub.mkdir()
    make_minimal_dicom(tmp_path / "IM000001")
    make_minimal_dicom(sub / "IM000002")
    result = list(iter_dicoms(tmp_path, recursive=True))
    names = {p.name for p in result}
    assert names == {"IM000001", "IM000002"}


def test_iter_dicoms_recursive_deeply_nested(tmp_path):
    deep = tmp_path / "a" / "b" / "c"
    deep.mkdir(parents=True)
    make_minimal_dicom(deep / "IM000001")
    result = list(iter_dicoms(tmp_path, recursive=True))
    assert len(result) == 1
    assert result[0].name == "IM000001"


def test_iter_dicoms_empty_directory(tmp_path):
    assert list(iter_dicoms(tmp_path)) == []
