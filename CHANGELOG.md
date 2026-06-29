# Changelog

All notable changes to this package are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/) and the project uses
[Semantic Versioning](https://semver.org/).

## [Unreleased]

### Changed

- **Conform `types` + `previewers` to the ADR-052 §13.1 developer contract**
  (#9). Types and previewers now consume only the public core surface and carry
  the §5 stability markers:
  - `types.py`: import core types from the public `scistudio.core.types` root
    (not deep `core.types.array` / `core.storage.ref`); `Label` reads its slots
    through the public `CompositeData` API (`get` / `slot_names`) instead of the
    private `_slots`; `Image` / `Mask` / `Label` / `Transform` (and their `Meta`)
    carry `@stable`, and each type ships the §13.1 MUST-shape `from_arrays(...)`
    domain constructor.
  - `previewers`: providers moved to `previewers/providers.py` (mirroring
    `scistudio-blocks-spectroscopy`); they read the sanctioned typed
    `request.storage` / `request.record_metadata` instead of the legacy
    `query["_storage"]` / `query["_record_metadata"]` carriers, and import
    `StorageReference` from `scistudio.core.types` (TYPE_CHECKING only). Public
    provider functions carry `@stable`. Package-owned TIFF/PNG decoders stay
    (core `data_access` reads Zarr only, by ADR-048 §4 design).
  - `assets/viewer.js`: restyled to the brand `--ss-*` tokens
    (`docs/ui-style-guide.md`) with literal fallbacks — no more stock blue/slate.
- Bumped the core floor `scistudio>=0.2.1a0` -> `>=0.3.1a0` (and OTA
  `min_core_base` 0.2.1 -> 0.3.1) for the contract surface above. Blocks-module
  conformance and the strict whole-package `validate_contract.py` /
  `test_developer_contract.py` are a tracked follow-up.

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
