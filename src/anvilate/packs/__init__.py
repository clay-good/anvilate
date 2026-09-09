"""Anvilate discipline packs: domain-specific member models and their screens.

A pack layers a discipline's vocabulary (its members, load cases, and code-cited
checks) over the deterministic T1 analysis library, keeping the core Design Spec
IR lean. :mod:`anvilate.packs.structural` declares AISC-flavored structural
members (beams, columns, connections, plates, lugs) and auto-dispatches each to
the right closed-form check; :mod:`anvilate.packs.industrial` serves the
machine-builder's flat work, starting with pressure-loaded covers and panels;
:mod:`anvilate.packs.geotechnical` serves the foundation engineer (footing
bearing, retaining-wall stability, slope stability); and
:mod:`anvilate.packs.hydraulics` serves the pump-system engineer (pump motor
adequacy and cavitation margin, and a pipe run's head budget); and
:mod:`anvilate.packs.masonry` serves the masonry
designer, screening a wall's TMS 402 axial and combined stresses; and
:mod:`anvilate.packs.noise_exposure` serves the industrial hygienist, screening
a worker's OSHA/NIOSH noise dose; :mod:`anvilate.packs.lighting` serves the
lighting designer, screening a layout's task illuminance against its energy-code
power density; and :mod:`anvilate.packs.ventilation` serves the HVAC/IAQ
engineer, screening a zone's ASHRAE 62.1 outdoor air and its air-change rate;
and :mod:`anvilate.packs.electrical` serves the electrical designer, screening a
feeder's voltage drop and conductor ampacity; and
:mod:`anvilate.packs.machinery` serves the machine designer, screening a
transmission shaft against the three limits that size one and disagree about it
— static distortion energy, rotating-shaft fatigue and torsional windup — and a
spur gear mesh against AGMA bending, pitting, contact ratio and undercut, which
four are moved by three different parameters, and the shaft's two neighbours a
card of its own cannot see: the key that drives it and the bearing that holds
it, plus a helical compression spring whose clearance and buckling checks pull
its free length in opposite directions. Each screen rolls its results into a
scorecard.
"""

from __future__ import annotations
