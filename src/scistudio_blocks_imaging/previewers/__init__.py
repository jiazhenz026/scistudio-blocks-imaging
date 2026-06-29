"""Package-owned Image/Label previewers (ADR-048 SPEC 1, FR-025 / FR-026).

Registers two ``PreviewerSpec`` records via :func:`get_previewers`:

- ``imaging.image.viewer``  -> ``Image`` (kind ARRAY).
- ``imaging.label.viewer``  -> ``Label`` (kind COMPOSITE).

Both ship the same vanilla-ESM ``assets/viewer.js`` and use ``priority=100`` so
the package specs win exact-type routing yet degrade to the core array/composite
renderers when the package is absent (FR-026). The backend providers live in
:mod:`scistudio_blocks_imaging.previewers.providers` (mirroring
``scistudio-blocks-spectroscopy``).

Registered two ways:

* installed mode — the ``scistudio.previewers`` entry point in ``pyproject.toml``
  resolves ``scistudio_blocks_imaging.previewers:get_previewers``;
* monorepo dev mode — re-exported from the package top-level ``__init__``,
  discovered by ``PreviewerRegistry._scan_monorepo_packages``.

Manifest-delivery seam (FR-022/FR-024): the frontend manifest is framework-stamped
onto the :class:`PreviewEnvelope` by the ``PreviewSessionManager`` from the
resolved :class:`PreviewerSpec` (#1579); this package declares it once per spec
via :func:`get_previewers` (``frontend_manifest=...``).
"""

from __future__ import annotations

from pathlib import Path

from scistudio.previewers.models import (
    PREVIEWER_API_VERSION,
    FrontendManifest,
    OwnerKind,
    PreviewerSpec,
)
from scistudio.stability import stable

from scistudio_blocks_imaging.previewers.providers import image_provider, label_provider

# ---------------------------------------------------------------------------
# Identity + manifest constants
# ---------------------------------------------------------------------------

#: Stable previewer ids. Project/package previewer ids are namespaced by owner.
IMAGE_PREVIEWER_ID = "imaging.image.viewer"
LABEL_PREVIEWER_ID = "imaging.label.viewer"

#: Owning package name (matches the distribution / monorepo dir).
OWNER_NAME = "scistudio-blocks-imaging"

#: Frontend asset-bundle fingerprint surfaced as ``FrontendManifest.version``.
#: Bump this on every change to ``assets/viewer.js`` so the manifest reports a
#: fresh fingerprint and clients don't keep serving a stale cached viewer after
#: an upgrade / OTA refresh. Starts from the package version and is bumped
#: independently per asset change (it can therefore lead the package version).
#: 0.1.0 -> 0.1.1: viewer.js restyled to the brand ``--ss-*`` tokens (#11, after
#: the #9 / PR #10 previewer refactor).
VIEWER_BUNDLE_VERSION = "0.1.1"

#: Backend-relative, same-origin module URL the host imports the ESM viewer
#: from. The API runtime serves it via ``/api/previews/assets/<id>/<file>``
#: after path-confinement under ``asset_root`` (FR-022/FR-024).
_VIEWER_FILE = "viewer.js"

#: Filesystem directory the package confines its frontend assets under. Never
#: serialised to the frontend; used only by the backend asset validator.
_ASSET_ROOT = str(Path(__file__).resolve().parent / "assets")


def _module_url(previewer_id: str) -> str:
    return f"/api/previews/assets/{previewer_id}/{_VIEWER_FILE}"


def _frontend_manifest(previewer_id: str) -> FrontendManifest:
    """Build the same-origin :class:`FrontendManifest` for *previewer_id*."""
    return FrontendManifest(
        previewer_id=previewer_id,
        module_url=_module_url(previewer_id),
        export_name="default",
        css=(),
        version=VIEWER_BUNDLE_VERSION,
        api_version=PREVIEWER_API_VERSION,
        asset_root=_ASSET_ROOT,
    )


@stable(since="0.1.0")
def get_previewers() -> list[PreviewerSpec]:
    """Return the imaging package's :class:`PreviewerSpec` list (FR-002/FR-025).

    Both ``Image`` and ``Label`` specs declare ``owner_kind=PACKAGE`` with a
    positive ``priority`` so they win exact-type routing over the core fallbacks
    while still degrading to them when imaging is absent (FR-026).
    """
    return [
        PreviewerSpec(
            previewer_id=IMAGE_PREVIEWER_ID,
            owner_kind=OwnerKind.PACKAGE,
            owner_name=OWNER_NAME,
            target_type="Image",
            supports_collection=False,
            priority=100,
            capabilities=("slice", "lut", "range", "zoom", "metadata", "export"),
            backend_provider=image_provider,
            frontend_manifest=_frontend_manifest(IMAGE_PREVIEWER_ID),
        ),
        PreviewerSpec(
            previewer_id=LABEL_PREVIEWER_ID,
            owner_kind=OwnerKind.PACKAGE,
            owner_name=OWNER_NAME,
            target_type="Label",
            supports_collection=False,
            priority=100,
            capabilities=("slots", "raster", "metadata", "export"),
            backend_provider=label_provider,
            frontend_manifest=_frontend_manifest(LABEL_PREVIEWER_ID),
        ),
    ]


__all__ = [
    "IMAGE_PREVIEWER_ID",
    "LABEL_PREVIEWER_ID",
    "OWNER_NAME",
    "VIEWER_BUNDLE_VERSION",
    "get_previewers",
    "image_provider",
    "label_provider",
]
