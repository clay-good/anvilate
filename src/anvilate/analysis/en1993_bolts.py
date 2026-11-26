"""T1 Eurocode 3 bolted connections: EN 1993-1-8 §3, by category.

A bolted shear connection is designed in one of **five declared categories**, and the
category is not a property of the bolts — it is a decision about what the connection is
allowed to do. Category A lets the plies slip into bearing and checks shear and bearing.
Categories B and C preload the bolts and forbid slip, B at the serviceability limit state
and C at the ultimate one. D and E are tension connections, E preloaded. The checks each
category requires are different, so a connection "checked to EN 1993-1-8" without its
category named has not been checked against anything in particular; :class:`BoltCategory`
is a required argument and :func:`category_requirements` says what each one asks for.

**Slip resistance reads a declared slip factor.**

    F_p,C  = 0,7·A_s·f_ub                                            (Eq. 3.7)
    F_s,Rd = k_s·n·μ·F_p,C/γ_M3                                      (Eq. 3.6)

μ is the slip factor of the **friction surface**, not of the bolt: EN 1993-1-8 Table 3.7
gives four classes from 0,5 down to 0,2, and the standard's own wording is that it comes
from tests on the surface or from that table. A connection whose surface preparation is not
stated has no μ, so :class:`FrictionClass` is a declaration too, and the four classes are
bundled with the table they were read from. k_s depends on the hole, not the surface
(Table 3.6), and n is the number of friction surfaces.

Under tension the preload is relieved, and the two slip-resistant categories subtract it at
their own limit state — 0,8·F_t,Ed,ser for category B and 0,8·F_t,Ed for category C.

**The bearing resistance is the one with the geometry in it.**

    F_b,Rd = k_1·α_b·f_u·d·t/γ_M2
    α_b    = min(α_d, f_ub/f_u, 1,0),  α_d = e_1/(3d_0) end, p_1/(3d_0) − 0,25 inner
    k_1    = min(2,8·e_2/d_0 − 1,7, 2,5)   edge bolts

f_u here is the **plate's** ultimate strength, not the bolt's; both appear in α_b and
swapping them is easy and quiet.

**Three places where the source disagrees with itself**, each recorded rather than
smoothed over, because a pack that silently picked one reading would be asserting a
judgement it never showed:

1. Its worked example prints α_b's middle term as ``600/360`` and evaluates it to 1,176,
   which is 600/**510**. 360 is S235's f_u and the connection is S355, whose 510 the same
   example uses in its net-section check. The printed denominator is the typo; α_b is
   governed by its first term either way.
2. The same example takes α_v = 0,6 for a class **6.8** bolt, where its own Table 2.4 (EN
   1993-1-8 Table 3.4) gives 0,5 for classes 4.8, 5.8, 6.8 and 10.9. This module follows
   the **table**, so :func:`shear_resistance_per_plane` returns 117,6 kN for that bolt where
   the example prints 141,1 kN. The example is not anchored on, and
   ``test_the_worked_example_used_a_shear_factor_its_own_table_refuses`` pins the
   disagreement so it cannot be mistaken for a bug here.
3. The table gives inner-bolt ``k_1`` as ``1,4·e_2/d_0 − 1,7`` while the example applies the
   edge-bolt ``2,8·e_2/d_0 − 1,7`` to its inner bolts. The two cannot both be right, and on
   that connection they differ by a factor of five. So **inner-bolt k_1 is refused** rather
   than guessed: :func:`bearing_factor_k1` serves edge bolts, where table and example agree.

**What is deliberately not here**: the group-of-fasteners rule and the long-joint reduction
β_Lf, which are properties of a *joint* rather than of a bolt and need a bolt layout this
module does not model; and bearing in oversized or slotted holes, which the source gives as
multipliers on a bearing resistance whose inner-bolt half is already refused.

**Source, read rather than recalled.** EN 1993-1-8 is copyrighted and is not bundled. The
categories, both strength tables, Table 3.4's resistances, and the slip factor and k_s
tables are read from
[*Eurocodes: Background and Applications — Design of Steel Buildings*](https://orbi.uliege.be/bitstream/2268/194798/1/Eurocodes%20Background&applications%20design%20of%20steel%20buildings.pdf),
the European Commission JRC report, chapter 2 (F. Wald), §2.1.1 to §2.1.8. The tables were
read as images: the text layer renders μ as a question mark and drops the direction of
every inequality.

**The edition** is EN 1993-1-8:2005. γ_M2 and γ_M3 are nationally determined parameters and,
like every partial factor in this pack, are arguments with no default.
"""

