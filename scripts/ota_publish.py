#!/usr/bin/env python3
"""Publish a SciStudio **package** OTA hot-update (issue #1784).

This is the package-side analogue of core's ``scripts/ota_publish.py``. It packs
this package's ``src/`` tree into a snapshot, hashes it, builds a
``manifest.json``, and uploads both to the package's own public, rolling
``ota-<channel>`` GitHub pre-release. The in-app SciStudio Package Manager reads
that manifest (declared via ``PackageInfo.ota`` / ``[tool.scistudio.ota]``) to
offer the update.

Unlike core OTA, a package update is compared by **semver**: the manifest
``version`` is the package version from ``pyproject.toml`` and there is no build
counter. ``requires.min_core_base`` records the minimum core ``a.b.c`` base a
client must run to apply it.

The publish target (repo + release tag) is derived from the ``manifest_url`` in
``[tool.scistudio.ota]`` so the upload location always matches what clients
fetch. The same URL/channel are mirrored in the package's ``PackageInfo.ota``;
``scripts/validate_contract.py`` enforces they agree.

Usage::

    python scripts/ota_publish.py                      # publish current version
    python scripts/ota_publish.py --dry-run            # build locally only
    python scripts/ota_publish.py --notes "Fix peak picking"

Requires the GitHub CLI (``gh``) authenticated with write access, except under
``--dry-run``.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import re
import subprocess
import tarfile
import tempfile
import tomllib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PYPROJECT = REPO_ROOT / "pyproject.toml"
SRC_DIR = REPO_ROOT / "src"

# https://github.com/<owner>/<repo>/releases/download/<tag>/manifest.json
_MANIFEST_URL_RE = re.compile(
    r"^https://github\.com/(?P<owner>[^/]+)/(?P<repo>[^/]+)/releases/download/(?P<tag>[^/]+)/[^/]+$"
)


# --------------------------------------------------------------------------- #
# Pure helpers (unit-tested in tests/test_ota_publish.py)
# --------------------------------------------------------------------------- #
def read_ota_config(pyproject_text: str) -> dict:
    """Return ``name``, ``version`` and the ``[tool.scistudio.ota]`` table."""
    data = tomllib.loads(pyproject_text)
    project = data.get("project", {})
    name = project.get("name")
    version = project.get("version")
    if not isinstance(name, str) or not name:
        raise ValueError("pyproject [project].name is missing")
    if not isinstance(version, str) or not version:
        raise ValueError("pyproject [project].version is missing")
    ota = (data.get("tool", {}) or {}).get("scistudio", {}).get("ota")
    if not isinstance(ota, dict) or not ota.get("manifest_url"):
        raise ValueError("pyproject [tool.scistudio.ota].manifest_url is missing")
    return {
        "name": name,
        "version": version,
        "manifest_url": str(ota["manifest_url"]),
        "channel": str(ota.get("channel") or "stable"),
        "min_core_base": str(ota.get("min_core_base") or ""),
    }


def parse_manifest_url(manifest_url: str) -> tuple[str, str]:
    """Return ``(repo, tag)`` parsed from a release ``manifest_url``."""
    match = _MANIFEST_URL_RE.match(manifest_url.strip())
    if not match:
        raise ValueError(f"manifest_url is not a GitHub release asset URL: {manifest_url!r}")
    return f"{match.group('owner')}/{match.group('repo')}", match.group("tag")


def asset_name(name: str, version: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "-", name.strip()).strip("._-").lower()
    return f"{safe}-{version}.tar.gz"


def asset_url(manifest_url: str, asset: str) -> str:
    base = manifest_url.rsplit("/", 1)[0]
    return f"{base}/{asset}"


def build_manifest(
    *,
    name: str,
    version: str,
    channel: str,
    min_core_base: str,
    url: str,
    sha256: str,
    size: int,
    notes: str,
    published_at: str,
) -> dict:
    """Assemble the manifest the in-app Package Manager compares against."""
    return {
        "package": name,
        "version": version,
        "channel": channel,
        "requires": {"min_core_base": min_core_base},
        "url": url,
        "sha256": sha256,
        "size": size,
        "notes": notes,
        "published_at": published_at,
    }


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


_SNAPSHOT_EXCLUDE_DIRS = {
    ".git",
    ".github",
    "__pycache__",
    "dist",
    "build",
    ".venv",
    "venv",
    "node_modules",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
}


def make_snapshot(src_dir: Path, out_path: Path) -> None:
    """Pack the whole installable package root into ``out_path`` as a gzip tarball.

    The archive must be a *build-complete* source package: the client installs
    it with ``pip install`` (hatchling), which validates files referenced by
    ``pyproject.toml`` such as ``readme = "README.md"`` and the license. Packing
    only ``src/`` (or only ``pyproject.toml`` + ``src/``) makes the build fail
    with "Readme file does not exist" and loses the real name/version. So pack
    the package root (``pyproject.toml``, ``README.md``, ``LICENSE``, ``src/``,
    …), excluding VCS, build, and cache dirs.
    """
    root = src_dir.parent

    def _filter(info: tarfile.TarInfo) -> tarfile.TarInfo | None:
        parts = Path(info.name).parts
        if any(part in _SNAPSHOT_EXCLUDE_DIRS for part in parts):
            return None
        if any(part.endswith(".egg-info") for part in parts):
            return None
        if info.name.endswith(".pyc") or info.name.endswith(".DS_Store"):
            return None
        return info

    with tarfile.open(out_path, "w:gz") as tar:
        tar.add(root, arcname=".", filter=_filter)


# --------------------------------------------------------------------------- #
# gh / IO side
# --------------------------------------------------------------------------- #
def _run(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, text=True, capture_output=True)


def ensure_release(repo: str, tag: str, channel: str) -> None:
    if _run(["gh", "release", "view", tag, "--repo", repo]).returncode == 0:
        return
    result = _run(
        [
            "gh",
            "release",
            "create",
            tag,
            "--repo",
            repo,
            "--prerelease",
            "--title",
            f"SciStudio package OTA ({channel})",
            "--notes",
            f"Rolling OTA channel for '{channel}'. Assets managed by scripts/ota_publish.py; do not edit manually.",
        ]
    )
    if result.returncode != 0:
        raise RuntimeError(f"Failed to create release {tag}: {result.stderr.strip()}")


def upload_assets(repo: str, tag: str, files: list[Path]) -> None:
    result = _run(["gh", "release", "upload", tag, "--repo", repo, "--clobber", *map(str, files)])
    if result.returncode != 0:
        raise RuntimeError(f"Asset upload failed: {result.stderr.strip()}")


def _utc_now_iso() -> str:
    return _dt.datetime.now(_dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Publish a SciStudio package OTA update.")
    parser.add_argument("--notes", default="", help="Human-readable patch notes for the manifest.")
    parser.add_argument("--src", type=Path, default=SRC_DIR, help="Source tree to snapshot (default: ./src).")
    parser.add_argument("--dry-run", action="store_true", help="Build snapshot + manifest locally, do not upload.")
    parser.add_argument("--yes", action="store_true", help="Skip the upload confirmation prompt.")
    args = parser.parse_args(argv)

    if not args.src.is_dir():
        parser.error(f"No source tree at {args.src}")

    config = read_ota_config(PYPROJECT.read_text(encoding="utf-8"))
    repo, tag = parse_manifest_url(config["manifest_url"])
    name = asset_name(config["name"], config["version"])
    url = asset_url(config["manifest_url"], name)

    workdir = Path(tempfile.mkdtemp(prefix="scistudio-pkg-ota-"))
    tarball = workdir / name
    print(f"Packing snapshot of {args.src} -> {tarball.name} ...")
    make_snapshot(args.src, tarball)
    digest = sha256_file(tarball)
    size = tarball.stat().st_size
    manifest = build_manifest(
        name=config["name"],
        version=config["version"],
        channel=config["channel"],
        min_core_base=config["min_core_base"],
        url=url,
        sha256=digest,
        size=size,
        notes=args.notes,
        published_at=_utc_now_iso(),
    )
    manifest_path = workdir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")

    print(f"\npackage={config['name']} version={config['version']} channel={config['channel']}")
    print(f"  repo  : {repo} ({tag})")
    print(f"  asset : {name} ({size} bytes)")
    print(f"  sha256: {digest}")
    print(f"  url   : {url}")

    if args.dry_run:
        print(f"\n[dry-run] artifacts left in {workdir}")
        print(f"[dry-run] manifest:\n{manifest_path.read_text()}")
        return 0

    if not args.yes:
        reply = input(f"\nUpload {config['version']} to {repo} ({tag})? [y/N] ").strip().lower()
        if reply not in {"y", "yes"}:
            print("Aborted.")
            return 1

    ensure_release(repo, tag, config["channel"])
    upload_assets(repo, tag, [tarball, manifest_path])
    print(f"\nPublished {config['name']} {config['version']} to {repo} release {tag}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
