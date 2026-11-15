"""Dowel-type timber connections by the yield limit equations.

A timber structure fails at its connections far more often than in its members, and the
timber pack screened members only. A bolt, lag screw, nail or screw through wood is
checked by the yield limit equations — Johansen's rigid-plastic theory, the European
Yield Model, which the NDS adopted: the capacity is the least of the yield modes, and
each is a closed form in the fastener diameter, the dowel bending yield strength and the
members' dowel bearing strengths.

**The equations here are the American Wood Council's Technical Report 12**, which
publishes the generalized form and is freely downloadable. What is proprietary is the
NDS's tabulated reduction terms and the reference values that result, and those are
never bundled: the reduction term per mode is the caller's input, with its citation, and
this module reports the unreduced 5% offset yield value ``P`` that TR12 itself computes.

Six modes, each a bearing or a hinge:

- **Im, Is** — the main or the side member crushes under the dowel, and the dowel does
  not bend. A product of a bearing resistance and a bearing length, and nothing else.
- **II** — the dowel rotates without a hinge, crushing both members.
- **IIIm, IIIs** — one plastic hinge in the dowel, with crushing in the other member.
- **IV** — two hinges, and the dowel's own bending governs.

Modes II and IIIm **do not apply to a double-shear connection**, which TR12 states in
the footnote to its own Table 1-1: the geometry is symmetric about the main member, so
the rotation those modes describe cannot happen. A capacity list that silently included
them would govern on a mode the connection cannot reach.

Out of scope here: hollow members and fasteners of varying diameter (TR12 Tables 1-2 and
1-3), the group-action and geometry factors, withdrawal, and metal connector plates. The
sign convention and the quadratic are the ones below, verified against every value of
TR12's own Example 3.1.
"""

from __future__ import annotations

from enum import StrEnum
from math import cos, isfinite, radians, sin, sqrt

from pydantic import ConfigDict, model_validator

from .._models import Provenance, StatableModel
from ..refusal import RefusalError, Remedy
from ..units import Quantity

__all__ = [
    "TR12_CITATION",
    "BEARING_FORMULA_CITATION",
    "YieldMode",
    "ShearPlanes",
    "DOUBLE_SHEAR_MODES",
    "DowelConnection",
    "ModeCapacity",
    "DowelYield",
    "dowel_yield_capacity",
    "dowel_bearing_strength",
    "hankinson_bearing_strength",
]

#: The document these equations are read from. Freely published by the American Wood
#: Council, which is why they ship; the NDS itself is copyrighted and its tables do not.
TR12_CITATION = (
    "AWC Technical Report 12 (2012 edition, ANSI/AWC NDS-2012), Table 1-1 general dowel "
    "equations for solid cross-section members"
)
#: The dowel bearing strength formulas, which TR12 reprints from the NDS in its own
#: Appendix A. A formula is not a table: these three expressions are what the caller
#: computes a bearing strength *from*, when they do not have a tabulated value.
BEARING_FORMULA_CITATION = (
    "AWC TR12 Appendix A, Table A1 (NDS Table 12.3.3 dowel bearing strength formulas)"
)

_CONNECTION_SOURCE = "the connection as declared: its fastener, its members and its gap"


class _DowelInputError(RefusalError, ValueError):
    """A dowel-connection input that cannot be used without correction.

    A ``ValueError`` as well as a refusal, as every other analysis module's input error
    is: raised inside a pydantic validator a bare ``RefusalError`` is a ``RuntimeError``
    and escapes the handler a document reader has for a bad field.
    """


def _refuse(message: str, *, subject: str, source: str = _CONNECTION_SOURCE) -> _DowelInputError:
    return _DowelInputError(
        message, remedies=(Remedy(action="replace", subject=subject, source=source),)
    )


def _dimensioned(value: object, *, name: str, dimension: str, source: str) -> Quantity:
    """``value`` as a Quantity of ``dimension``, refusing a bare number **by name**.

    A public function here is reachable from a caller who has a float, and the float is
    almost always in the unit the caller happens to be thinking in. Answering it with an
    ``AttributeError`` about `has_dimension` tells them nothing; this names the parameter
    and the unit to write, which is the contract every analysis function in this package
    keeps and a gate holds them all to.
    """
    if not isinstance(value, Quantity):
        raise _refuse(
            f"{name} is a Quantity, not a bare number; got {value!r}. Write it with its "
            f'unit — Quantity.parse("0.5 inch") — because a number with no unit is the '
            f"one input this library cannot check",
            subject=name,
            source=source,
        )
    if not value.has_dimension(dimension):
        raise _refuse(
            f"{name} is a {dimension}; got {value.dimensionality}", subject=name, source=source
        )
    # A NaN diameter reached `11,200 G` — a formula that does not mention the diameter —
    # and came back as a perfectly ordinary 5,600 psi. The poison never met a comparison
    # that could see it, because every `<` against a NaN is False, so the guards above let
    # it through and the branch it landed in threw it away. Finiteness is checked here,
    # once, rather than at each use.
    if not isfinite(value.magnitude):
        raise _refuse(
            f"{name} is a finite {dimension}; got {value}. A non-finite input does not "
            f"always produce a non-finite answer — it can land in a branch that never "
            f"reads it — so it is refused rather than carried",
            subject=name,
            source=source,
        )
    return value


