"""T1 analytical cantilever snap-fit checks (closed-form, constant section).

A snap-fit is the cheapest fastener there is: a moulded plastic finger that flexes
over a lip during assembly and springs back into an undercut to latch. It is designed
by *strain*, not stress — a plastic tolerates a definite peak fibre strain, and the
whole art is flexing the finger far enough to clear the lip without exceeding it.

For the common constant-section rectangular cantilever of length ``L``, root thickness
``h``, and width ``w``, elementary beam theory ties the tip deflection, the fibre
strain, and the deflecting force together exactly. The finger deflected to its tip by
``Y`` carries a peak root strain ε = 1.5·h·Y/L² (invert it for the deflection a
permissible strain ε allows, Y = ε·L²/(1.5·h)); the force that holds it there is
P = E·w·h²·ε/(6·L); and pushing it over the lead-in ramp at angle α against friction μ
takes a mating force W = P·(μ + tan α)/(1 − μ·tan α). The 1.5 factor is not a fudge —
it falls out of σ = 6·P·L/(w·h²) = E·ε and y = P·L³/(3·E·I) for I = w·h³/12.

So the design screen is: does the undercut the finger must clear demand a strain below
the material's permissible strain (a tapered finger or a longer, thinner one lowers it),
and is the resulting mating force something a hand or a press can supply? The permissible
strain ε is the material allowable the caller supplies (≈1–2 % for unfilled
engineering thermoplastics, lower for glass-filled); the insertion angle is a plain-float
degrees value; every length, modulus, and force is a dimension-checked
:class:`~anvilate.units.Quantity`.
"""

from __future__ import annotations

from math import radians, tan

from ..units import Quantity

__all__ = [
    "snap_fit_permissible_deflection",
    "snap_fit_strain",
    "snap_fit_deflection_force",
    "snap_fit_mating_force",
]


def _require(value: Quantity, expected: str, name: str) -> None:
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )


def _positive_length(value: Quantity, name: str) -> float:
    _require(value, "[length]", name)
    magnitude = value.to("mm").magnitude
    if magnitude <= 0:
        raise ValueError(f"{name} must be positive; got {value}")
    return magnitude


def snap_fit_permissible_deflection(
    *, permissible_strain: float, length: Quantity, thickness: Quantity
) -> Quantity:
    """The deflection Y = ε·L²/(1.5·h) a constant-section snap finger can flex to.

    The largest undercut a cantilever snap can clear without over-straining: for a
    permissible fibre strain ``permissible_strain`` ε (the material allowable, e.g.
    0.02 for an unfilled thermoplastic), a finger of ``length`` L and root
    ``thickness`` h flexes to Y = ε·L²/(1.5·h). A longer or thinner finger clears a
    deeper undercut at the same strain. ε must be positive. Returns Y in mm.
    """
    if permissible_strain <= 0:
        raise ValueError(f"permissible_strain must be positive; got {permissible_strain}")
    ell = _positive_length(length, "length")
    h = _positive_length(thickness, "thickness")
    return Quantity(magnitude=permissible_strain * ell**2 / (1.5 * h), unit="mm")


def snap_fit_strain(*, deflection: Quantity, length: Quantity, thickness: Quantity) -> float:
    """The peak root strain ε = 1.5·h·Y/L² of a constant-section snap finger.

    The inverse of :func:`snap_fit_permissible_deflection`: the fibre strain a required
    tip ``deflection`` Y imposes at the root of a finger of ``length`` L and root
    ``thickness`` h. Compare it against the material's permissible strain to screen the
    latch. Returns the dimensionless strain.
    """
    y = _positive_length(deflection, "deflection")
    ell = _positive_length(length, "length")
    h = _positive_length(thickness, "thickness")
    return 1.5 * h * y / ell**2


def snap_fit_deflection_force(
    *,
    permissible_strain: float,
    width: Quantity,
    thickness: Quantity,
    length: Quantity,
    elastic_modulus: Quantity,
) -> Quantity:
    """The force P = E·w·h²·ε/(6·L) to flex a snap finger to its permissible strain.

    The transverse force at the finger tip that develops the permissible fibre strain
    ``permissible_strain`` ε at the root: P = E·w·h²·ε/(6·L) for ``width`` w,
    ``thickness`` h, ``length`` L, and flexural ``elastic_modulus`` E. This is the
    finger's spring force — what holds the latch closed and, via the ramp, sets the
    mating force. ε must be positive. Returns the force in N.
    """
    if permissible_strain <= 0:
        raise ValueError(f"permissible_strain must be positive; got {permissible_strain}")
    _require(elastic_modulus, "[pressure]", "elastic_modulus")
    w = _positive_length(width, "width")
    h = _positive_length(thickness, "thickness")
    ell = _positive_length(length, "length")
    e = elastic_modulus.to("MPa").magnitude
    if e <= 0:
        raise ValueError(f"elastic_modulus must be positive; got {elastic_modulus}")
    force = e * w * h**2 * permissible_strain / (6.0 * ell)
    return Quantity(magnitude=force, unit="N")


def snap_fit_mating_force(
    *, deflection_force: Quantity, insertion_angle: float, friction_coefficient: float
) -> Quantity:
    """The assembly push W = P·(μ + tan α)/(1 − μ·tan α) to snap a finger home.

    Pushing the finger over its lead-in ramp resolves the spring force
    ``deflection_force`` P through the ramp angle and friction: W = P·(μ + tan α)/
    (1 − μ·tan α) for an ``insertion_angle`` α (degrees, the lead-in taper) and
    ``friction_coefficient`` μ. A shallow ramp (small α) assembles easily; as μ·tan α
    approaches 1 the finger locks and cannot be pushed in. α must be in (0, 90) with
    μ·tan α < 1, and μ non-negative. Returns the mating force in N.
    """
    _require(deflection_force, "[force]", "deflection_force")
    if not 0 < insertion_angle < 90:
        raise ValueError(f"insertion_angle must be in (0, 90) degrees; got {insertion_angle}")
    if friction_coefficient < 0:
        raise ValueError(f"friction_coefficient must be non-negative; got {friction_coefficient}")
    p = deflection_force.to("N").magnitude
    if p <= 0:
        raise ValueError(f"deflection_force must be positive; got {deflection_force}")
    tan_a = tan(radians(insertion_angle))
    denominator = 1.0 - friction_coefficient * tan_a
    if denominator <= 0:
        raise ValueError(
            "friction_coefficient*tan(insertion_angle) >= 1: the finger self-locks and "
            "cannot be pushed in; lower the insertion_angle or friction"
        )
    return Quantity(magnitude=p * (friction_coefficient + tan_a) / denominator, unit="N")
