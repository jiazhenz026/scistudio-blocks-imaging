<!--
This checklist IS the gate for a SciStudio package. There is no gate
ledger. Fill it in honestly; CI enforces the mechanical parts.
-->

## Summary

<!-- What changed and why. -->

## Issue

Closes #<!-- issue number -->

## Checklist

- [ ] One focused change; branched off `main`.
- [ ] Tests added or updated for the behavior change (or N/A — explain below).
- [ ] `README.md` and `docs/` updated to `docs/DOCUMENTATION-STANDARD.md`
      (or N/A — explain below).
- [ ] Public contract: no block/type/entry-point/port removed or renamed
      without a version bump + `CHANGELOG.md` note.
- [ ] `scistudio>=X` floor still reflects the minimum core contract used
      (raised if a newer core feature/contract is relied on).
- [ ] Local checks pass: `ruff format --check . && ruff check . && mypy src &&
      pytest && python scripts/validate_contract.py`.
- [ ] CI is green (lint, type, tests, wheel build, contract check).

## Notes / N/A rationale

<!-- Anything reviewers should know; justify any N/A boxes above. -->
