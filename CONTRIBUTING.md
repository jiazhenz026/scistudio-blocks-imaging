# Contributing

This is a SciStudio package. Governance is lightweight: a PR checklist
(`.github/pull_request_template.md`) plus CI. See `AGENTS.md` for the full
rule set (humans and AI agents both follow it).

## Dev setup

Core (`scistudio`) is private and not on PyPI yet, so install it first, then
install this package with its dev extras.

```bash
# 1. Install core (read access to the private repo required)
pip install "scistudio @ git+https://github.com/jiazhenz026/SciStudio.git@main"

# 2. Install this package in editable mode with dev tools
pip install -e ".[dev]"

# 3. Verify it registers with core
scistudio blocks
```

When core is published to PyPI, step 1 becomes unnecessary — `pip install -e
".[dev]"` will resolve `scistudio` from the index.

## Local checks (same as CI)

```bash
ruff format --check .            # format
ruff check .                     # lint
mypy src                         # types
pytest                           # tests
python scripts/validate_contract.py   # SciStudio plugin contract
python -m build                  # wheel + sdist
```

## Branch, commit, PR

- Branch off `main`; one focused change per PR.
- Every PR closes an open issue (`Closes #NNN` in the body).
- Add or update tests for any behavior change.
- Update `README.md` and `docs/` to `docs/DOCUMENTATION-STANDARD.md`.
- Fill in the PR template checklist. CI must be green.

## Releasing

1. Bump `version` in `pyproject.toml` and `__version__` in the package
   `__init__.py` (keep them equal).
2. Add a `CHANGELOG.md` entry.
3. Merge to `main`. CI builds the wheel + sdist and publishes them to a GitHub
   Release tagged `vX.Y.Z`, derived from the `pyproject.toml` version — no
   manual tagging. Bumping the version cuts a new release; re-merging the same
   version refreshes that release's assets. Users install the attached wheel via
   the SciStudio in-app Package Manager (local install) or `pip`.

## Compatibility with core

The `scistudio>=X` floor in `pyproject.toml` is the minimum core contract this
package relies on. Raise it when you start using a newer core feature or a
changed contract, and reference the relevant core ADR in the PR.