from __future__ import annotations

from enum import StrEnum
from math import isfinite, pi

from ..refusal import RefusalError, Remedy
from ..units import Quantity

__all__ = [
    "BoltCategory",
    "BoltClass",
    "FrictionClass",
    "HoleType",
    "BoltShearPlane",
    "BoltPosition",
    "bolt_strengths",
    "shear_factor",
    "category_requirements",
    "shear_resistance_per_plane",
    "bearing_factor_alpha_b",
    "bearing_factor_k1",
    "bearing_resistance",
    "bolt_tension_resistance",
    "punching_shear_resistance",
    "combined_shear_and_tension",
    "preload_force",
    "slip_factor",
    "slip_resistance",
]

_BOLT_SOURCE = "the bolt's class, from its marking or the order"
_SURFACE_SOURCE = "the friction surface's preparation, as specified and inspected"
_HOLE_SOURCE = "the hole type on the drawing"
_GEOMETRY_SOURCE = "the connection's bolt layout and plate thicknesses"
_PLATE_SOURCE = "the connected plate's steel grade, at its thickness"
_ANNEX_SOURCE = "the National Annex, or EN 1993-1-8's recommended value where it defers"
_CATEGORY_SOURCE = "the design basis, which states the connection's category"

#: EN 1993-1-8 Table 3.1, as (f_yb, f_ub) in N/mm².
_BOLT_STRENGTHS: dict[str, tuple[float, float]] = {
    "4.6": (240.0, 400.0),
    "4.8": (320.0, 400.0),
    "5.6": (300.0, 500.0),
    "5.8": (400.0, 500.0),
    "6.8": (480.0, 600.0),
    "8.8": (640.0, 800.0),
    "10.9": (900.0, 1000.0),
}

#: Table 3.4: α_v where the shear plane passes through the THREAD. Through the shank it is
#: 0,6 for every class, which is why this table only covers the threaded case.
_SHEAR_FACTOR_THREADED: dict[str, float] = {
    "4.6": 0.6, "5.6": 0.6, "8.8": 0.6,
    "4.8": 0.5, "5.8": 0.5, "6.8": 0.5, "10.9": 0.5,
}  # fmt: skip
_SHEAR_FACTOR_SHANK = 0.6

#: Table 3.7, the slip factor by class of friction surface.
_SLIP_FACTORS: dict[str, float] = {"A": 0.5, "B": 0.4, "C": 0.3, "D": 0.2}

#: Table 3.6, k_s by hole type.
_HOLE_FACTORS: dict[str, float] = {
    "normal": 1.00,
    "oversized or short slot perpendicular": 0.85,
    "long slot perpendicular": 0.70,
    "short slot parallel": 0.76,
    "long slot parallel": 0.63,
}

#: Table 3.4's cap on k_1, and the coefficient for an edge bolt.
_K1_CAP, _K1_EDGE_SLOPE, _K1_OFFSET = 2.5, 2.8, 1.7
#: Eq. 3.7's share of the bolt's tensile strength taken as preload.
_PRELOAD_SHARE = 0.7
#: The share of an applied tension that relieves the preload in Eqs. 3.8 and 3.9.
_TENSION_RELIEF = 0.8
#: Table 3.4's k_2, ordinary and countersunk.
_TENSION_FACTOR, _TENSION_FACTOR_COUNTERSUNK = 0.9, 0.63
#: Table 3.4's combined shear-and-tension denominator.
_COMBINED_TENSION_DIVISOR = 1.4


