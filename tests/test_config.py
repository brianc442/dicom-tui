from pathlib import Path
import pytest
from src.config import Config, DEFAULT_TAGS, load_config, save_config


def test_default_tags_are_non_empty():
    assert len(DEFAULT_TAGS) > 0
    assert "PatientName" in DEFAULT_TAGS
    assert "Modality" in DEFAULT_TAGS


def test_load_config_returns_defaults_when_no_file(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)  # no config.toml in cwd
    # Patch Path.home() directly so ~/.dicom-tui/config.toml resolves under tmp_path
    # (setenv("HOME") is not reliable on Windows which uses USERPROFILE)
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    config = load_config()
    assert config.include == DEFAULT_TAGS
    assert config.source_path is None
    assert config.warning is None


def test_load_config_reads_toml_file(tmp_path):
    cfg_file = tmp_path / "myconfig.toml"
    cfg_file.write_text('[tags]\ninclude = ["Modality", "PatientID"]\n')
    config = load_config(cfg_file)
    assert config.include == ["Modality", "PatientID"]
    assert config.source_path == cfg_file
    assert config.warning is None


def test_load_config_falls_back_to_defaults_on_malformed_toml(tmp_path):
    cfg_file = tmp_path / "bad.toml"
    cfg_file.write_text("this is not valid toml ][")
    config = load_config(cfg_file)
    assert config.include == DEFAULT_TAGS
    assert config.warning is not None
    assert "error" in config.warning.lower()


def test_load_config_cwd_lookup(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "config.toml").write_text('[tags]\ninclude = ["Rows"]\n')
    config = load_config()
    assert config.include == ["Rows"]


def test_save_config_creates_file(tmp_path):
    out = tmp_path / "saved.toml"
    save_config(out, ["PatientName", "Modality"])
    assert out.exists()
    # reload and verify
    config = load_config(out)
    assert config.include == ["PatientName", "Modality"]


def test_save_config_updates_existing_file(tmp_path):
    out = tmp_path / "existing.toml"
    out.write_text('[tags]\ninclude = ["Rows"]\n[other]\nkey = "value"\n')
    save_config(out, ["PatientID"])
    config = load_config(out)
    assert config.include == ["PatientID"]
    # other sections preserved — use the same conditional import as src/config.py
    try:
        import tomllib
    except ImportError:
        import tomli as tomllib  # type: ignore[no-redef]
    with open(out, "rb") as f:
        data = tomllib.load(f)
    assert data["other"]["key"] == "value"


def test_save_config_creates_parent_dirs(tmp_path):
    out = tmp_path / "nested" / "dir" / "config.toml"
    save_config(out, ["Modality"])
    assert out.exists()
