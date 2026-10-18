"""Fracture-control classification as a candidate, never a ruling (NASA-STD-5019A).

NASA-STD-5019A (*Fracture Control Requirements for Spaceflight Hardware*, w/Change 4,
approved 2024-07-29, revalidated 2025-09-05) classifies every part as exempt,
non-fracture-critical (NFC) or fracture critical [FCR 5], and a part that fits no NFC
route is fracture critical. Most NFC routes rest on a hazard assessment: low-released
mass, contained, fail-safe and documented non-hazardous failure are findings about what a
failure would do, and the standard gives no released-mass or energy threshold for them.
Two routes do rest on numbers, and those are what this module checks:

- **A low-risk metallic part** (§6.2.5.a): K_Ic/F_ty ≥ 1.66 √mm (0.33 √in) with no
  environmentally assisted, sustained-load or stress-corrosion cracking sensitivity; no
  short-transverse load in aluminium raw stock thicker than 7.62 cm (3 in); net-section
  stress at limit load less than 30% of the ultimate strength; and four service lifetimes
  shown, by fatigue with 1.5 on local cyclic stress or by damage tolerance from a
  0.127 mm (0.005 in) initial crack. Additively manufactured parts never qualify, and
  welds and castings only on inspection data.
- **A sealed container** (§6.1.4): no hazardous contents, leak-before-burst at maximum
  design pressure, stored energy below 19,307 J (14,240 ft-lb), and MDP at most 152 kPa
  (22 psi), or up to 304 kPa (44 psi) with a positive burst margin at 2.5 × MDP or a
  proof test to at least 1.5 × MDP.

Each condition is reported with its clause, as met, not met, or not evaluated when the
design did not declare what it needs. A part meeting every condition is a **candidate**:
the standard gives the Responsible Fracture Control Board (RFCB) the approval of every
classification ([FCR 1], [FCR 24]), so no surface here shows a classification until that
acceptance is recorded with who accepted it and when.
"""

from __future__ import annotations

from datetime import date
from enum import StrEnum
from math import sqrt

from pydantic import ConfigDict, model_validator

from ._models import Named, Provenance, StatableModel
from .refusal import RefusalError, Remedy
from .units import Quantity, require_finite

__all__ = [
    "ConditionState",
    "FractureCondition",
    "FractureAcceptance",
    "FractureCandidate",
    "LifeMethod",
    "low_risk_metallic_candidate",
    "sealed_container_candidate",
]

_STANDARD = "NASA-STD-5019A w/Change 4"
_DESIGN_SOURCE = "the part's stress report and material record"


class _FractureInputError(RefusalError, ValueError):
    """A fracture-control input that cannot be used without correction."""


def _refusal(message: str, *, subject: str, source: str = _DESIGN_SOURCE) -> _FractureInputError:
    return _FractureInputError(
        message, remedies=(Remedy(action="replace", subject=subject, source=source),)
    )


class ConditionState(StrEnum):
    """Whether one classification condition holds, or could not be judged."""

    MET = "met"
    NOT_MET = "not_met"
    NOT_EVALUATED = "not_evaluated"


class FractureCondition(StatableModel):
    """One condition of a NASA-STD-5019A route, its clause, and its state."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    clause: Provenance
    condition: Named
    state: ConditionState
    detail: Named

    def __str__(self) -> str:
        return f"[{self.state.value}] {self.condition} ({self.clause}): {self.detail}"


class FractureAcceptance(StatableModel):
    """The RFCB's acceptance of a candidate: who, when, and the record it is in."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    accepted_by: Named
    accepted_on: date
    record: Provenance


