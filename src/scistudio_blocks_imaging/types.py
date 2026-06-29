"""Imaging plugin public data types (T-IMG-001).

The package's developer-facing reuse surface (ADR-052 §4.2, §13.1): the four
``DataObject`` subclasses an author names on a port and builds. Each is public
at the package top level, subclasses a core type imported from the public
``scistudio.core.types`` root, carries an ADR-052 §5 stability marker, and ships
the §13.1 MUST-shape ``from_arrays(...)`` domain constructor on the type. The
ergonomic accessors (``to_memory`` / ``to_numpy`` / ``with_meta`` / ``sel``)
stay core's and are never shadowed here.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, ClassVar

import numpy as np
from ome_types.model import OME
from pydantic import BaseModel, ConfigDict, field_validator
from scistudio.core.meta import ChannelInfo
from scistudio.core.types import Array, CompositeData, DataFrame
from scistudio.core.units import PhysicalQuantity
from scistudio.stability import stable


@stable(since="0.1.0")
class Image(Array):
    """General-purpose microscopy image, 2D to 6D."""

    required_axes: ClassVar[frozenset[str]] = frozenset({"y", "x"})
    allowed_axes: ClassVar[frozenset[str] | None] = frozenset({"t", "z", "c", "lambda", "y", "x"})
    canonical_order: ClassVar[tuple[str, ...]] = ("t", "z", "c", "lambda", "y", "x")

    @stable(since="0.1.0")
    class Meta(BaseModel):
        """Per-instance imaging metadata."""

        # ADR-043 / spec adr-043-package-migration FR-006: ``ome`` is a typed
        # carrier for the canonical OME-XML metadata structure. Populated by
        # IO handlers (Bio-Formats, OME-TIFF, PNG/JPEG EXIF mapping) and
        # propagated through ProcessBlocks per the propagation contract
        # (FR-009 modes A/B/C). The default is ``None`` so existing call sites
        # constructing ``Image.Meta()`` remain backward-compatible.
        # Pydantic v2 needs ``arbitrary_types_allowed`` to embed the
        # ``ome_types`` model class because it is exposed as a non-BaseModel
        # subclass after compat shimming on some platforms; declare it
        # alongside ``frozen=True``.
        model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

        pixel_size: PhysicalQuantity | None = None
        z_spacing: PhysicalQuantity | None = None
        time_interval: PhysicalQuantity | None = None
        channels: list[ChannelInfo] | None = None
        wavelengths_nm: list[float] | None = None
        objective: str | None = None
        acquisition_date: datetime | None = None
        source_file: str | None = None
        instrument: str | None = None
        ome: OME | None = None

        @field_validator("channels", mode="before")
        @classmethod
        def _coerce_channels(cls, value: Any) -> Any:
            if value is None:
                return None
            if not isinstance(value, list):
                return value

            coerced: list[Any] = []
            for item in value:
                if isinstance(item, str):
                    coerced.append(ChannelInfo(name=item))
                else:
                    coerced.append(item)
            return coerced

    @classmethod
    @stable(since="0.1.0")
    def from_arrays(
        cls,
        pixels: Any,
        *,
        axes: list[str] | None = None,
        meta: Image.Meta | None = None,
    ) -> Image:
        """Construct an :class:`Image` from a domain-native pixel array.

        The ADR-052 §13.1 MUST-shape packing constructor: takes the author's
        natural input (a NumPy-like pixel array) and the named axes, packs it
        into the canonical ``data=`` form, and returns ``cls(...)`` so callers
        never touch the storage layer. A 2-D array defaults to ``["y", "x"]``;
        higher-rank arrays require explicit *axes* because the axis alphabet
        (``t/z/c/lambda/y/x``) cannot be inferred from rank alone.
        """
        arr = np.asarray(pixels)
        if axes is None:
            if arr.ndim == 2:
                resolved_axes = ["y", "x"]
            else:
                raise ValueError(
                    f"{cls.__name__}.from_arrays needs explicit axes for a {arr.ndim}-D array "
                    "(only 2-D input defaults to ['y', 'x'])"
                )
        else:
            resolved_axes = list(axes)
        return cls(axes=resolved_axes, shape=tuple(arr.shape), dtype=str(arr.dtype), data=arr, meta=meta)


@stable(since="0.1.0")
class Mask(Image):
    """Binary mask image. Enforces ``dtype=bool`` at construction."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._validate_mask_dtype()

    def _validate_mask_dtype(self) -> None:
        """Enforce ``dtype == bool``."""
        if self.dtype is None:
            return
        if np.dtype(self.dtype) != np.dtype(bool):
            raise ValueError(f"Mask requires dtype=bool, got {self.dtype}")

    @classmethod
    @stable(since="0.1.0")
    def from_arrays(
        cls,
        mask: Any,
        *,
        axes: list[str] | None = None,
        meta: Image.Meta | None = None,
    ) -> Mask:
        """Construct a :class:`Mask` from a domain-native array, coercing to ``bool``.

        Mirrors :meth:`Image.from_arrays` but casts the input to ``bool`` so the
        result always satisfies the strict mask-dtype invariant.
        """
        return super().from_arrays(np.asarray(mask).astype(bool), axes=axes, meta=meta)


