"""Anvilate: a local-first design agent for mechanical engineers.

Plain-English part descriptions compile into a typed Design Spec, which drives a
deterministic parametric-geometry and physics-validation pipeline. This release
implements the two foundational layers everything else builds on:

- :mod:`anvilate.units` — SI and US customary as first-class citizens.
- :mod:`anvilate.spec` — the typed, versioned, diffable Design Spec IR.
"""

from __future__ import annotations

__version__ = "0.0.1"