class FractureCandidate(StatableModel):
    """A part's candidacy for a non-fracture-critical route, condition by condition.

    ``route`` names the NASA-STD-5019A route. ``is_candidate`` is True only when every
    condition is met; ``acceptance`` is None until the RFCB's decision is recorded with
    :meth:`accept`, and :attr:`classification` stays None until then.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    part: Named
    route: Named
    conditions: tuple[FractureCondition, ...]
    acceptance: FractureAcceptance | None = None

    @model_validator(mode="after")
    def _accepted_only_as_candidate(self) -> FractureCandidate:
        if self.acceptance is not None and not self.is_candidate:
            raise _refusal(
                f"'{self.part}' does not meet every condition of {self.route}, so there is no "
                "candidate classification to accept",
                subject="acceptance",
                source="the RFCB's alternative-approach approval under [FCR 26]",
            )
        return self

    @property
    def is_candidate(self) -> bool:
        """Every condition met: a candidate for the route, still awaiting acceptance."""
        return all(c.state is ConditionState.MET for c in self.conditions)

    @property
    def classification(self) -> str | None:
        """'non-fracture-critical' once accepted; None while it is only a candidate."""
        return "non-fracture-critical" if self.acceptance is not None else None

    def accept(self, *, accepted_by: str, accepted_on: date, record: str) -> FractureCandidate:
        """This candidate with the RFCB's acceptance recorded ([FCR 24] e)."""
        return self.model_copy(
            update={
                "acceptance": FractureAcceptance(
                    accepted_by=accepted_by, accepted_on=accepted_on, record=record
                )
            }
        )

    def __str__(self) -> str:
        if self.acceptance is not None:
            head = (
                f"{self.part}: non-fracture-critical by {self.route}, accepted by "
                f"{self.acceptance.accepted_by} on {self.acceptance.accepted_on.isoformat()} "
                f"({self.acceptance.record})"
            )
        elif self.is_candidate:
            head = f"{self.part}: candidate for {self.route}, awaiting RFCB acceptance"
        else:
            failing = [c for c in self.conditions if c.state is not ConditionState.MET]
            head = (
                f"{self.part}: not a candidate for {self.route} — {len(failing)} of "
                f"{len(self.conditions)} conditions not met or not evaluated"
            )
        return "\n".join([head, *(f"  {c}" for c in self.conditions)])


class LifeMethod(StrEnum):
    """How the four service lifetimes of §6.2.5.a(5) were shown."""

    FATIGUE = "fatigue"
    DAMAGE_TOLERANCE = "damage_tolerance"


def _condition(clause: str, condition: str, met: bool | None, detail: str) -> FractureCondition:
    if met is None:
        state = ConditionState.NOT_EVALUATED
    else:
        state = ConditionState.MET if met else ConditionState.NOT_MET
    return FractureCondition(
        clause=f"{_STANDARD} {clause}", condition=condition, state=state, detail=detail
    )


def _stress(value: Quantity | None, name: str) -> float | None:
    if value is None:
        return None
    if not isinstance(value, Quantity):
        raise _refusal(f"{name} must be a stress quantity; got {value!r}", subject=name)
    try:
        converted = value.to("MPa").magnitude
    except Exception as error:
        raise _refusal(f"{name} is {value}, which is not a stress", subject=name) from error
    magnitude = require_finite(converted, name=name)
    if magnitude < 0 or (magnitude == 0 and name != "net_section_stress"):
        raise _refusal(f"{name} must be positive; got {value}", subject=name)
    return magnitude


