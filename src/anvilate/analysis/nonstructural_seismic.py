"""The seismic design force on a piece of equipment, by the edition that governs it.

Most machines, tanks, panels, skids and racks end up bolted to a slab, and in much of the
world the governing load on those bolts is an earthquake acting on the equipment itself,
not on the building. The nonstructural-component chapter of the building code gives that
force, and **the 2022 edition rewrote the equation**, so the same chiller on the same
slab has two different design forces depending on which edition the jurisdiction adopted.
Both forms are here, each named, because a force reported without its edition is not a
number anyone can check.

**The 2016 form** (ASCE/SEI 7-16 Eq. 13.3-1), a component amplification factor and a
component response modification factor over a linear rise with height:

    Fp = 0.4·S_DS·a_p·(1 + 2z/h)·W_p / (R_p/I_p)

**The 2022 form** (Eq. 13.3-1 as the 2020 NEHRP Provisions wrote it, and as ASCE/SEI 7-22
adopted it), four factors that each stand for one physical effect — how the floor
acceleration grows with height, how much the *building's* ductility takes off it, whether
the component resonates with the building and how ductile it is, and the component's own
reserve strength:

    Fp = 0.4·S_DS·I_p·W_p·(H_f/R_μ)·(C_AR/R_po)          (13.3-1)
    H_f = 1 + a_1(z/h) + a_2(z/h)^10                      (13.3-4)
    H_f = 1 + 2.5(z/h)      period unknown                (13.3-5)
    R_μ = (1.1R/Ω_0)^½ ≥ 1.3                              (13.3-6)

with a_1 = 1/T_a ≤ 2.5 and a_2 = [1 − (0.4/T_a)²] > 0. Both editions bound the result the
same way — not required to exceed 1.6·S_DS·I_p·W_p (Eq. 13.3-2), not less than
0.3·S_DS·I_p·W_p (Eq. 13.3-3) — and both ask for a concurrent vertical force of
0.2·S_DS·W_p (§13.3.1.6).

**Which numbers are the engineer's.** a_p, R_p, C_AR and R_po are table values: the code
tabulates them per component type in Tables 13.5-1 and 13.6-1, and those tables are
copyrighted and are not bundled here. Each arrives as a :class:`TabulatedCoefficient`
carrying the table it was read from, so a force computed from a coefficient nobody can
trace is a state this module will not reach. S_DS and I_p are the site's and the
component's, and H_f and R_μ are computed from the supporting structure.

**Sources, read rather than recalled.** The 2022 form is read from
[FEMA P-2082-1, *2020 NEHRP Recommended Seismic Provisions*](https://www.fema.gov/sites/default/files/2020-10/fema_2020-nehrp-provisions_part-1-and-part-2.pdf),
whose "SECTION 13.3.1 SEISMIC DESIGN FORCES. Replace Section 13.3.1 with the following"
is the text ASCE/SEI 7-22 adopted; Equations 13.3-1 through 13.3-6, §13.3.1.6 and
§13.3.1.7 are quoted from it. The 2016 form and both bounds are read from
[NIST GCR 18-917-43](https://doi.org/10.6028/NIST.GCR.18-917-43) (the ATC-120 report
behind the rewrite), which restates ASCE/SEI 7-16 Eq. 13.3-1 in its §4.1 and Eqs. 13.3-2
and 13.3-3 in its §4.4 and §4.5. ASCE 7 itself is behind a login from here and secondary
web pages disagree with each other about which form belongs to which edition, so neither
was used.

**What the 2022 arithmetic was checked against.** NIST GCR 18-917-43 Tables 4-12 and 4-14
tabulate Fp/Wp for archetype buildings at S_DS = 1.0. For its 4-story steel ordinary
concentrically braced frame (T_a = 0.41 s from its own §4.8; R = 3.25 and Ω_0 = 2 from its
Table 4-3, which also prints R_μ = 1.33) with an unlikely-resonance component
(C_AR = 1.0, R_po = 1.3), this module reproduces every published z/h cell of that row to
the two decimals the report prints — 0.80, 0.65, 0.51, 0.37 and the 0.30 floor, and each
again after the report's Ω_0 = 1.5 anchor factor. The floor cell is the useful one: it is
the only published value that exercises Eq. 13.3-3. It also reproduces only on the
report's own terms, and the difference is worth knowing: the report carries the
*building's* R_μ down to z/h = 0, which puts the equation at 0.23 and lets the floor bite,
whereas §13.3.1.2 as enacted sets R_μ = 1.0 for a component supported at or below grade,
which gives 0.31 and clears the floor. ATC-120 predates that sentence. Both are available
here because R_μ is the caller's — which value applies is a reading of the clause, not of
the arithmetic.

**One difference from the report, deliberately.** ATC-120 proposed a cap of 2.0·S_DS·I_p·W_p
and its Table 4-12 column is headed so. The Provisions adopted 1.6 (Eq. 13.3-2), which is
what this module applies — the report's recommendation is not the text that was enacted.
Its Table 4-13, the uncapped one, prints 3.21 for this archetype's
roof with an elastic component, which this module reproduces: the uncapped equation is
pinned on a published value, and the 1.6 that is then applied to it is the enacted text's,
not the report's 2.0.

This module produces a **force**, not an anchor check: feed it to
:func:`~anvilate.analysis.anchorage.anchor_pattern_demand` for what each anchor then
carries.
"""

