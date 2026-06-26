# Changelog

All notable changes to this package are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/) and the project uses
[Semantic Versioning](https://semver.org/).

## [Unreleased]

- OTA hot-update support (#1784): self-declared update source via
  `PackageInfo.ota` / `[tool.scistudio.ota]`; `scripts/ota_publish.py`
  publishes manifest + snapshot to the package's own `ota-<channel>`
  GitHub pre-release for the in-app Package Manager.

### Added

- Package governance from `scistudio-package-template`: CI (lint, type, test,
  wheel build, SciStudio contract check), `AGENTS.md` + PR checklist,
  `CONTRIBUTING.md`, `docs/DOCUMENTATION-STANDARD.md`, `docs/package-overview.md`,
  `LICENSE` (MIT), and `scripts/validate_contract.py`.
- `pyproject.toml`: `[tool.ruff]`/`[tool.mypy]` (mirror core), a `dev` extra,
  and a `license` field.

### Fixed

- Migrated off the deprecated `Array._data` attribute to the core data API
  (`to_memory()`/`data=`); see the migration PR.

## [0.1.0]

- Initial imaging package: 49 blocks, types `Image`/`Mask`/`Label`, 2 previewers.
