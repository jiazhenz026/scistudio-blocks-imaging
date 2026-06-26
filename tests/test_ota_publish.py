"""Unit tests for the pure helpers in scripts/ota_publish.py (#1784)."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "ota_publish.py"
_spec = importlib.util.spec_from_file_location("ota_publish", _SCRIPT)
assert _spec and _spec.loader
ota_publish = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ota_publish)


PYPROJECT = """
[project]
name = "scistudio-package-example"
version = "1.2.0"

[tool.scistudio.ota]
manifest_url = "https://github.com/jiazhenz026/scistudio-package-example/releases/download/ota-alpha/manifest.json"
channel = "alpha"
min_core_base = "0.2.1"
"""


def test_read_ota_config():
    config = ota_publish.read_ota_config(PYPROJECT)
    assert config["name"] == "scistudio-package-example"
    assert config["version"] == "1.2.0"
    assert config["channel"] == "alpha"
    assert config["min_core_base"] == "0.2.1"
    assert config["manifest_url"].endswith("/manifest.json")


def test_read_ota_config_requires_manifest_url():
    with pytest.raises(ValueError, match="manifest_url is missing"):
        ota_publish.read_ota_config('[project]\nname = "x"\nversion = "1.0.0"\n')


def test_parse_manifest_url():
    repo, tag = ota_publish.parse_manifest_url(
        "https://github.com/jiazhenz026/scistudio-package-example/releases/download/ota-alpha/manifest.json"
    )
    assert repo == "jiazhenz026/scistudio-package-example"
    assert tag == "ota-alpha"


def test_parse_manifest_url_rejects_non_release_url():
    with pytest.raises(ValueError, match="not a GitHub release asset URL"):
        ota_publish.parse_manifest_url("https://example.com/manifest.json")


def test_asset_name_and_url():
    assert (
        ota_publish.asset_name("scistudio-blocks-spectroscopy", "1.2.0") == "scistudio-blocks-spectroscopy-1.2.0.tar.gz"
    )
    url = ota_publish.asset_url(
        "https://github.com/o/r/releases/download/ota-alpha/manifest.json",
        "scistudio-blocks-spectroscopy-1.2.0.tar.gz",
    )
    assert url == "https://github.com/o/r/releases/download/ota-alpha/scistudio-blocks-spectroscopy-1.2.0.tar.gz"


def test_build_manifest_shape():
    manifest = ota_publish.build_manifest(
        name="scistudio-blocks-spectroscopy",
        version="1.2.0",
        channel="alpha",
        min_core_base="0.2.1",
        url="https://example.com/a.tar.gz",
        sha256="a" * 64,
        size=10,
        notes="fix",
        published_at="2026-06-26T00:00:00Z",
    )
    assert manifest["package"] == "scistudio-blocks-spectroscopy"
    assert manifest["version"] == "1.2.0"
    assert manifest["requires"] == {"min_core_base": "0.2.1"}
    assert manifest["sha256"] == "a" * 64


def test_make_snapshot_round_trips(tmp_path):
    src = tmp_path / "src" / "scistudio_blocks_demo"
    src.mkdir(parents=True)
    (src / "__init__.py").write_text("BLOCKS = []\n", encoding="utf-8")
    (src / "__pycache__").mkdir()
    (src / "__pycache__" / "x.pyc").write_bytes(b"junk")

    out = tmp_path / "snap.tar.gz"
    ota_publish.make_snapshot(tmp_path / "src", out)

    import tarfile

    with tarfile.open(out) as tar:
        names = tar.getnames()
    assert "src/scistudio_blocks_demo/__init__.py" in names
    assert not any("__pycache__" in n or n.endswith(".pyc") for n in names)
