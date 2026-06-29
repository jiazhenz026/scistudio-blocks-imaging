# Package Overview — scistudio-blocks-imaging

The structured catalog required by `docs/DOCUMENTATION-STANDARD.md`. Keep it in
sync with the code: the blocks listed here match `get_blocks()` and the
`README.md` block list. Full per-block parameters live in each block's class
docstring.

## Purpose

Microscopy imaging blocks for SciStudio (Phase 11): IO, preprocessing,
morphology, segmentation, measurement, registration, projection, math,
visualization, and interactive external-app blocks. 49 concrete block classes.

## Scope and non-goals

- In scope: 2-D to 6-D images, binary masks, and label images, plus their IO,
  processing, segmentation, measurement, and rendering.
- Out of scope / deferred (Phase 12): `Deconvolve`, `TrackObjects`.

## Data types

| Type | Core base | Represents | Notes |
| --- | --- | --- | --- |
| `Image` | `Array` | General 2-D–6-D microscopy image | axes from `{t, z, c, lambda, y, x}`; OME metadata via `Image.Meta.ome` |
| `Mask` | `Image` | Binary mask | enforces `dtype=bool` |
| `Label` | `CompositeData` | Label image (`raster` + optional `polygons` slots) | OME carried via `Label.Meta.ome` |
| `Transform` | `Array` | Registration transform (affine matrix) | `shape` is `(2, 3)` or `(3, 3)` |

All four are public, `@stable` (ADR-052 §5) reuse-surface types exported at the
package top level and via `get_types()`. Each ships the ADR-052 §13.1 MUST-shape
`from_arrays(...)` domain constructor (`Image.from_arrays(pixels, axes=…)`,
`Mask.from_arrays(mask)`, `Label.from_arrays(raster=…, polygons=…)`,
`Transform.from_arrays(matrix, transform_type=…)`); the ergonomic accessors
(`to_numpy` / `to_memory` / `with_meta`) stay core's and are not shadowed.

## Blocks (49)

| Group | Blocks |
| --- | --- |
| IO | LoadImage, SaveImage |
| Preprocess | Denoise, BackgroundSubtract, Normalize, FlatFieldCorrect, Rotate, Flip, Crop, Pad, Resize, ConvertDType, AxisSplit, AxisMerge |
| Morphology | MorphologyOp, EdgeDetect, RidgeFilter, Sharpen, FFTFilter |
| Segmentation | Threshold, Watershed, CellposeSegment, BlobDetect, ConnectedComponents, RemoveSmallObjects, RemoveBorderObjects, FillHoles, ExpandLabels, ShrinkLabels |
| Measurement | RegionProps, PairwiseDistance, Colocalization |
| Registration | ComputeRegistration, ApplyTransform, RegisterSeries |
| Projection | AxisProjection, SelectSlice |
| Math | AddScalar, SubtractScalar, MultiplyScalar, DivideScalar, ImageCalculator |
| Visualization | RenderPseudoColor, RenderOverlay, RenderMontage, RenderMovie, RenderHistogram |
| Interactive | FijiBlock, NapariBlock |

## IO / format support (ADR-043)

`LoadImage`/`SaveImage` declare `FormatCapability` records:

| Format | Suffixes | Capability |
| --- | --- | --- |
| TIFF | `.tif`, `.tiff` | `pixel_only` |
| Zarr | `.zarr` | `pixel_only` |

`pixel_only` is conservative: the payload and structural axes round-trip, but
typed `Image.Meta` domain fields (pixel size, etc.) are not guaranteed to
persist across all formats. Optional Bio-Formats (`[bioformats]`, needs a JVM)
and PNG/JPEG (EXIF-mapped) handlers extend coverage.

## Previewers (ADR-048)

| Previewer | Targets | Kind | Capabilities |
| --- | --- | --- | --- |
| `imaging.image.viewer` | `Image` | array | slice, lut, range, zoom, metadata, export |
| `imaging.label.viewer` | `Label` | composite | slots, raster, metadata, export |

Both ship a self-contained vanilla-ESM `previewers/assets/viewer.js`, styled to
the SciStudio brand `--ss-*` tokens (`docs/ui-style-guide.md`). The backend
providers live in `previewers/providers.py` and read only the sanctioned typed
author surface (`request.storage` / `request.record_metadata`); TIFF/PNG
decoding is package-owned (core `data_access` reads Zarr only, by ADR-048 §4).

## Optional extras

- `[cellpose]` — `CellposeSegment` deep-learning segmentation.
- `[bioformats]` — Bio-Formats IO (requires `python-bioformats` + a JVM).

## Compatibility

- Requires `scistudio>=0.3.1a0` (ADR-052 §13.1 contract baseline).
- Python `>=3.11`.
