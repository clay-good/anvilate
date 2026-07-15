"""T1 analytical helical compression-spring checks (closed-form).

A round-wire helical spring under an axial force ``F`` carries a torsional shear
stress in the wire, ``τ = K_w · 8·F·D/(π·d³)``, where ``D`` is the mean coil
diameter, ``d`` the wire diameter, and ``K_w`` the Wahl factor correcting for
curvature and the direct shear (Shigley). The spring index ``C = D/d`` sets the
correction. The same coil deflects at the rate ``k = G·d⁴/(8·D³·N_a)`` on its
``N_a`` active coils (its surge mode lives in
:func:`~anvilate.analysis.dynamics.spring_surge_frequency`).

A slender coil also buckles sideways like a column once its axial deflection
grows past a critical value; :func:`helical_spring_buckling` screens that from
the free length, mean diameter, and the two elastic moduli (Shigley). As with the
other checks, inputs and outputs are dimension-checked
:class:`~anvilate.units.Quantity` values.
"""

from __future__ import annotations

from math import pi, sqrt

from pydantic import BaseModel, ConfigDict

from ..units import Quantity

# End-condition constant α relating a coil's free length to its effective column
# length for the buckling screen (Shigley, Mechanical Engineering Design, Table
# 10-2). Smaller α ⇒ a stiffer restraint ⇒ a more stable spring.
SPRING_END_PARALLEL_PLATES = 0.5  # both ends squared/ground on fixed parallel plates
SPRING_END_FIXED_HINGED = 0.707  # one end fixed (plate), the other pivoted
SPRING_END_HINGED_HINGED = 1.0  # both ends pivoted (on ball seats)
SPRING_END_CLAMPED_FREE = 2.0  # one end fixed, the other free (a cantilevered coil)

__all__ = [
    "spring_index",
    "wahl_factor",
    "spring_shear_stress",
    "helical_spring_rate",
    "SPRING_END_PARALLEL_PLATES",
    "SPRING_END_FIXED_HINGED",
    "SPRING_END_HINGED_HINGED",
    "SPRING_END_CLAMPED_FREE",
    "SpringBucklingResult",
    "helical_spring_buckling",
]


def _require(value: Quantity, expected: str, name: str) -> None:
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )


def spring_index(*, mean_coil_diameter: Quantity, wire_diameter: Quantity) -> float:
    """The spring index C = D/d (mean coil diameter over wire diameter).

    Practical springs run C ≈ 4–12; the wire diameter must be below the mean coil
    diameter, else :class:`ValueError`.
    """
    _require(mean_coil_diameter, "[length]", "mean_coil_diameter")
    _require(wire_diameter, "[length]", "wire_diameter")
    big = mean_coil_diameter.to("mm").magnitude
    small = wire_diameter.to("mm").magnitude
    if not 0 < small < big:
        raise ValueError(
            f"wire_diameter ({wire_diameter}) must be positive and below the mean coil "
            f"diameter ({mean_coil_diameter})"
        )
    return big / small


def wahl_factor(spring_index: float) -> float:
    """The Wahl stress-correction factor K_w = (4C−1)/(4C−4) + 0.615/C for a
    spring of index ``spring_index`` (C), correcting the nominal shear stress for
    curvature and direct shear. ``spring_index`` must exceed 1."""
    c = spring_index
    if c <= 1:
        raise ValueError(f"spring_index must exceed 1; got {c}")
    return (4 * c - 1) / (4 * c - 4) + 0.615 / c


def spring_shear_stress(
    *,
    force: Quantity,
    mean_coil_diameter: Quantity,
    wire_diameter: Quantity,
) -> Quantity:
    """The Wahl-corrected torsional shear stress τ = K_w·8·F·D/(π·d³) in the wire
    of a round-wire helical compression spring.

    ``force`` is the axial spring force, ``mean_coil_diameter`` D, ``wire_diameter``
    d. Returns the peak shear stress in MPa; every quantity is dimension-checked.
    """
    _require(force, "[force]", "force")
    c = spring_index(mean_coil_diameter=mean_coil_diameter, wire_diameter=wire_diameter)
    kw = wahl_factor(c)
    stress = kw * 8 * force.pint * mean_coil_diameter.pint / (pi * wire_diameter.pint**3)
    converted = stress.to("MPa")
    return Quantity(magnitude=float(converted.magnitude), unit="MPa")