def low_risk_metallic_candidate(
    *,
    part: str,
    fracture_toughness: Quantity | None,
    yield_strength: Quantity | None,
    ultimate_strength: Quantity | None,
    net_section_stress: Quantity | None,
    cracking_sensitive: bool | None,
    lifetimes_shown: float | None,
    life_method: LifeMethod | None,
    additively_manufactured: bool,
    weld_or_casting_without_inspection_data: bool,
    aluminium_short_transverse_over_3_in: bool | None = False,
) -> FractureCandidate:
    """A metallic part against the low-risk route, NASA-STD-5019A §6.2.5.a, condition by condition.

    ``fracture_toughness`` K_Ic and ``yield_strength`` F_ty are in the applicable
    environment; ``net_section_stress`` is the larger of maximum principal and von Mises at
    limit load, without stress concentrations; ``cracking_sensitive`` is whether the alloy
    is sensitive to environmentally assisted, sustained-load or stress-corrosion cracking
    per NASA-STD-6016; ``lifetimes_shown`` is the service lives the ``life_method``
    analysis demonstrates (with 1.5 on cyclic stress, or from a 0.005 in crack). An input
    left as None leaves its condition not evaluated, and the part is then not a candidate.
    """
    k = None
    if fracture_toughness is not None:
        if not isinstance(fracture_toughness, Quantity):
            raise _refusal("fracture_toughness must be a quantity in MPa·√m",
                           subject="fracture_toughness")  # fmt: skip
        try:
            converted = fracture_toughness.to("MPa*m**0.5").magnitude
        except Exception as error:
            raise _refusal(f"fracture_toughness is {fracture_toughness}, which is not a "
                           "stress intensity", subject="fracture_toughness") from error  # fmt: skip
        k = require_finite(converted, name="fracture_toughness")
        if k <= 0:
            raise _refusal("fracture_toughness must be positive", subject="fracture_toughness")
    fty = _stress(yield_strength, "yield_strength")
    ftu = _stress(ultimate_strength, "ultimate_strength")
    sigma = _stress(net_section_stress, "net_section_stress")
    if lifetimes_shown is not None:
        lifetimes_shown = require_finite(lifetimes_shown, name="lifetimes_shown")
    conditions = [
        _condition(
            "§6.2.5", "not additively manufactured", not additively_manufactured,
            "additively manufactured parts do not qualify as low-risk parts"
            if additively_manufactured else "conventionally manufactured",
        ),
        _condition(
            "§6.2.5 guidance", "no weld or casting without inspection data",
            not weld_or_casting_without_inspection_data,
            "a weld or casting qualifies only on inspection data showing no flaw can grow"
            if weld_or_casting_without_inspection_data else "no uninspected weld or casting",
        ),
    ]  # fmt: skip
    if k is None or fty is None:
        conditions.append(_condition("§6.2.5.a(2)", "K_Ic/F_ty ≥ 1.66 √mm", None,
                                     "declare fracture_toughness and yield_strength"))  # fmt: skip
    else:
        ratio = k * sqrt(1000) / fty
        conditions.append(
            _condition("§6.2.5.a(2)", "K_Ic/F_ty ≥ 1.66 √mm", ratio >= 1.66,
                       f"K_Ic/F_ty = {ratio:.3g} √mm")
        )  # fmt: skip
    conditions.append(
        _condition(
            "§6.2.5.a(2)", "no EAC, SLC or SCC sensitivity",
            None if cracking_sensitive is None else not cracking_sensitive,
            "declare cracking_sensitive per NASA-STD-6016" if cracking_sensitive is None
            else ("sensitive" if cracking_sensitive else "not sensitive"),
        )
    )  # fmt: skip
    conditions.append(
        _condition(
            "§6.2.5.a(3)", "no short-transverse load in aluminium stock over 7.62 cm",
            None if aluminium_short_transverse_over_3_in is None
            else not aluminium_short_transverse_over_3_in,
            "declare aluminium_short_transverse_over_3_in"
            if aluminium_short_transverse_over_3_in is None
            else ("loaded short-transverse in thick stock"
                  if aluminium_short_transverse_over_3_in else "not loaded so"),
        )
    )  # fmt: skip
    if sigma is None or ftu is None:
        conditions.append(
            _condition("§6.2.5.a(4)", "net-section stress < 30% of ultimate", None,
                       "declare net_section_stress and ultimate_strength")
        )  # fmt: skip
    else:
        share = sigma / ftu
        conditions.append(
            _condition("§6.2.5.a(4)", "net-section stress < 30% of ultimate", share < 0.30,
                       f"{share:.1%} of the ultimate strength at limit load")
        )  # fmt: skip
    if lifetimes_shown is None or life_method is None:
        conditions.append(_condition("§6.2.5.a(5)", "four service lifetimes shown", None,
                                     "declare lifetimes_shown and life_method"))  # fmt: skip
    else:
        how = ("fatigue with 1.5 on local cyclic stress" if life_method is LifeMethod.FATIGUE
               else "damage tolerance from a 0.127 mm (0.005 in) crack")  # fmt: skip
        conditions.append(
            _condition("§6.2.5.a(5)", "four service lifetimes shown", lifetimes_shown >= 4,
                       f"{lifetimes_shown:g} lifetimes by {how}")
        )  # fmt: skip
    return FractureCandidate(part=part, route="the low-risk part route (§6.2.5.a)",
                             conditions=tuple(conditions))  # fmt: skip


