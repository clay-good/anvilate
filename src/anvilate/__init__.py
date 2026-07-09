"""Anvilate: a local-first design agent for mechanical engineers.

Plain-English part descriptions compile into a typed Design Spec, which drives a
deterministic parametric-geometry and physics-validation pipeline. The
implemented layers everything else builds on:

- :mod:`anvilate.units` — SI and US customary as first-class citizens.
- :mod:`anvilate.spec` — the typed, versioned, diffable Design Spec IR.
- :mod:`anvilate.standards` — cited, provenance-tagged reference data
  (materials, standard components, metric threads and clearance holes).
- :mod:`anvilate.tolerance` — ISO 2768 general tolerances and ISO 286 fits.
- :mod:`anvilate.analysis` — T1 closed-form analytical checks (beam, column,
  torsion, pressure vessel, bolted joint, von Mises).
- :mod:`anvilate.scorecard` — the tri-state check-result vocabulary
  (pass / fail / not-evaluated).
"""

from __future__ import annotations

__version__ = "0.0.1"
