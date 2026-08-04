"""NDS timber: the adjusted design value, a reference value times its factor chain.

The National Design Specification for Wood Construction (NDS) checks a member's
stress against an *adjusted* design value: a reference value from the species/grade
tables, multiplied by a chain of adjustment factors that account for the service
conditions — F'_b = F_b · C_D · C_M · C_t · C_L · C_F · … The reference values are
copyrighted table data the caller supplies; Anvilate composes the factor chain,
keeps every factor visible, and screens the stress against the result.

The one factor with a short, universally-republished set of values — the load
duration factor C_D (NDS Table 2.3.2) — is provided here as a lookup; every other
factor is caller-supplied (from the NDS tables for the member's size, moisture, and
temperature), so the doctrine is the familiar one: user-supplied allowables, cited
composition. Stresses may be in psi or MPa — the unit layer handles both.
"""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum
from math import prod, sqrt

from ..scorecard import CheckStatus, ScorecardEntry
from ..units import Quantity

__all__ = [
    "LoadDuration",
    "nds_load_duration_factor",
    "nds_adjusted_design_value",
    "nds_bending_scorecard",
    "nds_euler_buckling_stress",
    "nds_column_stability_factor",
]

# NDS §3.7.1 buckling coefficient and the c parameter of the Ylinen column formula.
_NDS_EULER_COEFFICIENT = 0.822
_NDS_YLINEN_C_SAWN = 0.8  # sawn lumber (0.9 glulam, 0.85 round timber poles)


class LoadDuration(StrEnum):
    """A load-duration category from NDS Table 2.3.2, keyed to its C_D factor.

    Wood carries more stress for a shorter time, so the load duration factor C_D
    rises from 0.9 for a permanent (dead) load to 2.0 for an impact. The typical
    design load of each category is noted; :func:`nds_load_duration_factor` returns
    the C_D.
    """

    PERMANENT = "permanent"  # dead load
    TEN_YEAR = "ten_year"  # occupancy live load (the normal reference, C_D = 1.0)
    TWO_MONTH = "two_month"  # snow load
    SEVEN_DAY = "seven_day"  # construction load
    TEN_MINUTE = "ten_minute"  # wind / earthquake load
    IMPACT = "impact"  # impact load


# NDS Table 2.3.2 load-duration factors — a short, universally republished list.
_LOAD_DURATION_FACTORS: dict[LoadDuration, float] = {
    LoadDuration.PERMANENT: 0.9,
    LoadDuration.TEN_YEAR: 1.0,
    LoadDuration.TWO_MONTH: 1.15,
    LoadDuration.SEVEN_DAY: 1.25,
    LoadDuration.TEN_MINUTE: 1.6,
    LoadDuration.IMPACT: 2.0,
}


def nds_load_duration_factor(duration: LoadDuration) -> float:
    """The NDS Table 2.3.2 load-duration factor C_D for a load-duration category.

    C_D scales the reference design value for how long the load acts: 0.9 permanent,
    1.0 ten-year (occupancy live), 1.15 snow, 1.25 construction, 1.6 wind/earthquake,
    2.0 impact. It does not apply to the compression-perpendicular-to-grain value or
    the modulus of elasticity — those the caller simply omits from the chain.
    """
    return _LOAD_DURATION_FACTORS[duration]


def nds_adjusted_design_value(
    *,
    reference_value: Quantity,
    factors: Mapping[str, float],
) -> Quantity:
    """The NDS adjusted design value F' = F · ∏ Cᵢ (reference value × its factor chain).

    ``reference_value`` F is the tabulated design value for the species and grade
    (caller-supplied — the NDS tables are copyrighted), and ``factors`` is the chain
    of adjustment factors keyed by name (``{"C_D": 1.15, "C_M": 0.85, "C_F": 1.1,
    …}``) so every factor that moved the value stays visible in the record. Each
    factor must be positive. Returns the adjusted value in the reference value's
    kind (a stress in psi or MPa, a modulus, …).
    """
    if not reference_value.has_dimension("[pressure]"):
        raise ValueError(
            f"reference_value must be a [pressure] quantity (a design stress); got "
            f"{reference_value.dimensionality} ({reference_value})"
        )
    for name, value in factors.items():
        if value <= 0:
            raise ValueError(f"adjustment factor {name!r} must be positive; got {value}")
    ref = reference_value.to("MPa").magnitude
    return Quantity(magnitude=ref * prod(factors.values(), start=1.0), unit="MPa")