from __future__ import annotations

from collections.abc import Sequence
from enum import StrEnum
from math import isfinite, sqrt

from pydantic import ConfigDict, model_validator

from .._models import Named, Provenance, StatableModel, each_one
from ..refusal import RefusalError, Remedy
from ..units import Quantity, render, require_finite

__all__ = [
    "ComponentForceEdition",
    "ForceBound",
    "TabulatedCoefficient",
    "ComponentForce",
    "LateralLoadCase",
    "height_amplification_factor",
    "structure_ductility_reduction_factor",
    "component_seismic_design_force_asce_7_16",
    "component_seismic_design_force_asce_7_22",
    "component_vertical_seismic_force",
    "governing_lateral_load_case",
]

_METHOD_ASCE_7_16 = (
    "ASCE/SEI 7-16 Eq. 13.3-1 with the bounds of Eqs. 13.3-2 and 13.3-3, as NIST GCR "
    "18-917-43 §4.1, §4.4 and §4.5 restate them"
)
_METHOD_ASCE_7_22 = (
    "Eq. 13.3-1 with the bounds of Eqs. 13.3-2 and 13.3-3, read from FEMA P-2082-1 (2020 "
    "NEHRP Provisions) §13.3.1, the text ASCE/SEI 7-22 adopted"
)

_TABLE_SOURCE = "Table 13.5-1 or Table 13.6-1 of the edition the design basis pins"
_SITE_SOURCE = "the site's seismic design parameters and the component's importance factor"
_STRUCTURE_SOURCE = "the supporting structure's seismic force-resisting system and height"
_EQUIPMENT_SOURCE = "the equipment schedule: its operating weight and where it is attached"
_CASE_SOURCE = "the declared lateral load cases on the equipment"

_FORCE_FRACTION = 0.4  # Eq. 13.3-1, both editions: 0.4·S_DS is the peak ground acceleration
_MAXIMUM_FRACTION = 1.6  # Eq. 13.3-2
_MINIMUM_FRACTION = 0.3  # Eq. 13.3-3
_VERTICAL_FRACTION = 0.2  # §13.3.1.6
_A1_CAP = 2.5  # a_1 = 1/T_a ≤ 2.5, under Eq. 13.3-4
_A2_PERIOD = 0.4  # a_2 = [1 − (0.4/T_a)²] > 0, under Eq. 13.3-4
_HEIGHT_EXPONENT = 10  # the exponent on z/h in Eq. 13.3-4
_UNKNOWN_PERIOD_SLOPE = 2.5  # Eq. 13.3-5, where T_a is unknown
_DUCTILITY_NUMERATOR = 1.1  # Eq. 13.3-6
_DUCTILITY_FLOOR = 1.3  # Eq. 13.3-6


class _NonstructuralSeismicInputError(RefusalError, ValueError):
    """A nonstructural-component force input that cannot be used without correction."""


def _refuse(message: str, *, subject: str, source: str) -> _NonstructuralSeismicInputError:
    return _NonstructuralSeismicInputError(
        message, remedies=(Remedy(action="replace", subject=subject, source=source),)
    )


def _check(value: Quantity, expected: str, name: str, *, source: str) -> float:
    """The magnitude of ``value`` in SI, having refused what is not a finite ``expected``."""
    if not isinstance(value, Quantity):
        raise _refuse(
            f"{name} must be a {expected} quantity; got {value!r}", subject=name, source=source
        )
    if not value.has_dimension(expected):
        raise _refuse(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})",
            subject=name,
            source=source,
        )
    if not isfinite(value.magnitude):
        raise _refuse(f"{name} must be finite; got {value}", subject=name, source=source)
    return value.magnitude


