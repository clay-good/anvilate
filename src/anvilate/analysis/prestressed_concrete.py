"""T1 analytical prestressed-concrete checks (load balancing, closed-form).

Prestressed concrete is designed around service stresses, not the ultimate-strength picture of
ordinary reinforced concrete, and T. Y. Lin's load-balancing view makes the arithmetic clean: a
draped tendon pushes up on the beam, and the design chooses the prestress so that push cancels a
chosen part of the gravity load.

A parabolic tendon with drape (sag) e under a force P over a span L exerts a uniform upward load
w_b = 8·P·e/L² — the balanced load. Set it equal to the gravity load and the beam carries that load
in pure axial compression, with no bending at all: the extreme-fibre stress collapses to −P/A. Away
from balance, the bottom-fibre stress is f = M/S − P/A − P·e/S (tension positive), the service
check that keeps a beam from cracking or over-compressing. The top fibre needs its own expression,
f = −M/S_t − P/A + P·e/S_t: two of the three terms flip, and the section modulus is the one measured
to the top. That is the check that governs at transfer, when the prestress is full and only
self-weight resists it, and the eccentric force puts the *top* in tension.

The cracking moment — the applied moment that first opens the bottom fibre — is
M_cr = f_r·S + P·(S/A + e), the prestress decompression plus the concrete's modulus of rupture. The
effective prestress force, the section properties, and the modulus of rupture are the caller's; the
balancing arithmetic is here.

Sources: ACI 318 (prestressed concrete) with the PCI *Design Handbook* — the balanced load a
draped tendon applies, the top and bottom fibre stresses at transfer and service, and the
cracking moment from the modulus of rupture.
"""

from __future__ import annotations

from ..units import Quantity

__all__ = [
    "prestress_balanced_load",
    "prestress_bottom_fiber_stress",
    "prestress_cracking_moment",
    "prestress_top_fiber_stress",
]


def prestress_balanced_load(
    *,
    prestress_force: Quantity,
    tendon_drape: Quantity,
    span: Quantity,
) -> Quantity:
    """The uniform load a parabolic tendon balances, w_b = 8·P·e/L² (T. Y. Lin).

    A tendon draped in a parabola pushes up on the beam with a uniform load set by its curvature:
    w_b = 8·P·e/L², from the ``prestress_force`` P, the ``tendon_drape`` e (the sag between the
    tendon's high and low points), and the ``span`` L. Choosing P so w_b equals the gravity load
    leaves the beam in pure axial compression — the whole point of load balancing. Returns the
    balanced load as a force per unit length (kN/m).
    """
    _check(prestress_force, "[force]", "prestress_force")
    _check(tendon_drape, "[length]", "tendon_drape")
    _check(span, "[length]", "span")
    e = tendon_drape.to("m").magnitude
    length = span.to("m").magnitude
    if e <= 0:
        raise ValueError("tendon_drape must be positive")
    if length <= 0:
        raise ValueError("span must be positive")
    w = 8.0 * prestress_force.to("N").magnitude * e / length**2
    return Quantity(magnitude=w / 1000.0, unit="kN/m")


def prestress_bottom_fiber_stress(
    *,
    applied_moment: Quantity,
    prestress_force: Quantity,
    area: Quantity,
    tendon_eccentricity: Quantity,
    section_modulus: Quantity,
) -> Quantity:
    """The bottom-fibre stress of a prestressed beam, f = M/S − P/A − P·e/S (tension positive).

    The service stress at the extreme bottom fibre, superposing the applied moment on the prestress:
    f = M/S − P/A − P·e/S, from the ``applied_moment`` M, ``prestress_force`` P, section ``area`` A,
    ``tendon_eccentricity`` e (below the centroid), and ``section_modulus`` S = I/c. Positive is
    tension. Under exactly the balanced load (M = P·e) the moment terms cancel and it reduces to the
    uniform axial −P/A — a compression, the load-balancing result. Returns the stress in MPa.
    """
    _check(applied_moment, "[force]*[length]", "applied_moment")
    _check(prestress_force, "[force]", "prestress_force")
    _check(area, "[length]**2", "area")
    _check(tendon_eccentricity, "[length]", "tendon_eccentricity")
    _check(section_modulus, "[length]**3", "section_modulus")
    if area.to("m**2").magnitude <= 0:
        raise ValueError("area must be positive")
    if section_modulus.to("m**3").magnitude <= 0:
        raise ValueError("section_modulus must be positive")
    m = applied_moment.to("N*m").magnitude
    p = prestress_force.to("N").magnitude
    a = area.to("m**2").magnitude
    e = tendon_eccentricity.to("m").magnitude
    s = section_modulus.to("m**3").magnitude
    stress = m / s - p / a - p * e / s
    return Quantity(magnitude=stress / 1e6, unit="MPa")


