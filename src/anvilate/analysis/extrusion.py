"""T1 analytical (direct) extrusion checks (closed-form).

Extrusion forces a billet through a die to make a long constant-section shape — rod, tube, or the
aluminium profiles in every window frame. With :mod:`anvilate.analysis.forging` (compression between
dies) and :mod:`anvilate.analysis.rolling` (a continuous roll gap), it is the third of the canonical
bulk-deformation processes, and the one that reaches the largest reductions in a single step.

How much the section shrinks is the *extrusion ratio* R = A₀/A_f, the billet area over the extrudate
area — a ratio of 40 for aluminium is routine. The work of squeezing the metal down by that much
sets the ram pressure: ideally, homogeneous deformation costs p = Y_avg·ln(R), the average flow
stress of the (work-hardening) metal times the natural strain ln(R) it undergoes. Real extrusion
costs more — friction on the container wall and the die, and the redundant work of the internal
shearing, so the ideal pressure is divided by a deformation efficiency η (~0.5–0.65) to estimate the
actual ram pressure.

That pressure acting on the billet cross-section is the ram force F = p·A₀ the press must supply.
Because pressure climbs with ln(R), extreme ratios push the press hard — the reason extrusion runs
hot, where the flow stress is low, for all but the softest metals.
"""

from __future__ import annotations

from math import log

from ..units import Quantity

__all__ = [
    "extrusion_force",
    "extrusion_pressure",
    "extrusion_ratio",
]


def extrusion_ratio(*, billet_area: Quantity, extrudate_area: Quantity) -> float:
    """The extrusion ratio, R = A₀/A_f.

    How much the cross-section is reduced in one pass: the ``billet_area`` A₀ over the
    ``extrudate_area`` A_f, R = A₀/A_f. It is the headline measure of an extrusion — ratios of
    10–40 (and far higher for soft aluminium) are worked in a single step, which is what sets
    extrusion apart from rolling. It drives the ram pressure through the strain ln(R) (see
    :func:`extrusion_pressure`). Returns the dimensionless extrusion ratio.
    """
    _check(billet_area, "[area]", "billet_area")
    _check(extrudate_area, "[area]", "extrudate_area")
    a0 = billet_area.to("mm**2").magnitude
    af = extrudate_area.to("mm**2").magnitude
    if a0 <= 0 or af <= 0:
        raise ValueError("billet_area and extrudate_area must be positive")
    if af >= a0:
        raise ValueError("extrudate_area must be smaller than billet_area (extrusion reduces area)")
    return a0 / af


def extrusion_pressure(
    *,
    flow_stress: Quantity,
    extrusion_ratio: float,
    deformation_efficiency: float = 1.0,
) -> Quantity:
    """The ram pressure to extrude, p = Y_avg·ln(R)/η.

    The pressure the ram must apply to push the billet through the die, from the average
    ``flow_stress`` Y_avg of the metal (see :mod:`anvilate.analysis.forging`) and the
    ``extrusion_ratio`` R: ideally p = Y_avg·ln(R) for homogeneous deformation, divided by
    the ``deformation_efficiency`` η (0 to 1, ~0.5–0.65) to include the container/die friction and
    the redundant shearing work that make real extrusion cost more. Feeds :func:`extrusion_force`.
    Returns the ram pressure in MPa.
    """
    _check(flow_stress, "[pressure]", "flow_stress")
    y = flow_stress.to("MPa").magnitude
    if y <= 0:
        raise ValueError("flow_stress must be positive")
    if extrusion_ratio <= 1.0:
        raise ValueError("extrusion_ratio must exceed 1 (extrusion reduces the section)")
    if not 0.0 < deformation_efficiency <= 1.0:
        raise ValueError(f"deformation_efficiency must be in (0, 1]; got {deformation_efficiency}")
    return Quantity(magnitude=y * log(extrusion_ratio) / deformation_efficiency, unit="MPa")


def extrusion_force(*, extrusion_pressure: Quantity, billet_area: Quantity) -> Quantity:
    """The ram force to extrude, F = p·A₀.

    The force the press must supply, the ``extrusion_pressure`` p (from
    :func:`extrusion_pressure`) acting on the ``billet_area`` A₀ it pushes on: F = p·A₀. This is the
    tonnage that sizes the extrusion press — and because the pressure grows with ln(R), a high
    ratio drives it up steeply, which is why extrusion is usually done hot to keep the flow stress,
    and so the force, down. Returns the ram force in kN.
    """
    _check(extrusion_pressure, "[pressure]", "extrusion_pressure")
    _check(billet_area, "[area]", "billet_area")
    p = extrusion_pressure.to("Pa").magnitude
    a0 = billet_area.to("m**2").magnitude
    if p <= 0:
        raise ValueError("extrusion_pressure must be positive")
    if a0 <= 0:
        raise ValueError("billet_area must be positive")
    return Quantity(magnitude=p * a0 / 1000.0, unit="kN")


def _check(value: Quantity, expected: str, name: str) -> None:
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )
