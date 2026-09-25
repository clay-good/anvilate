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

import json
import re
from collections.abc import Sequence
from enum import StrEnum
from math import isfinite
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, model_validator

from .._models import RevalidatedModel, cited, each_one
from ..derivation import Derivation, SymbolValue
from ..scorecard import CheckStatus, Need, ScorecardEntry, ValueSource
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
    "carbon_factor_from_openepd",
]

_CLAUSE_EN15978 = "EN 15978:2011 life-cycle modules; ISO 14040:2006 cradle-to-gate boundary"

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


if TYPE_CHECKING:
    _FactorSource = str
else:
    _FactorSource = cited(
        "where this factor came from — the dataset and its identifier, the EPD, or the "
        "publication. A factor with no source cannot be checked, and an unbounded number "
        "nobody can check is not a screen"
    )


class CarbonFactor(RevalidatedModel):
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
    source: _FactorSource
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
    if not isinstance(finished_mass, Quantity):
        raise ValueError(f"finished_mass must be a [mass] quantity; got {finished_mass!r}")
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
    if not isinstance(mass, Quantity):
        raise ValueError(f"mass must be a [mass] quantity; got {mass!r}")
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
    contributions = each_one(contributions, CarbonContribution, named="contributions")
    if not isinstance(contributions, Sequence):
        raise ValueError(
            f"contributions must be a sequence, not a single value; got {contributions!r}"
        )
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


# What the carbon screen was waiting on, for the report in `anvilate.needs`.
_NEEDS_AN_ESTIMATE = Need(
    declaration="estimate",
    takes=(
        "the design's carbon estimate from embodied_carbon_estimate, with a factor for every "
        "material"
    ),
    sources=(ValueSource.DATABASE, ValueSource.USER),
)
_NEEDS_A_CARBON_BUDGET = Need(
    declaration="budget",
    takes="the carbon the design may embody, in kg CO2e over the declared scope",
    dimension="[mass]",
    units=("kg", "t"),
    sources=(ValueSource.USER, ValueSource.STANDARD),
)


# What a check here could not run without, for the report in `anvilate.needs`.
_NEEDS_CONTRIBUTIONS = Need(
    declaration="contributions",
    takes="each material's mass and carbon factor",
    sources=(ValueSource.USER, ValueSource.DATABASE),
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
    if estimate is not None and not isinstance(estimate, EmbodiedCarbonEstimate):
        raise ValueError(f"estimate must be an EmbodiedCarbonEstimate; got {estimate!r}")
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
            needs=(_NEEDS_AN_ESTIMATE,),
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
            needs=(_NEEDS_A_CARBON_BUDGET,),
        )
    if not isinstance(budget, Quantity):
        raise ValueError(f"budget must be a [mass] quantity; got {budget!r}")
    if not budget.has_dimension("[mass]"):
        raise ValueError(f"budget must be a [mass] quantity of CO2e; got {budget}")
    allowed = budget.to("kg").magnitude
    if allowed <= 0:
        raise ValueError(f"budget must be positive; got {budget}")
    computed = None if total == 0 else allowed / total
    entry = ScorecardEntry.from_safety_factor(
        name,
        computed=computed,
        required=1.0,
        unavailable=(
            "the contributions sum to zero kgCO2e, so there is nothing to judge against the "
            "budget; declare each contribution's mass and carbon factor"
        ),
        needs=(_NEEDS_CONTRIBUTIONS,),
    )
    # The sum written out line by line rather than as a Σ, because embodied carbon is
    # almost always concentrated in one material and a Σ hides which. Each term is one
    # contribution's mass times its factor, already evaluated — the factor's own units
    # (kgCO2e per kg, per m², per m) differ line to line, so multiplying them out here
    # would render a sum of quantities that do not share a dimension.
    derivation = Derivation(
        symbolic="E = "
        + " + ".join(f"e_{index}" for index in range(1, len(estimate.contributions) + 1)),
        inputs=tuple(
            SymbolValue(
                symbol=f"e_{index}",
                description=(
                    f"{contribution.label}: {contribution.mass} at "
                    f"{contribution.factor.value} ({contribution.factor.source})"
                ),
                value=contribution.emissions,
                unit="kg",
            )
            for index, contribution in enumerate(estimate.contributions, start=1)
        ),
        result=SymbolValue(
            symbol="E",
            description=(
                f"cradle-to-gate embodied carbon over {estimate.scope.value}, "
                f"against a {allowed:.4g} kgCO2e budget"
            ),
            value=estimate.total,
            unit="kg",
        ),
        citation=_CLAUSE_EN15978,
    )
    detail = f"{detail} Budget {allowed:.4g} kgCO2e."
    if entry.status is CheckStatus.NOT_EVALUATED:
        detail = f"{entry.detail}; {detail}"
    return entry.model_copy(
        update={
            "detail": detail,
            "reference": _CLAUSE_EN15978,
            "derivation": derivation,
        }
    )


# openEPD (Building Transparency / C Change Labs, Apache-2.0) states each impact as
# ``impacts[<LCIA method>][<indicator>][<module scope>] = {mean, unit, rsd}``, with global
# warming potential under ``gwp`` in kgCO2e and cradle to gate under ``A1A2A3``. The reference
# implementation's `ScopeSetGwp` allows exactly that unit, so nothing else is converted here.
_OPENEPD_GWP_UNIT = "kgCO2e"
_ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}")


def _openepd_mass_in_kg(amount: object, where: str) -> float | None:
    """``{qty, unit}`` as kilograms, or ``None`` when it is not a mass at all."""
    if not isinstance(amount, dict):
        return None
    qty, unit = amount.get("qty"), amount.get("unit")
    if isinstance(qty, bool) or not isinstance(qty, int | float) or not isinstance(unit, str):
        return None
    if not isfinite(qty):
        raise ValueError(f"the declaration's {where} must be a finite quantity; got {amount}")
    try:
        quantity = Quantity(magnitude=float(qty), unit=unit)
    except (ValueError, TypeError):
        return None
    if not quantity.has_dimension("[mass]"):
        return None
    kilograms = quantity.to("kg").magnitude
    if not isfinite(kilograms) or kilograms <= 0:
        raise ValueError(f"the declaration's {where} must be a positive mass; got {amount}")
    return kilograms


