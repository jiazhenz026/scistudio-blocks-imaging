"""OTA self-declaration contract (#1784)."""

from __future__ import annotations

import tomllib
from pathlib import Path

import scistudio_blocks_imaging as pkg


def test_package_info_ota_matches_pyproject() -> None:
    info = pkg.get_package_info()
    assert info.ota is not None, "PackageInfo.ota must be declared for OTA hot-update"
    pyproject = tomllib.loads((Path(__file__).resolve().parent.parent / "pyproject.toml").read_text(encoding="utf-8"))
    ota = pyproject["tool"]["scistudio"]["ota"]
    assert info.ota.manifest_url == ota["manifest_url"]
    assert info.ota.channel == ota["channel"]
    assert info.ota.manifest_url.startswith("https://")
