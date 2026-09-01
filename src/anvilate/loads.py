"""Load combinations: factored sums over load cases, and which one governs.

Every code check the structural packs cite assumes a *combination* of load cases
as its input — a factored sum under LRFD, a service sum under ASD — not a single
case. Doing that bookkeeping in your head is the silent-error class this library
exists to remove: the governing combination is often not the obvious one (an
uplift case where wind counteracts dead load can govern a connection the
gravity cases never stress).

This module carries the combination vocabulary and generates the ASCE 7-22 basic
combination sets (§2.3.1 strength / §2.4.1 allowable stress) and the seismic sets
(§2.3.6 / §2.4.5, with the design spectral acceleration S_DS and redundancy factor
as typed user inputs). The combination expressions are short, universally
republished equation lists; deriving the load *magnitudes* (wind, seismic, snow
from maps and site parameters) stays firmly out of scope — the caller supplies each
case's magnitude.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from enum import StrEnum
from math import isfinite

from pydantic import BaseModel, ConfigDict, Field, computed_field, model_validator

from ._models import Named, Provenance, RevalidatedModel, cited
from .derivation import Derivation, SymbolValue
from .scorecard import CheckStatus, ScorecardEntry

__all__ = [
    "LoadNature",
    "LoadCombination",
    "CombinationSet",
    "asce7_lrfd_basic",
    "asce7_asd_basic",
    "asce7_lrfd_seismic",
    "asce7_asd_seismic",
    "combination_scorecard",
    "CombinationEvidence",
    "combination_evidence",
]


class LoadNature(StrEnum):
    """The nature of a load case, by its ASCE 7 symbol.

    The factor a combination applies depends on the load's nature, not its name —
    dead load is always factored as dead load. Seismic (``E``) carries the
    horizontal earthquake effect ρ·Q_E; the vertical part folds into the dead factor.
    """

    DEAD = "D"
    LIVE = "L"
    ROOF_LIVE = "Lr"
    SNOW = "S"
    RAIN = "R"
    WIND = "W"
    SEISMIC = "E"


# The roof companion group: "(Lr or S or R)" in the ASCE expressions. A combination
# with a roof companion is expanded into one variant per present nature; absent
# loads evaluate to zero, so generating all three never inflates the envelope.
_ROOF_COMPANIONS = (LoadNature.ROOF_LIVE, LoadNature.SNOW, LoadNature.RAIN)


class LoadCombination(BaseModel):
    """One factored sum over load natures, with the clause it comes from.

    ``factors`` maps each contributing nature to its factor; ``evaluate`` sums
    ``factor · magnitude`` over the caller's supplied loads, treating any nature the
    combination does not name (or the caller does not supply) as zero.
    """

    model_config = ConfigDict(frozen=True)

    name: Named
    # At least one. A combination that factors nothing sums to zero, so it can never
    # govern in either direction: it sits in the set looking like a case that was
    # checked, and is the one case that was not.
    factors: Mapping[LoadNature, float] = Field(min_length=1)
    citation: Provenance

    def evaluate(self, loads: Mapping[LoadNature, float]) -> float:
        """The combined demand: ``Σ factor · load`` over this combination's natures.

        A load the caller supplies whose nature this combination does not factor is
        simply not part of this sum; a nature the combination factors but the caller
        omits contributes zero.

        **A non-finite load is rejected here rather than carried.** A NaN load poisons
        only the combinations that factor its nature, and because ``max`` and ``min``
        compare with ``>`` and ``<`` — both False against NaN — those combinations are
        then silently *dropped* from the envelope instead of contaminating it. A single
        NaN wind load removes every wind combination from an ASCE 7 set, including the
        counteracting uplift case the check exists to catch, and the largest surviving
        gravity demand is reported as governing with a comfortable PASS. Raising is the
        only outcome that cannot be mistaken for an answer.
        """
        for nature, factor in self.factors.items():
            value = loads.get(nature, 0.0)
            if not isfinite(value):
                raise ValueError(
                    f"the {nature.value} load is {value}, which is not a finite number; "
                    f"combination {self.name} cannot be evaluated. A non-finite load "
                    f"would be dropped from the envelope by max/min rather than "
                    f"reported, so it is refused here"
                )
            if not isfinite(factor):
                raise ValueError(
                    f"combination {self.name} has a non-finite factor on {nature.value}"
                )
        return sum(factor * loads.get(nature, 0.0) for nature, factor in self.factors.items())

    def __str__(self) -> str:
        terms = " + ".join(f"{factor:g}{nature.value}" for nature, factor in self.factors.items())
        return f"{self.name}: {terms}"


class CombinationSet(BaseModel):
    """A named set of load combinations — a code basis, or a custom list.

    ``evaluate_all`` returns every combination's demand; ``governing`` names the
    combination with the largest demand (the strength envelope), its ``minimize``
    form names the smallest — the counteracting case that governs uplift and
    overturning, where wind or seismic relieves gravity — and its ``by_magnitude``
    form names the largest regardless of sign, which is what a check judging
    ``capacity/|demand|`` needs.
    """

    model_config = ConfigDict(frozen=True)

    basis: str
    combinations: tuple[LoadCombination, ...]

    def evaluate_all(self, loads: Mapping[LoadNature, float]) -> tuple[tuple[str, float], ...]:
        """Each combination's ``(name, demand)`` in declaration order."""
        return tuple((c.name, c.evaluate(loads)) for c in self.combinations)

    def governing(
        self,
        loads: Mapping[LoadNature, float],
        *,
        minimize: bool = False,
        by_magnitude: bool = False,
    ) -> tuple[LoadCombination, float]:
        """The governing combination and its demand.

        The largest demand by default — the strength envelope. ``minimize=True``
        returns the smallest, the counteracting combination that governs an uplift
        or overturning check (e.g. 0.9D + 1.0W netting upward).

        ``by_magnitude=True`` ignores sign and returns the largest ``|demand|``,
        which is what a check judging ``capacity/|demand|`` actually needs: a set
        holding +100 kN of gravity and −420 kN of uplift is governed by the uplift,
        and signed selection would hand back the 100 kN. The demand is returned
        signed either way, so the caller still sees which direction governs.
        """
        if not self.combinations:
            raise ValueError("an empty combination set has no governing combination")

        def key(combination: LoadCombination) -> float:
            value = combination.evaluate(loads)
            return abs(value) if by_magnitude else value

        chooser = min if minimize and not by_magnitude else max
        governing = chooser(self.combinations, key=key)
        return governing, governing.evaluate(loads)

    def envelope(self, loads: Mapping[LoadNature, float]) -> float:
        """The largest demand across the set — the number a strength check screens."""
        return self.governing(loads)[1]


