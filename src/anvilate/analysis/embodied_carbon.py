"""Cradle-to-gate embodied carbon, screening grade, beside the physics verdict.

A part's embodied carbon is mass times a factor, which makes it sound trivial and is
why so many published figures are wrong. The arithmetic is not the hard part; the
bookkeeping is. Three things decide whether a number means anything:

**Which life-cycle modules it covers.** EN 15978 splits a product's life into modules —
A1-A3 is cradle-to-gate (raw material supply, transport, manufacturing), A4-A5 adds
delivery and installation, B and C cover use and end of life. A factor is only ever
quoted *for a scope*, and adding an A1-A3 figure to an A1-A5 figure produces a number
that is not an estimate of anything. This module refuses to do it.

**Where the factor came from.** A generic industry-average factor and a
product-specific EPD for the actual supplier can differ by a factor of three for the
same material — recycled-content steel against blast-furnace steel is the standard
example. Following the library's user-supplied-allowables doctrine, no factor table is
bundled: every factor carries its source, dataset identity, version and geography, and
a factor with no source is refused rather than averaged in.

**How wide the band is.** A screening factor is a central value with real spread, and a
total quoted without its band invites a comparison the data cannot support. Every
factor declares a band and the estimate propagates it.

What comes out is a **screening estimate**, not an EPD, not a declaration, and not a
certification. It exists to make mass reduction legible as a carbon decision while the
design is still cheap to change. Comparing two of your own variants computed the same
way is what it is for; quoting the absolute number in a disclosure is not.

Sources: EN 15978 for the life-cycle module framing, and ISO 14040/14044 for the
cradle-to-gate boundary and the requirement that a scope be declared with any result.
"""

from __future__ import annotations

from enum import StrEnum
from math import isfinite

from pydantic import BaseModel, ConfigDict, model_validator

from ..scorecard import CheckStatus, ScorecardEntry
from ..units import Quantity

__all__ = [
    "ModuleScope",
    "CarbonFactor",
    "CarbonContribution",
    "EmbodiedCarbonEstimate",
    "material_loss_mass",
    "carbon_contribution",
    "embodied_carbon_estimate",
    "embodied_carbon_scorecard",
]

_CLAUSE_EN15978 = "EN 15978 life-cycle modules; ISO 14040 cradle-to-gate boundary"

# The label that has to travel with every number this module produces.
_SCREENING_LABEL = (
    "screening estimate, not an EPD or a declaration: comparable against other variants "
    "computed the same way, not quotable as an absolute figure"
)


class ModuleScope(StrEnum):
    """Which EN 15978 life-cycle modules a factor or an estimate covers.

    The scope is not a label on the answer, it is part of what the answer *is*. Two
    factors quoted over different module sets are not addable, and a total whose scope
    is unstated cannot be compared with anything. Values are the standard module
    ranges, so a report prints the same string a reviewer reads in the source.
    """

    A1_A3 = "A1-A3 (cradle to gate)"
    A1_A4 = "A1-A4 (cradle to site)"
    A1_A5 = "A1-A5 (cradle to practical completion)"


class CarbonFactor(BaseModel):
    """An EN 15978 mass-specific carbon factor, and what is needed to know what it means.

    ``value`` is kgCO2e per kg of material — dimensionless, because CO2-equivalent is
    itself a mass and the ratio of two masses carries no unit. That is not a shortcut:
    it means an estimate's total is a genuine ``[mass]`` quantity that the units layer
    checks like any other.

    ``band_low`` and ``band_high`` are multipliers on ``value`` bracketing the
    plausible range (0.8 and 1.4, say). They are required. A screening factor without a
    band invites a comparison the data cannot support, and defaulting them to 1.0 would
    quietly assert a precision nobody has.

    ``source``, ``dataset_id``, ``version`` and ``geography`` are the provenance. No
    factor table is bundled with this library — the redistribution-clean sources are
    the ones the user cites, and the ones that are not redistribution-clean must not be
    copied in. A blank source is refused.
    """

    model_config = ConfigDict(frozen=True)

    material: str
    value: float  # kgCO2e per kg
    scope: ModuleScope
    source: str
    band_low: float
    band_high: float
    dataset_id: str = ""
    version: str = ""
    geography: str = ""

    @model_validator(mode="after")
    def _well_formed(self) -> CarbonFactor:
        if not isfinite(self.value) or self.value <= 0:
            raise ValueError(
                f"value must be a positive, finite kgCO2e/kg; got {self.value}. A NaN "
                f"slips past `value <= 0` — the comparison is False for it — and a NaN "
                f"factor produces a NaN total that prints as 'nan kgCO2e (nan-nan)'."
            )
        for bound, bound_name in ((self.band_low, "band_low"), (self.band_high, "band_high")):
            if not isfinite(bound):
                raise ValueError(f"{bound_name} must be finite; got {bound}")
        if not self.source.strip():
            raise ValueError(
                "source must record where this factor came from — the dataset and its "
                "identifier, the EPD, or the publication. A factor with no source cannot "
                "be checked, and an unbounded number nobody can check is not a screen."
            )
        if not 0 < self.band_low <= 1.0 <= self.band_high:
            raise ValueError(
                f"band_low must be in (0, 1] and band_high at least 1.0, as multipliers "
                f"on value; got {self.band_low} and {self.band_high}"
            )
        return self

    def __str__(self) -> str:
        where = f" [{self.geography}]" if self.geography else ""
        return f"{self.material}: {self.value:.4g} kgCO2e/kg {self.scope.value}{where}"


