"""Backend preview providers for ``Image`` and ``Label`` (ADR-048 SPEC 1).

These providers migrate the *rich* image-domain preview behaviour
(``frontend/src/components/DataPreview.parts/ImageViewer.tsx``: LUT colormaps,
display range, single-axis slice slider, zoom/pan, OME/channel metadata) out of
core and into ``scistudio-blocks-imaging``. Core keeps only the *generic*
numeric Array fallback (``core.array.basic``); this package owns the ``Image``
and ``Label`` target types (ADR-048 §4, §6).

Author-surface conventions (ADR-052 §8.5):

* the resolved storage reference is read from the typed ``request.storage`` and
  forwarded to ``request.data_access`` — the provider never reconstructs a
  :class:`~scistudio.core.types.StorageReference` or reads the legacy
  ``query["_storage"]`` carrier;
* recorded metadata is read from the typed ``request.record_metadata`` — never
  the legacy ``query["_record_metadata"]`` carrier.

Package-owned decoders: core ``data_access`` reads Zarr/array stores only and
keeps image-format decoders out of core by design (ADR-048 §4). This package
therefore decodes TIFF/PNG/JPEG itself for non-Zarr Image storage, reading
bounded planes capped by ``request.limits``.

Fallback design (FR-026): the Image envelope uses ``kind=ARRAY`` and carries a
PNG ``src`` data-URI plus shape/axes/slice metadata in exactly the shape the
core Array viewer understands, so a failed packaged-JS load degrades to the core
Array viewer for the same envelope with no extra round trip. ``Label`` uses
``kind=COMPOSITE`` and degrades to the core composite viewer.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

from scistudio.previewers.data_access import ArrayPlane, SliceAxis
from scistudio.previewers.models import (
    EnvelopeKind,
    PreviewEnvelope,
    PreviewMetadata,
    PreviewRequest,
    PreviewResource,
)
from scistudio.stability import stable

if TYPE_CHECKING:
    # Type-only: the runtime hands us the resolved ref on ``request.storage``;
    # an author reads and forwards it, never constructs it (ADR-052 §8.5).
    # Imported from the PUBLIC ``core.types`` re-export, never ``core.storage.ref``.
    from scistudio.core.types import StorageReference

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Request helpers (ADR-052 §8.5 author surface: typed request.storage / record_metadata)
# ---------------------------------------------------------------------------


def _ref_for(request: PreviewRequest) -> StorageReference | None:
    """Return the runtime-resolved storage reference (ADR-052 §8.5).

    The session manager resolves the catalog ref and sets it on
    ``request.storage``; the provider reads it directly and forwards it to
    ``request.data_access`` or its own bounded decoder — it never constructs a
    ``StorageReference`` or inspects the legacy ``_storage`` query carrier.
    """
    return request.storage


def _record_metadata(request: PreviewRequest) -> dict[str, Any]:
    """Return the recorded data-record metadata (ADR-052 §8.5).

    Read from the typed ``request.record_metadata`` the session manager
    populates, not the legacy ``_record_metadata`` query carrier.
    """
    return dict(request.record_metadata)


def _coerce_int(value: object, default: int) -> int:
    if value is None:
        return default
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float, str)):
        try:
            return int(value)
        except (TypeError, ValueError):
            return default
    return default


def _is_core_array_storage(ref: StorageReference) -> bool:
    path = Path(ref.path)
    backend = str(ref.backend or "").lower()
    fmt = str(ref.format or "").lower()
    return backend == "zarr" or fmt == "zarr" or path.suffix.lower() == ".zarr" or path.is_dir()


def _image_axes(ref: StorageReference, shape: tuple[int, ...]) -> list[str]:
    axes_raw = ref.metadata.get("axes") if ref.metadata else None
    if isinstance(axes_raw, list) and len(axes_raw) == len(shape):
        return [str(axis) for axis in axes_raw]
    if len(shape) == 2:
        return ["y", "x"]
    if len(shape) == 3 and int(shape[-1]) in {3, 4}:
        return ["y", "x", "c"]
    axes = [f"axis {idx}" for idx in range(len(shape))]
    if len(shape) >= 2:
        axes[-2] = "y"
        axes[-1] = "x"
    return axes


def _pillow_mode_bytes(mode: str) -> int:
    if mode.startswith("I;16"):
        return 2
    if mode in {"I", "F"}:
        return 4
    return 1


def _load_package_image_array(ref: StorageReference, *, max_bytes: int) -> Any:
    path = Path(ref.path)
    suffix = path.suffix.lower()
    fmt = str(ref.format or "").lower()

    if suffix in {".tif", ".tiff"} or fmt in {"tif", "tiff", "ome_tiff", "ome-tiff"}:
        import numpy as np
        import tifffile

        with tifffile.TiffFile(str(path)) as tf:
            page = tf.pages[0]
            try:
                page_nbytes = int(page.size) * int(page.dtype.itemsize) if page.dtype is not None else 0
            except (AttributeError, TypeError):
                page_nbytes = 0
            if page_nbytes and page_nbytes > max_bytes:
                try:
                    return np.asarray(tifffile.memmap(str(path), page=0, mode="r"))
                except (ValueError, OSError, MemoryError) as exc:
                    raise ValueError("TIFF page exceeds preview cap and is not memmappable") from exc
            return np.asarray(page.asarray())

    if suffix in {".png", ".jpg", ".jpeg"} or fmt in {"png", "jpg", "jpeg"}:
        import numpy as np
        from PIL import Image as PILImage

        with PILImage.open(path) as image:
            width, height = image.size
            bands = max(1, len(image.getbands()))
            estimated_nbytes = int(width) * int(height) * bands * _pillow_mode_bytes(image.mode)
            if estimated_nbytes > max_bytes:
                raise ValueError("image exceeds preview cap")
            return np.asarray(image)

    raise ValueError(f"unsupported imaging preview format: {suffix or fmt or path.name}")


def _finite_extent(matrix: Any) -> tuple[float | None, float | None]:
    import numpy as np

    arr = np.asarray(matrix, dtype=float)
    finite = arr[np.isfinite(arr)]
    if finite.size == 0:
        return None, None
    return float(finite.min()), float(finite.max())


def _json_matrix(matrix: Any) -> list[list[float | None]]:
    import math

    import numpy as np

    arr = np.asarray(matrix, dtype=float)
    return [[(float(v) if math.isfinite(float(v)) else None) for v in row] for row in arr.tolist()]


def _downsample(matrix: Any, *, max_dim: int) -> Any:
    import numpy as np

    arr = np.asarray(matrix)
    h, w = int(arr.shape[0]), int(arr.shape[1])
    if max(h, w) <= max_dim:
        return arr
    new_h = max(1, int(h * (max_dim / max(h, w))))
    new_w = max(1, int(w * (max_dim / max(h, w))))
    row_idx = np.linspace(0, h - 1, new_h, dtype=int)
    col_idx = np.linspace(0, w - 1, new_w, dtype=int)
    return arr[np.ix_(row_idx, col_idx)]


def _package_image_plane(ref: StorageReference, *, slice_index: int, max_dim: int, max_bytes: int) -> ArrayPlane:
    import numpy as np

    arr = np.asarray(_load_package_image_array(ref, max_bytes=max_bytes))
    if arr.size * arr.dtype.itemsize > max_bytes:
        raise ValueError("image array exceeds preview cap")
    full_shape = [int(dim) for dim in arr.shape]
    ndim = len(full_shape)
    axes = _image_axes(ref, tuple(arr.shape))
    slice_axes: list[SliceAxis] = []

    if ndim == 0:
        plane = arr.reshape(1, 1)
    elif ndim == 1:
        plane = arr.reshape(1, int(arr.shape[0]))
    elif axes and "y" in axes and "x" in axes:
        y_idx = axes.index("y")
        x_idx = axes.index("x")
        selectors: list[Any] = [slice(None)] * ndim
        extra_dims = [idx for idx in range(ndim) if idx not in (y_idx, x_idx)]
        for extra in extra_dims:
            size = int(full_shape[extra])
            idx = max(0, min(int(slice_index), size - 1)) if size > 0 else 0
            selectors[extra] = idx
            slice_axes.append(SliceAxis(axis=extra, name=axes[extra], size=size, index=idx))
        plane = np.asarray(arr[tuple(selectors)])
        if y_idx > x_idx:
            plane = plane.T
    else:
        plane = np.asarray(arr)
        while plane.ndim > 2:
            size = int(plane.shape[0])
            idx = max(0, min(int(slice_index), size - 1)) if size > 0 else 0
            slice_axes.append(SliceAxis(axis=len(slice_axes), name=f"axis {len(slice_axes)}", size=size, index=idx))
            plane = plane[idx]

    if plane.ndim == 0:
        plane = plane.reshape(1, 1)
    elif plane.ndim == 1:
        plane = plane.reshape(1, int(plane.shape[0]))
    while plane.ndim > 2:
        plane = plane[0]
    first = slice_axes[0] if slice_axes else None
    downsampled = _downsample(plane, max_dim=max_dim)
    vmin, vmax = _finite_extent(plane)
    return ArrayPlane(
        shape=full_shape,
        axes=axes,
        dtype=str(arr.dtype),
        slice_axis_name=first.name if first is not None else None,
        slice_axis_size=first.size if first is not None else None,
        slice_index=first.index if first is not None else None,
        slice_axes=slice_axes,
        matrix=_json_matrix(downsampled),
        vmin=vmin,
        vmax=vmax,
        truncated=max(int(plane.shape[0]), int(plane.shape[1])) > max_dim if plane.ndim >= 2 else False,
        ndim=ndim,
    )


def _image_metadata_panel(record_md: dict[str, Any]) -> dict[str, Any]:
    """Extract a bounded, JSON-safe OME/channel metadata panel.

    Surfaces only display-relevant scalar fields from the recorded ``Image``/
    ``Label`` metadata so the packaged viewer can render an info panel without
    ever materialising the full OME-XML model. Unknown shapes are skipped.
    """
    panel: dict[str, Any] = {}
    for key in (
        "pixel_size",
        "z_spacing",
        "time_interval",
        "objective",
        "instrument",
        "acquisition_date",
        "source_file",
        "wavelengths_nm",
        "n_objects",
    ):
        value = record_md.get(key)
        if value is not None and isinstance(value, (str, int, float, list)):
            panel[key] = value

    channels = record_md.get("channels")
    if isinstance(channels, list):
        bounded: list[dict[str, Any]] = []
        for ch in channels:
            if isinstance(ch, dict):
                name = ch.get("name")
                entry: dict[str, Any] = {}
                if isinstance(name, str):
                    entry["name"] = name
                exc = ch.get("excitation_nm")
                if isinstance(exc, (int, float)):
                    entry["excitation_nm"] = exc
                if entry:
                    bounded.append(entry)
            elif isinstance(ch, str):
                bounded.append({"name": ch})
        if bounded:
            panel["channels"] = bounded

    # OME is recorded but is a large model; expose only a presence flag.
    if record_md.get("ome") is not None:
        panel["has_ome"] = True
    return panel


def _error_envelope(request: PreviewRequest, message: str) -> PreviewEnvelope:
    """Embed a typed error envelope (providers must not raise for routine
    failures — FR-028)."""
    from scistudio.previewers.models import PreviewErrorCode, PreviewErrorInfo

    return PreviewEnvelope(
        previewer_id=request.spec.previewer_id,
        target=request.target,
        kind=EnvelopeKind.ERROR,
        metadata=PreviewMetadata(complete=False, failed=True),
        error=PreviewErrorInfo(code=PreviewErrorCode.PROVIDER_EXCEPTION, message=message),
    )


# ---------------------------------------------------------------------------
# Image provider (rich image-domain preview; kind=ARRAY for core fallback)
# ---------------------------------------------------------------------------


@stable(since="0.1.0")
def image_provider(request: PreviewRequest) -> PreviewEnvelope:
    """Render a rich Image preview envelope (ADR-048 FR-025).

    Reads one bounded, downsampled 2-D plane — via ``request.data_access`` for
    Zarr/array stores, or this package's bounded decoder for TIFF/PNG/JPEG — and
    encodes it as a grayscale PNG data-URI (the same payload the core Array
    viewer consumes). The packaged JS viewer adds LUT, display-range, slice
    slider, zoom/pan, and an OME/channel info panel on top. ``kind=ARRAY`` so a
    failed dynamic-module load degrades cleanly to the core Array viewer
    (FR-026).
    """
    ref = _ref_for(request)
    if ref is None:
        return _error_envelope(request, "image preview failed: no storage reference on the request")
    slice_index = _coerce_int(request.query.get("slice_index"), 0)
    uses_core_array_storage = _is_core_array_storage(ref)
    try:
        if uses_core_array_storage:
            plane = request.data_access.array_plane(ref, slice_index=slice_index)
        else:
            plane = _package_image_plane(
                ref,
                slice_index=slice_index,
                max_dim=request.limits.max_dim,
                max_bytes=request.limits.max_bytes,
            )
    except Exception as exc:
        logger.debug("imaging image preview failed for %s", ref.path, exc_info=True)
        return _error_envelope(request, f"image preview failed: {exc}")

    src = request.data_access.png_data_uri(plane.matrix)
    record_md = _record_metadata(request)
    info_panel = _image_metadata_panel(record_md)

    resources_list: list[PreviewResource] = []
    if uses_core_array_storage:
        resources_list.append(
            PreviewResource(
                resource_id="tile",
                kind="tile",
                media_type="application/json",
                description="bounded image tile read",
                params={"slice_index": plane.slice_index or 0},
            )
        )
    resources_list.append(
        PreviewResource(
            resource_id="export",
            kind="asset",
            media_type="image/png",
            description="export the displayed image plane as PNG",
            params={"format": "png", "slice_index": plane.slice_index or 0},
        )
    )
    resources = tuple(resources_list)

    extra: dict[str, Any] = {
        "shape": plane.shape,
        "dtype": plane.dtype,
        "axes": plane.axes,
        "image_metadata": info_panel,
    }
    return PreviewEnvelope(
        previewer_id=request.spec.previewer_id,
        target=request.target,
        kind=EnvelopeKind.ARRAY,
        payload={
            "shape": plane.shape,
            "dtype": plane.dtype,
            "axes": plane.axes,
            "ndim": plane.ndim,
            "slice_axis_name": plane.slice_axis_name,
            "slice_axis_size": plane.slice_axis_size,
            "slice_index": plane.slice_index,
            "thumbnail": plane.matrix,
            "src": src,
            "image_metadata": info_panel,
        },
        resources=resources,
        metadata=PreviewMetadata(
            sampled=plane.truncated,
            truncated=plane.truncated,
            complete=not plane.truncated,
            extra=extra,
        ),
    )


# ---------------------------------------------------------------------------
# Label provider (composite: raster + polygon slot inventory)
# ---------------------------------------------------------------------------


@stable(since="0.1.0")
def label_provider(request: PreviewRequest) -> PreviewEnvelope:
    """Render a Label preview envelope (ADR-048 FR-025).

    A ``Label`` is a ``CompositeData`` with ``raster`` and/or ``polygons``
    slots. This provider surfaces the slot inventory (no eager child render),
    a bounded raster plane (as a PNG data-URI) when a raster slot exists, and
    the OME/object-count metadata panel. ``kind=COMPOSITE`` so the host routes
    to the packaged label viewer (and to the core composite viewer if the
    dynamic module fails).
    """
    record_md = _record_metadata(request)
    slots = request.data_access.composite_slots(record_md)
    info_panel = _image_metadata_panel(record_md)

    payload: dict[str, Any] = {"slots": slots.slots, "image_metadata": info_panel}
    diagnostics: list[str] = []
    truncated = False

    # Bounded raster preview when a raster slot is present.
    ref = _ref_for(request)
    raster_plane = None
    if ref is not None and "raster" in slots.slots:
        try:
            raster_plane = request.data_access.composite_raster_slot(ref, slot_name="raster")
        except Exception as exc:  # pragma: no cover - defensive
            diagnostics.append(f"raster slot preview failed: {exc}")
    if raster_plane is not None:
        truncated = bool(raster_plane.truncated)
        payload["raster"] = {
            "shape": raster_plane.shape,
            "dtype": raster_plane.dtype,
            "axes": raster_plane.axes,
            "ndim": raster_plane.ndim,
            "slice_axis_name": raster_plane.slice_axis_name,
            "slice_axis_size": raster_plane.slice_axis_size,
            "slice_index": raster_plane.slice_index,
            "thumbnail": raster_plane.matrix,
            "src": request.data_access.png_data_uri(raster_plane.matrix),
        }

    resources = tuple(
        PreviewResource(
            resource_id=f"slot:{name}",
            kind="child",
            description=f"child preview for slot '{name}' ({type_name})",
            params={"slot": name, "slot_type": type_name},
        )
        for name, type_name in slots.slots.items()
    )

    extra: dict[str, Any] = {
        "slot_count": len(slots.slots),
        "image_metadata": info_panel,
    }
    return PreviewEnvelope(
        previewer_id=request.spec.previewer_id,
        target=request.target,
        kind=EnvelopeKind.COMPOSITE,
        payload=payload,
        resources=resources,
        diagnostics=tuple(diagnostics),
        metadata=PreviewMetadata(
            sampled=truncated,
            truncated=truncated,
            complete=not truncated,
            extra=extra,
        ),
    )


__all__ = ["image_provider", "label_provider"]
