# Documentation Standard

Every SciStudio package must meet this standard. Reviewers check it on
each PR (see the PR checklist). The goal: a scientist who is not fluent in code
can tell, from the docs alone, what the package provides and how to use it —
without reading the source.

The reference implementation of this standard is
`scistudio-blocks-spectroscopy`.

## 1. Required files

| File | Purpose |
| --- | --- |
| `README.md` | The front door. Sections 2 below are mandatory. |
| `docs/package-overview.md` | "What's in this package" — the structured catalog. |
| `CHANGELOG.md` | One entry per release; follows Keep a Changelog. |
| `LICENSE` | MIT (matches core). |

## 2. `README.md` required sections

1. **Title + one-line purpose** — what the package is, in one sentence.
2. **Scope / non-goals** — what it deliberately does not cover, and which
   sibling packages it must not import.
3. **Data types** — each package-owned `DataObject` type: what it represents,
   its core base class, and its key metadata fields.
4. **Blocks** — a table grouped by category: `| Group | Blocks |`. Every
   exported block appears. Match the names returned by `get_blocks()`.
5. **IO / format support** (if the package has IO blocks) — which formats are
   advertised vs. deferred, per ADR-043 `FormatCapability`.
6. **Previewers** (if any) — which type each previews and its capabilities.
7. **Install** — how to install (GUI local package installer, or pip), and the
   `scistudio>=X` compatibility floor.
8. **License** — name the license.

## 3. `docs/package-overview.md`

The structured catalog that backs the README. Use the template in this repo
(`docs/package-overview.md`). It enumerates every type, block (with ports and
parameters), and previewer. Keep it in sync with the code — a block that exists
in `get_blocks()` but is absent here (or vice-versa) is a documentation defect.

## 4. Docstrings

- Every exported block class has a class docstring: what it does, its input and
  output ports, and its parameters.
- Every package-owned type has a class docstring naming its core base type and
  semantic contract.
- Public module docstrings state the module's responsibility.

## 5. Keep docs and code in sync

- The block table in `README.md`, the catalog in `docs/package-overview.md`,
  and `get_blocks()` must list the same blocks. A test that asserts this
  (see `tests/`) is recommended and is the spectroscopy package's approach
  (`test_readme_blocks.py`).
- Document compatibility: when the `scistudio>=X` floor changes, say why in
  `CHANGELOG.md`.