def _combo(name: str, clause: str, **factors: float) -> LoadCombination:
    return LoadCombination(
        name=name,
        factors={LoadNature(symbol): factor for symbol, factor in factors.items()},
        citation=clause,
    )


def _expand_roof(
    prefix: str, clause: str, base: dict[str, float], companion_factor: float
) -> list[LoadCombination]:
    """One combination per roof companion (Lr/S/R), each at ``companion_factor``."""
    out = []
    for companion in _ROOF_COMPANIONS:
        factors = dict(base)
        factors[companion.value] = companion_factor
        out.append(_combo(f"{prefix} [{companion.value}]", clause, **factors))
    return out


def asce7_lrfd_basic() -> CombinationSet:
    """The ASCE 7-22 §2.3.1 basic combinations for strength design (LRFD).

    Dead, live, roof-live, snow, rain, and wind; the roof companion "(Lr or S or R)"
    is expanded into one variant per companion, and combination 3's "(L or 0.5W)"
    alternative into its two forms. Seismic is :func:`asce7_lrfd_seismic`.
    """
    clause = "ASCE 7-22 §2.3.1"
    combos: list[LoadCombination] = [
        _combo("LRFD 1", clause, D=1.4),
        # 2. 1.2D + 1.6L + 0.5(Lr or S or R)
        *_expand_roof("LRFD 2", clause, {"D": 1.2, "L": 1.6}, 0.5),
        # 3. 1.2D + 1.6(Lr or S or R) + (L or 0.5W)
        *_expand_roof("LRFD 3 (+L)", clause, {"D": 1.2, "L": 1.0}, 1.6),
        *_expand_roof("LRFD 3 (+0.5W)", clause, {"D": 1.2, "W": 0.5}, 1.6),
        # 4. 1.2D + 1.0W + L + 0.5(Lr or S or R)
        *_expand_roof("LRFD 4", clause, {"D": 1.2, "W": 1.0, "L": 1.0}, 0.5),
        # 5. 0.9D + 1.0W
        _combo("LRFD 5", clause, D=0.9, W=1.0),
    ]
    return CombinationSet(basis="ASCE 7-22 LRFD (strength)", combinations=tuple(combos))