def carbon_factor_from_openepd(
    document: str,
    *,
    material: str,
    method: str | None = None,
    as_of: str | None = None,
) -> CarbonFactor:
    """A cradle-to-gate :class:`CarbonFactor` read from one openEPD declaration.

    ``document`` is the declaration's JSON text, as the user downloaded it. Declarations are
    the publisher's and the manufacturer's, so this library ships none, and it reads a file
    rather than calling any service. The factor is the declared A1-A3 global warming
    potential over the mass of one declared unit. It carries the declaration's identity as
    its ``source`` and ``dataset_id``, so a result built on it names the declaration and not
    a generic table.

    The band is the declaration's own: one stated relative standard deviation either side
    (``rsd``), or no band at all when it states none. The generic factor's band does not
    carry over to a product-specific value.

    Everything the conversion would otherwise have to guess is refused, naming the fix. That
    covers a document of another type, several impact methods when ``method`` does not
    choose one, no A1A2A3 GWP, a unit other than kgCO2e, and a declared unit that is not a
    mass with no ``kg_per_declared_unit`` beside it. With ``as_of`` (an ISO date the caller
    states, since nothing here reads the clock), a declaration past its ``valid_until`` is
    refused too.
    """
    if not isinstance(document, str):
        raise ValueError(f"document must be the declaration's JSON text; got {document!r}")
    if not isinstance(material, str) or not material.strip():
        raise ValueError(f"material must name the material the factor is for; got {material!r}")
    if as_of is not None and (not isinstance(as_of, str) or not _ISO_DATE.match(as_of)):
        raise ValueError(f"as_of must be an ISO date such as 2026-09-24; got {as_of!r}")
    try:
        epd = json.loads(document)
    except json.JSONDecodeError as error:
        raise ValueError(
            f"the document is not JSON ({error}); pass the openEPD file's text"
        ) from error
    if not isinstance(epd, dict):
        raise ValueError("an openEPD document is a JSON object; this one is not")
    doctype = epd.get("doctype")
    if not isinstance(doctype, str) or doctype.lower() != "openepd":
        raise ValueError(
            f"the document's doctype is {doctype!r}, not 'openEPD'; an industry-wide or "
            "generic estimate is not a product declaration, so pass the product's own EPD"
        )
    identity = epd.get("id") if isinstance(epd.get("id"), str) else ""
    name = next((epd[key] for key in ("product_name", "name") if isinstance(epd.get(key), str)), "")
    if not identity.strip() and not name.strip():
        raise ValueError(
            "the declaration names neither an id nor a product, so a factor read from it could "
            "not say where it came from; use the document as its program operator publishes it"
        )

    impacts = epd.get("impacts")
    if not isinstance(impacts, dict) or not impacts:
        raise ValueError("the declaration states no impacts, so there is no GWP to read")
    with_gwp = sorted(
        key for key, value in impacts.items() if isinstance(value, dict) and "gwp" in value
    )
    if method is None:
        if len(with_gwp) != 1:
            raise ValueError(
                f"the declaration states GWP under {len(with_gwp)} impact methods "
                f"({', '.join(with_gwp) or 'none'}); pass `method` naming the one to read, "
                "since they are different characterizations of the same product"
            )
        method = with_gwp[0]
    if method not in with_gwp:
        raise ValueError(
            f"the declaration states no GWP under {method!r}; it states it under "
            f"{', '.join(with_gwp) or 'no method'}"
        )
    a1_a3 = (
        impacts[method]["gwp"].get("A1A2A3") if isinstance(impacts[method]["gwp"], dict) else None
    )
    if not isinstance(a1_a3, dict):
        raise ValueError(
            f"the declaration states no A1A2A3 (cradle-to-gate) GWP under {method}; a factor "
            "for other modules is not an A1-A3 factor, and summing modules is the declaration's "
            "own job"
        )
    mean, unit, rsd = a1_a3.get("mean"), a1_a3.get("unit"), a1_a3.get("rsd")
    if unit != _OPENEPD_GWP_UNIT:
        raise ValueError(
            f"the A1A2A3 GWP is stated in {unit!r}; openEPD states GWP in {_OPENEPD_GWP_UNIT}"
        )
    if (
        isinstance(mean, bool)
        or not isinstance(mean, int | float)
        or not isfinite(mean)
        or mean <= 0
    ):
        raise ValueError(f"the A1A2A3 GWP mean must be a positive number; got {mean!r}")
    if rsd is not None and (
        isinstance(rsd, bool) or not isinstance(rsd, int | float) or not 0 < rsd < 1
    ):
        raise ValueError(f"the A1A2A3 GWP rsd must lie in (0, 1); got {rsd!r}")

    per_unit = _openepd_mass_in_kg(epd.get("declared_unit"), "declared unit")
    if per_unit is None:
        per_unit = _openepd_mass_in_kg(epd.get("kg_per_declared_unit"), "kg_per_declared_unit")
    if per_unit is None:
        raise ValueError(
            f"the declared unit is {epd.get('declared_unit')!r}, which is not a mass, and the "
            "declaration states no kg_per_declared_unit; a kgCO2e/kg factor needs the mass of "
            "one declared unit"
        )

    valid_until = epd.get("valid_until")
    if as_of is not None and isinstance(valid_until, str) and _ISO_DATE.match(valid_until):
        if valid_until[:10] < as_of[:10]:
            raise ValueError(
                f"the declaration was valid until {valid_until[:10]}, before {as_of[:10]}; "
                "use the program operator's current version"
            )

    manufacturer = epd.get("manufacturer")
    maker = manufacturer.get("name") if isinstance(manufacturer, dict) else None
    band = f"band ±1 declared rsd ({rsd:g})" if rsd is not None else "no uncertainty declared"
    source = (
        f"openEPD {identity or name}: {name or 'unnamed product'}"
        + (f" by {maker}" if isinstance(maker, str) and maker.strip() else "")
        + f", {method} GWP A1A2A3; {band}"
    )
    geography = epd.get("geography")
    return CarbonFactor(
        material=material.strip(),
        value=float(mean) / per_unit,
        scope=ModuleScope.A1_A3,
        source=source,
        band_low=1.0 - rsd if rsd is not None else 1.0,
        band_high=1.0 + rsd if rsd is not None else 1.0,
        dataset_id=identity,
        version=str(epd.get("version", "")) if epd.get("version") is not None else "",
        geography=", ".join(g for g in geography if isinstance(g, str))
        if isinstance(geography, list)
        else "",
    )