def _positive(value: float, name: str, *, source: str) -> float:
    """``value`` as a finite positive float, or a refusal naming the parameter."""
    require_finite(value, name=name)
    if value <= 0:
        raise _refuse(f"{name} must be positive; got {value}", subject=name, source=source)
    return float(value)


class ComponentForceEdition(StrEnum):
    """Which edition's nonstructural-component equation a force was computed by.

    ASCE/SEI 7-16 and ASCE/SEI 7-22 give the same component a different design force, and
    both are in force somewhere, so a reported force carries the edition it came from.
    """

    ASCE_7_16 = "asce_7_16"
    ASCE_7_22 = "asce_7_22"

    @property
    def method(self) -> str:
        """The clauses this edition's force is a result of, for the record it goes into."""
        return _METHOD_ASCE_7_16 if self is ComponentForceEdition.ASCE_7_16 else _METHOD_ASCE_7_22


class ForceBound(StrEnum):
    """Which of ASCE/SEI 7's Eq. 13.3-1 and its two bounds set the force reported."""

    EQUATION = "equation"
    MINIMUM = "minimum"
    MAXIMUM = "maximum"


class TabulatedCoefficient(StatableModel):
    """One coefficient ASCE/SEI 7 tabulates, as the engineer read it out of the table.

    The standard's component tables (Tables 13.5-1 and 13.6-1) are copyrighted and are not
    bundled, so every coefficient they carry arrives this way: a value, the symbol it stands
    for, and the table it came from. ``table`` is what makes the force checkable by someone who
    was not there — a reviewer can open that table and read the same row.
    """

    model_config = ConfigDict(frozen=True)

    states_requirements = True

    symbol: Named
    value: float
    table: Provenance

    @model_validator(mode="after")
    def _is_a_coefficient(self) -> TabulatedCoefficient:
        # Every coefficient in these equations divides or multiplies a force, and a zero or
        # negative one is a table misread rather than a design: R_p = 0 is a division by
        # zero and C_AR = 0 is a component the earthquake does not reach.
        _positive(self.value, f"{self.symbol} value", source=_TABLE_SOURCE)
        return self

    def __str__(self) -> str:
        return f"{self.symbol} = {self.value:g} ({self.table})"


class ComponentForce(StatableModel):
    """A component's horizontal seismic design force, with the bounds it was held to.

    ``edition`` is which of ASCE/SEI 7-16 and 7-22 produced it and ``method`` the clauses
    that edition's answer rests on, because the two editions disagree about the same
    equipment and a force without its edition cannot be checked.
    """

    model_config = ConfigDict(frozen=True)

    states_requirements = True

    force: Quantity
    from_equation: Quantity
    minimum: Quantity
    maximum: Quantity
    governed_by: ForceBound
    coefficients: tuple[TabulatedCoefficient, ...]
    edition: ComponentForceEdition
    method: Provenance

    def __str__(self) -> str:
        applied = render(self.force, pretty=True)
        if self.governed_by is ForceBound.EQUATION:
            return f"Fp = {applied}, between its bounds"
        bound = render(self.minimum if self.governed_by is ForceBound.MINIMUM else self.maximum)
        raw = render(self.from_equation)
        return f"Fp = {applied}, the {self.governed_by.value} ({bound}) rather than {raw}"


class LateralLoadCase(StatableModel):
    """One declared horizontal load on the equipment, whatever its origin.

    ASCE/SEI 7-22 §13.3.1.7 is the rule this models: *"Where nonseismic loads on nonstructural
    components exceed Fp, such loads shall govern the strength design."* A declared wind
    pressure on rooftop equipment, a machine's own dynamic force and an impact allowance are all
    load cases on the same anchors, so the seismic force is one case among them and not a
    different kind of thing.
    """

    model_config = ConfigDict(frozen=True)

    states_requirements = True

    tag: Named
    force: Quantity
    source: Provenance

    @model_validator(mode="after")
    def _is_a_load(self) -> LateralLoadCase:
        magnitude = _check(self.force, "[force]", f"{self.tag} force", source=_CASE_SOURCE)
        if magnitude < 0:
            raise _refuse(
                f"{self.tag} is a magnitude here; got {self.force}. A direction belongs to "
                f"the statics that apply it, and a negative force would reverse it silently",
                subject=f"{self.tag} force",
                source=_CASE_SOURCE,
            )
        return self

    def __str__(self) -> str:
        return f"{self.tag}: {render(self.force, pretty=True)} — from {self.source}"