class YieldMode(StrEnum):
    """The six yield modes of the European Yield Model, as the NDS names them."""

    IM = "Im"
    IS = "Is"
    II = "II"
    IIIM = "IIIm"
    IIIS = "IIIs"
    IV = "IV"

    @property
    def description(self) -> str:
        """What the mode is, in the words TR12 section 2.2 uses."""
        return _MODE_DESCRIPTIONS[self]


#: A TOTAL map. A seventh mode cannot be added without saying what it is.
_MODE_DESCRIPTIONS: dict[YieldMode, str] = {
    YieldMode.IM: "the main member crushes under the dowel, which does not bend",
    YieldMode.IS: "the side member crushes under the dowel, which does not bend",
    YieldMode.II: "the dowel rotates without a hinge, crushing both members",
    YieldMode.IIIM: "one hinge in the dowel, with the main member crushing",
    YieldMode.IIIS: "one hinge in the dowel, with the side member crushing",
    YieldMode.IV: "two hinges in the dowel; its own bending governs",
}

#: The modes a double-shear connection can reach. TR12's footnote 1 to Table 1-1: modes
#: II and IIIm do not apply, because the geometry is symmetric about the main member and
#: the rotation those two describe cannot happen.
DOUBLE_SHEAR_MODES: frozenset[YieldMode] = frozenset(
    {YieldMode.IM, YieldMode.IS, YieldMode.IIIS, YieldMode.IV}
)


class ShearPlanes(StrEnum):
    """How many shear planes the fastener crosses, which decides the mode set.

    Single and double shear are the two cases AWC TR12 Table 1-1 tabulates, and the NDS
    yield limit equations read the same distinction.
    """

    SINGLE = "single"
    DOUBLE = "double"


class DowelConnection(StatableModel):
    """One dowel-type fastener through a main member and its side member(s).

    Every field is an input to the AWC TR12 Table 1-1 general dowel equations, which are
    the NDS yield limit equations in their published generalized form.

    ``main_bearing_strength`` and ``side_bearing_strength`` are the dowel bearing
    strengths *of each member in the direction its load acts* — resolve an angled load
    with :func:`hankinson_bearing_strength` first, because the yield equations take one
    number per member and the angle is not theirs to apply.

    ``gap`` is the space between the members, which TR12 carries through every mode: a
    bolted connection with a quarter-inch gap loses about a tenth of its capacity, and
    the clause most engineers use has no term for it at all.
    """

    model_config = ConfigDict(frozen=True)

    states_requirements = True

    diameter: Quantity
    bending_yield_strength: Quantity
    main_bearing_length: Quantity
    side_bearing_length: Quantity
    main_bearing_strength: Quantity
    side_bearing_strength: Quantity
    gap: Quantity | None = None
    shear_planes: ShearPlanes = ShearPlanes.SINGLE
    source: Provenance = TR12_CITATION

    @model_validator(mode="after")
    def _is_a_connection(self) -> DowelConnection:
        lengths = (
            (self.diameter, "diameter"),
            (self.main_bearing_length, "main_bearing_length"),
            (self.side_bearing_length, "side_bearing_length"),
        )
        stresses = (
            (self.bending_yield_strength, "bending_yield_strength"),
            (self.main_bearing_strength, "main_bearing_strength"),
            (self.side_bearing_strength, "side_bearing_strength"),
        )
        for value, name in lengths:
            if not value.has_dimension("[length]"):
                raise _refuse(f"{name} is a length; got {value.dimensionality}", subject=name)
            if value.magnitude <= 0:
                raise _refuse(f"{name} is positive; got {value}", subject=name)
        for value, name in stresses:
            if not value.has_dimension("[pressure]"):
                raise _refuse(f"{name} is a stress; got {value.dimensionality}", subject=name)
            if value.magnitude <= 0:
                raise _refuse(f"{name} is positive; got {value}", subject=name)
        if self.gap is not None:
            if not self.gap.has_dimension("[length]"):
                raise _refuse(f"gap is a length; got {self.gap.dimensionality}", subject="gap")
            if self.gap.magnitude < 0:
                raise _refuse(
                    f"a gap between members is not negative; got {self.gap}. Members that "
                    f"overlap are a different connection",
                    subject="gap",
                )
        return self

    @property
    def main_resistance(self) -> float:
        """``q_m = F_em · D`` in pounds per inch, the unit TR12's equations are in."""
        return self.main_bearing_strength.to("psi").magnitude * self.diameter.to("inch").magnitude

    @property
    def side_resistance(self) -> float:
        """``q_s = F_es · D`` in pounds per inch."""
        return self.side_bearing_strength.to("psi").magnitude * self.diameter.to("inch").magnitude

    @property
    def dowel_moment(self) -> float:
        """``M_d = F_yb · D³ / 6`` in inch-pounds, the dowel's own moment resistance."""
        return (
            self.bending_yield_strength.to("psi").magnitude
            * self.diameter.to("inch").magnitude ** 3
            / 6.0
        )

    def __str__(self) -> str:
        gap = f", {self.gap} gap" if self.gap is not None else ""
        return (
            f"{self.diameter} dowel in {self.shear_planes.value} shear, "
            f"{self.main_bearing_length} main / {self.side_bearing_length} side{gap}"
        )


