"""T1 analytical bolted/pinned-joint checks (closed-form).

The workhorse relation for a bolted joint is ``T = K·F·d``: the tightening torque
``T`` produces a preload ``F`` in a thread of nominal diameter ``d``, scaled by
the nut factor ``K`` (an empirical coefficient rolling up thread and under-head
friction). It inverts to ``F = T/(K·d)``. Given a fastener's nominal diameter
from the standards tables, those two functions convert between the torque a shop
applies and the preload it develops — a screening estimate, since K varies
widely with lubrication and surface finish.

A separate failure mode is bearing (the fastener crushing the hole it passes
through): ``σ_bearing = F/(d·t)`` over the projected pin-and-plate contact area.

A bolt in tension does not carry its axial load on the nominal shank area but on
the smaller *tensile stress area* through the threads, ``A_t = (π/4)·(d −
0.9382·P)²`` (ISO 898 / Shigley), midway between the pitch- and minor-diameter
areas — so the axial stress is ``σ = F/A_t``, always higher than F over the
nominal area.

As with the beam and column checks, inputs and outputs are dimension-checked
:class:`~anvilate.units.Quantity` values and the arithmetic runs through Pint.
"""

from __future__ import annotations

from math import pi

from ..units import Quantity

# ISO 898 tensile-stress-area factor: A_t = (pi/4)(d - 0.9382*P)^2, where the
# effective diameter is the mean of the pitch and rounded-root minor diameters.
_TENSILE_AREA_PITCH_FACTOR = 0.9382

__all__ = [
    "NUT_FACTOR_AS_RECEIVED",
    "bolt_preload_from_torque",
    "torque_for_preload",
    "bearing_stress",
    "bolt_shear_stress",
    "bolt_tensile_stress_area",
    "bolt_axial_stress",
]

# Typical nut factor K for as-received (lightly-oiled) steel fasteners. Dry/rough
# joints run higher (~0.3), well-lubricated or coated ones lower (~0.15); K is the
# dominant uncertainty in torque-tension, so it is exposed as a parameter.
NUT_FACTOR_AS_RECEIVED = 0.2


def _require(value: Quantity, expected: str, name: str) -> None:
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )


def _positive_factor(nut_factor: float) -> None:
    if nut_factor <= 0:
        raise ValueError(f"nut_factor must be positive; got {nut_factor}")


def bolt_preload_from_torque(
    *,
    torque: Quantity,
    nominal_diameter: Quantity,
    nut_factor: float = NUT_FACTOR_AS_RECEIVED,
) -> Quantity:
    """The preload F = T/(K·d) a tightening ``torque`` develops in a thread.

    ``nominal_diameter`` is the thread's nominal diameter d (e.g. 8 mm for M8,
    from the standards tables); ``nut_factor`` is K. Returns the preload as a
    force. ``torque`` must be a torque (force·length) and ``nominal_diameter`` a
    length; ``nut_factor`` must be positive.
    """
    _require(torque, "[force] * [length]", "torque")
    _require(nominal_diameter, "[length]", "nominal_diameter")
    _positive_factor(nut_factor)
    preload = torque.pint / (nut_factor * nominal_diameter.pint)
    converted = preload.to("N")
    return Quantity(magnitude=float(converted.magnitude), unit="N")


def torque_for_preload(
    *,
    preload: Quantity,
    nominal_diameter: Quantity,
    nut_factor: float = NUT_FACTOR_AS_RECEIVED,
) -> Quantity:
    """The tightening torque T = K·F·d for a target ``preload``.

    The inverse of :func:`bolt_preload_from_torque`. ``preload`` must be a force
    and ``nominal_diameter`` a length; ``nut_factor`` must be positive. Returns the
    torque in newton-metres.
    """
    _require(preload, "[force]", "preload")
    _require(nominal_diameter, "[length]", "nominal_diameter")
    _positive_factor(nut_factor)
    torque = nut_factor * preload.pint * nominal_diameter.pint
    converted = torque.to("N*m")
    return Quantity(magnitude=float(converted.magnitude), unit="N*m")


