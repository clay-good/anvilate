# Change: Semantic GD&T layer — an open feature-control-frame data model

## Why

Research confirmed the niche is vacant: outside two small 1D stack-up hobby tools
(https://github.com/slightlynybbled/tol-stack, https://github.com/aevyrie/tolstack),
no open-source semantic GD&T model exists — no feature-control-frame parser, no
datum-reference-frame library, no ASME Y14.5 / ISO 1101 vocabulary layer. Commercial
tolerance software (CETOL-class) owns the space. Anvilate's tolerance capability already
declares geometric tolerances and does stack-up math at or beyond the OSS state of the
art; what's missing is the semantic layer that makes those declarations a typed model —
the bridge to AP242 semantic PMI on export, QIF characteristics in quality interchange,
and richer stack-up consumption (position tolerances contributing to chains).

## What Changes

- `tolerance-management` gains two requirements: a typed semantic GD&T model (feature
  control frames with symbols, values, modifiers, and datum reference frames, using
  Y14.5/ISO 1101 vocabulary, validated against the semantic tag graph), and defined
  export/interchange semantics (the same model populates drawing feature control frames,
  AP242 semantic PMI, and QIF characteristics — one model, three consumers).

## Impact

- Affected specs: `tolerance-management` (2 added requirements); consumed by
  `drawing-generation`, `artifact-export`, and the QIF export (all unchanged — they
  already reference geometric tolerances; this types the source they render).
- Affected code (when implemented): GD&T model types, tag-graph validation, stack-up
  integration for position tolerances.