class ModeCapacity(StatableModel):
    """One yield mode's capacity, or why the mode does not apply to this connection.

    One row of the AWC TR12 Table 1-1 mode set that the NDS yield limit equations use.
    """

    model_config = ConfigDict(frozen=True)

    mode: YieldMode
    capacity: Quantity | None = None
    not_applicable: str = ""

    @model_validator(mode="after")
    def _one_or_the_other(self) -> ModeCapacity:
        if (self.capacity is None) == (not self.not_applicable.strip()):
            stated = (
                "both a capacity and a reason it does not apply"
                if self.capacity
                else "neither a capacity nor a reason"
            )
            raise _refuse(
                f"mode {self.mode.value} states {stated}; a mode either has a value or "
                f"has a reason it has none",
                subject="capacity and not_applicable",
                source="the yield mode's own applicability",
            )
        if self.capacity is not None and (
            not isfinite(self.capacity.magnitude) or self.capacity.magnitude <= 0
        ):
            raise _refuse(
                f"mode {self.mode.value} computed a capacity of {self.capacity}; a yield "
                f"capacity is a positive finite force",
                subject="capacity",
                source="the yield equations and the connection they were given",
            )
        return self

    def __str__(self) -> str:
        if self.capacity is None:
            return f"{self.mode.value}: does not apply — {self.not_applicable}"
        return f"{self.mode.value}: {self.capacity} — {self.mode.description}"


class DowelYield(StatableModel):
    """Every yield mode of one connection, and the one that governs.

    ``capacity`` is the **unreduced** 5% offset yield value TR12 calls ``P``. The NDS's
    reference design value ``Z`` is that divided by a reduction term per mode, and those
    terms are a copyrighted table this library does not carry: divide by the term the
    document declares, with its citation.
    """

    model_config = ConfigDict(frozen=True)

    modes: tuple[ModeCapacity, ...]
    citation: Provenance = TR12_CITATION

    @model_validator(mode="after")
    def _every_mode_once(self) -> DowelYield:
        seen = [entry.mode for entry in self.modes]
        if len(set(seen)) != len(seen) or set(seen) != set(YieldMode):
            raise _refuse(
                f"a yield result states {sorted(m.value for m in seen)}; it states all six "
                f"modes, each once, because a mode left out reads as one that did not "
                f"govern rather than one nobody computed",
                subject="modes",
                source="the six modes of the yield limit equations",
            )
        if not any(entry.capacity is not None for entry in self.modes):
            raise _refuse(
                "no yield mode applies to this connection, so there is no capacity to "
                "report; a result of nothing is not a result",
                subject="modes",
                source="the connection's shear planes and geometry",
            )
        return self

    @property
    def governing(self) -> ModeCapacity:
        """The mode with the least capacity — which is the connection's capacity."""
        return min(
            (entry for entry in self.modes if entry.capacity is not None),
            key=lambda entry: entry.capacity.to("lbf").magnitude,  # type: ignore[union-attr]
        )

    @property
    def capacity(self) -> Quantity:
        """The unreduced 5% offset yield value: the least of the applicable modes."""
        return self.governing.capacity  # type: ignore[return-value]

    def of(self, mode: YieldMode) -> ModeCapacity:
        """One mode's result, by name."""
        return next(entry for entry in self.modes if entry.mode is mode)

    def __str__(self) -> str:
        return (
            f"{self.capacity} by mode {self.governing.mode.value} "
            f"({self.governing.mode.description}); unreduced 5% offset yield, "
            f"{self.citation}"
        )