def helical_spring_rate(
    *,
    mean_coil_diameter: Quantity,
    wire_diameter: Quantity,
    active_coils: float,
    shear_modulus: Quantity,
) -> Quantity:
    """The helical-spring rate k = G·d⁴/(8·D³·N_a) of a round-wire coil.

    ``active_coils`` N_a counts the coils free to deflect (total coils minus
    the closed-and-ground end coils); ``shear_modulus`` G is the wire's, e.g.
    a material record's. Returns newtons per millimetre; every quantity is
    dimension-checked, the coil geometry is validated through the spring
    index, and ``active_coils`` must be positive.
    """
    spring_index(mean_coil_diameter=mean_coil_diameter, wire_diameter=wire_diameter)
    _require(shear_modulus, "[pressure]", "shear_modulus")
    if active_coils <= 0:
        raise ValueError(f"active_coils must be positive; got {active_coils}")
    if shear_modulus.to("Pa").magnitude <= 0:
        raise ValueError(f"shear_modulus must be positive; got {shear_modulus}")
    rate = (
        shear_modulus.pint * wire_diameter.pint**4 / (8 * mean_coil_diameter.pint**3 * active_coils)
    )
    converted = rate.to("N/mm")
    return Quantity(magnitude=float(converted.magnitude), unit="N/mm")


class SpringBucklingResult(BaseModel):
    """The lateral-buckling screen of a helical compression spring.

    ``effective_slenderness`` is λ_eff = α·L₀/D, the spring's column-like
    slenderness. ``absolutely_stable`` is ``True`` when λ_eff stays below the
    Shigley threshold √C₂′ — the coil then will not buckle at any deflection up to
    solid, and ``critical_deflection`` is ``None``. Otherwise
    ``critical_deflection`` is the axial deflection y_cr at which buckling begins;
    an operating deflection beyond it buckles the spring sideways.
    """

    model_config = ConfigDict(frozen=True)

    effective_slenderness: float
    absolutely_stable: bool
    critical_deflection: Quantity | None

    def will_buckle(self, deflection: Quantity) -> bool:
        """Whether an operating ``deflection`` buckles the spring.

        ``False`` whenever the spring is absolutely stable; otherwise ``True`` once
        ``deflection`` reaches the critical deflection. ``deflection`` must be a
        length.
        """
        _require(deflection, "[length]", "deflection")
        if self.absolutely_stable or self.critical_deflection is None:
            return False
        return deflection.to("mm").magnitude >= self.critical_deflection.to("mm").magnitude


def helical_spring_buckling(
    *,
    free_length: Quantity,
    mean_coil_diameter: Quantity,
    elastic_modulus: Quantity,
    shear_modulus: Quantity,
    end_condition_constant: float = SPRING_END_PARALLEL_PLATES,
) -> SpringBucklingResult:
    """Screen a helical compression spring for lateral (column) buckling.

    A slender coil compressed axially can snap sideways once its deflection passes
    a critical value. Following Shigley, the effective slenderness λ_eff = α·L₀/D
    and two dimensionless elastic ratios

        C₁′ = E/(2(E−G)),   C₂′ = 2π²(E−G)/(2G+E)

    give a critical deflection y_cr = L₀·C₁′·[1 − √(1 − C₂′/λ_eff²)]. When
    λ_eff ≤ √C₂′ the radicand never turns negative and the coil is *absolutely
    stable* — it will not buckle at any deflection — so ``critical_deflection`` is
    ``None``.

    ``free_length`` L₀ is the unloaded length, ``mean_coil_diameter`` D, and
    ``elastic_modulus`` E / ``shear_modulus`` G the wire's moduli.
    ``end_condition_constant`` α selects the end restraint (the
    ``SPRING_END_*`` constants; default parallel plates, α = 0.5). Returns a
    :class:`SpringBucklingResult`. Every quantity is dimension-checked and α must
    be positive.
    """
    _require(free_length, "[length]", "free_length")
    _require(mean_coil_diameter, "[length]", "mean_coil_diameter")
    _require(elastic_modulus, "[pressure]", "elastic_modulus")
    _require(shear_modulus, "[pressure]", "shear_modulus")
    if end_condition_constant <= 0:
        raise ValueError(f"end_condition_constant must be positive; got {end_condition_constant}")
    l0 = free_length.to("mm").magnitude
    d = mean_coil_diameter.to("mm").magnitude
    if not d > 0:
        raise ValueError(f"mean_coil_diameter must be positive; got {mean_coil_diameter}")
    e = elastic_modulus.to("Pa").magnitude
    g = shear_modulus.to("Pa").magnitude
    if not e > g > 0:
        raise ValueError(
            f"need elastic_modulus > shear_modulus > 0; got E={elastic_modulus}, G={shear_modulus}"
        )

    lam = end_condition_constant * l0 / d
    c1 = e / (2 * (e - g))
    c2 = 2 * pi**2 * (e - g) / (2 * g + e)

    if lam <= sqrt(c2):
        return SpringBucklingResult(
            effective_slenderness=lam, absolutely_stable=True, critical_deflection=None
        )
    y_cr = l0 * c1 * (1 - sqrt(1 - c2 / lam**2))
    return SpringBucklingResult(
        effective_slenderness=lam,
        absolutely_stable=False,
        critical_deflection=Quantity(magnitude=y_cr, unit="mm"),
    )