def height_amplification_factor(
    *,
    height_ratio: float,
    fundamental_period: Quantity | None = None,
) -> float:
    """The force amplification with height H_f (ASCE/SEI 7-22 §13.3.1.1, Eqs. 13.3-4, 13.3-5).

    How much larger the floor's peak acceleration is than the ground's, at the height the
    component is attached. ``height_ratio`` is z/h, the attachment height over the average
    roof height; the standard says z is 0 for items at or below the base and that z/h
    *need not exceed* 1.0, so a larger ratio is taken as 1.0 rather than refused.

    With the supporting structure's approximate ``fundamental_period`` T_a this is
    Eq. 13.3-4, ``1 + a_1(z/h) + a_2(z/h)^10``, where ``a_1 = 1/T_a ≤ 2.5`` and
    ``a_2 = [1 − (0.4/T_a)²] > 0``. Without it — the standard permits this where the period
    is unknown — it is Eq. 13.3-5, ``1 + 2.5(z/h)``. The two agree at the base and part
    company higher up: a stiff structure amplifies more than the straight line, a flexible
    one less.

    The tenth power is the shape of the thing. a_2 is near zero below T_a = 0.4 s and the
    term it multiplies is near zero below z/h ≈ 0.8, so it is a kick at the roof of a
    flexible structure and nothing anywhere else. Returns the dimensionless H_f.
    """
    require_finite(height_ratio, name="height_ratio")
    if height_ratio < 0:
        raise _refuse(
            f"height_ratio is measured up from the base; got {height_ratio}. For a component "
            f"at or below the base the standard sets z to 0, which is a ratio of 0",
            subject="height_ratio",
            source=_EQUIPMENT_SOURCE,
        )
    ratio = min(float(height_ratio), 1.0)
    if fundamental_period is None:
        return 1.0 + _UNKNOWN_PERIOD_SLOPE * ratio
    _check(fundamental_period, "[time]", "fundamental_period", source=_STRUCTURE_SOURCE)
    period = _positive(
        fundamental_period.to("s").magnitude, "fundamental_period", source=_STRUCTURE_SOURCE
    )
    a1 = min(1.0 / period, _A1_CAP)
    a2 = max(1.0 - (_A2_PERIOD / period) ** 2, 0.0)
    return 1.0 + a1 * ratio + a2 * ratio**_HEIGHT_EXPONENT


def structure_ductility_reduction_factor(
    *,
    response_modification_factor: float,
    overstrength_factor: float,
) -> float:
    """The supporting structure's ductility reduction R_μ (ASCE/SEI 7-22 §13.3.1.2, Eq. 13.3-6).

    A building that yields in the earthquake delivers less acceleration to what is bolted
    inside it, and this is how much less: ``R_μ = (1.1R/Ω_0)^½``, from the supporting
    structure's own ``response_modification_factor`` R and ``overstrength_factor`` Ω_0.
    The standard floors it at 1.3 — the value it also directs you to use where the
    force-resisting system is unspecified or not tabulated — so a very low-ductility
    system gets no credit below that. For a component at or below grade R_μ is 1.0 by
    §13.3.1.2, which is a case this function is not asked for rather than a value it
    computes.

    Returns the dimensionless R_μ, at least 1.3. A steel ordinary concentrically braced
    frame (R = 3.25, Ω_0 = 2) gives 1.34, which is NIST GCR 18-917-43 Table 4-3's value.
    """
    r = _positive(
        response_modification_factor, "response_modification_factor", source=_STRUCTURE_SOURCE
    )
    omega = _positive(overstrength_factor, "overstrength_factor", source=_STRUCTURE_SOURCE)
    return max(sqrt(_DUCTILITY_NUMERATOR * r / omega), _DUCTILITY_FLOOR)