def _positive_root(a: float, b: float, c: float, *, double: bool) -> float | None:
    """The yield equations' quadratic: ``(−B + √(B² − 4AC)) / (2A)``, or ``/A`` doubled.

    The sign is the one thing a reader of TR12's Table 1-1 gets wrong, because the
    table's layout puts the leading minus where a line break hides it. With a positive
    ``B`` and the negative ``C`` every mode has, ``(+B + √…)`` gives a number about six
    times too large — large enough to look like a capacity and not like an error. Every
    value of TR12's own Example 3.1 is reproduced by the form below and by no other.
    """
    discriminant = b * b - 4.0 * a * c
    if discriminant < 0.0 or a <= 0.0:
        return None
    root = (-b + sqrt(discriminant)) / ((1.0 if double else 2.0) * a)
    return root if root > 0.0 else None


def dowel_yield_capacity(connection: DowelConnection) -> DowelYield:
    """Every yield mode of a dowel connection, by the AWC TR12 Table 1-1 equations.

    These are the NDS yield limit equations in their published generalized form.

    Returns the unreduced 5% offset yield value per mode. Modes II and IIIm are reported
    as not applicable on a double-shear connection, with the reason, rather than omitted.
    """
    if not isinstance(connection, DowelConnection):
        raise _refuse(
            f"connection is a DowelConnection; got {type(connection).__name__}. Build "
            f"one from the fastener and the two members, and the yield equations read "
            f"their resistances off it",
            subject="connection",
        )
    double = connection.shear_planes is ShearPlanes.DOUBLE
    qm, qs = connection.main_resistance, connection.side_resistance
    lm = connection.main_bearing_length.to("inch").magnitude
    ls = connection.side_bearing_length.to("inch").magnitude
    gap = 0.0 if connection.gap is None else connection.gap.to("inch").magnitude
    moment = connection.dowel_moment

    def pounds(value: float | None) -> Quantity | None:
        return None if value is None else Quantity(magnitude=value, unit="lbf")

    # Modes Im and Is are a bearing resistance times a bearing length, and the double
    # shear case doubles the side members because there are two of them.
    found: list[ModeCapacity] = [
        ModeCapacity(mode=YieldMode.IM, capacity=pounds(qm * lm)),
        ModeCapacity(mode=YieldMode.IS, capacity=pounds((2.0 if double else 1.0) * qs * ls)),
    ]
    unreachable = (
        "a double-shear connection is symmetric about its main member, so the rotation "
        "this mode describes cannot happen (AWC TR12 Table 1-1, footnote 1)"
    )
    quadratics = (
        (
            YieldMode.II,
            1.0 / (4.0 * qs) + 1.0 / (4.0 * qm),
            ls / 2.0 + gap + lm / 2.0,
            -qs * ls * ls / 4.0 - qm * lm * lm / 4.0,
        ),
        (
            YieldMode.IIIM,
            1.0 / (2.0 * qs) + 1.0 / (4.0 * qm),
            gap + lm / 2.0,
            -moment - qm * lm * lm / 4.0,
        ),
        (
            YieldMode.IIIS,
            1.0 / (4.0 * qs) + 1.0 / (2.0 * qm),
            ls / 2.0 + gap,
            -qs * ls * ls / 4.0 - moment,
        ),
        (YieldMode.IV, 1.0 / (2.0 * qs) + 1.0 / (2.0 * qm), gap, -moment - moment),
    )
    for mode, a, b, c in quadratics:
        if double and mode not in DOUBLE_SHEAR_MODES:
            found.append(ModeCapacity(mode=mode, not_applicable=unreachable))
            continue
        value = _positive_root(a, b, c, double=double)
        if value is None:
            found.append(
                ModeCapacity(
                    mode=mode,
                    not_applicable=(
                        "the mode's quadratic has no positive root for this connection, so "
                        "the mechanism it describes does not form"
                    ),
                )
            )
            continue
        found.append(ModeCapacity(mode=mode, capacity=pounds(value)))
    return DowelYield(modes=tuple(found))


