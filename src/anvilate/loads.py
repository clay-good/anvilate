"""Load combinations: factored sums over load cases, and which one governs.

Every code check the structural packs cite assumes a *combination* of load cases
as its input — a factored sum under LRFD, a service sum under ASD — not a single
case. Doing that bookkeeping in your head is the silent-error class this library
exists to remove: the governing combination is often not the obvious one (an
uplift case where wind counteracts dead load can govern a connection the
gravity cases never stress).

This module carries the combination vocabulary and generates the ASCE 7-22 basic
combination sets (§2.3.1 strength / §2.4.1 allowable stress). The combination
expressions are short, universally republished equation lists; deriving the load
*magnitudes* (wind, seismic, snow from maps and site parameters) stays firmly out
of scope — the caller supplies each case's magnitude.

Seismic combinations (§2.3.6 / §2.4.5, which need E split into its Ev and Eh parts
from S_DS) are a later slice; the generators here cover the dead/live/roof/snow/
rain/wind basic sets.
"""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum

from pydantic import BaseModel, ConfigDict

from .scorecard import ScorecardEntry

__all__ = [
    "LoadNature",
    "LoadCombination",
    "CombinationSet",
    "asce7_lrfd_basic",
    "asce7_asd_basic",
    "combination_scorecard",
]


class LoadNature(StrEnum):
    """The nature of a load case, by its ASCE 7 symbol.

    The factor a combination applies depends on the load's nature, not its name —
    dead load is always factored as dead load. Seismic (``E``) is carried in the
    vocabulary but not yet produced by the basic generators.
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

    name: str
    factors: Mapping[LoadNature, float]
    citation: str

    def evaluate(self, loads: Mapping[LoadNature, float]) -> float:
        """The combined demand: ``Σ factor · load`` over this combination's natures.

        A load the caller supplies whose nature this combination does not factor is
        simply not part of this sum; a nature the combination factors but the caller
        omits contributes zero.
        """
        return sum(factor * loads.get(nature, 0.0) for nature, factor in self.factors.items())

    def __str__(self) -> str:
        terms = " + ".join(f"{factor:g}{nature.value}" for nature, factor in self.factors.items())
        return f"{self.name}: {terms}"


class CombinationSet(BaseModel):
    """A named set of load combinations — a code basis, or a custom list.

    ``evaluate_all`` returns every combination's demand; ``governing`` names the
    combination with the largest demand (the strength envelope), and its
    ``minimize`` form names the smallest — the counteracting case that governs
    uplift and overturning, where wind or seismic relieves gravity.
    """

    model_config = ConfigDict(frozen=True)

    basis: str
    combinations: tuple[LoadCombination, ...]

    def evaluate_all(self, loads: Mapping[LoadNature, float]) -> tuple[tuple[str, float], ...]:
        """Each combination's ``(name, demand)`` in declaration order."""
        return tuple((c.name, c.evaluate(loads)) for c in self.combinations)

    def governing(
        self, loads: Mapping[LoadNature, float], *, minimize: bool = False
    ) -> tuple[LoadCombination, float]:
        """The governing combination and its demand.

        The largest demand by default — the strength envelope. ``minimize=True``
        returns the smallest, the counteracting combination that governs an uplift
        or overturning check (e.g. 0.9D + 1.0W netting upward).
        """
        if not self.combinations:
            raise ValueError("an empty combination set has no governing combination")
        chooser = min if minimize else max
        governing = chooser(self.combinations, key=lambda c: c.evaluate(loads))
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
    alternative into its two forms. Seismic (§2.3.6) is a later slice.
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
    reference: str | None = None,
) -> ScorecardEntry:
    """Screen a ``capacity`` against the governing combination's demand.

    The demand is the governing combination's factored sum — the strength envelope
    by default, or the counteracting minimum when ``minimize=True`` (an uplift or
    overturning check). The safety factor is ``capacity / |demand|``, judged against
    ``required``. The entry names which combination governed in its detail and takes
    that combination's citation as its reference, so the scorecard shows the
    controlling combination rather than silently reducing the set to one number.
    """
    governing, demand = combinations.governing(loads, minimize=minimize)
    magnitude = abs(demand)
    computed = float("inf") if magnitude == 0 else capacity / magnitude
    entry = ScorecardEntry.from_safety_factor(name, computed=computed, required=required)
    detail = f"{entry.detail}; demand {demand:g} from {governing}"
    return entry.model_copy(update={"detail": detail, "reference": reference or governing.citation})


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