def bearing_stress(
    *,
    force: Quantity,
    diameter: Quantity,
    thickness: Quantity,
) -> Quantity:
    """The bearing stress σ = F/(d·t) a fastener exerts on the hole it bears in.

    ``force`` is the load transferred through the joint, ``diameter`` the pin or
    bolt diameter, and ``thickness`` the bearing plate thickness — the projected
    contact area is d·t. Returns the bearing stress in MPa; every quantity is
    dimension-checked and ``diameter``/``thickness`` must be positive.
    """
    _require(force, "[force]", "force")
    _require(diameter, "[length]", "diameter")
    _require(thickness, "[length]", "thickness")
    for value, name in ((diameter, "diameter"), (thickness, "thickness")):
        if value.to("mm").magnitude <= 0:
            raise ValueError(f"{name} must be positive; got {value}")
    stress = force.pint / (diameter.pint * thickness.pint)
    converted = stress.to("MPa")
    return Quantity(magnitude=float(converted.magnitude), unit="MPa")


def bolt_shear_stress(
    *,
    force: Quantity,
    diameter: Quantity,
    shear_planes: int = 1,
) -> Quantity:
    """The average shear stress τ = F/(n·A) across a bolt or pin in shear.

    ``force`` is the transverse load, ``diameter`` the shank diameter (A = π·d²/4),
    and ``shear_planes`` the number of shear planes — 1 for single shear (a lap
    joint), 2 for double shear (a clevis). Returns the shear stress in MPa;
    ``shear_planes`` must be a positive integer.
    """
    _require(force, "[force]", "force")
    _require(diameter, "[length]", "diameter")
    if shear_planes < 1:
        raise ValueError(f"shear_planes must be a positive integer; got {shear_planes}")
    area = pi * diameter.pint**2 / 4
    stress = force.pint / (shear_planes * area)
    converted = stress.to("MPa")
    return Quantity(magnitude=float(converted.magnitude), unit="MPa")


def bolt_tensile_stress_area(*, nominal_diameter: Quantity, pitch: Quantity) -> Quantity:
    """The ISO 898 tensile stress area A_t = (π/4)·(d − 0.9382·P)² of a metric
    thread.

    A threaded bolt in tension carries its load on A_t — an effective area midway
    between the pitch- and minor-diameter areas — not on the nominal shank. Recovers
    the ISO 898-1 table values (M10×1.5 → 58.0 mm², M8×1.25 → 36.6 mm²).
    ``nominal_diameter`` is the thread's nominal diameter d and ``pitch`` its thread
    pitch P (both from the standards :class:`~anvilate.standards.MetricThread`).
    Returns the area in mm²; both must be lengths and d must exceed 0.9382·P.
    """
    _require(nominal_diameter, "[length]", "nominal_diameter")
    _require(pitch, "[length]", "pitch")
    d = nominal_diameter.to("mm").magnitude
    p = pitch.to("mm").magnitude
    if p <= 0:
        raise ValueError(f"pitch must be positive; got {pitch}")
    effective = d - _TENSILE_AREA_PITCH_FACTOR * p
    if effective <= 0:
        raise ValueError(
            f"nominal_diameter ({nominal_diameter}) must exceed 0.9382·pitch "
            f"({pitch}) for a valid thread"
        )
    return Quantity(magnitude=pi * effective**2 / 4, unit="mm**2")


def bolt_axial_stress(
    *, tension: Quantity, nominal_diameter: Quantity, pitch: Quantity
) -> Quantity:
    """The axial tensile stress σ = F/A_t in a threaded bolt over its ISO 898
    tensile stress area.

    ``tension`` is the axial force F, ``nominal_diameter`` the thread diameter d,
    and ``pitch`` its pitch P. Uses :func:`bolt_tensile_stress_area`, so the stress
    is the one that governs bolt proof/yield — higher than F over the nominal shank
    area. Returns the stress in MPa; ``tension`` must be a force.
    """
    _require(tension, "[force]", "tension")
    area = bolt_tensile_stress_area(nominal_diameter=nominal_diameter, pitch=pitch).pint
    stress = tension.pint / area
    converted = stress.to("MPa")
    return Quantity(magnitude=float(converted.magnitude), unit="MPa")