def _bounded(
    *,
    unbounded: float,
    design_spectral_acceleration: float,
    component_weight: Quantity,
    importance_factor: float,
    coefficients: tuple[TabulatedCoefficient, ...],
    edition: ComponentForceEdition,
) -> ComponentForce:
    """``unbounded`` held between Eqs. 13.3-3 and 13.3-2, which both editions share."""
    weight = component_weight.magnitude
    unit = component_weight.unit
    scale = design_spectral_acceleration * importance_factor * weight
    floor = _MINIMUM_FRACTION * scale
    cap = _MAXIMUM_FRACTION * scale
    if unbounded > cap:
        applied, bound = cap, ForceBound.MAXIMUM
    elif unbounded < floor:
        applied, bound = floor, ForceBound.MINIMUM
    else:
        applied, bound = unbounded, ForceBound.EQUATION
    return ComponentForce(
        force=Quantity(magnitude=applied, unit=unit),
        from_equation=Quantity(magnitude=unbounded, unit=unit),
        minimum=Quantity(magnitude=floor, unit=unit),
        maximum=Quantity(magnitude=cap, unit=unit),
        governed_by=bound,
        coefficients=coefficients,
        edition=edition,
        method=edition.method,
    )


def _operating_weight(component_weight: Quantity) -> float:
    """``component_weight`` as a finite, non-negative force, or a refusal naming it.

    An operating weight is a magnitude. A negative one passes straight through both force
    equations and comes back as a negative design force, which the anchorage statics then
    read as a *hold-down* — a bolt resisting nothing, reported as capacity nobody installed.
    Both the horizontal force and the vertical one come through here so neither can be the
    one that forgot.
    """
    magnitude = _check(component_weight, "[force]", "component_weight", source=_EQUIPMENT_SOURCE)
    if magnitude < 0:
        raise _refuse(
            f"component_weight is an operating weight, which is a magnitude; got "
            f"{component_weight}",
            subject="component_weight",
            source=_EQUIPMENT_SOURCE,
        )
    return magnitude


def _force_inputs(
    *,
    design_spectral_acceleration: float,
    component_weight: Quantity,
    importance_factor: float,
) -> tuple[float, float]:
    """S_DS and I_p, checked, with ``component_weight`` checked for its dimension."""
    _operating_weight(component_weight)
    sds = _positive(
        design_spectral_acceleration, "design_spectral_acceleration", source=_SITE_SOURCE
    )
    ip = _positive(importance_factor, "importance_factor", source=_SITE_SOURCE)
    return sds, ip


def component_seismic_design_force_asce_7_22(
    *,
    design_spectral_acceleration: float,
    component_weight: Quantity,
    height_amplification: float,
    ductility_reduction: float,
    resonance_ductility: TabulatedCoefficient,
    component_strength: TabulatedCoefficient,
    importance_factor: float = 1.0,
) -> ComponentForce:
    """The horizontal seismic design force by the ASCE/SEI 7-22 form (Eq. 13.3-1, bounded).

    ``Fp = 0.4·S_DS·I_p·W_p·(H_f/R_μ)·(C_AR/R_po)``, then held to Eq. 13.3-2's cap of
    1.6·S_DS·I_p·W_p and Eq. 13.3-3's floor of 0.3·S_DS·I_p·W_p.

    ``design_spectral_acceleration`` S_DS is the short-period design spectral acceleration
    in g and ``component_weight`` W_p the operating weight as a force.
    ``height_amplification`` H_f comes from :func:`height_amplification_factor` and
    ``ductility_reduction`` R_μ from :func:`structure_ductility_reduction_factor` — both
    1.0 for a component supported at or below grade. ``resonance_ductility`` C_AR and
    ``component_strength`` R_po are table values and arrive as
    :class:`TabulatedCoefficient` with the table they were read from, because this module
    bundles none of the code's tables.

    The force is applied at the component's centre of gravity, independently in two
    orthogonal horizontal directions, together with the concurrent vertical force of
    :func:`component_vertical_seismic_force`.
    """
    sds, ip = _force_inputs(
        design_spectral_acceleration=design_spectral_acceleration,
        component_weight=component_weight,
        importance_factor=importance_factor,
    )
    hf = _positive(height_amplification, "height_amplification", source=_STRUCTURE_SOURCE)
    r_mu = _positive(ductility_reduction, "ductility_reduction", source=_STRUCTURE_SOURCE)
    coefficients = each_one(
        (resonance_ductility, component_strength),
        TabulatedCoefficient,
        named="resonance_ductility and component_strength",
    )
    car, rpo = coefficients
    unbounded = (
        _FORCE_FRACTION
        * sds
        * ip
        * component_weight.magnitude
        * (hf / r_mu)
        * (car.value / rpo.value)
    )
    return _bounded(
        unbounded=unbounded,
        design_spectral_acceleration=sds,
        component_weight=component_weight,
        importance_factor=ip,
        coefficients=coefficients,
        edition=ComponentForceEdition.ASCE_7_22,
    )