def sealed_container_candidate(
    *,
    part: str,
    stored_energy: Quantity,
    maximum_design_pressure: Quantity,
    hazardous_contents: bool,
    leak_before_burst: bool | None,
    burst_margin_at_2_5_mdp: bool | None = None,
    proof_test_factor: float | None = None,
) -> FractureCandidate:
    """A sealed container against NASA-STD-5019A §6.1.4's numeric conditions.

    ``stored_energy`` is the adiabatic expansion energy of the contents as a perfect gas;
    ``maximum_design_pressure`` MDP is gauge. Up to 152 kPa (22 psi) nothing more is
    needed; up to 304 kPa (44 psi) either ``burst_margin_at_2_5_mdp`` or a
    ``proof_test_factor`` of at least 1.5; above that the route is closed. The route's
    other conditions (supports, alloys, coatings, leak checks) are the caller's record.
    """
    if not isinstance(stored_energy, Quantity) or not isinstance(maximum_design_pressure, Quantity):
        raise _refusal("stored_energy and maximum_design_pressure must be quantities",
                       subject="stored_energy")  # fmt: skip
    try:
        joules = stored_energy.to("J").magnitude
    except Exception as error:
        raise _refusal(f"stored_energy is {stored_energy}, which is not an energy",
                       subject="stored_energy") from error  # fmt: skip
    energy = require_finite(joules, name="stored_energy")
    try:
        kpa = maximum_design_pressure.to("kPa").magnitude
    except Exception as error:
        raise _refusal(f"maximum_design_pressure is {maximum_design_pressure}, which is not "
                       "a pressure", subject="maximum_design_pressure") from error  # fmt: skip
    mdp = require_finite(kpa, name="maximum_design_pressure")
    if energy < 0 or mdp < 0:
        raise _refusal("stored energy and MDP are zero or positive", subject="stored_energy")
    if proof_test_factor is not None:
        proof_test_factor = require_finite(proof_test_factor, name="proof_test_factor")
    conditions = [
        _condition("§6.1.4", "no hazardous contents", not hazardous_contents,
                   "hazardous contents" if hazardous_contents else "contents not hazardous"),
        _condition("§6.1.4", "leak-before-burst at MDP", leak_before_burst,
                   "declare leak_before_burst" if leak_before_burst is None
                   else ("shown" if leak_before_burst else "not shown")),
        _condition("§6.1.4", "stored energy below 19,307 J (14,240 ft-lb)", energy < 19_307,
                   f"{energy:,.0f} J"),
    ]  # fmt: skip
    if mdp <= 152:
        conditions.append(_condition("§6.1.4", "MDP within 152 kPa (22 psi)", True,
                                     f"MDP {mdp:.4g} kPa"))  # fmt: skip
    elif mdp <= 304:
        proven = bool(burst_margin_at_2_5_mdp) or (
            proof_test_factor is not None and proof_test_factor >= 1.5
        )
        unknown = burst_margin_at_2_5_mdp is None and proof_test_factor is None
        conditions.append(
            _condition(
                "§6.1.4", "152–304 kPa: burst margin at 2.5 × MDP or proof test to 1.5 × MDP",
                None if unknown else proven,
                f"MDP {mdp:.4g} kPa; declare burst_margin_at_2_5_mdp or proof_test_factor"
                if unknown else f"MDP {mdp:.4g} kPa",
            )
        )  # fmt: skip
    else:
        conditions.append(_condition("§6.1.4", "MDP at most 304 kPa (44 psi)", False,
                                     f"MDP {mdp:.4g} kPa is above the route"))  # fmt: skip
    return FractureCandidate(part=part, route="the sealed-container route (§6.1.4)",
                             conditions=tuple(conditions))  # fmt: skip