def nds_bending_scorecard(
    name: str,
    *,
    bending_stress: Quantity,
    adjusted_bending_value: Quantity | None,
    required: float = 1.0,
) -> ScorecardEntry:
    """Screen a bending stress against the adjusted bending design value → an entry.

    The safety factor is the adjusted design value F'_b over the applied
    ``bending_stress`` f_b, judged against ``required`` (1.0 = exactly the NDS
    allowable, whose margin is already in the reference value). When
    ``adjusted_bending_value`` is ``None`` — no reference design value was supplied —
    the entry is ``NOT_EVALUATED`` rather than a silent pass: the species/grade value
    is the caller's to provide, and a timber check without one has not been made.
    """
    if adjusted_bending_value is None:
        return ScorecardEntry(
            name=name,
            status=CheckStatus.NOT_EVALUATED,
            detail="not evaluated — no NDS reference design value supplied",
            reference="NDS",
        )
    if not bending_stress.has_dimension("[pressure]"):
        raise ValueError(
            f"bending_stress must be a [pressure] quantity; got {bending_stress.dimensionality}"
        )
    fb = abs(bending_stress.to("MPa").magnitude)
    fb_allow = adjusted_bending_value.to("MPa").magnitude
    computed = float("inf") if fb == 0 else fb_allow / fb
    return ScorecardEntry.from_safety_factor(name, computed=computed, required=required).model_copy(
        update={"reference": "NDS"}
    )


def nds_euler_buckling_stress(
    *,
    min_modulus: Quantity,
    slenderness_ratio: float,
) -> Quantity:
    """The NDS §3.7.1 column Euler critical buckling stress F_cE = 0.822·E'_min/(l_e/d)².

    The elastic buckling stress that sets the column stability factor: ``min_modulus``
    E'_min is the adjusted modulus for stability (the reduced 5th-percentile modulus
    from the NDS tables, times its own factor chain — caller-supplied), and
    ``slenderness_ratio`` l_e/d is the effective length over the least cross-section
    dimension. A stubbier column (small l_e/d) buckles at a higher stress. Returns
    F_cE as a stress in the modulus's kind.
    """
    if not min_modulus.has_dimension("[pressure]"):
        raise ValueError(
            f"min_modulus must be a [pressure] quantity; got {min_modulus.dimensionality}"
        )
    e = min_modulus.to("MPa").magnitude
    if e <= 0:
        raise ValueError(f"min_modulus must be positive; got {min_modulus}")
    if slenderness_ratio <= 0:
        raise ValueError(f"slenderness_ratio must be positive; got {slenderness_ratio}")
    return Quantity(magnitude=_NDS_EULER_COEFFICIENT * e / slenderness_ratio**2, unit="MPa")


def nds_column_stability_factor(
    *,
    euler_buckling_stress: Quantity,
    reference_compression: Quantity,
    c: float = _NDS_YLINEN_C_SAWN,
) -> float:
    """The NDS §3.7.1 column stability factor C_P (the Ylinen column equation).

    C_P knocks the compression-parallel design value down for buckling:

        α = F_cE / F*_c,
        C_P = (1 + α)/(2c) − √{[(1 + α)/(2c)]² − α/c},

    where ``euler_buckling_stress`` F_cE is from :func:`nds_euler_buckling_stress`,
    ``reference_compression`` F*_c is the compression-parallel value adjusted by every
    factor *except* C_P itself, and ``c`` is the Ylinen parameter (0.8 sawn lumber,
    0.9 glulam, 0.85 round poles). A very stubby column gives C_P → 1 (no buckling
    penalty); a slender one drives it toward zero. Multiply F*_c by C_P for the
    adjusted compression value F'_c. ``c`` must lie in (0, 1]. Returns C_P in (0, 1].
    """
    if not euler_buckling_stress.has_dimension("[pressure]"):
        raise ValueError("euler_buckling_stress must be a [pressure] quantity")
    if not reference_compression.has_dimension("[pressure]"):
        raise ValueError("reference_compression must be a [pressure] quantity")
    if not 0 < c <= 1:
        raise ValueError(f"c must lie in (0, 1]; got {c}")
    fce = euler_buckling_stress.to("MPa").magnitude
    fc_star = reference_compression.to("MPa").magnitude
    if fce <= 0 or fc_star <= 0:
        raise ValueError("euler_buckling_stress and reference_compression must be positive")
    alpha = fce / fc_star
    half = (1.0 + alpha) / (2.0 * c)
    return half - sqrt(half**2 - alpha / c)