def component_seismic_design_force_asce_7_16(
    *,
    design_spectral_acceleration: float,
    component_weight: Quantity,
    height_ratio: float,
    amplification: TabulatedCoefficient,
    response_modification: TabulatedCoefficient,
    importance_factor: float = 1.0,
) -> ComponentForce:
    """The horizontal seismic design force by the ASCE/SEI 7-16 form (Eq. 13.3-1, bounded).

    ``Fp = 0.4·S_DS·a_p·(1 + 2z/h)·W_p/(R_p/I_p)``, then held to the same two bounds the
    2022 form uses — Eq. 13.3-2's cap of 1.6·S_DS·I_p·W_p and Eq. 13.3-3's floor of
    0.3·S_DS·I_p·W_p, which did not change between the editions.

    ``amplification`` a_p and ``response_modification`` R_p are the table values, carrying
    the table they were read from. ``height_ratio`` is z/h, which here rises linearly and
    is capped at 1.0 for the same reason it is in the later form.

    This is kept beside the 2022 form rather than replaced by it: the editions are both in
    force, jurisdiction by jurisdiction, and a design basis that pins 7-16 is answered by
    this equation and not by the newer one.
    """
    sds, ip = _force_inputs(
        design_spectral_acceleration=design_spectral_acceleration,
        component_weight=component_weight,
        importance_factor=importance_factor,
    )
    require_finite(height_ratio, name="height_ratio")
    if height_ratio < 0:
        raise _refuse(
            f"height_ratio is measured up from the base; got {height_ratio}",
            subject="height_ratio",
            source=_EQUIPMENT_SOURCE,
        )
    ratio = min(float(height_ratio), 1.0)
    coefficients = each_one(
        (amplification, response_modification),
        TabulatedCoefficient,
        named="amplification and response_modification",
    )
    ap, rp = coefficients
    unbounded = (
        _FORCE_FRACTION
        * sds
        * ap.value
        * (1.0 + 2.0 * ratio)
        * component_weight.magnitude
        / (rp.value / ip)
    )
    return _bounded(
        unbounded=unbounded,
        design_spectral_acceleration=sds,
        component_weight=component_weight,
        importance_factor=ip,
        coefficients=coefficients,
        edition=ComponentForceEdition.ASCE_7_16,
    )


def component_vertical_seismic_force(
    *,
    design_spectral_acceleration: float,
    component_weight: Quantity,
) -> Quantity:
    """The concurrent vertical seismic force 0.2·S_DS·W_p (ASCE/SEI 7-22 §13.3.1.6).

    Both editions ask for this at the same time as the horizontal force, and it is the one
    term of the set that **no coefficient reduces**: not the component's ductility, not the
    building's, not its importance factor. On equipment bolted down against overturning it
    is what lightens the weight resisting the moment, so it works against the anchors twice
    — once as a load and once by taking away what holds the thing down.

    The standard excepts lay-in access-floor and ceiling panels, which are components this
    does not know about; applying the exception is the caller's. Returns the force in the
    unit ``component_weight`` was given in.
    """
    _operating_weight(component_weight)
    sds = _positive(
        design_spectral_acceleration, "design_spectral_acceleration", source=_SITE_SOURCE
    )
    return Quantity(
        magnitude=_VERTICAL_FRACTION * sds * component_weight.magnitude,
        unit=component_weight.unit,
    )


def governing_lateral_load_case(cases: Sequence[LateralLoadCase]) -> LateralLoadCase:
    """The largest of the declared horizontal load cases, which is the one that governs.

    ASCE/SEI 7-22 §13.3.1.7: *"Where nonseismic loads on nonstructural components exceed
    Fp, such loads shall govern the strength design, but the detailing requirements and limitations
    prescribed in this chapter shall apply."* So the comparison is a plain one between
    magnitudes — pass the seismic force in as a case alongside the declared wind, dynamic
    and impact ones and this returns the case the anchors are sized for, named, so the
    answer says which load it was.

    The second half of that sentence is why this returns the **case** and not the force: a
    wind case that governs the strength does not suspend the chapter's seismic detailing,
    and a caller holding only a number has lost the one fact that decides it.

    Ties go to the case declared first, which keeps the answer stable rather than
    arbitrary.
    """
    cases = each_one(cases, LateralLoadCase, named="cases")
    if not cases:
        raise _refuse(
            "a governing load case needs at least one case; got none",
            subject="cases",
            source=_CASE_SOURCE,
        )
    return max(cases, key=lambda case: case.force.to("N").magnitude)
