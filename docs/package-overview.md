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
| `Transform` | (internal) | Registration transform | helper type, not a public DataObject |

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

Both ship a self-contained vanilla-ESM `previewers/assets/viewer.js`.

## Optional extras

- `[cellpose]` — `CellposeSegment` deep-learning segmentation.
- `[bioformats]` — Bio-Formats IO (requires `python-bioformats` + a JVM).

## Compatibility

- Requires `scistudio>=0.2.1a0`.
- Python `>=3.11`.