class CarbonContribution(BaseModel):
    """One line of an EN 15978 estimate: a mass, the factor applied, and the result."""

    model_config = ConfigDict(frozen=True)

    label: str
    mass: Quantity
    factor: CarbonFactor
    emissions: Quantity
    low: Quantity
    high: Quantity


class EmbodiedCarbonEstimate(BaseModel):
    """An itemised ISO 14040 cradle-to-gate estimate, its band, and its EN 15978 scope.

    ``total`` is the sum of the contributions and ``low``/``high`` the band carried
    through from each factor. ``scope`` is the single module range every contribution
    shares — the constructor refuses a mixture, because a sum across scopes is not an
    estimate of anything.

    ``dominant`` names the contribution carrying the most, which is the only part of
    this worth acting on first: embodied carbon is almost always concentrated in one
    material, and a redesign that trims the other three is motion without progress.
    """

    model_config = ConfigDict(frozen=True)

    contributions: tuple[CarbonContribution, ...]
    total: Quantity
    low: Quantity
    high: Quantity
    scope: ModuleScope

    @property
    def dominant(self) -> CarbonContribution:
        """The single contribution carrying the most — where a redesign should start."""
        return max(self.contributions, key=lambda c: c.emissions.to("kg").magnitude)

    def __str__(self) -> str:
        return (
            f"{self.total.to('kg').magnitude:.4g} kgCO2e "
            f"({self.low.to('kg').magnitude:.4g}-{self.high.to('kg').magnitude:.4g}) "
            f"{self.scope.value}, {_SCREENING_LABEL}"
        )


def material_loss_mass(*, finished_mass: Quantity, yield_fraction: float) -> Quantity:
    """The material made but not shipped in the part — ISO 14040 upstream mass, in kg.

    A machined part starts as a billet and leaves most of it on the floor; a stamped one
    leaves a skeleton. The carbon of that removed material was still emitted, and a
    cradle-to-gate estimate that counts only the finished mass understates a heavily
    machined part by more than the machining energy it usually worries about instead.

    ``yield_fraction`` is finished mass over input mass — 0.9 for near-net stamping, as
    low as 0.1 for a machined-from-solid aerospace fitting. Returns the *loss*, so the
    input mass is ``finished_mass + material_loss_mass(...)``.

    Scrap that is recycled is not free and is not full price either; how much credit it
    earns is a boundary decision (module D) this screen does not make. Counting the loss
    at full factor is the conservative reading, and it is the one to state.
    """
    if not finished_mass.has_dimension("[mass]"):
        raise ValueError(f"finished_mass must be a [mass] quantity; got {finished_mass}")
    if not isfinite(finished_mass.magnitude) or finished_mass.magnitude <= 0:
        raise ValueError(f"finished_mass must be a positive, finite quantity; got {finished_mass}")
    if not 0 < yield_fraction <= 1.0:
        raise ValueError(
            f"yield_fraction is finished mass over input mass and must lie in (0, 1]; "
            f"got {yield_fraction}"
        )
    finished = finished_mass.to("kg").magnitude
    return Quantity(magnitude=finished * (1.0 / yield_fraction - 1.0), unit="kg")


def carbon_contribution(
    *, label: str, mass: Quantity, factor: CarbonFactor | None
) -> CarbonContribution | None:
    """One line of an EN 15978 estimate: ``mass`` × ``factor``, with the band carried.

    Returns ``None`` when ``factor`` is ``None``. That is the whole point of the return
    type: a material with no factor supplied contributes an **unknown** amount, not
    zero, and an estimate that silently drops it reports a total lower than the design's
    — the most flattering possible error, in the one direction nobody checks.
    """
    if not mass.has_dimension("[mass]"):
        raise ValueError(f"mass must be a [mass] quantity; got {mass}")
    if not isfinite(mass.magnitude) or mass.magnitude < 0:
        raise ValueError(
            f"mass must be a finite, non-negative quantity; got {mass}. A NaN passes "
            f"`< 0` and carries all the way to a NaN total."
        )
    if factor is None:
        return None
    kg = mass.to("kg").magnitude
    central = kg * factor.value
    return CarbonContribution(
        label=label,
        mass=mass.to("kg"),
        factor=factor,
        emissions=Quantity(magnitude=central, unit="kg"),
        low=Quantity(magnitude=central * factor.band_low, unit="kg"),
        high=Quantity(magnitude=central * factor.band_high, unit="kg"),
    )


