"""Anvilate discipline packs: domain-specific member models and their screens.

A pack layers a discipline's vocabulary (its members, load cases, and code-cited
checks) over the deterministic T1 analysis library, keeping the core Design Spec
IR lean. :mod:`anvilate.packs.structural` declares AISC-flavored structural
members (beams, columns, connections, plates, lugs) and auto-dispatches each to
the right closed-form check; :mod:`anvilate.packs.industrial` serves the
machine-builder's flat work, starting with pressure-loaded covers and panels;
:mod:`anvilate.packs.geotechnical` serves the foundation engineer (footing
bearing, retaining-wall stability, slope stability); and
:mod:`anvilate.packs.hydraulics` serves the pump-system engineer (motor adequacy
and cavitation margin); and :mod:`anvilate.packs.masonry` serves the masonry
designer, screening a wall's TMS 402 axial and combined stresses. Each screen
rolls its results into a scorecard.
"""

from __future__ import annotations