class _En1993BoltInputError(RefusalError, ValueError):
    """An EN 1993-1-8 bolt input that cannot be used without correction."""


def _refuse(message: str, *, subject: str, source: str) -> _En1993BoltInputError:
    return _En1993BoltInputError(
        message, remedies=(Remedy(action="replace", subject=subject, source=source),)
    )


class BoltClass(StrEnum):
    """The seven bolt classes EN 1993-1-8 covers, named as the standard writes them."""

    C4_6 = "4.6"
    C4_8 = "4.8"
    C5_6 = "5.6"
    C5_8 = "5.8"
    C6_8 = "6.8"
    C8_8 = "8.8"
    C10_9 = "10.9"


class FrictionClass(StrEnum):
    """The class of a friction surface, which is what a slip factor belongs to.

    Not a property of the bolt and not derivable from anything else in a connection: it is
    the surface's preparation, and EN 1993-1-8 expects it from tests or from Table 3.7.
    """

    A = "A"
    B = "B"
    C = "C"
    D = "D"


class HoleType(StrEnum):
    """The hole, which sets k_s in the slip resistance (EN 1993-1-8 Table 3.6)."""

    NORMAL = "normal"
    OVERSIZED_OR_SHORT_SLOT_PERPENDICULAR = "oversized or short slot perpendicular"
    LONG_SLOT_PERPENDICULAR = "long slot perpendicular"
    SHORT_SLOT_PARALLEL = "short slot parallel"
    LONG_SLOT_PARALLEL = "long slot parallel"


class BoltShearPlane(StrEnum):
    """Whether the shear plane crosses the thread or the shank (EN 1993-1-8 Table 3.4)."""

    THREADED = "threaded"
    SHANK = "shank"


class BoltPosition(StrEnum):
    """An end/inner bolt for α_b, an edge/inner bolt for k_1 (EN 1993-1-8 Table 3.4)."""

    END = "end"
    INNER = "inner"


class BoltCategory(StrEnum):
    """EN 1993-1-8 Table 3.2's five categories of bolted connection.

    A, B and C are loaded in shear; D and E in tension. The category decides which checks
    the connection must pass, which is why it is declared rather than inferred.
    """

    A_BEARING = "A"
    B_SLIP_RESISTANT_AT_SERVICEABILITY = "B"
    C_SLIP_RESISTANT_AT_ULTIMATE = "C"
    D_NON_PRELOADED_TENSION = "D"
    E_PRELOADED_TENSION = "E"


_CATEGORY_REQUIREMENTS: dict[str, tuple[str, ...]] = {
    "A": ("shear", "bearing"),
    "B": ("slip at serviceability", "shear", "bearing"),
    "C": ("slip at ultimate", "bearing", "net section"),
    "D": ("tension", "punching shear"),
    "E": ("tension", "punching shear"),
}
#: Which categories require a preloaded bolt, and so a class 8.8 or 10.9 one.
_PRELOADED = ("B", "C", "E")
_PRELOADABLE_CLASSES = (BoltClass.C8_8, BoltClass.C10_9)