def embodied_carbon_estimate(
    contributions: tuple[CarbonContribution, ...] | list[CarbonContribution],
) -> EmbodiedCarbonEstimate:
    """Sum contributions, refusing a mixture of EN 15978 module scopes.

    The refusal is the load-bearing part. Adding an A1-A3 factor to an A1-A5 one gives a
    number that is neither, and nothing downstream can tell — the units check, the
    arithmetic checks, and the answer means nothing. Scopes are compared, not coerced.

    Requires at least one contribution: an estimate over nothing is not zero carbon, it
    is an estimate that was never made, and :func:`embodied_carbon_scorecard` reports
    that as ``NOT_EVALUATED``.
    """
    items = tuple(contributions)
    if not items:
        raise ValueError(
            "an estimate needs at least one contribution; a total over nothing is not "
            "zero embodied carbon, it is an estimate that was not made"
        )
    scopes = {c.factor.scope for c in items}
    if len(scopes) > 1:
        raise ValueError(
            "the contributions are quoted over different EN 15978 module scopes ("
            + ", ".join(sorted(s.value for s in scopes))
            + "), and their sum would not be an estimate of anything. Re-source the "
            "factors onto one scope."
        )
    total = sum(c.emissions.to("kg").magnitude for c in items)
    low = sum(c.low.to("kg").magnitude for c in items)
    high = sum(c.high.to("kg").magnitude for c in items)
    return EmbodiedCarbonEstimate(
        contributions=items,
        total=Quantity(magnitude=total, unit="kg"),
        low=Quantity(magnitude=low, unit="kg"),
        high=Quantity(magnitude=high, unit="kg"),
        scope=scopes.pop(),
    )


def embodied_carbon_scorecard(
    name: str,
    *,
    estimate: EmbodiedCarbonEstimate | None,
    budget: Quantity | None = None,
    missing: str = "",
) -> ScorecardEntry:
    """Screen an EN 15978 embodied-carbon estimate against a budget → a scorecard entry.

    The safety factor is the ``budget`` over the estimate's total, so a part inside its
    allowance passes. The detail always carries the band, the module scope, the dominant
    contribution, and the screening label — a carbon figure without its scope is not a
    result someone else can use.

    ``estimate`` of ``None`` is ``NOT_EVALUATED``, never zero: a bill of materials with a
    factor missing has not been estimated, and reporting the sum of the materials that
    happened to have factors would understate the design in the one direction nobody
    audits. ``missing`` names what was absent.

    ``budget`` of ``None`` is also ``NOT_EVALUATED`` — but a *reporting* one: the estimate
    is computed and shown, and only the verdict is withheld, because there is no target
    to judge it against. That is the honest state for a first pass, and it still puts the
    number in front of the reader.
    """
    if estimate is None:
        detail = "not evaluated"
        detail += (
            f" — {missing.strip()}"
            if missing.strip()
            else (
                " — a factor was missing for at least one material, and the materials that "
                "do have factors do not add up to the design"
            )
        )
        return ScorecardEntry(
            name=name,
            status=CheckStatus.NOT_EVALUATED,
            detail=detail,
            reference=_CLAUSE_EN15978,
        )
    total = estimate.total.to("kg").magnitude
    dominant = estimate.dominant
    share = 100.0 * dominant.emissions.to("kg").magnitude / total if total > 0 else 0.0
    detail = (
        f"{total:.4g} kgCO2e ({estimate.low.to('kg').magnitude:.4g}-"
        f"{estimate.high.to('kg').magnitude:.4g}) over {estimate.scope.value}; "
        f"{dominant.label} carries {share:.0f}% of it. {_SCREENING_LABEL}."
    )
    if budget is None:
        return ScorecardEntry(
            name=name,
            status=CheckStatus.NOT_EVALUATED,
            detail=f"no carbon budget supplied, so there is no verdict to give. {detail}",
            reference=_CLAUSE_EN15978,
        )
    if not budget.has_dimension("[mass]"):
        raise ValueError(f"budget must be a [mass] quantity of CO2e; got {budget}")
    allowed = budget.to("kg").magnitude
    if allowed <= 0:
        raise ValueError(f"budget must be positive; got {budget}")
    computed = None if total == 0 else allowed / total
    entry = ScorecardEntry.from_safety_factor(name, computed=computed, required=1.0)
    return entry.model_copy(
        update={
            "detail": f"{detail} Budget {allowed:.4g} kgCO2e.",
            "reference": _CLAUSE_EN15978,
        }
    )