def dowel_bearing_strength(
    *, specific_gravity: float, diameter: Quantity, perpendicular: bool = False
) -> Quantity:
    """Dowel bearing strength from the cited formula, for a fastener of ``diameter``.

    Three formulas, each from AWC TR12 Appendix A Table A1, which reprints them from NDS
    Table 12.3.3. A **formula** and not a table: these are what a caller computes a
    bearing strength from when they have a specific gravity and no tabulated value, and
    a tabulated value the caller does have is the better input.

    - ``D ≥ ¼ in``, parallel to grain: ``11,200 G``
    - ``D ≥ ¼ in``, perpendicular: ``6,100 G^1.45 / √D``
    - ``D < ¼ in``, either direction: ``16,600 G^1.84`` — the small-dowel formula has no
      direction, which is why ``perpendicular`` changes nothing below the quarter inch.
    """
    # `perpendicular` reads as a flag, and a flag read by truthiness accepts anything: a
    # string, a list, a NaN. `"no"` is truthy, so the caller who writes it gets the
    # perpendicular formula and the opposite of what they asked for.
    if not isinstance(perpendicular, bool):
        raise _refuse(
            f"perpendicular is True or False, not {type(perpendicular).__name__}; got "
            f"{perpendicular!r}. It selects which of the two formulas is read, and a "
            f"value read for its truth would select one silently",
            subject="perpendicular",
            source="the direction the load acts relative to the member's grain",
        )
    if isinstance(specific_gravity, Quantity) or not isinstance(specific_gravity, (int, float)):
        raise _refuse(
            f"specific_gravity is a plain ratio, not a quantity; got {specific_gravity!r}",
            subject="specific_gravity",
            source="the species' specific gravity, from the design document",
        )
    diameter = _dimensioned(
        diameter, name="diameter", dimension="[length]", source=BEARING_FORMULA_CITATION
    )
    if not (isfinite(specific_gravity) and 0.0 < specific_gravity < 1.5):
        raise _refuse(
            f"a specific gravity is between 0 and 1.5; got {specific_gravity}",
            subject="specific_gravity",
            source="the species' specific gravity, from the design document",
        )
    if diameter.magnitude <= 0:
        raise _refuse(
            f"diameter is a positive length; got {diameter}",
            subject="diameter",
            source=BEARING_FORMULA_CITATION,
        )
    inches = diameter.to("inch").magnitude
    if inches < 0.25:
        return Quantity(magnitude=16600.0 * specific_gravity**1.84, unit="psi")
    if perpendicular:
        return Quantity(magnitude=6100.0 * specific_gravity**1.45 / sqrt(inches), unit="psi")
    return Quantity(magnitude=11200.0 * specific_gravity, unit="psi")


def hankinson_bearing_strength(
    *, parallel: Quantity, perpendicular: Quantity, angle: Quantity
) -> Quantity:
    """The bearing strength at an angle to the grain, by the Hankinson formula.

    The NDS gives this as its dowel bearing strength at an angle to grain.

    ``F_eθ = F_e∥ · F_e⊥ / (F_e∥ sin²θ + F_e⊥ cos²θ)``. At zero it is the parallel
    value and at ninety the perpendicular one, and a caller who hands the yield
    equations an unresolved pair has handed them the wrong number for every angle
    between.
    """
    where = "the member's dowel bearing strength in that direction"
    for value, name in ((parallel, "parallel"), (perpendicular, "perpendicular")):
        value = _dimensioned(value, name=name, dimension="[pressure]", source=where)
        if value.magnitude <= 0:
            raise _refuse(f"{name} is a positive stress; got {value}", subject=name, source=where)
    if not isinstance(angle, Quantity):
        raise _refuse(
            f"angle is a Quantity, not a bare number; got {angle!r}. Write it with its "
            f'unit — Quantity.parse("30 degree") — because degrees and radians read '
            f"the same as a bare number and differ by a factor of 57",
            subject="angle",
            source="the angle between the load and the grain",
        )
    if str(angle.pint.dimensionality) != "dimensionless":
        raise _refuse(
            f"angle is an angle; got {angle.dimensionality}",
            subject="angle",
            source="the angle between the load and the grain",
        )
    degrees = angle.to("degree").magnitude
    if not 0.0 <= degrees <= 90.0:
        raise _refuse(
            f"a load-to-grain angle is between 0 and 90 degrees; got {degrees:g}. Past "
            f"ninety the formula reflects, and a caller writing 120 means 60",
            subject="angle",
            source="the angle between the load and the grain",
        )
    theta = radians(degrees)
    para = parallel.to("psi").magnitude
    perp = perpendicular.to("psi").magnitude
    denominator = para * sin(theta) ** 2 + perp * cos(theta) ** 2
    return Quantity(magnitude=para * perp / denominator, unit="psi")
