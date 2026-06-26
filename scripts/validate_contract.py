#!/usr/bin/env python3
"""Validate that this package honors the SciStudio plugin contract.

Run from the repository root (CI and local):

    python scripts/validate_contract.py

Exits non-zero on any violation. Requires this package and ``scistudio``
(core) to be installed in the environment — CI installs core from the private
repo (see ``.github/workflows/ci.yml``).

This script is package-agnostic: it reads the entry points declared in
``pyproject.toml`` and validates them, so the four packages share it
unchanged.

Checks:
  1. ``[project].name`` and the three entry-point groups are declared.
  2. Each declared entry point imports and returns the contracted shape:
       - ``scistudio.blocks``     -> ``(PackageInfo, [Block subclasses])``
       - ``scistudio.types``      -> ``[type, ...]``
       - ``scistudio.previewers`` -> ``[PreviewerSpec-like, ...]``
  3. ``python -m scistudio blocks`` loads the full core registry without error
     (integration: proves the package actually installs into core).
"""

from __future__ import annotations

import importlib
import subprocess
import sys
import tomllib
from collections.abc import Callable
from pathlib import Path
from typing import Any

BLOCKS_GROUP = "scistudio.blocks"
TYPES_GROUP = "scistudio.types"
PREVIEWERS_GROUP = "scistudio.previewers"


def _fail(msg: str) -> None:
    print(f"  ✗ {msg}", file=sys.stderr)
    raise SystemExit(1)


def _load(ref: str) -> Callable[[], Any]:
    """Resolve an entry-point reference ``module[:attr.subattr]`` to an object."""
    module_name, _, attr_path = ref.partition(":")
    obj: Any = importlib.import_module(module_name)
    for part in filter(None, attr_path.split(".")):
        obj = getattr(obj, part)
    return obj


def main() -> int:
    root = Path(__file__).resolve().parent.parent
    pyproject = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    project = pyproject.get("project", {})
    name = project.get("name")
    if not name:
        _fail("pyproject [project].name is missing")
    print(f"Validating SciStudio plugin contract for: {name}")

    entry_points = project.get("entry-points", {})
    for group in (BLOCKS_GROUP, TYPES_GROUP, PREVIEWERS_GROUP):
        if not entry_points.get(group):
            _fail(f"missing entry-point group [{group}] in pyproject.toml")

    # OTA self-declaration (#1784): the publish-time source of truth lives in
    # [tool.scistudio.ota]; the package's PackageInfo.ota must mirror it so the
    # in-app Package Manager checks the same URL ota_publish.py uploads to.
    ota_config = (pyproject.get("tool", {}) or {}).get("scistudio", {}).get("ota")
    if not isinstance(ota_config, dict) or not ota_config.get("manifest_url"):
        _fail("missing [tool.scistudio.ota].manifest_url in pyproject.toml")
    ota_url = str(ota_config["manifest_url"])
    ota_channel = str(ota_config.get("channel") or "stable")
    if not ota_url.startswith("https://"):
        _fail(f"[tool.scistudio.ota].manifest_url must be HTTPS: {ota_url!r}")

    # Core base classes (require core installed).
    try:
        from scistudio.blocks.base.block import Block
        from scistudio.blocks.base.package_info import PackageInfo
    except ImportError as exc:  # pragma: no cover - environment guard
        _fail(f"could not import scistudio core ({exc}); is it installed?")

    # 1. scistudio.blocks -> (PackageInfo, [Block subclasses])
    for ref in entry_points[BLOCKS_GROUP].values():
        result = _load(ref)()
        if not (isinstance(result, tuple) and len(result) == 2):
            _fail(f"{ref}() must return (PackageInfo, [block classes])")
        info, blocks = result
        if not isinstance(info, PackageInfo):
            _fail(f"{ref}() first element is not a PackageInfo")
        if not blocks:
            _fail(f"{ref}() returned no block classes")
        for block in blocks:
            if not (isinstance(block, type) and issubclass(block, Block)):
                _fail(f"{block!r} from {ref} is not a Block subclass")
        # PackageInfo.ota must be declared and agree with pyproject (#1784).
        ota = getattr(info, "ota", None)
        if ota is None:
            _fail(f"{ref}() PackageInfo.ota is not declared (see [tool.scistudio.ota])")
        if getattr(ota, "manifest_url", None) != ota_url:
            _fail(f"{ref}() PackageInfo.ota.manifest_url does not match [tool.scistudio.ota].manifest_url")
        if getattr(ota, "channel", None) != ota_channel:
            _fail(f"{ref}() PackageInfo.ota.channel does not match [tool.scistudio.ota].channel")
        print(f"  ✓ blocks: {len(blocks)} block(s) via {ref}; OTA → {ota_channel}")

    # 2. scistudio.types -> [type, ...]
    for ref in entry_points[TYPES_GROUP].values():
        types = _load(ref)()
        if not isinstance(types, list) or not all(isinstance(t, type) for t in types):
            _fail(f"{ref}() must return a list of classes")
        print(f"  ✓ types: {len(types)} type(s) via {ref}")

    # 3. scistudio.previewers -> [PreviewerSpec-like, ...]
    for ref in entry_points[PREVIEWERS_GROUP].values():
        previewers = _load(ref)()
        if not isinstance(previewers, list):
            _fail(f"{ref}() must return a list (empty is allowed)")
        for spec in previewers:
            if not hasattr(spec, "previewer_id"):
                _fail(f"{spec!r} from {ref} is not a PreviewerSpec")
        print(f"  ✓ previewers: {len(previewers)} previewer(s) via {ref}")

    # 4. Integration: core loads the full registry with this package present.
    proc = subprocess.run(
        [sys.executable, "-m", "scistudio", "blocks"],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        sys.stdout.write(proc.stdout)
        sys.stderr.write(proc.stderr)
        _fail("`scistudio blocks` failed to load the registry")
    print("  ✓ `scistudio blocks` loaded the full registry")

    print("Contract OK.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