def combination_scorecard(
    name: str,
    *,
    combinations: CombinationSet,
    loads: Mapping[LoadNature, float],
    capacity: float,
    required: float,
    minimize: bool = False,
    unclassified: Sequence[str] = (),
    reference: str | None = None,
) -> ScorecardEntry:
    """Screen a ``capacity`` against the governing combination's demand.

    ``unclassified`` names load cases that carry a force and no ``nature`` — see
    :meth:`~anvilate.spec.DesignSpec.unclassified_force_cases`. Any at all and the check
    reports ``NOT_EVALUATED`` **before a number is computed**, because the combination
    generators treat a nature nobody supplied as zero: a spec that declares a 200 kN case
    and forgets to classify it otherwise screens its capacity against a demand that never
    saw the 200 kN, and passes. That is a subset evaluation, and a subset evaluation is
    not a smaller answer to the same question — it is an answer to a different one.

    The demand is the governing combination's factored sum, chosen by *magnitude*
    because the safety factor is ``capacity / |demand|``: selecting by signed value
    while judging by magnitude is how a set holding +100 kN of gravity and −420 kN of
    uplift used to return PASS on the 100 kN and never look at the uplift. Pure uplift
    was worse — every gravity combination evaluated to exactly 0, the signed maximum
    picked one of them, and a zero demand short-circuited to an *infinite* safety
    factor, so the check passed without the criterion ever being evaluated.

    Selecting by magnitude fixed only half of that. A demand of exactly zero is still
    not a criterion that was evaluated and passed — it is a criterion with nothing to
    evaluate, and dividing by it yields an *infinite* safety factor that reads as the
    strongest possible PASS. It arises from ordinary input: ``LoadNature`` is optional
    on a load case, so a spec that declares a 50 kN load and forgets to classify it
    reaches here with an empty ``loads`` mapping and every combination summing to 0.
    Such a check is reported ``NOT_EVALUATED``, which the roll-up in
    :class:`~anvilate.scorecard.Scorecard` refuses to treat as a pass.

    ``minimize=True`` still forces the counteracting side explicitly, for a caller who
    wants that combination named whatever its magnitude. The safety factor is judged
    against ``required``. The entry names which combination governed in its detail and
    takes that combination's citation as its reference, so the scorecard shows the
    controlling combination rather than silently reducing the set to one number.
    """
    if unclassified:
        return ScorecardEntry(
            name=name,
            status=CheckStatus.NOT_EVALUATED,
            detail=(
                f"{len(unclassified)} load case(s) carry a force and no nature, so they "
                f"enter no combination: {', '.join(unclassified)}. A demand summed from "
                f"part of the declared loads is not this part's demand"
            ),
            reference=reference or combinations.basis,
        )
    governing, demand = _governing_for_check(combinations, loads, minimize=minimize)
    magnitude = abs(demand)
    if magnitude == 0:
        return ScorecardEntry(
            name=name,
            status=CheckStatus.NOT_EVALUATED,
            detail=(
                "no load to check: every combination in "
                f"{combinations.basis} sums to zero demand. Classify each load case with a "
                "`nature` so it enters a combination."
            ),
            reference=reference or governing.citation,
        )
    computed = capacity / magnitude
    entry = ScorecardEntry.from_safety_factor(name, computed=computed, required=required)
    detail = f"{entry.detail}; demand {demand:g} from {governing}"
    citation = reference or governing.citation
    return entry.model_copy(
        update={
            "detail": detail,
            "reference": citation,
            "derivation": _combination_derivation(governing, loads, demand, citation),
        }
    )


def _combination_derivation(
    governing: LoadCombination,
    loads: Mapping[LoadNature, float],
    demand: float,
    citation: str,
) -> Derivation:
    """The governing combination written out as the standard writes it.

    The symbolic line is built from the combination's own factors — ``U = 1.2·D + 1.6·L``
    — rather than from a fixed template, because which combination governs is the answer
    and a template would render the same expression for all of them. Only the natures this
    combination factors appear: a load the set does not factor is not part of this sum, and
    showing it beside a zero factor invites a reviewer to look for it in the total.

    The loads are bare numbers here, not quantities. The caller's own unit is what the
    capacity and the demand are both in, so the substituted line is unitless on purpose —
    stating one would be inventing it.
    """
    terms: list[str] = []
    inputs: list[SymbolValue] = []
    for nature, factor in governing.factors.items():
        sign = " − " if factor < 0 else (" + " if terms else "")
        # ASCE writes its factors to at least one decimal — 1.0W, not 1W — and a bare "1"
        # beside a "1.2" reads as a typo rather than as the unit factor it is.
        written = f"{abs(factor):g}"
        terms.append(f"{sign}{written if '.' in written else written + '.0'} · {nature.value}")
        inputs.append(
            SymbolValue(
                symbol=nature.value,
                description=f"{_NATURE_NAMES[nature]} load, as the caller supplied it",
                value=float(loads.get(nature, 0.0)),
            )
        )
    return Derivation(
        symbolic="U = " + "".join(terms),
        inputs=tuple(inputs),
        result=SymbolValue(
            symbol="U",
            description=f"factored demand from the governing combination, {governing.name}",
            value=demand,
        ),
        citation=citation,
    )