@stable(since="0.1.0")
class Label(CompositeData):
    """Label image with raster and/or polygon representation."""

    expected_slots: ClassVar[dict[str, type]] = {
        "raster": Array,
        "polygons": DataFrame,
    }

    @stable(since="0.1.0")
    class Meta(BaseModel):
        """Per-instance label-image metadata."""

        # ADR-043 / spec adr-043-package-migration FR-007: ``ome`` is added
        # explicitly here because ``Label.Meta`` inherits from
        # :class:`pydantic.BaseModel` directly (sibling of ``Image.Meta``,
        # not subclass). The field carries the source ``Image``'s OME
        # metadata across shape-preserving cross-type derivations (FR-009
        # Mode C, e.g. segmentation: ``Image → Label``).
        model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)
        source_file: str | None = None
        n_objects: int | None = None
        ome: OME | None = None

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._validate_label_slots()

    @property
    def slots(self) -> dict[str, Any]:
        """Expose populated composite slots for downstream blocks/tests.

        Built through the public :class:`CompositeData` accessors
        (:attr:`~CompositeData.slot_names` / :meth:`~CompositeData.get`) so the
        package never reaches into core's private slot storage.
        """
        return {name: self.get(name) for name in self.slot_names}

    def _validate_label_slots(self) -> None:
        """Enforce at least one of ``raster`` / ``polygons`` is populated."""
        if not ({"raster", "polygons"} & set(self.slot_names)):
            raise ValueError("Label requires at least one of raster or polygons to be non-None")

    @classmethod
    @stable(since="0.1.0")
    def from_arrays(
        cls,
        raster: Any = None,
        polygons: Any = None,
        *,
        axes: list[str] | None = None,
        meta: Label.Meta | None = None,
    ) -> Label:
        """Construct a :class:`Label` from a raster array and/or a polygon table.

        The ADR-052 §13.1 MUST-shape packing constructor for the composite
        ``Label`` type. At least one representation is required:

        * *raster* — a NumPy-like integer label array, packed into a core
          :class:`~scistudio.core.types.Array` slot (2-D defaults to
          ``["y", "x"]``; higher rank requires explicit *axes*).
        * *polygons* — a ``pyarrow.Table`` (or a ``pandas.DataFrame``), packed
          into a core :class:`~scistudio.core.types.DataFrame` slot.
        """
        if raster is None and polygons is None:
            raise ValueError("Label.from_arrays requires at least one of raster or polygons")

        slots: dict[str, Any] = {}
        if raster is not None:
            arr = np.asarray(raster)
            if axes is None:
                if arr.ndim == 2:
                    resolved_axes = ["y", "x"]
                else:
                    raise ValueError(
                        f"Label.from_arrays needs explicit axes for a {arr.ndim}-D raster "
                        "(only 2-D input defaults to ['y', 'x'])"
                    )
            else:
                resolved_axes = list(axes)
            slots["raster"] = Array(axes=resolved_axes, shape=tuple(arr.shape), dtype=str(arr.dtype), data=arr)
        if polygons is not None:
            import pyarrow as pa

            table = polygons if isinstance(polygons, pa.Table) else pa.Table.from_pandas(polygons)
            slots["polygons"] = DataFrame(columns=table.column_names, row_count=table.num_rows, data=table)

        return cls(slots=slots, meta=meta)


@stable(since="0.1.0")
class Transform(Array):
    """Affine transform matrix."""

    required_axes: ClassVar[frozenset[str]] = frozenset({"row", "col"})
    allowed_axes: ClassVar[frozenset[str] | None] = frozenset({"row", "col"})
    canonical_order: ClassVar[tuple[str, ...]] = ("row", "col")

    @stable(since="0.1.0")
    class Meta(BaseModel):
        """Per-instance transform metadata."""

        model_config = ConfigDict(frozen=True)
        transform_type: str
        reference_shape: tuple[int, ...] | None = None

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._validate_transform_shape()

    def _validate_transform_shape(self) -> None:
        if self.shape is None:
            return
        if self.shape not in {(2, 3), (3, 3)}:
            raise ValueError(f"Transform shape must be (2, 3) or (3, 3), got {self.shape}")

    @classmethod
    @stable(since="0.1.0")
    def from_arrays(
        cls,
        matrix: Any,
        *,
        transform_type: str,
        reference_shape: tuple[int, ...] | None = None,
    ) -> Transform:
        """Construct a :class:`Transform` from a domain-native affine matrix.

        The ADR-052 §13.1 MUST-shape packing constructor: takes a ``(2, 3)`` or
        ``(3, 3)`` matrix and the *transform_type*, packs the matrix into the
        canonical ``data=`` form on the fixed ``["row", "col"]`` axes, and
        returns ``cls(...)``.
        """
        arr = np.asarray(matrix)
        return cls(
            axes=["row", "col"],
            shape=tuple(arr.shape),
            dtype=str(arr.dtype),
            data=arr,
            meta=cls.Meta(transform_type=transform_type, reference_shape=reference_shape),
        )


__all__ = ["Image", "Label", "Mask", "Transform"]