def _finite(value: object, name: str, *, source: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise _refuse(f"{name} must be a number; got {value!r}", subject=name, source=source)
    number = float(value)
    if not isfinite(number):
        raise _refuse(f"{name} must be finite; got {number}", subject=name, source=source)
    return number


def _length(value: object, name: str, *, source: str = _GEOMETRY_SOURCE) -> float:
    if not isinstance(value, Quantity) or not value.has_dimension("[length]"):
        raise _refuse(
            f"{name} must be a [length] quantity; got {value!r}", subject=name, source=source
        )
    magnitude = value.to("mm").magnitude
    if not isfinite(magnitude):
        raise _refuse(f"{name} must be finite; got {value}", subject=name, source=source)
    if magnitude <= 0:
        raise _refuse(f"{name} must be positive; got {value}", subject=name, source=source)
    return magnitude


def _stress(value: object, name: str, *, source: str) -> float:
    if not isinstance(value, Quantity) or not value.has_dimension("[pressure]"):
        raise _refuse(
            f"{name} must be a stress quantity; got {value!r}", subject=name, source=source
        )
    magnitude = value.to("MPa").magnitude
    if not isfinite(magnitude):
        raise _refuse(f"{name} must be finite; got {value}", subject=name, source=source)
    if magnitude <= 0:
        raise _refuse(f"{name} must be positive; got {value}", subject=name, source=source)
    return magnitude


def _force(value: object, name: str, *, source: str, allow_zero: bool = False) -> float:
    if not isinstance(value, Quantity) or not value.has_dimension("[force]"):
        raise _refuse(
            f"{name} must be a [force] quantity; got {value!r}", subject=name, source=source
        )
    magnitude = value.to("N").magnitude
    if not isfinite(magnitude):
        raise _refuse(f"{name} must be finite; got {value}", subject=name, source=source)
    if magnitude < 0 or (magnitude == 0 and not allow_zero):
        raise _refuse(f"{name} must be positive; got {value}", subject=name, source=source)
    return magnitude


def _area(value: object, name: str) -> float:
    if not isinstance(value, Quantity) or not value.has_dimension("[area]"):
        raise _refuse(
            f"{name} must be an [area] quantity; got {value!r}",
            subject=name,
            source=_BOLT_SOURCE,
        )
    magnitude = value.to("mm^2").magnitude
    if not isfinite(magnitude) or magnitude <= 0:
        raise _refuse(
            f"{name} must be finite and positive; got {value}",
            subject=name,
            source=_BOLT_SOURCE,
        )
    return magnitude


def _partial_factor(value: object, name: str) -> float:
    gamma = _finite(value, name, source=_ANNEX_SOURCE)
    if gamma < 1.0:
        raise _refuse(
            f"{name} must be at least 1; got {gamma}. A factor below 1 raises a resistance "
            "above its characteristic value",
            subject=name,
            source=_ANNEX_SOURCE,
        )
    return gamma


def _member(value: object, kind: type, name: str, *, source: str):
    if not isinstance(value, kind):
        raise _refuse(
            f"{name} must be a {kind.__name__}; got {value!r}", subject=name, source=source
        )
    return value


def bolt_strengths(*, bolt_class: BoltClass) -> tuple[Quantity, Quantity]:
    """(f_yb, f_ub) for a bolt class, from EN 1993-1-8 Table 3.1.

    Both are returned because a connection uses each: f_ub sets the bolt's own resistances
    and its preload, and f_yb is what an anchor bolt's limits in §3.1 are written against.
    """
    chosen = _member(bolt_class, BoltClass, "bolt_class", source=_BOLT_SOURCE)
    yield_strength, ultimate = _BOLT_STRENGTHS[chosen.value]
    return (
        Quantity(magnitude=yield_strength, unit="MPa"),
        Quantity(magnitude=ultimate, unit="MPa"),
    )


def shear_factor(*, bolt_class: BoltClass, plane: BoltShearPlane) -> float:
    """α_v, the shear factor of EN 1993-1-8 Table 3.4.

    Through the **shank** it is 0,6 for every class. Through the **thread** it is 0,6 for
    classes 4.6, 5.6 and 8.8 and 0,5 for 4.8, 5.8, 6.8 and 10.9 — the higher-ductility
    classes keep the larger factor, and the pattern is not monotonic in strength, so it is
    bundled as a table rather than as a rule about class numbers.

    The source's own worked example takes 0,6 for a class 6.8 bolt, which this table
    refuses; see the module docstring.
    """
    chosen = _member(bolt_class, BoltClass, "bolt_class", source=_BOLT_SOURCE)
    where = _member(plane, BoltShearPlane, "plane", source=_GEOMETRY_SOURCE)
    if where is BoltShearPlane.SHANK:
        return _SHEAR_FACTOR_SHANK
    return _SHEAR_FACTOR_THREADED[chosen.value]


def category_requirements(*, category: BoltCategory) -> tuple[str, ...]:
    """Which checks EN 1993-1-8 Table 3.2 requires of a connection in this category.

    Returned as names rather than run, because the checks need inputs this function is not
    given — the point is that the *set* differs by category, and a caller that screens a
    category B connection for shear and bearing alone has skipped the one check that makes
    it category B.
    """
    chosen = _member(category, BoltCategory, "category", source=_CATEGORY_SOURCE)
    return _CATEGORY_REQUIREMENTS[chosen.value]


def shear_resistance_per_plane(
    *,
    bolt_class: BoltClass,
    plane: BoltShearPlane,
    stress_area: Quantity,
    partial_factor_m2: float,
) -> Quantity:
    """F_v,Rd for ONE shear plane (EN 1993-1-8 Table 3.4): α_v·A·f_ub/γ_M2.

    ``stress_area`` is the bolt's tensile stress area A_s where the plane crosses the
    thread, and its gross shank area where it does not. Per plane, so a connection in double
    shear multiplies by two — done by the caller, because the number of planes is a property
    of the joint's geometry rather than of the bolt.
    """
    _, ultimate = bolt_strengths(bolt_class=bolt_class)
    alpha_v = shear_factor(bolt_class=bolt_class, plane=plane)
    area = _area(stress_area, "stress_area")
    gamma = _partial_factor(partial_factor_m2, "partial_factor_m2")
    newtons = alpha_v * area * ultimate.magnitude / gamma
    return Quantity(magnitude=newtons, unit="N").to("kN")


def bearing_factor_alpha_b(
    *,
    position: BoltPosition,
    spacing: Quantity,
    hole_diameter: Quantity,
    bolt_ultimate_strength: Quantity,
    plate_ultimate_strength: Quantity,
) -> float:
    """α_b = min(α_d, f_ub/f_u, 1,0), in the direction of load transfer
    (EN 1993-1-8 Table 3.4).

    ``spacing`` is the end distance e_1 for an end bolt and the pitch p_1 for an inner one,
    which take different α_d expressions — e_1/(3d_0) and p_1/(3d_0) − 0,25.

    The two ultimate strengths are **different materials** and the ratio is the bolt's over
    the plate's. Swapping them is quiet. On the source's own connection it would not even
    show: the ratio is 1,176 the right way up and 0,85 inverted, and α_d is 0,606 and 0,811
    at the two bolt positions, so the first term governs either way. It shows on a connection
    with generous spacing — an inverted ratio caps α_b at 0,85 where it should reach 1,0,
    understating the bearing resistance by up to 15% on exactly the connections that had
    room to spare. That is the shape of the error worth guarding: invisible on the example
    that would be used to check it.
    """
    where = _member(position, BoltPosition, "position", source=_GEOMETRY_SOURCE)
    pitch = _length(spacing, "spacing")
    hole = _length(hole_diameter, "hole_diameter")
    bolt_fu = _stress(bolt_ultimate_strength, "bolt_ultimate_strength", source=_BOLT_SOURCE)
    plate_fu = _stress(plate_ultimate_strength, "plate_ultimate_strength", source=_PLATE_SOURCE)
    alpha_d = pitch / (3.0 * hole)
    if where is BoltPosition.INNER:
        alpha_d -= 0.25
    if alpha_d <= 0:
        raise _refuse(
            f"the spacing {spacing} gives a non-positive alpha_d against a hole of "
            f"{hole_diameter}; an inner bolt needs p_1 greater than three quarters of a hole "
            "diameter before it bears at all",
            subject="spacing",
            source=_GEOMETRY_SOURCE,
        )
    return min(alpha_d, bolt_fu / plate_fu, 1.0)


def bearing_factor_k1(
    *, position: BoltPosition, edge_distance: Quantity, hole_diameter: Quantity
) -> float:
    """k_1 = min(2,8·e_2/d_0 − 1,7, 2,5) for an **edge** bolt (EN 1993-1-8 Table 3.4).

    ``position`` must be :attr:`BoltPosition.END`. The inner-bolt expression is **refused**:
    the source prints it as 1,4·e_2/d_0 − 1,7 in its table and then applies the edge-bolt
    2,8·e_2/d_0 − 1,7 to the inner bolts of its own worked example, and on that connection
    the two differ by a factor of five — 0,53 against the capped 2,5. Only one can be right
    and the source does not say which, so neither is shipped under a guess.
    """
    where = _member(position, BoltPosition, "position", source=_GEOMETRY_SOURCE)
    if where is BoltPosition.INNER:
        raise _refuse(
            "k_1 for an inner bolt is not carried: the source gives it as 1,4·e_2/d_0 - 1,7 "
            "in its table and applies the edge-bolt 2,8·e_2/d_0 - 1,7 in its own worked "
            "example, and the two differ by a factor of five. An edge bolt, where the table "
            "and the example agree, is BoltPosition.END",
            subject="position",
            source=_GEOMETRY_SOURCE,
        )
    edge = _length(edge_distance, "edge_distance")
    hole = _length(hole_diameter, "hole_diameter")
    return min(_K1_EDGE_SLOPE * edge / hole - _K1_OFFSET, _K1_CAP)


def bearing_resistance(
    *,
    factor_k1: float,
    factor_alpha_b: float,
    plate_ultimate_strength: Quantity,
    bolt_diameter: Quantity,
    plate_thickness: Quantity,
    partial_factor_m2: float,
) -> Quantity:
    """F_b,Rd = k_1·α_b·f_u·d·t/γ_M2 (EN 1993-1-8 Table 3.4).

    ``f_u`` is the **plate's**, and ``d`` the bolt's nominal diameter rather than the hole's
    — the bolt bears on the plate over its own width.
    """
    k_1 = _finite(factor_k1, "factor_k1", source=_GEOMETRY_SOURCE)
    alpha_b = _finite(factor_alpha_b, "factor_alpha_b", source=_GEOMETRY_SOURCE)
    for name, value in (("factor_k1", k_1), ("factor_alpha_b", alpha_b)):
        if value <= 0:
            raise _refuse(
                f"{name} must be positive; got {value}",
                subject=name,
                source=_GEOMETRY_SOURCE,
            )
    if alpha_b > 1.0:
        raise _refuse(
            f"factor_alpha_b is capped at 1,0 by Table 3.4; got {alpha_b}",
            subject="factor_alpha_b",
            source=_GEOMETRY_SOURCE,
        )
    if k_1 > _K1_CAP:
        raise _refuse(
            f"factor_k1 is capped at {_K1_CAP} by Table 3.4; got {k_1}",
            subject="factor_k1",
            source=_GEOMETRY_SOURCE,
        )
    plate_fu = _stress(plate_ultimate_strength, "plate_ultimate_strength", source=_PLATE_SOURCE)
    diameter = _length(bolt_diameter, "bolt_diameter")
    thickness = _length(plate_thickness, "plate_thickness")
    gamma = _partial_factor(partial_factor_m2, "partial_factor_m2")
    newtons = k_1 * alpha_b * plate_fu * diameter * thickness / gamma
    return Quantity(magnitude=newtons, unit="N").to("kN")


def bolt_tension_resistance(
    *,
    bolt_class: BoltClass,
    stress_area: Quantity,
    partial_factor_m2: float,
    countersunk: bool = False,
) -> Quantity:
    """F_t,Rd = k_2·A_s·f_ub/γ_M2, k_2 = 0,9 or 0,63 countersunk (EN 1993-1-8 Table 3.4)."""
    _, ultimate = bolt_strengths(bolt_class=bolt_class)
    if not isinstance(countersunk, bool):
        raise _refuse(
            f"countersunk must be True or False; got {countersunk!r}",
            subject="countersunk",
            source=_GEOMETRY_SOURCE,
        )
    k_2 = _TENSION_FACTOR_COUNTERSUNK if countersunk else _TENSION_FACTOR
    area = _area(stress_area, "stress_area")
    gamma = _partial_factor(partial_factor_m2, "partial_factor_m2")
    newtons = k_2 * area * ultimate.magnitude / gamma
    return Quantity(magnitude=newtons, unit="N").to("kN")


def punching_shear_resistance(
    *,
    mean_head_diameter: Quantity,
    plate_thickness: Quantity,
    plate_ultimate_strength: Quantity,
    partial_factor_m2: float,
) -> Quantity:
    """B_p,Rd = 0,6·π·d_m·t_p·f_u/γ_M2 (EN 1993-1-8 Table 3.4): the head pulling through.

    ``d_m`` is the mean of the head's across-points and across-flats dimensions, which is
    the standard's own definition and is not the nominal bolt diameter.
    """
    head = _length(mean_head_diameter, "mean_head_diameter", source=_BOLT_SOURCE)
    thickness = _length(plate_thickness, "plate_thickness")
    plate_fu = _stress(plate_ultimate_strength, "plate_ultimate_strength", source=_PLATE_SOURCE)
    gamma = _partial_factor(partial_factor_m2, "partial_factor_m2")
    newtons = 0.6 * pi * head * thickness * plate_fu / gamma
    return Quantity(magnitude=newtons, unit="N").to("kN")


def combined_shear_and_tension(
    *,
    applied_shear: Quantity,
    shear_resistance: Quantity,
    applied_tension: Quantity,
    tension_resistance_value: Quantity,
) -> float:
    """F_v,Ed/F_v,Rd + F_t,Ed/(1,4·F_t,Rd), which EN 1993-1-8 Table 3.4 holds at or below 1.

    The 1,4 sits under the **tension** term only, so the two halves are not symmetric: a
    bolt can carry rather more tension alongside its shear than a linear interaction would
    allow. Returned as the utilisation rather than a verdict, so a caller sees the margin.
    """
    shear_applied = _force(applied_shear, "applied_shear", source=_GEOMETRY_SOURCE,
                           allow_zero=True)  # fmt: skip
    shear_capacity = _force(shear_resistance, "shear_resistance", source=_BOLT_SOURCE)
    tension_applied = _force(applied_tension, "applied_tension", source=_GEOMETRY_SOURCE,
                             allow_zero=True)  # fmt: skip
    tension_capacity = _force(
        tension_resistance_value, "tension_resistance_value", source=_BOLT_SOURCE
    )
    return shear_applied / shear_capacity + tension_applied / (
        _COMBINED_TENSION_DIVISOR * tension_capacity
    )


def preload_force(*, bolt_class: BoltClass, stress_area: Quantity) -> Quantity:
    """F_p,C = 0,7·A_s·f_ub (EN 1993-1-8 Eq. 3.7), the controlled preload.

    Only classes 8.8 and 10.9 are preloaded, and this refuses the others rather than
    returning a number for a bolt that is never tightened to it — a preload on a class 4.6
    bolt is not a conservative answer, it is a connection that does not exist.
    """
    chosen = _member(bolt_class, BoltClass, "bolt_class", source=_BOLT_SOURCE)
    if chosen not in _PRELOADABLE_CLASSES:
        raise _refuse(
            f"class {chosen.value} bolts are not preloaded; EN 1993-1-8 gives the controlled "
            "preload for classes 8.8 and 10.9 only, and a slip-resistant connection uses "
            "one of those",
            subject="bolt_class",
            source=_BOLT_SOURCE,
        )
    _, ultimate = bolt_strengths(bolt_class=chosen)
    area = _area(stress_area, "stress_area")
    newtons = _PRELOAD_SHARE * area * ultimate.magnitude
    return Quantity(magnitude=newtons, unit="N").to("kN")


def slip_factor(*, friction_class: FrictionClass) -> float:
    """μ from EN 1993-1-8 Table 3.7: 0,5, 0,4, 0,3 and 0,2 for classes A to D.

    A property of the **surface preparation**, not of the bolt or the plate grade. The
    standard's own alternative is a test on the actual surface, so a project with a treatment
    that is not one of these four has a measured μ and passes it to
    :func:`slip_resistance` directly.
    """
    chosen = _member(friction_class, FrictionClass, "friction_class", source=_SURFACE_SOURCE)
    return _SLIP_FACTORS[chosen.value]


def slip_resistance(
    *,
    category: BoltCategory,
    preload: Quantity,
    slip_factor_value: float,
    friction_surfaces: int,
    hole: HoleType,
    partial_factor_m3: float,
    applied_tension: Quantity | None = None,
) -> Quantity:
    """F_s,Rd = k_s·n·μ·F_p,C/γ_M3 (EN 1993-1-8 Eq. 3.6), less any applied tension.

    Only categories B and C are slip-resistant, and they differ in *which* limit state the
    check is made at — B at serviceability and C at ultimate. That is not a detail this can
    absorb: the applied tension belongs to the matching limit state, so the category is
    required and any other one refuses rather than returning a resistance for a connection
    that has no slip check.

    ``applied_tension`` relieves the preload at 0,8 per Eqs. 3.8 and 3.9 and must be the
    tension at the category's own limit state — F_t,Ed,ser for B and F_t,Ed for C.

    ``slip_factor_value`` is μ, from :func:`slip_factor` or from a test on the surface.
    """
    chosen = _member(category, BoltCategory, "category", source=_CATEGORY_SOURCE)
    if chosen.value not in ("B", "C"):
        raise _refuse(
            f"category {chosen.value} is not slip-resistant, so it has no slip resistance; "
            "EN 1993-1-8 gives the check for categories B and C, which preload their bolts",
            subject="category",
            source=_CATEGORY_SOURCE,
        )
    where = _member(hole, HoleType, "hole", source=_HOLE_SOURCE)
    k_s = _HOLE_FACTORS[where.value]
    mu = _finite(slip_factor_value, "slip_factor_value", source=_SURFACE_SOURCE)
    if not 0.0 < mu <= 1.0:
        raise _refuse(
            f"slip_factor_value is a coefficient of friction and lies in (0, 1]; got {mu}",
            subject="slip_factor_value",
            source=_SURFACE_SOURCE,
        )
    if isinstance(friction_surfaces, bool) or not isinstance(friction_surfaces, int):
        raise _refuse(
            f"friction_surfaces must be a whole number; got {friction_surfaces!r}",
            subject="friction_surfaces",
            source=_GEOMETRY_SOURCE,
        )
    if friction_surfaces < 1:
        raise _refuse(
            f"friction_surfaces must be at least 1; got {friction_surfaces}. A connection "
            "with no friction surface cannot be slip-resistant",
            subject="friction_surfaces",
            source=_GEOMETRY_SOURCE,
        )
    clamp = _force(preload, "preload", source=_BOLT_SOURCE)
    gamma = _partial_factor(partial_factor_m3, "partial_factor_m3")
    if applied_tension is not None:
        tension = _force(
            applied_tension, "applied_tension", source=_GEOMETRY_SOURCE, allow_zero=True
        )
        clamp -= _TENSION_RELIEF * tension
        if clamp <= 0:
            raise _refuse(
                f"an applied tension of {applied_tension} relieves the whole preload of "
                f"{preload}, so there is no clamping force left and the connection cannot be "
                "slip-resistant",
                subject="applied_tension",
                source=_GEOMETRY_SOURCE,
            )
    newtons = k_s * friction_surfaces * mu * clamp / gamma
    return Quantity(magnitude=newtons, unit="N").to("kN")