_NATURE_NAMES = {
    LoadNature.DEAD: "dead",
    LoadNature.LIVE: "live",
    LoadNature.ROOF_LIVE: "roof live",
    LoadNature.SNOW: "snow",
    LoadNature.RAIN: "rain",
    LoadNature.WIND: "wind",
    LoadNature.SEISMIC: "seismic",
}


def asce7_lrfd_seismic(*, s_ds: float, redundancy: float = 1.0) -> CombinationSet:
    """The ASCE 7-22 §2.3.6 strength (LRFD) combinations with earthquake load.

    The earthquake effect E splits into a vertical part Ev = 0.2·S_DS·D — folded
    into the dead-load factor — and a horizontal part Eh = ρ·Q_E, carried on the
    seismic nature ``E`` (the caller supplies Q_E as the seismic load magnitude).
    ``s_ds`` is the design spectral acceleration S_DS and ``redundancy`` the factor
    ρ, both typed user inputs — Anvilate factors the combination, it does not derive
    the seismic hazard. Each combination is generated for both horizontal directions
    (±Eh) so the envelope and the minimizing (overturning) case each see the
    governing sense.
    """
    clause = "ASCE 7-22 §2.3.6"
    ev = 0.2 * s_ds
    combos: list[LoadCombination] = []
    for sign, tag in ((1.0, "+E"), (-1.0, "-E")):
        eh = sign * redundancy
        # 6. (1.2 + 0.2·S_DS)D + ρQ_E + L + 0.2S
        combos.append(_combo(f"LRFD 6 ({tag})", clause, D=1.2 + ev, E=eh, L=1.0, S=0.2))
        # 7. (0.9 − 0.2·S_DS)D + ρQ_E  (reduced dead — the overturning case)
        combos.append(_combo(f"LRFD 7 ({tag})", clause, D=0.9 - ev, E=eh))
    return CombinationSet(basis="ASCE 7-22 LRFD (seismic)", combinations=tuple(combos))


def asce7_asd_seismic(*, s_ds: float, redundancy: float = 1.0) -> CombinationSet:
    """The ASCE 7-22 §2.4.5 allowable-stress (ASD) combinations with earthquake load.

    The ASD 0.7 factor on E carries through: the vertical Ev folds into the dead
    factor (0.7·0.2·S_DS = 0.14·S_DS, and 0.525·0.2·S_DS = 0.105·S_DS in the
    live-companion combination), and the horizontal Eh = ρ·Q_E rides the seismic
    nature at 0.7ρ or 0.525ρ. ``s_ds`` and ``redundancy`` are typed user inputs.
    Combination 9's "(Lr or S or R)" roof companion is expanded; both ±Eh directions
    are generated.
    """
    clause = "ASCE 7-22 §2.4.5"
    combos: list[LoadCombination] = []
    for sign, tag in ((1.0, "+E"), (-1.0, "-E")):
        # 8. (1.0 + 0.14·S_DS)D + 0.7ρQ_E
        combos.append(
            _combo(f"ASD 8 ({tag})", clause, D=1.0 + 0.14 * s_ds, E=sign * 0.7 * redundancy)
        )
        # 9. (1.0 + 0.105·S_DS)D + 0.525ρQ_E + 0.75L + 0.75(Lr or S or R)
        combos.extend(
            _expand_roof(
                f"ASD 9 ({tag})",
                clause,
                {"D": 1.0 + 0.105 * s_ds, "E": sign * 0.525 * redundancy, "L": 0.75},
                0.75,
            )
        )
        # 10. (0.6 − 0.14·S_DS)D + 0.7ρQ_E  (reduced dead — the overturning case)
        combos.append(
            _combo(f"ASD 10 ({tag})", clause, D=0.6 - 0.14 * s_ds, E=sign * 0.7 * redundancy)
        )
    return CombinationSet(basis="ASCE 7-22 ASD (seismic)", combinations=tuple(combos))


