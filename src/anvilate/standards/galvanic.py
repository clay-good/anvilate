"""The galvanic series, and whether a couple of metals may be put in contact.

Two metals in contact with an electrolyte between them make a cell, and the more active
one corrodes in place of the other. Which one that is, and how fast, is set by how far
apart they are in the **galvanic series** for the electrolyte they sit in.

**What is bundled and what is not.** The series below is MIL-STD-889C's Table II, read
from the standard itself. MIL-STD-889C is a US Department of Defense standard, approved
for public release with distribution unlimited, so the table ships. What does **not**
ship is a threshold: 889C gives no number for how far apart is too far. It says only
that "the closer one metal is to another in the series, the more compatible they will
be", and that metals "widely separated in the galvanic series shall be protected". So the
limit is the caller's, declared with its own basis, and this refuses to invent one.

Three rules of the standard that a separation alone misses, each from the clause it is
in and each a way a couple that looks fine is not:

- **A humidity-controlled environment may only be claimed if it is assured.** Note (g):
  humidity control "can be assured only by hermetically sealed compartments or containers",
  and where it cannot be, "dissimilar metal contacts shall be treated as if protection were
  required against the worst environment". A declared controlled environment that nobody
  assured is screened as sea water.
- **The cathode is the smaller area, never the larger.** §5.2(a): "bolts or screws of
  stainless steel for fastening aluminum sheet, but not the reverse". A small anode feeding
  a large cathode concentrates the whole couple's current into very little metal.
- **Magnesium takes the maximum protective system, always.** §5.1.6: where magnesium is one
  of the metals, "the maximum protective systems shall always be employed ... whether or not
  the combination is to serve in an electrical conducting system". One gasket does not clear
  a magnesium couple.

Sources: MIL-STD-889C, "Dissimilar Metals" (2016), §5.1.1, §5.1.2, §5.1.6, §5.2 and
Table II, whose series is credited there to Army Missile Command Report ARS-TR-67-11.
Table I of the same standard, the per-pair guide to protective systems, is a scanned
image in the published PDF rather than text, and is **not** transcribed here: two hundred
compatibility cells read off a 1967 scan by eye is a table nobody could check.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import ConfigDict, model_validator

from .._models import Named, Provenance, StatableModel
from ..refusal import RefusalError, Remedy

__all__ = [
    "GALVANIC_SERIES",
    "GALVANIC_SERIES_CITATION",
    "LISTED_TWICE",
    "WORST_ENVIRONMENT",
    "GalvanicEnvironment",
    "GalvanicCouple",
    "GalvanicVerdict",
    "series_position",
    "screen_galvanic_couple",
]

#: The table these names and this order come from, as it is cited on every verdict.
GALVANIC_SERIES_CITATION = (
    "MIL-STD-889C (2016), Table II, galvanic series of selected metals in sea water, "
    "credited there to Army Missile Command Report ARS-TR-67-11"
)

#: MIL-STD-889C Table II, in the published order: most active (anodic) first, most noble
#: (cathodic) last. The metal higher in this list is the anode of any couple it is in, and
#: corrodes preferentially to the one below it (§5.1.1).
GALVANIC_SERIES: tuple[str, ...] = (
    "Magnesium",
    "Mg Alloy AZ-31B",
    "MG Alloy HK-31A",
    "Zinc (hot-dip, die cast or plated)",
    "Beryllium (hot pressed)",
    "Aluminum (Al) 7072 cl. on 7075",
    "Al alloy 2014-T3",
    "Al alloy 1160-1114",
    "Al alloy 7079-T6",
    "Cadmium (plated)",
    "Uranium",
    "Al alloy 218 (die cast)",
    "Al alloy 5052-0",
    "Al alloy 5052-H12",
    "Al alloy 5456-0, H353",
    "Al alloy 5052-H32",
    "Al alloy 1100-0",
    "Al alloy 3003-H25",
    "Al alloy 6061-T6",
    "Al alloy A360 (die cast)",
    "Al alloy 7075-T6",
    "Al alloy 1160-1114",
    "Al alloy 6061-0",
    "Indium",
    "Al alloy 2014-0",
    "Al alloy 2024-T4",
    "Al alloy 5052-H16",
    "Tin (plated)",
    "Stainless steel 430 (active)",
    "Lead",
    "Steel 1010",
    "Iron, cast",
    "Stainless steel 410 (active)",
    "Copper (plated, cast or wrought)",
    "Nickel (plated)",
    "Chromium (plated)",
    "Tantalum",
    "AM350 (active)",
    "Stainless steel 310 (active)",
    "Stainless steel 301 (active)",
    "Stainless steel 304 (active)",
    "Stainless steel 430 (passive)",
    "Stainless steel 410 (passive)",
    "Stainless steel 17-7 PH (active)",
    "Tungsten",
    "Niobium (Columbium) 1% Zr",
    "Brass, yellow, 268",
    "Uranium 8% Mo",
    "Brass, Naval, 464",
    "Yellow brass",
    "Muntz metal 280",
    "Brass plated",
    "Nickel-silver (18% Ni)",
    "Stainless steel 316L (active)",
    "Bronze 220",
    "Copper 110",
    "Red brass",
    "Stainless steel 347 (active)",
    "Molybdenum, Comm pure",
    "Copper-Nickel 715",
    "Admiralty brass",
    "Stainless steel 202 (active)",
    "Bronze, Phosphor 534 (B-1)",
    "Monel 400",
    "Stainless steel 201 (active)",
    "Carpenter 20 (active)",
    "Stainless steel 321 (active)",
    "Stainless steel 316 (active)",
    "Stainless steel 309 (passive)",
    "Stainless steel 17-7 PH (passive)",
    "Silicone Bronze 655",
    "Stainless steel 304 (passive)",
    "Stainless steel 301 (passive)",
    "Stainless steel 321 (passive)",
    "Stainless steel 201 (passive)",
    "Stainless steel 286 (active)",
    "Stainless steel 316L (passive)",
    "AM355 (active)",
    "Stainless steel 202 (passive)",
    "Carpenter 20 (passive)",
    "AM355 (passive)",
    "A286 (passive)",
    "Titanium 5A1, 2.5 Sn",
    "Titanium 13V, 11Cr, 3A1 (annealed)",
    "Titanium 6A1, 4V (solution treated and aged)",
    "Titanium 6A1, 4V (annealed)",
    "Titanium 8 Mn",
    "Titanium 13V, 11Cr, 3A1 (solution treated and aged)",
    "Titanium 75A",
    "AM350 (passive)",
    "Silver",
    "Gold",
    "Graphite",
)

#: Names Table II prints at two different places in the series. The standard lists
#: "Al alloy 1160-1114" twice, and a name that means two positions cannot be looked up:
#: :func:`series_position` refuses it rather than silently taking the first.
LISTED_TWICE: frozenset[str] = frozenset(
    name for name in GALVANIC_SERIES if GALVANIC_SERIES.count(name) > 1
)

_SERIES_SOURCE = "MIL-STD-889C Table II, by the name it prints"
_COUPLE_SOURCE = "the assembly declaration: the two metals in contact and what separates them"


class _GalvanicInputError(RefusalError, ValueError):
    """A galvanic-couple input that cannot be used without correction."""


def _refuse(message: str, *, subject: str, source: str = _COUPLE_SOURCE):
    return _GalvanicInputError(
        message, remedies=(Remedy(action="replace", subject=subject, source=source),)
    )


class GalvanicEnvironment(StrEnum):
    """The electrolyte the couple sits in, as MIL-STD-889C Table I names them.

    ``CONTROLLED`` is the humidity-controlled case of note (g), and it is the one that
    needs a second declaration: control can be assured only by a hermetically sealed
    compartment, and where it is not assured the standard says to treat the contact as if
    it were in the worst environment.
    """

    SEA_WATER = "sea water"
    MARINE_ATMOSPHERE = "marine atmosphere"
    INDUSTRIAL_ATMOSPHERE = "industrial atmosphere"
    CONTROLLED = "humidity controlled"


#: The environment note (g) sends an unassured controlled one to.
WORST_ENVIRONMENT = GalvanicEnvironment.SEA_WATER


def series_position(metal: str) -> int:
    """Where ``metal`` sits in :data:`GALVANIC_SERIES`, refusing a name it does not print.

    Zero is the most active. A name the table does not print is refused with the closest
    ones it does, because a metal screened under a name the standard does not use has been
    screened against a position nobody chose.
    """
    if not isinstance(metal, str):
        raise _refuse(
            f"a metal is named by the string MIL-STD-889C Table II prints; got {metal!r}",
            subject="metal",
            source=_SERIES_SOURCE,
        )
    if metal in LISTED_TWICE:
        raise _refuse(
            f"MIL-STD-889C Table II prints {metal!r} at two different places in the series, "
            f"so the name does not say which position is meant; name the one you have "
            f"another way, or declare its position",
            subject="metal",
            source=_SERIES_SOURCE,
        )
    try:
        return GALVANIC_SERIES.index(metal)
    except ValueError:
        import difflib

        # 0.78, not the 0.6 default: at 0.6 "aluminium" was answered with "Uranium",
        # "Magnesium" and "Indium", which is three wrong metals offered with the same
        # confidence as a right one. A suggestion nobody can use is worse than none.
        near = difflib.get_close_matches(metal, GALVANIC_SERIES, n=3, cutoff=0.78)
        suggestion = f"; did you mean {', '.join(repr(n) for n in near)}?" if near else ""
        raise _refuse(
            f"MIL-STD-889C Table II does not print {metal!r}{suggestion}. The table holds "
            f"{len(GALVANIC_SERIES)} names and a metal screened under one it does not use "
            f"has been screened against a position nobody chose",
            subject="metal",
            source=_SERIES_SOURCE,
        ) from None


class GalvanicCouple(StatableModel):
    """Two metals in contact, where they sit, and what the document declares about it.

    ``separation_limit`` is how many places apart in the series the document will allow
    before the couple needs protecting. **MIL-STD-889C states no such number**, so this is
    the caller's with its own basis — which is why it is required rather than defaulted.

    ``isolation`` names the measure §5.2 calls for, if one is declared; ``humidity_assured``
    is note (g)'s second declaration; and the two areas, when declared, are checked against
    §5.2(a)'s rule that the cathode is the smaller of them.
    """

    model_config = ConfigDict(frozen=True)

    states_requirements = True

    first: Named
    second: Named
    environment: GalvanicEnvironment
    separation_limit: int
    limit_basis: Provenance
    isolation: str = ""
    humidity_assured: bool = False
    first_area_mm2: float | None = None
    second_area_mm2: float | None = None

    @model_validator(mode="after")
    def _is_a_couple(self) -> GalvanicCouple:
        for metal in (self.first, self.second):
            series_position(metal)
        if self.first == self.second:
            raise _refuse(
                f"a galvanic couple is two different metals; both are {self.first!r}. A "
                f"same-metal couple is what MIL-STD-889C Table I marks 'G', and it needs no "
                f"screen",
                subject="first and second",
            )
        if self.separation_limit < 0:
            raise _refuse(
                f"separation_limit is a count of places in the series; got {self.separation_limit}",
                subject="separation_limit",
            )
        for value, name in (
            (self.first_area_mm2, "first_area_mm2"),
            (self.second_area_mm2, "second_area_mm2"),
        ):
            if value is not None and value <= 0:
                raise _refuse(f"{name} is a positive area; got {value}", subject=name)
        if self.humidity_assured and self.environment is not GalvanicEnvironment.CONTROLLED:
            raise _refuse(
                f"humidity_assured is declared with a {self.environment.value} environment, "
                f"where it says nothing; it is note (g)'s second declaration about a "
                f"humidity controlled one",
                subject="humidity_assured",
            )
        return self

    @property
    def screened_environment(self) -> GalvanicEnvironment:
        """The environment this is actually screened in, after note (g).

        A controlled environment nobody assured is screened as the worst one, because the
        standard says a contact whose humidity control is uncertain is treated as if
        protection were required against the worst environment.
        """
        if self.environment is GalvanicEnvironment.CONTROLLED and not self.humidity_assured:
            return WORST_ENVIRONMENT
        return self.environment

    @property
    def anode(self) -> str:
        """The metal higher in the series, which corrodes preferentially (§5.1.1)."""
        return min(self.first, self.second, key=series_position)

    @property
    def cathode(self) -> str:
        """The metal lower in the series."""
        return max(self.first, self.second, key=series_position)

    @property
    def separation(self) -> int:
        """How many places apart the two sit in the series."""
        return abs(series_position(self.first) - series_position(self.second))


class GalvanicVerdict(StatableModel):
    """What the couple comes to, and every reason it did."""

    model_config = ConfigDict(frozen=True)

    states_requirements = True

    anode: Named
    cathode: Named
    separation: int
    separation_limit: int
    environment: GalvanicEnvironment
    declared_environment: GalvanicEnvironment
    acceptable: bool
    reasons: tuple[str, ...]
    citation: Provenance = GALVANIC_SERIES_CITATION

    def __str__(self) -> str:
        verdict = "acceptable" if self.acceptable else "not acceptable"
        return (
            f"{self.anode} (anode) against {self.cathode}: {self.separation} places apart "
            f"in {self.environment.value}, {verdict}"
            + ("; " + "; ".join(self.reasons) if self.reasons else "")
        )


def screen_galvanic_couple(couple: GalvanicCouple) -> GalvanicVerdict:
    """Is this couple one MIL-STD-889C would let stand as declared?

    The separation is the first question and not the only one. Each of the other three is
    a rule of the standard that a separation alone misses:

    - a **controlled environment nobody assured** is screened as the worst one (note (g));
    - the **cathode must be the smaller area** (§5.2(a)), and a couple that has it the other
      way round is called out whether or not it is within the limit;
    - a **magnesium** couple takes the maximum protective system whatever else is declared
      (§5.1.6), so one declared isolation measure does not clear it.

    An isolation measure clears a separation past the limit, and does not clear the other
    two: they are about the couple itself and not the distance between its metals.
    """
    if not isinstance(couple, GalvanicCouple):
        raise _refuse(
            f"couple is a GalvanicCouple; got {type(couple).__name__}",
            subject="couple",
        )
    environment = couple.screened_environment
    reasons: list[str] = []
    acceptable = True

    if environment is not couple.environment:
        reasons.append(
            f"declared {couple.environment.value} and screened as {environment.value}: "
            f"MIL-STD-889C note (g) treats a contact whose humidity control is not assured "
            f"as if protection were required against the worst environment"
        )
    if couple.separation > couple.separation_limit:
        if couple.isolation:
            reasons.append(
                f"{couple.separation} places apart, past the declared limit of "
                f"{couple.separation_limit} ({couple.limit_basis}), and isolated by "
                f"{couple.isolation} (MIL-STD-889C §5.1.2)"
            )
        else:
            acceptable = False
            reasons.append(
                f"{couple.separation} places apart, past the declared limit of "
                f"{couple.separation_limit} ({couple.limit_basis}), and nothing separates "
                f"them: §5.1.2 requires metals widely separated in the series to be "
                f"protected against contact"
            )
    areas = (couple.first_area_mm2, couple.second_area_mm2)
    if all(area is not None for area in areas):
        by_metal = {couple.first: areas[0], couple.second: areas[1]}
        if by_metal[couple.cathode] > by_metal[couple.anode]:  # type: ignore[operator]
            acceptable = False
            reasons.append(
                f"the cathode {couple.cathode} is the larger area "
                f"({by_metal[couple.cathode]:g} mm² against {by_metal[couple.anode]:g}): "
                f"§5.2(a) designs the couple the other way round — stainless bolts in an "
                f"aluminium sheet, but not the reverse — because a small anode feeding a "
                f"large cathode carries the whole couple's current in very little metal"
            )
    if "magnesium" in (couple.anode + couple.cathode).lower():
        reasons.append(
            "magnesium is in this couple, so MIL-STD-889C §5.1.6 asks for the maximum "
            "protective system whatever else is declared, and whether or not the joint "
            "carries current"
        )
        if not couple.isolation:
            acceptable = False
    if acceptable and not reasons:
        reasons.append(
            f"{couple.separation} places apart, within the declared limit of "
            f"{couple.separation_limit} ({couple.limit_basis})"
        )
    return GalvanicVerdict(
        anode=couple.anode,
        cathode=couple.cathode,
        separation=couple.separation,
        separation_limit=couple.separation_limit,
        environment=environment,
        declared_environment=couple.environment,
        acceptable=acceptable,
        reasons=tuple(reasons),
    )
