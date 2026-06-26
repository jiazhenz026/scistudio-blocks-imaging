# AGENTS.md

Behavior guide for work in a **SciStudio package** repository. This is a
plugin package, not the SciStudio core monorepo. The governance here is
deliberately lightweight: a PR checklist and CI, **not** the core gate-ledger
workflow.

## 1. What This Package Is

A SciStudio package extends the core `scistudio` runtime through three
entry points, discovered at startup:

- `scistudio.blocks`     → `get_block_package()` → `(PackageInfo, [block classes])`
- `scistudio.types`      → `get_types()` → `[DataObject subclasses]`
- `scistudio.previewers` → `get_previewers()` → `[PreviewerSpec]`

The package depends on `scistudio` (core) but core never imports the package
except through these entry points. Keep that boundary: package logic stays in
the package; never edit core to make a package easier.

## 2. How To Work Here

- Understand the block contract before editing. The canonical reference is the
  core repo's `docs/block-development/` (block-contract, custom-types,
  collection-guide, previewers-and-plots, testing, publishing). Do not restate
  it here; link to it.
- Keep changes small and focused. One coherent change per branch and PR.
- Prefer core helpers, base classes, and patterns over local re-inventions.
- Model new code on `scistudio-blocks-spectroscopy` — it is the reference
  package for layout, typing, IO/format capabilities, and previewers.

## 3. Hard Rules

- Work on a dedicated branch. Do not push directly to `main`.
- Every PR closes an open issue. Create one if it does not exist; do not open a
  duplicate when an issue already tracks the work.
- Behavior changes require tests. Adding/altering a block, type, previewer, or
  IO format must add or update at least one test file.
- Documentation is part of the change. Update `README.md` and `docs/` to the
  `docs/DOCUMENTATION-STANDARD.md`, or state why N/A in the PR.
- Do not break the public contract silently. Renaming/removing a block, type,
  entry point, or changing a port's accepted types is a breaking change: bump
  the version and note it in `CHANGELOG.md`.
- Track compatibility with core. The `scistudio>=X` floor in `pyproject.toml`
  must reflect the minimum core contract the package relies on. When a core
  ADR changes a contract you use, cite the ADR in the PR.
- CI must pass before a PR is complete (lint, type, tests, wheel build, and the
  SciStudio contract check).
- No placeholder/untracked deferrals. Defer work only with a `TODO(#issue)`
  that cites a tracked issue.

## 4. The Gate Is A PR Checklist

This repo does **not** use the core gate-record ledger or any multi-step gate
workflow. The complete gate is `.github/pull_request_template.md`: fill it in
honestly, and let CI enforce it. Local self-attestation is not evidence; CI is
authoritative.

## 5. Validate The Contract

Before opening a PR, prove the package still loads into core:

```bash
python scripts/validate_contract.py   # checks all three entry points + registry
scistudio blocks                      # lists registered blocks (must include yours)
```

CI runs both. They require `scistudio` (core) installed in the environment.

## 6. Pointers

- Dev setup + PR checklist: `CONTRIBUTING.md`
- Documentation standard: `docs/DOCUMENTATION-STANDARD.md`
- Claude runtime pointer: `.claude/rules/rules.md`
- Codex runtime pointer: `.codex/rules/rules.md`
- Block contract (core repo): `docs/block-development/`