def asce7_asd_basic() -> CombinationSet:
    """The ASCE 7-22 §2.4.1 basic combinations for allowable stress design (ASD).

    Dead, live, roof-live, snow, rain, and wind, with the roof companion expanded.
    Seismic (§2.4.5) is a later slice.
    """
    clause = "ASCE 7-22 §2.4.1"
    combos: list[LoadCombination] = [
        _combo("ASD 1", clause, D=1.0),
        _combo("ASD 2", clause, D=1.0, L=1.0),
        # 3. D + (Lr or S or R)
        *_expand_roof("ASD 3", clause, {"D": 1.0}, 1.0),
        # 4. D + 0.75L + 0.75(Lr or S or R)
        *_expand_roof("ASD 4", clause, {"D": 1.0, "L": 0.75}, 0.75),
        # 5. D + 0.6W
        _combo("ASD 5", clause, D=1.0, W=0.6),
        # 6. D + 0.75L + 0.75(0.6W) + 0.75(Lr or S or R)
        *_expand_roof("ASD 6", clause, {"D": 1.0, "L": 0.75, "W": 0.45}, 0.75),
        # 7. 0.6D + 0.6W
        _combo("ASD 7", clause, D=0.6, W=0.6),
    ]
    return CombinationSet(basis="ASCE 7-22 ASD (allowable stress)", combinations=tuple(combos))


def _governing_for_check(
    combinations: CombinationSet, loads: Mapping[LoadNature, float], *, minimize: bool
) -> tuple[LoadCombination, float]:
    """The combination a check screens against — one rule, used by every consumer.

    Signed selection for an explicitly-requested counteracting case, by magnitude
    otherwise, because a check judges ``capacity / |demand|``. It exists as one function
    so the combination the evidence bundle *names* cannot drift from the one the scorecard
    *screened against*; two copies of this rule would be two places for it to change.
    """
    return combinations.governing(loads, minimize=minimize, by_magnitude=not minimize)


class CombinationEvidence(RevalidatedModel):
    """Which combination a part's checks were screened against, for the evidence bundle.

    The scorecard entry names the governing combination in its detail, which a reader
    sees and nothing consumes. This is the structured form: the basis, the combination,
    its clause, the demand it produced, and — the part that decides the status — the load
    cases that carried a force and entered no combination.
    """

    model_config = ConfigDict(frozen=True)

    basis: str
    governing: str
    citation: cited("the clause the governing combination comes from")
    demand_newtons: float
    # Load cases carrying a force with no declared nature. Any at all and the evidence is
    # NOT_EVALUATED: the demand was summed from part of the declared loads.
    unclassified: tuple[str, ...] = ()

    @model_validator(mode="after")
    def _well_formed(self) -> CombinationEvidence:
        for field, value in (
            ("basis", self.basis),
            ("governing", self.governing),
        ):
            if not value.strip():
                raise ValueError(f"combination evidence must state its {field}")
        if not isfinite(self.demand_newtons):
            raise ValueError(
                f"the governing demand is {self.demand_newtons}, which is not a finite "
                "number; a non-finite demand is refused rather than recorded"
            )
        return self

    # A verdict a serialised document does not carry is one its reader has to
    # rebuild. See `Scorecard.status` for what that costs.
    @computed_field  # type: ignore[prop-decorator]
    @property
    def status(self) -> CheckStatus:
        """``NOT_EVALUATED`` when the demand was summed from part of the declared loads,
        or when every combination summed to zero — otherwise ``PASS``, meaning the
        governing combination is named and the checks were screened against it."""
        if self.unclassified or self.demand_newtons == 0:
            return CheckStatus.NOT_EVALUATED
        return CheckStatus.PASS

    def detail(self) -> str:
        """One line: the combination that governed, or why none can be named."""
        if self.unclassified:
            return (
                f"{len(self.unclassified)} load case(s) carry a force and no nature "
                f"({', '.join(self.unclassified)}), so the {self.basis} demand was summed "
                "from part of the declared loads"
            )
        if self.demand_newtons == 0:
            return f"every combination in {self.basis} sums to zero demand; no load to check"
        return (
            f"{self.governing} governs under {self.basis} "
            f"({self.demand_newtons:g} N, {self.citation})"
        )

    def __str__(self) -> str:
        return self.detail()


def combination_evidence(
    combinations: CombinationSet,
    loads: Mapping[LoadNature, float],
    *,
    unclassified: Sequence[str] = (),
    minimize: bool = False,
) -> CombinationEvidence:
    """The governing combination as a bundle-ready record.

    Selects the combination with :func:`_governing_for_check`, the same rule
    :func:`combination_scorecard` screens with, so the bundle cannot name a different
    combination from the one the checks used.
    """
    governing, demand = _governing_for_check(combinations, loads, minimize=minimize)
    return CombinationEvidence(
        basis=combinations.basis,
        governing=governing.name,
        citation=governing.citation,
        demand_newtons=demand,
        unclassified=tuple(unclassified),
    )
