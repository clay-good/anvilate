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
from math import isfinite, prod, sqrt

from ..derivation import Derivation, SymbolValue
from ..scorecard import CheckStatus, ScorecardEntry
from ..units import Quantity, require_finite

__all__ = [
    "LoadDuration",
    "nds_load_duration_factor",
    "nds_adjusted_design_value",
    "nds_bearing_area_factor",
    "nds_bearing_scorecard",
    "nds_bearing_stress",
    "nds_bending_scorecard",
    "nds_euler_buckling_stress",
    "nds_beam_slenderness_ratio",
    "nds_bending_buckling_stress",
    "nds_beam_stability_factor",
    "nds_column_stability_factor",
    "nds_combined_bending_compression",
    "nds_compression_scorecard",
    "nds_shear_scorecard",
    "nds_shear_stress",
]

# NDS §3.7.1 buckling coefficient and the c parameter of the Ylinen column formula.
_NDS_EULER_COEFFICIENT = 0.822
_NDS_YLINEN_C_SAWN = 0.8  # sawn lumber (0.9 glulam, 0.85 round timber poles)
# NDS §3.7.1.4 caps the column slenderness at l_e/d = 50 in service (75 is tolerated only
# during construction). Past it the Ylinen curve still returns a number, but the member is
# outside the standard and the number is not a design value.
_NDS_MAX_SLENDERNESS = 50.0
_NDS_MAX_SLENDERNESS_CONSTRUCTION = 75.0


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
    2.0 impact.

    **It does not apply to compression perpendicular to grain or to either modulus.**
    Composing the chain by hand, the caller omits it — which is a rule stated in prose and
    enforced by nobody. :meth:`~anvilate.standards.timber.TimberDesignValue.adjusted`
    enforces NDS Table 4.3.1 instead, refusing a factor its property does not take; use it
    where the reference value is a record rather than a bare number.
    """
    if duration not in _LOAD_DURATION_FACTORS:
        raise ValueError(
            f"duration must be one of {sorted(_LOAD_DURATION_FACTORS)}; got {duration!r}"
        )
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
    if not isinstance(reference_value, Quantity):
        raise ValueError(f"reference_value must be a [pressure] quantity; got {reference_value!r}")
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


def _adjusted_design_value(value: Quantity, name: str) -> float:
    """An adjusted NDS design value in MPa, or the library's own refusal.

    The applied stress in each of these screens is guarded twice — `isinstance`, then
    `has_dimension` — and the **allowable** was not guarded at all: it went straight to
    `.to("MPa")` and pint answered for us. That is wrong in two ways at once. The message
    becomes "Cannot convert from 'millimeter' ([length]) to 'megapascal'", naming neither the
    parameter nor the screen, where every sibling says `allowable must be a [pressure]
    quantity; got [length] (5 mm)`. And `pint.DimensionalityError` is a **TypeError**, while
    every guard in this library raises `ValueError` — so a caller catching the documented
    refusal type missed this one entirely.

    One function rather than four copies: the rule is the same in bending, shear, bearing and
    compression, and a fifth screen should not have to remember it.
    """
    if not isinstance(value, Quantity):
        raise ValueError(f"{name} must be a [pressure] quantity; got {value!r}")
    if not value.has_dimension("[pressure]"):
        raise ValueError(
            f"{name} must be a [pressure] quantity; got {value.dimensionality} ({value})"
        )
    require_finite(value, name=name)
    return value.to("MPa").magnitude


def _nds_margin_derivation(
    *,
    applied: Quantity,
    allowable: Quantity,
    computed: float | None,
    applied_symbol: str,
    allowable_symbol: str,
    what: str,
) -> Derivation:
    """The margin an NDS check is: the adjusted design value over the applied stress.

    Both figures reach these checks already formed — the stress from the member analysis,
    the adjusted value from :func:`nds_adjusted_value`, which is where the reference value
    meets its C factors. The quotient is the work done here, and the product behind the
    allowable is named in that symbol's gloss rather than shown as a term of a sum it is
    not part of.
    """
    return Derivation(
        symbolic=f"n = {allowable_symbol} / {applied_symbol}",
        inputs=(
            SymbolValue(
                symbol=allowable_symbol,
                description=(
                    f"adjusted {what} design value — the NDS reference value times the "
                    f"applicable adjustment factors"
                ),
                value=allowable,
                unit="MPa",
            ),
            SymbolValue(
                symbol=applied_symbol,
                description=f"applied {what}",
                value=applied,
                unit="MPa",
            ),
        ),
        result=SymbolValue(
            symbol="n",
            description=(
                "margin against the adjusted design value; 1.0 is exactly the NDS allowable"
            ),
            value=0.0 if computed is None else computed,
        ),
        citation="NDS",
    )


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
    if not isinstance(bending_stress, Quantity):
        raise ValueError(f"bending_stress must be a [pressure] quantity; got {bending_stress!r}")
    if not bending_stress.has_dimension("[pressure]"):
        raise ValueError(
            f"bending_stress must be a [pressure] quantity; got {bending_stress.dimensionality}"
        )
    fb = abs(bending_stress.to("MPa").magnitude)
    fb_allow = _adjusted_design_value(adjusted_bending_value, "adjusted_bending_value")
    # Zero applied stress is a check with nothing to evaluate, not one that passed.
    computed = None if fb == 0 else fb_allow / fb
    return ScorecardEntry.from_safety_factor(name, computed=computed, required=required).model_copy(
        update={
            "reference": "NDS",
            "derivation": _nds_margin_derivation(
                applied=bending_stress,
                allowable=adjusted_bending_value,
                computed=computed,
                applied_symbol="f_b",
                allowable_symbol="F'_b",
                what="bending",
            ),
        }
    )


def nds_shear_stress(
    *,
    shear_force: Quantity,
    width: Quantity,
    depth: Quantity,
) -> Quantity:
    """The maximum horizontal shear stress in a rectangular beam, f_v = 1.5·V/(b·d) (NDS §3.4.2).

    Shear stress in a rectangular section peaks at the neutral axis at 1.5× the average V/A:
    f_v = 1.5·V/(b·d), from the ``shear_force`` V, section ``width`` b, and ``depth`` d. In timber
    it is the check that governs short, heavily loaded spans, where the horizontal shear parallel to
    the grain reaches F'_v before the bending stress reaches F'_b. Returns the shear stress in the
    force/area kind (a stress in psi or MPa).
    """
    if not isinstance(shear_force, Quantity):
        raise ValueError(f"shear_force must be a [force] quantity; got {shear_force!r}")
    if not shear_force.has_dimension("[force]"):
        raise ValueError(
            f"shear_force must be a [force] quantity; got {shear_force.dimensionality}"
        )
    if not width.has_dimension("[length]") or not depth.has_dimension("[length]"):
        raise ValueError("width and depth must be [length] quantities")
    b = width.to("m").magnitude
    d = depth.to("m").magnitude
    if b <= 0 or d <= 0:
        raise ValueError("width and depth must be positive")
    stress = 1.5 * abs(shear_force.to("N").magnitude) / (b * d)
    return Quantity(magnitude=stress / 1e6, unit="MPa")


def nds_shear_scorecard(
    name: str,
    *,
    shear_stress: Quantity,
    adjusted_shear_value: Quantity | None,
    required: float = 1.0,
) -> ScorecardEntry:
    """Screen a horizontal shear stress against the adjusted shear design value → an entry.

    The safety factor is the adjusted design value F'_v over the applied ``shear_stress`` f_v,
    judged against ``required`` (1.0 = exactly the NDS allowable). When ``adjusted_shear_value`` is
    ``None`` — no reference F_v was supplied — the entry is ``NOT_EVALUATED`` rather than a silent
    pass, mirroring :func:`nds_bending_scorecard`.
    """
    if adjusted_shear_value is None:
        return ScorecardEntry(
            name=name,
            status=CheckStatus.NOT_EVALUATED,
            detail="not evaluated — no NDS reference shear value supplied",
            reference="NDS",
        )
    if not isinstance(shear_stress, Quantity):
        raise ValueError(f"shear_stress must be a [pressure] quantity; got {shear_stress!r}")
    if not shear_stress.has_dimension("[pressure]"):
        raise ValueError(
            f"shear_stress must be a [pressure] quantity; got {shear_stress.dimensionality}"
        )
    fv = abs(shear_stress.to("MPa").magnitude)
    fv_allow = _adjusted_design_value(adjusted_shear_value, "adjusted_shear_value")
    # Zero applied stress is a check with nothing to evaluate, not one that passed.
    computed = None if fv == 0 else fv_allow / fv
    return ScorecardEntry.from_safety_factor(name, computed=computed, required=required).model_copy(
        update={
            "reference": "NDS",
            "derivation": _nds_margin_derivation(
                applied=shear_stress,
                allowable=adjusted_shear_value,
                computed=computed,
                applied_symbol="f_v",
                allowable_symbol="F'_v",
                what="shear",
            ),
        }
    )


def nds_bearing_area_factor(
    *,
    bearing_length: Quantity,
    end_distance: Quantity | None = None,
) -> float:
    """The NDS §3.10.4 bearing area factor C_b = (l_b + 0.375 in)/l_b.

    A short bearing perpendicular to the grain carries a little more than its nominal area because
    the fibres just past each end share the load: C_b = (l_b + 0.375 in)/l_b, from the
    ``bearing_length`` l_b measured along the grain. The 0.375-inch bonus is fixed, so the factor is
    largest for short bearings (1.25 at 1.5 in) and fades toward 1.0 as the bearing lengthens. It
    applies only to bearings under 6 in long and at least 3 in from the member end; outside that
    C_b is 1.0.

    ``end_distance`` is the distance from the member end to the near edge of the bearing. Supply it
    and a bearing nearer than 3 in to the end returns C_b = 1.0 (there is no fibre past the end to
    share the load). Left ``None`` the end distance is taken as satisfied — the common interior
    bearing — so a support *at* a member end must pass its own end distance to be screened
    correctly. Returns the dimensionless factor.
    """
    if not isinstance(bearing_length, Quantity):
        raise ValueError(f"bearing_length must be a [length] quantity; got {bearing_length!r}")
    if not bearing_length.has_dimension("[length]"):
        raise ValueError(
            f"bearing_length must be a [length] quantity; got {bearing_length.dimensionality}"
        )
    lb = bearing_length.to("inch").magnitude
    if lb <= 0:
        raise ValueError("bearing_length must be positive")
    if end_distance is not None:
        if not isinstance(end_distance, Quantity):
            raise ValueError(f"end_distance must be a [length] quantity; got {end_distance!r}")
        if not end_distance.has_dimension("[length]"):
            raise ValueError(
                f"end_distance must be a [length] quantity; got {end_distance.dimensionality}"
            )
        if end_distance.to("inch").magnitude < 0:
            raise ValueError("end_distance must not be negative")
        # NDS 3.10.4 grants C_b only to a bearing at least 3 in from the member end.
        if end_distance.to("inch").magnitude < 3.0:
            return 1.0
    # NDS 3.10.4 scopes C_b to bearings shorter than 6 in and not nearer than 3 in to the member
    # end; outside that C_b is 1.0. Without the check a 10 in bearing collected a 3.75% capacity
    # bonus the docstring explicitly says it should not get.
    if lb >= 6.0:
        return 1.0
    return (lb + 0.375) / lb


def nds_bearing_stress(
    *,
    bearing_force: Quantity,
    width: Quantity,
    bearing_length: Quantity,
) -> Quantity:
    """The compression-perpendicular-to-grain bearing stress f_c⊥ = P/(b·l_b) (NDS §3.10.2).

    Where a joist sits on a plate or a beam lands on a post, the reaction is delivered across the
    grain over the contact patch: f_c⊥ = P/(b·l_b), from the ``bearing_force`` P (the reaction),
    the member ``width`` b, and the ``bearing_length`` l_b measured along the grain. Wood is far
    weaker across the grain than along it — a species with a 900 psi bending value may carry only
    a few hundred psi perpendicular — so a member that passes bending and shear can still crush at
    its support. Returns the bearing stress in the force/area kind (a stress in psi or MPa).
    """
    if not isinstance(bearing_force, Quantity):
        raise ValueError(f"bearing_force must be a [force] quantity; got {bearing_force!r}")
    if not bearing_force.has_dimension("[force]"):
        raise ValueError(
            f"bearing_force must be a [force] quantity; got {bearing_force.dimensionality}"
        )
    if not width.has_dimension("[length]") or not bearing_length.has_dimension("[length]"):
        raise ValueError("width and bearing_length must be [length] quantities")
    b = width.to("m").magnitude
    lb = bearing_length.to("m").magnitude
    if b <= 0 or lb <= 0:
        raise ValueError("width and bearing_length must be positive")
    return Quantity(magnitude=abs(bearing_force.to("N").magnitude) / (b * lb) / 1e6, unit="MPa")


def nds_bearing_scorecard(
    name: str,
    *,
    bearing_stress: Quantity,
    adjusted_bearing_value: Quantity | None,
    required: float = 1.0,
) -> ScorecardEntry:
    """Screen a bearing stress against the adjusted compression-perpendicular value → an entry.

    The safety factor is the adjusted design value F'_c⊥ over the applied ``bearing_stress`` f_c⊥,
    judged against ``required`` (1.0 = exactly the NDS allowable). F'_c⊥ is the reference F_c⊥
    times its own chain — C_M, C_t, C_i, and the bearing area factor C_b from
    :func:`nds_bearing_area_factor` — and notably *not* the load-duration factor C_D, which NDS
    §2.3.2 does not apply to compression perpendicular to grain. When ``adjusted_bearing_value`` is
    ``None`` — no reference F_c⊥ was supplied — the entry is ``NOT_EVALUATED`` rather than a silent
    pass, mirroring :func:`nds_bending_scorecard`.
    """
    if adjusted_bearing_value is None:
        return ScorecardEntry(
            name=name,
            status=CheckStatus.NOT_EVALUATED,
            detail="not evaluated — no NDS reference bearing value supplied",
            reference="NDS",
        )
    if not isinstance(bearing_stress, Quantity):
        raise ValueError(f"bearing_stress must be a [pressure] quantity; got {bearing_stress!r}")
    if not bearing_stress.has_dimension("[pressure]"):
        raise ValueError(
            f"bearing_stress must be a [pressure] quantity; got {bearing_stress.dimensionality}"
        )
    fc = abs(bearing_stress.to("MPa").magnitude)
    fc_allow = _adjusted_design_value(adjusted_bearing_value, "adjusted_bearing_value")
    # Zero applied stress is a check with nothing to evaluate, not one that passed.
    computed = None if fc == 0 else fc_allow / fc
    return ScorecardEntry.from_safety_factor(name, computed=computed, required=required).model_copy(
        update={
            "reference": "NDS",
            "derivation": _nds_margin_derivation(
                applied=bearing_stress,
                allowable=adjusted_bearing_value,
                computed=computed,
                applied_symbol="f_c⊥",
                allowable_symbol="F'_c⊥",
                what="compression perpendicular to grain",
            ),
        }
    )


def nds_euler_buckling_stress(
    *,
    min_modulus: Quantity,
    slenderness_ratio: float,
    during_construction: bool = False,
) -> Quantity:
    """The NDS §3.7.1 column Euler critical buckling stress F_cE = 0.822·E'_min/(l_e/d)².

    The elastic buckling stress that sets the column stability factor: ``min_modulus``
    E'_min is the adjusted modulus for stability (the reduced 5th-percentile modulus
    from the NDS tables, times its own factor chain — caller-supplied), and
    ``slenderness_ratio`` l_e/d is the effective length over the least cross-section
    dimension. A stubbier column (small l_e/d) buckles at a higher stress. Returns
    F_cE as a stress in the modulus's kind.

    NDS §3.7.1.4 caps l_e/d at 50 for a column in service, and tolerates 75 only during
    construction — set ``during_construction`` to screen against the looser cap. Past the
    cap this refuses rather than returning the (very small, very plausible) stress the
    formula would give: a column that slender is outside the standard, and the number is
    not a design value.
    """
    if not isinstance(min_modulus, Quantity):
        raise ValueError(f"min_modulus must be a [pressure] quantity; got {min_modulus!r}")
    if not min_modulus.has_dimension("[pressure]"):
        raise ValueError(
            f"min_modulus must be a [pressure] quantity; got {min_modulus.dimensionality}"
        )
    e = min_modulus.to("MPa").magnitude
    if e <= 0:
        raise ValueError(f"min_modulus must be positive; got {min_modulus}")
    if slenderness_ratio <= 0:
        raise ValueError(f"slenderness_ratio must be positive; got {slenderness_ratio}")
    limit = _NDS_MAX_SLENDERNESS_CONSTRUCTION if during_construction else _NDS_MAX_SLENDERNESS
    if slenderness_ratio > limit:
        where = "during construction" if during_construction else "in service"
        raise ValueError(
            f"slenderness_ratio l_e/d = {slenderness_ratio:.4g} exceeds the NDS 3.7.1.4 limit "
            f"of {limit:.0f} {where}: the column is outside the standard"
        )
    return Quantity(magnitude=_NDS_EULER_COEFFICIENT * e / slenderness_ratio**2, unit="MPa")


# NDS §3.3.3 beam stability. F_bE = 1.20·E'_min/R_B², and the Ylinen-form C_L uses 1.9 and
# 0.95 where the column's C_P uses 2c and c. The constants are not interchangeable: the
# column's c is 0.8 for sawn lumber and varies by product, while the beam's are fixed.
_NDS_BENDING_BUCKLING_COEFFICIENT = 1.20
_NDS_BEAM_STABILITY_A = 1.9
_NDS_BEAM_STABILITY_B = 0.95
# NDS §3.3.3.7 caps the bending slenderness at R_B = 50. Past it the formula still returns
# a plausible number and the beam is outside the standard.
_NDS_MAX_BEAM_SLENDERNESS = 50.0


def nds_beam_slenderness_ratio(
    *, effective_length: Quantity, depth: Quantity, breadth: Quantity
) -> float:
    """The NDS §3.3.3.6 bending slenderness ratio R_B = √(l_e·d / b²).

    ``effective_length`` l_e is the *effective* unbraced length from Table 3.3.3, not the
    clear span: the table converts an unbraced length and a loading pattern into l_e, and
    that conversion is the caller's — it depends on where the load acts and how the
    compression edge is held, neither of which a section knows. ``depth`` d is the
    dimension in the plane of bending and ``breadth`` b the one across it.

    **R_B is capped at 50 by §3.3.3.7**, and this refuses past it rather than returning
    the small, entirely plausible stability factor the formula would give: a beam that
    slender is outside the standard, and the number is not a design value. There is no
    construction-stage relief here, unlike the column's §3.7.1.4 cap which tolerates 75
    while a frame is going up — the asymmetry is the standard's, not an omission.

    A beam whose depth does not exceed its breadth needs no lateral support at all
    (§3.3.3.1) and takes C_L = 1.0; :func:`nds_beam_stability_factor` is not the route to
    that answer, and this returns the ratio regardless so a caller can see it.
    """
    for value, name in (
        (effective_length, "effective_length"),
        (depth, "depth"),
        (breadth, "breadth"),
    ):
        if not isinstance(value, Quantity):
            raise ValueError(f"{name} must be a [length] quantity; got {value!r}")
        if not value.has_dimension("[length]"):
            raise ValueError(f"{name} must be a [length] quantity; got {value.dimensionality}")
        require_finite(value, name=name)
    le = effective_length.to("mm").magnitude
    d = depth.to("mm").magnitude
    b = breadth.to("mm").magnitude
    if le <= 0 or d <= 0 or b <= 0:
        raise ValueError(
            f"the effective length, depth and breadth must all be positive; got "
            f"{effective_length}, {depth}, {breadth}"
        )
    ratio = sqrt(le * d / (b * b))
    if ratio > _NDS_MAX_BEAM_SLENDERNESS:
        raise ValueError(
            f"R_B = {ratio:.4g} exceeds the NDS 3.3.3.7 limit of "
            f"{_NDS_MAX_BEAM_SLENDERNESS:.0f}: the beam is outside the standard, and the "
            f"stability factor the formula would return is not a design value"
        )
    return ratio


def nds_bending_buckling_stress(*, min_modulus: Quantity, slenderness_ratio: float) -> Quantity:
    """The NDS §3.3.3.8 critical buckling design value F_bE = 1.20·E'_min/R_B².

    The lateral-torsional buckling stress that sets the beam stability factor, in the
    same shape as the column's :func:`nds_euler_buckling_stress` and with a **different
    coefficient**: 1.20 here against 0.822 there. ``min_modulus`` E'_min is the adjusted
    modulus for stability — the reduced 5th-percentile modulus times its own factor
    chain, which the caller supplies — and ``slenderness_ratio`` is R_B from
    :func:`nds_beam_slenderness_ratio`. Returns F_bE as a stress.
    """
    if not isinstance(min_modulus, Quantity):
        raise ValueError(f"min_modulus must be a [pressure] quantity; got {min_modulus!r}")
    if not min_modulus.has_dimension("[pressure]"):
        raise ValueError(
            f"min_modulus must be a [pressure] quantity; got {min_modulus.dimensionality}"
        )
    require_finite(min_modulus, name="min_modulus")
    e = min_modulus.to("MPa").magnitude
    if e <= 0:
        raise ValueError(f"min_modulus must be positive; got {min_modulus}")
    if not isfinite(slenderness_ratio) or slenderness_ratio <= 0:
        raise ValueError(
            f"slenderness_ratio R_B must be a positive, finite number; got {slenderness_ratio}"
        )
    if slenderness_ratio > _NDS_MAX_BEAM_SLENDERNESS:
        raise ValueError(
            f"R_B = {slenderness_ratio:.4g} exceeds the NDS 3.3.3.7 limit of "
            f"{_NDS_MAX_BEAM_SLENDERNESS:.0f}"
        )
    return Quantity(
        magnitude=_NDS_BENDING_BUCKLING_COEFFICIENT * e / slenderness_ratio**2, unit="MPa"
    )


def nds_beam_stability_factor(
    *, buckling_stress: Quantity, reference_bending_value: Quantity
) -> float:
    r"""The NDS §3.3.3.8 beam stability factor C_L, from F_bE and F_b*.

    With x = F_bE/F_b*::

        C_L = (1 + x)/1.9 − √( [(1 + x)/1.9]² − x/0.95 )

    ``reference_bending_value`` is **F_b\***: the reference bending design value with
    every adjustment applied *except* C_L itself, and except the volume factor C_V for
    glulam. Passing the fully adjusted F'_b instead — the number a design summary
    reports — overstates the denominator, and because C_L rises with x that returns a
    stability factor **larger** than the beam has, which is the unconservative direction.

    C_L rises monotonically with x and approaches but never reaches 1: a beam braced into
    stiffness loses nothing, and one that buckles early loses in proportion. Both are
    swept in the tests rather than asserted from the shape of the formula.

    Multiply it into :func:`nds_adjusted_design_value`'s factor chain like any other C.
    """
    for value, name in (
        (buckling_stress, "buckling_stress"),
        (reference_bending_value, "reference_bending_value"),
    ):
        if not isinstance(value, Quantity):
            raise ValueError(f"{name} must be a [pressure] quantity; got {value!r}")
        if not value.has_dimension("[pressure]"):
            raise ValueError(f"{name} must be a [pressure] quantity; got {value.dimensionality}")
        require_finite(value, name=name)
    fbe = buckling_stress.to("MPa").magnitude
    fb = reference_bending_value.to("MPa").magnitude
    if fbe <= 0 or fb <= 0:
        raise ValueError(
            f"the buckling stress and the reference bending value must both be positive; "
            f"got {buckling_stress} and {reference_bending_value}"
        )
    x = fbe / fb
    a = (1.0 + x) / _NDS_BEAM_STABILITY_A
    # No clamp on the square root. The discriminant [(1+x)/1.9]² − x/0.95 has its minimum
    # at x = 0.9, where it is 1/19 ≈ 0.0526 — a long way from a floating-point sign flip,
    # so a max(0, ...) here would be a guard that never fires and reads as though the
    # expression could go negative. It cannot, for any positive x.
    return a - sqrt(a * a - x / _NDS_BEAM_STABILITY_B)


def nds_compression_scorecard(
    name: str,
    *,
    compression_stress: Quantity,
    adjusted_compression_value: Quantity | None,
    required: float = 1.0,
) -> ScorecardEntry:
    """Screen a compression-parallel stress against the adjusted design value → an entry.

    The safety factor is the adjusted design value F'_c over the applied
    ``compression_stress`` f_c, judged against ``required`` (1.0 = exactly the NDS
    allowable). F'_c is F*_c — the compression-parallel value adjusted by every factor
    except C_P — times the column stability factor C_P from
    :func:`nds_column_stability_factor`, which is where the buckling penalty enters. When
    ``adjusted_compression_value`` is ``None`` — no reference F_c was supplied — the entry
    is ``NOT_EVALUATED`` rather than a silent pass, mirroring :func:`nds_bending_scorecard`.
    """
    if adjusted_compression_value is None:
        return ScorecardEntry(
            name=name,
            status=CheckStatus.NOT_EVALUATED,
            detail="not evaluated — no NDS reference compression value supplied",
            reference="NDS",
        )
    if not isinstance(compression_stress, Quantity):
        raise ValueError(
            f"compression_stress must be a [pressure] quantity; got {compression_stress!r}"
        )
    if not compression_stress.has_dimension("[pressure]"):
        raise ValueError(
            f"compression_stress must be a [pressure] quantity; got "
            f"{compression_stress.dimensionality}"
        )
    fc = abs(compression_stress.to("MPa").magnitude)
    fc_allow = _adjusted_design_value(adjusted_compression_value, "adjusted_compression_value")
    # Zero applied stress is a check with nothing to evaluate, not one that passed.
    computed = None if fc == 0 else fc_allow / fc
    return ScorecardEntry.from_safety_factor(name, computed=computed, required=required).model_copy(
        update={
            "reference": "NDS",
            "derivation": _nds_margin_derivation(
                applied=compression_stress,
                allowable=adjusted_compression_value,
                computed=computed,
                applied_symbol="f_c",
                allowable_symbol="F'_c",
                what="compression parallel to grain",
            ),
        }
    )


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
    if not isinstance(euler_buckling_stress, Quantity):
        raise ValueError(
            f"euler_buckling_stress must be a [pressure] quantity; got {euler_buckling_stress!r}"
        )
    if not euler_buckling_stress.has_dimension("[pressure]"):
        raise ValueError("euler_buckling_stress must be a [pressure] quantity")
    if not isinstance(reference_compression, Quantity):
        raise ValueError(
            f"reference_compression must be a [pressure] quantity; got {reference_compression!r}"
        )
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


def nds_combined_bending_compression(
    *,
    compression_stress: Quantity,
    adjusted_compression: Quantity,
    bending_stress: Quantity,
    adjusted_bending: Quantity,
    euler_buckling_stress: Quantity,
) -> float:
    """The NDS §3.9.2 combined bending + axial compression interaction (≤ 1 passes).

    A beam-column is checked with the interaction

        (f_c/F'_c)² + f_b / [F'_b·(1 − f_c/F_cE)] ≤ 1.0,

    where ``compression_stress`` f_c and ``bending_stress`` f_b are the applied
    stresses, ``adjusted_compression`` F'_c and ``adjusted_bending`` F'_b the adjusted
    design values (F'_c includes the column stability factor C_P), and
    ``euler_buckling_stress`` F_cE from :func:`nds_euler_buckling_stress` about the
    bending axis. The (1 − f_c/F_cE) denominator is the moment amplification — the axial
    load bending the already-deflected member further — so it must stay positive
    (f_c < F_cE, or the member has buckled). Returns the interaction value; a caller
    passes when it is at or below 1.0.
    """
    for value, label in (
        (compression_stress, "compression_stress"),
        (adjusted_compression, "adjusted_compression"),
        (bending_stress, "bending_stress"),
        (adjusted_bending, "adjusted_bending"),
        (euler_buckling_stress, "euler_buckling_stress"),
    ):
        if not isinstance(value, Quantity):
            raise ValueError(f"{label} must be a [pressure] quantity; got {value!r}")
        if not value.has_dimension("[pressure]"):
            raise ValueError(f"{label} must be a [pressure] quantity; got {value}")
    fc = abs(compression_stress.to("MPa").magnitude)
    fpc = adjusted_compression.to("MPa").magnitude
    fb = abs(bending_stress.to("MPa").magnitude)
    fpb = adjusted_bending.to("MPa").magnitude
    fce = euler_buckling_stress.to("MPa").magnitude
    if fpc <= 0 or fpb <= 0 or fce <= 0:
        raise ValueError("the adjusted values and Euler stress must be positive")
    amplification = 1.0 - fc / fce
    if amplification <= 0:
        raise ValueError(
            f"compression stress ({fc:.4g} MPa) reaches the Euler buckling stress "
            f"({fce:.4g} MPa): the member has buckled, the interaction is undefined"
        )
    return (fc / fpc) ** 2 + fb / (fpb * amplification)