def prestress_top_fiber_stress(
    *,
    applied_moment: Quantity,
    prestress_force: Quantity,
    area: Quantity,
    tendon_eccentricity: Quantity,
    section_modulus: Quantity,
) -> Quantity:
    """The top-fibre stress of a prestressed beam, f = −M/S_t − P/A + P·e/S_t (tension positive).

    The other half of the service check that :func:`prestress_bottom_fiber_stress` starts, and the
    half that usually governs. From the ``applied_moment`` M, ``prestress_force`` P, section
    ``area`` A, ``tendon_eccentricity`` e (below the centroid), and ``section_modulus``
    S_t = I/c_top measured to the *top* fibre: f = −M/S_t − P/A + P·e/S_t. It is not a sign flip of
    the bottom-fibre expression — the moment and eccentricity terms reverse while the axial term
    does not, and S_t differs from the bottom modulus for any asymmetric section, so the two must be
    called separately with their own moduli. The case to watch is transfer: with the prestress at
    full force and only self-weight to resist it, the eccentric force hogs the beam and drives the
    top fibre into *tension*, which is what cracks a girder at release and what the bottom-fibre
    check cannot see. Under exactly the balanced load (M = P·e) it reduces to the uniform axial
    −P/A, matching the bottom fibre. Returns the stress in MPa.
    """
    _check(applied_moment, "[force]*[length]", "applied_moment")
    _check(prestress_force, "[force]", "prestress_force")
    _check(area, "[length]**2", "area")
    _check(tendon_eccentricity, "[length]", "tendon_eccentricity")
    _check(section_modulus, "[length]**3", "section_modulus")
    if area.to("m**2").magnitude <= 0:
        raise ValueError("area must be positive")
    if section_modulus.to("m**3").magnitude <= 0:
        raise ValueError("section_modulus must be positive")
    m = applied_moment.to("N*m").magnitude
    p = prestress_force.to("N").magnitude
    a = area.to("m**2").magnitude
    e = tendon_eccentricity.to("m").magnitude
    s = section_modulus.to("m**3").magnitude
    stress = -m / s - p / a + p * e / s
    return Quantity(magnitude=stress / 1e6, unit="MPa")


def prestress_cracking_moment(
    *,
    prestress_force: Quantity,
    area: Quantity,
    tendon_eccentricity: Quantity,
    section_modulus: Quantity,
    modulus_of_rupture: Quantity,
) -> Quantity:
    """The moment that first cracks a prestressed section, M_cr = f_r·S + P·(S/A + e).

    The applied moment that brings the bottom fibre from its prestress compression up to the
    concrete's tensile modulus of rupture: M_cr = f_r·S + P·(S/A + e), from the ``prestress_force``
    P, section ``area`` A, ``tendon_eccentricity`` e, ``section_modulus`` S = I/c, and
    ``modulus_of_rupture`` f_r (≈ 0.62√f'c MPa, caller-supplied). It is the prestress decompression
    plus the tensile strength — the service margin against cracking. Returns the cracking moment in
    kN·m.
    """
    _check(prestress_force, "[force]", "prestress_force")
    _check(area, "[length]**2", "area")
    _check(tendon_eccentricity, "[length]", "tendon_eccentricity")
    _check(section_modulus, "[length]**3", "section_modulus")
    _check(modulus_of_rupture, "[pressure]", "modulus_of_rupture")
    a = area.to("m**2").magnitude
    if a <= 0:
        raise ValueError("area must be positive")
    s = section_modulus.to("m**3").magnitude
    if s <= 0:
        raise ValueError("section_modulus must be positive")
    p = prestress_force.to("N").magnitude
    e = tendon_eccentricity.to("m").magnitude
    fr = modulus_of_rupture.to("Pa").magnitude
    m_cr = fr * s + p * (s / a + e)
    return Quantity(magnitude=m_cr / 1000.0, unit="kN*m")


def _check(value: Quantity, expected: str, name: str) -> None:
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )
