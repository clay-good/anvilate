"""T1 Eurocode 3 cross-section resistance: EN 1993-1-1 §6.2, closed-form.

What a section's class is for. Once
:mod:`~anvilate.analysis.en1993_classification` has given a class, §6.2 turns it into a
resistance: a class 1 or 2 section is worked on its **plastic** capacity, a class 3 one on
its **elastic** capacity, and a class 4 one on the elastic capacity of a reduced effective
section (clause 6.2.1(3)).

The resistances, each as the clause states it:

    tension      N_pl,Rd = A·f_y/γ_M0                                      (6.2.3, Eq. 1.26)
                 N_u,Rd  = 0,9·A_net·f_u/γ_M2                              (6.2.3, Eq. 1.27)
                 N_t,Rd  = the smaller of the two, where there are holes
    compression  N_c,Rd  = A·f_y/γ_M0                                      (6.2.4, Eq. 1.31)
    bending      M_c,Rd  = W·f_y/γ_M0, W by class                      (6.2.5, Eqs. 1.47-49)
    shear        V_pl,Rd = A_v·(f_y/√3)/γ_M0                               (6.2.6, Eq. 1.53)

and the interactions:

    bending and shear   below half of V_pl,Rd, nothing; at or above it, the shear area
                        works at (1−ρ)·f_y with ρ = (2·V_Ed/V_pl,Rd − 1)²       (6.2.8)
                        M_y,V,Rd = (W_pl,y − ρ·A_w²/(4·t_w))·f_y/γ_M0     (6.2.8, Eq. 1.54)
    bending and axial   M_N,y,Rd = M_pl,y,Rd·(1−n)/(1−0,5a), ≤ M_pl,y,Rd  (6.2.9.1, Eq. 1.62)
                        M_N,z,Rd = M_pl,z,Rd                 if n ≤ a     (6.2.9.1, Eq. 1.63)
                        M_N,z,Rd = M_pl,z,Rd·[1−((n−a)/(1−a))²] if n > a  (6.2.9.1, Eq. 1.64)
                        with n = N_Ed/N_pl,Rd and a the area ratio, a ≤ 0,5
    biaxial bending     (M_y,Ed/M_pl,y,Rd)^α + (M_z,Ed/M_pl,z,Rd)^β ≤ 1,0    (6.2.9, Eq. 1.50)

**γ_M0 and γ_M2 are arguments with no defaults.** They are nationally determined
parameters: the standard recommends values and a National Annex may change them, and a
partial factor that defaults silently is the one number in a resistance nobody notices is
wrong. Bundling the recommended values as typed inputs with a cited override is its own
task, and until it exists the factor is stated at every call.

**Source, read rather than recalled.** EN 1993-1-1 is copyrighted and is not bundled. The
equations and clause numbers are read from
[*Eurocodes: Background and Applications — Design of Steel Buildings*](https://orbi.uliege.be/bitstream/2268/194798/1/Eurocodes%20Background&applications%20design%20of%20steel%20buildings.pdf),
the European Commission JRC report, §1.3.2.1 to §1.3.5.1, with its own equation numbers
given above beside the clauses. The equation pages were read as images, because the text
layer drops every γ, ρ, α and √ — see
:mod:`~anvilate.analysis.en1993_classification` for the same precaution on Table 5.2.

**A typo in the source, recorded so nobody "corrects" this module toward it.** The report's
Eq. (1.27) prints ``N_pl,Rd = A·f_y/γ_M0`` — a verbatim repeat of its Eq. (1.26) — where it
means the net-section ultimate resistance. The surrounding sentence names A_net, f_u and
γ_M2, and its own Eq. (1.28) rearranges ``N_u,Rd > N_pl,Rd`` into
``A_net/A > (f_y/0,9f_u)·(γ_M2/γ_M0)``, which is satisfied only by
``N_u,Rd = 0,9·A_net·f_u/γ_M2``. That is what is implemented, and the report's own
inequality is a test.

**What the arithmetic is checked against.** Four worked results from the same report, all
replayed in the tests: an HEB 340's N_c,Rd of 6067,0 kN; and two complete axial-plus-bending
reductions — N_pl,Rd 5726,2 kN with n = 0,30, a = 0,24 and M_N,y,Rd 606,9 kNm from
M_pl,y,Rd 762,9 kNm, and a second whose area ratio comes out 0,55 and is **capped at 0,5**,
giving M_N,y,Rd 81,5 kNm from M_pl,y,Rd 127,4 kNm. The cap is the branch a reader is most
likely to leave out, and the report exercises it.

**The edition** is the 2005 generation with its 2014 amendment, as in the classification
module. Nothing here answers EN 1993-1-1:2022.
"""

from __future__ import annotations

from enum import StrEnum
from math import isfinite, sqrt

from pydantic import ConfigDict

from .._models import Named, Provenance, StatableModel
from ..refusal import RefusalError, Remedy
from ..units import Quantity, render, require_finite
from .en1993_classification import SectionClass

__all__ = [
    "TensionGoverned",
    "TensionResistance",
    "tension_resistance",
    "compression_resistance",
    "bending_resistance",
    "shear_resistance",
    "shear_buckling_check_needed",
    "shear_reduction_rho",
    "bending_resistance_with_shear",
    "axial_reduction_negligible",
    "reduced_plastic_moment_major",
    "reduced_plastic_moment_minor",
    "biaxial_bending_utilisation",
]

_STEEL_SOURCE = "the steel grade's product standard, at the element's thickness"
_SECTION_SOURCE = "the section table or the measured cross-section"
_ANNEX_SOURCE = "the National Annex, or EN 1993-1-1's recommended value where it defers"
_FORCE_SOURCE = "the design forces from the governing load combination"

#: Eq. (1.27)'s coefficient on the net section: the standard's allowance for the
#: stress concentration at a hole, not a partial factor.
_NET_SECTION_COEFFICIENT = 0.9
#: §6.2.8's threshold: below half of V_pl,Rd the bending resistance is not reduced.
_SHEAR_INTERACTION_THRESHOLD = 0.5
#: Clause 6.2.9.1(5): a is capped at 0,5 whatever the flange area works out to.
_MAX_AREA_RATIO = 0.5
#: Clause 6.2.9.1(4), the condition the source states: the reduction may be neglected
#: below a quarter of the plastic axial resistance.
_NEGLIGIBLE_AXIAL_SHARE = 0.25
#: Under Eq. (1.53): the von Mises shear yield, f_y/√3.
_SHEAR_YIELD_DIVISOR = sqrt(3.0)
#: The shear-buckling trigger of §6.2.6: h_w/t_w > 72ε/η.
_SHEAR_BUCKLING_COEFFICIENT = 72.0


class _En1993ResistanceInputError(RefusalError, ValueError):
    """An EN 1993 resistance input that cannot be used without correction."""


def _refuse(message: str, *, subject: str, source: str) -> _En1993ResistanceInputError:
    return _En1993ResistanceInputError(
        message, remedies=(Remedy(action="replace", subject=subject, source=source),)
    )


def _quantity(value: object, dimension: str, name: str, *, source: str) -> float:
    """``value`` as a finite, positive magnitude of ``dimension`` in SI."""
    if not isinstance(value, Quantity):
        raise _refuse(
            f"{name} must be a {dimension} quantity; got {value!r}", subject=name, source=source
        )
    if not value.has_dimension(dimension):
        raise _refuse(
            f"{name} must be a {dimension} quantity; got {value.dimensionality} ({value})",
            subject=name,
            source=source,
        )
    if not isfinite(value.magnitude):
        raise _refuse(f"{name} must be finite; got {value}", subject=name, source=source)
    if value.magnitude <= 0:
        raise _refuse(f"{name} must be positive; got {value}", subject=name, source=source)
    return value.magnitude


def _moment(value: object, dimension: str, name: str) -> float:
    """An applied moment: finite and of ``dimension``, but allowed to be zero.

    :func:`_quantity` refuses a zero, which is right for an area or a strength and wrong
    for an applied moment — a beam-column bent about one axis only has M_z,Ed = 0, and
    Eq. (1.50) is exactly where that is the ordinary case.
    """
    if not isinstance(value, Quantity):
        raise _refuse(
            f"{name} must be a {dimension} quantity; got {value!r}",
            subject=name,
            source=_FORCE_SOURCE,
        )
    if not value.has_dimension(dimension):
        raise _refuse(
            f"{name} must be a {dimension} quantity; got {value.dimensionality} ({value})",
            subject=name,
            source=_FORCE_SOURCE,
        )
    return require_finite(value, name=name)


def _exponent(value: float, name: str) -> float:
    """An interaction exponent: finite and positive, taken positionally so the AST sees it.

    ``base ** nan`` is 1,0 wherever the base is 1,0, so a NaN exponent in Eq. (1.50) returns
    a utilisation of exactly 2,0 for a section at its limits on both axes — a number that
    looks like an ordinary overload rather than a missing input. The guard is this call, and
    it takes ``value`` positionally because the exponent census in
    tests/test_fraction_guards.py resolves one hop through a private helper's positional
    argument and cannot see a parameter handed in through a loop variable.
    """
    require_finite(value, name=name)
    if value <= 0:
        raise _refuse(f"{name} must be positive; got {value}", subject=name, source=_SECTION_SOURCE)
    return float(value)


def _factor(value: float, name: str) -> float:
    """A partial factor: finite and at least 1, since it divides a resistance."""
    require_finite(value, name=name)
    if value < 1.0:
        raise _refuse(
            f"{name} divides a resistance and is at least 1; got {value}. A factor below 1 "
            f"would report more capacity than the characteristic value",
            subject=name,
            source=_ANNEX_SOURCE,
        )
    return float(value)


def _newtons(area_mm2: float, stress_mpa: float, factor: float) -> Quantity:
    """``area·stress/factor`` as a force, with mm² and MPa giving newtons directly."""
    return Quantity(magnitude=area_mm2 * stress_mpa / factor, unit="N")


class TensionGoverned(StrEnum):
    """Which of EN 1993-1-1 §6.2.3's two resistances is smaller, and so the member's."""

    GROSS_SECTION = "gross_section"
    NET_SECTION = "net_section"


class TensionResistance(StatableModel):
    """A member's design tension resistance to EN 1993-1-1 §6.2.3, and what governed it."""

    model_config = ConfigDict(frozen=True)

    states_requirements = True

    resistance: Quantity
    gross_section: Quantity
    net_section: Quantity | None
    governed_by: TensionGoverned
    dissipative_capable: bool
    method: Provenance
    clause: Named

    def __str__(self) -> str:
        applied = render(self.resistance, pretty=True)
        if self.net_section is None:
            return f"N_t,Rd = {applied} on the gross section; no holes declared"
        return f"N_t,Rd = {applied}, governed by the {self.governed_by.value.replace('_', ' ')}"


def tension_resistance(
    *,
    area: Quantity,
    yield_strength: Quantity,
    partial_factor_m0: float,
    net_area: Quantity | None = None,
    ultimate_strength: Quantity | None = None,
    partial_factor_m2: float | None = None,
) -> TensionResistance:
    """The design tension resistance N_t,Rd (EN 1993-1-1 §6.2.3).

    Without holes this is the gross section's plastic resistance A·f_y/γ_M0 alone
    (Eq. 1.26). Declare ``net_area``, ``ultimate_strength`` and ``partial_factor_m2``
    together and the net section's ultimate resistance 0,9·A_net·f_u/γ_M2 is computed too
    (Eq. 1.27), and N_t,Rd is **the smaller of the two** — which is what the clause says and
    what makes a bolted tension member's resistance a question about its holes.

    The three net-section inputs are all-or-nothing: given some and not others this refuses
    rather than falling back to the gross section, because a net-section resistance silently
    not computed is a member reported stronger than the clause allows.

    ``dissipative_capable`` on the result is clause 6.2.3(3): where capacity design needs
    the member to yield before it tears, N_u,Rd must exceed N_pl,Rd. The report writes that
    as A_net/A > (f_y/0,9f_u)·(γ_M2/γ_M0); this reports whether it holds rather than
    refusing, since it is a requirement of the design situation and not of the section.
    """
    _quantity(area, "[area]", "area", source=_SECTION_SOURCE)
    _quantity(yield_strength, "[pressure]", "yield_strength", source=_STEEL_SOURCE)
    m0 = _factor(partial_factor_m0, "partial_factor_m0")
    a_mm2 = area.to("mm^2").magnitude
    fy_mpa = yield_strength.to("MPa").magnitude
    gross = _newtons(a_mm2, fy_mpa, m0)

    declared = (net_area, ultimate_strength, partial_factor_m2)
    if all(value is None for value in declared):
        return TensionResistance(
            resistance=gross,
            gross_section=gross,
            net_section=None,
            governed_by=TensionGoverned.GROSS_SECTION,
            dissipative_capable=True,
            method="EN 1993-1-1 §6.2.3 Eq. (6.6): the gross section's plastic resistance",
            clause="EN 1993-1-1 clause 6.2.3(2)",
        )
    if any(value is None for value in declared):
        raise _refuse(
            "net_area, ultimate_strength and partial_factor_m2 are declared together or not "
            "at all: the net-section resistance needs all three, and computing none of them "
            "would report the gross section as the member's resistance",
            subject="net_area, ultimate_strength and partial_factor_m2",
            source=_SECTION_SOURCE,
        )
    assert net_area is not None and ultimate_strength is not None  # narrowed above
    _quantity(net_area, "[area]", "net_area", source=_SECTION_SOURCE)
    _quantity(ultimate_strength, "[pressure]", "ultimate_strength", source=_STEEL_SOURCE)
    m2 = _factor(partial_factor_m2 or 0.0, "partial_factor_m2")
    # Compared in one unit. `_quantity` hands back each value's OWN magnitude, so comparing
    # those directly reads 8 566 mm² as larger than 100 cm² — the same number in two units,
    # and a refusal for a net section that is in fact 86% of the gross one.
    net = net_area.to("mm^2").magnitude
    fu = ultimate_strength.to("MPa").magnitude
    if net > a_mm2:
        raise _refuse(
            f"net_area {net_area} exceeds the gross area {area}; a net section is the gross "
            f"section less its holes",
            subject="net_area",
            source=_SECTION_SOURCE,
        )
    if fu < fy_mpa:
        raise _refuse(
            f"ultimate_strength {ultimate_strength} is below yield_strength {yield_strength}",
            subject="ultimate_strength",
            source=_STEEL_SOURCE,
        )
    ultimate = _newtons(
        _NET_SECTION_COEFFICIENT * net_area.to("mm^2").magnitude,
        ultimate_strength.to("MPa").magnitude,
        m2,
    )
    governing = min(gross, ultimate, key=lambda q: q.to("N").magnitude)
    return TensionResistance(
        resistance=governing,
        gross_section=gross,
        net_section=ultimate,
        governed_by=(
            TensionGoverned.GROSS_SECTION
            if governing.to("N").magnitude == gross.to("N").magnitude
            else TensionGoverned.NET_SECTION
        ),
        dissipative_capable=ultimate.to("N").magnitude > gross.to("N").magnitude,
        method=(
            "EN 1993-1-1 §6.2.3: the smaller of the gross section's plastic resistance and "
            "the net section's ultimate resistance"
        ),
        clause="EN 1993-1-1 clause 6.2.3(2)",
    )


def compression_resistance(
    *,
    area: Quantity,
    yield_strength: Quantity,
    partial_factor_m0: float,
) -> Quantity:
    """The design compression resistance N_c,Rd = A·f_y/γ_M0 (EN 1993-1-1 §6.2.4).

    One equation covers classes 1, 2 and 3 on the gross area (Eq. 1.31); a class 4 section
    takes the same equation on its effective area A_eff (Eq. 1.32), so pass A_eff as
    ``area``. Holes for fasteners may be neglected where they are filled and neither
    oversize nor slotted (clause 6.2.4(3)) — whether they are is the caller's to know.

    This is a **cross-section** resistance and not a buckling resistance: a real column is
    governed by §6.3's flexural buckling, which this is the ceiling for.
    """
    _quantity(area, "[area]", "area", source=_SECTION_SOURCE)
    _quantity(yield_strength, "[pressure]", "yield_strength", source=_STEEL_SOURCE)
    m0 = _factor(partial_factor_m0, "partial_factor_m0")
    return _newtons(area.to("mm^2").magnitude, yield_strength.to("MPa").magnitude, m0)


def bending_resistance(
    *,
    section_class: SectionClass,
    yield_strength: Quantity,
    partial_factor_m0: float,
    plastic_modulus: Quantity | None = None,
    elastic_modulus: Quantity | None = None,
    effective_modulus: Quantity | None = None,
) -> Quantity:
    """The design bending resistance M_c,Rd about one axis (EN 1993-1-1 §6.2.5(2)).

    The class chooses the modulus, and that mapping is the whole of clause 6.2.5(2):

    - class 1 or 2 → ``plastic_modulus`` W_pl (Eq. 1.47)
    - class 3 → ``elastic_modulus`` W_el,min (Eq. 1.48)
    - class 4 → ``effective_modulus`` W_eff,min (Eq. 1.49)

    So the modulus the class calls for is required and the others are refused if given
    instead. Passing W_pl for a class 3 section is the mistake this shape exists to stop:
    it reports the plastic moment for a section that buckles before it reaches it, and
    nothing downstream can tell.
    """
    if not isinstance(section_class, SectionClass):
        raise _refuse(
            f"section_class must be a SectionClass; got {section_class!r}. It comes from "
            "anvilate.analysis.en1993_classification",
            subject="section_class",
            source=_SECTION_SOURCE,
        )
    wanted = {
        SectionClass.CLASS_1: ("plastic_modulus", plastic_modulus, "W_pl (Eq. 1.47)"),
        SectionClass.CLASS_2: ("plastic_modulus", plastic_modulus, "W_pl (Eq. 1.47)"),
        SectionClass.CLASS_3: ("elastic_modulus", elastic_modulus, "W_el,min (Eq. 1.48)"),
        SectionClass.CLASS_4: ("effective_modulus", effective_modulus, "W_eff,min (Eq. 1.49)"),
    }[section_class]
    name, value, described = wanted
    if value is None:
        raise _refuse(
            f"a class {int(section_class)} section bends on {described}, so {name} is "
            f"required; clause 6.2.5(2) gives each class its own modulus",
            subject=name,
            source=_SECTION_SOURCE,
        )
    given = {
        "plastic_modulus": plastic_modulus,
        "elastic_modulus": elastic_modulus,
        "effective_modulus": effective_modulus,
    }
    extra = sorted(other for other, held in given.items() if held is not None and other != name)
    if extra:
        raise _refuse(
            f"a class {int(section_class)} section bends on {described} and {', '.join(extra)} "
            f"was given as well; one class takes one modulus and passing two leaves which one "
            f"was used to the reader",
            subject=", ".join(extra),
            source=_SECTION_SOURCE,
        )
    _quantity(value, "[volume]", name, source=_SECTION_SOURCE)
    _quantity(yield_strength, "[pressure]", "yield_strength", source=_STEEL_SOURCE)
    m0 = _factor(partial_factor_m0, "partial_factor_m0")
    return Quantity(
        magnitude=value.to("mm^3").magnitude * yield_strength.to("MPa").magnitude / m0,
        unit="N*mm",
    )


def shear_resistance(
    *,
    shear_area: Quantity,
    yield_strength: Quantity,
    partial_factor_m0: float,
) -> Quantity:
    """Plastic shear resistance V_pl,Rd = A_v·(f_y/√3)/γ_M0 (EN 1993-1-1 §6.2.6, Eq. 1.53).

    The f_y/√3 is the von Mises shear yield, and ``shear_area`` A_v is the part of the
    section parallel to the shear — for an I-section sheared across its web, roughly the
    web. Clause 6.2.6(3) gives A_v per standard shape and the profile tables publish it;
    this does not derive it, because deriving it from h and t_w would be a different section
    for a rolled shape than the table's.
    """
    _quantity(shear_area, "[area]", "shear_area", source=_SECTION_SOURCE)
    _quantity(yield_strength, "[pressure]", "yield_strength", source=_STEEL_SOURCE)
    m0 = _factor(partial_factor_m0, "partial_factor_m0")
    return _newtons(
        shear_area.to("mm^2").magnitude,
        yield_strength.to("MPa").magnitude / _SHEAR_YIELD_DIVISOR,
        m0,
    )


def shear_buckling_check_needed(
    *,
    web_depth: Quantity,
    web_thickness: Quantity,
    epsilon: float,
    eta: float = 1.0,
) -> bool:
    """Whether an unstiffened web needs EN 1993-1-5's shear-buckling check (§6.2.6).

    True when h_w/t_w > 72ε/η. ``eta`` is EN 1993-1-5's factor, which the source says may
    **conservatively be taken as 1,0**, and 1,0 is the default here for that reason.

    Note which way η runs in *this* expression, because it is the opposite of the way the
    word "conservative" suggests: η divides, so a larger η gives a **lower** threshold and
    asks for the buckling check **sooner**. η = 1,0 is the source's conservative choice for
    η's other role — it scales the shear buckling resistance of EN 1993-1-5, where smaller
    is safer — and in the trigger above it is the permissive end. A National Annex value of
    1,2 takes the threshold from 72ε to 60ε.

    A True answer is not a failure: it says the plastic shear resistance above is not the
    whole story and the web's buckling has to be checked in a part this module does not
    implement.
    """
    depth = _quantity(web_depth, "[length]", "web_depth", source=_SECTION_SOURCE)
    thickness = _quantity(web_thickness, "[length]", "web_thickness", source=_SECTION_SOURCE)
    require_finite(epsilon, name="epsilon")
    require_finite(eta, name="eta")
    if epsilon <= 0 or eta <= 0:
        raise _refuse(
            f"epsilon and eta must be positive; got {epsilon} and {eta}",
            subject="epsilon and eta",
            source=_STEEL_SOURCE,
        )
    return depth / thickness > _SHEAR_BUCKLING_COEFFICIENT * epsilon / eta


def shear_reduction_rho(*, shear_force: Quantity, shear_capacity: Quantity) -> float:
    """EN 1993-1-1 §6.2.8's ρ = (2·V_Ed/V_pl,Rd − 1)², and 0 below half of V_pl,Rd.

    Below half the plastic shear resistance the clause asks for no reduction at all — the
    loss is small there and strain hardening covers it — so this returns 0,0 rather than a
    small number, which is the clause and not a simplification. At exactly half it is still
    0,0, which is also what the formula gives: (2·0,5 − 1)² = 0.

    Returns ρ in [0, 1]; at V_Ed = V_pl,Rd it is 1 and the shear area carries no bending.
    """
    v_ed = _quantity(shear_force, "[force]", "shear_force", source=_FORCE_SOURCE)
    v_rd = _quantity(shear_capacity, "[force]", "shear_capacity", source=_SECTION_SOURCE)
    ratio = shear_force.to("N").magnitude / shear_capacity.to("N").magnitude
    if ratio > 1.0:
        raise _refuse(
            f"shear_force {shear_force} exceeds shear_capacity {shear_capacity}, so the "
            f"section fails in shear before any bending interaction applies",
            subject="shear_force",
            source=_FORCE_SOURCE,
        )
    del v_ed, v_rd
    if ratio <= _SHEAR_INTERACTION_THRESHOLD:
        return 0.0
    return (2.0 * ratio - 1.0) ** 2


def bending_resistance_with_shear(
    *,
    plastic_modulus: Quantity,
    web_area: Quantity,
    web_thickness: Quantity,
    yield_strength: Quantity,
    partial_factor_m0: float,
    shear_force: Quantity,
    shear_capacity: Quantity,
) -> Quantity:
    """M_y,V,Rd for an I or H with equal flanges (EN 1993-1-1 §6.2.8, Eq. 1.54).

    ``(W_pl,y − ρ·A_w²/(4·t_w))·f_y/γ_M0``, capped at the unreduced M_y,c,Rd — the cap
    matters because at ρ = 0 the expression already equals it, and without the cap a
    rounding could report more. ``web_area`` is A_w = h_w·t_w.

    Major axis only, and equal flanges only, because that is the scope Eq. 1.54 states.
    """
    _quantity(plastic_modulus, "[volume]", "plastic_modulus", source=_SECTION_SOURCE)
    aw = _quantity(web_area, "[area]", "web_area", source=_SECTION_SOURCE)
    tw = _quantity(web_thickness, "[length]", "web_thickness", source=_SECTION_SOURCE)
    _quantity(yield_strength, "[pressure]", "yield_strength", source=_STEEL_SOURCE)
    m0 = _factor(partial_factor_m0, "partial_factor_m0")
    del aw, tw
    rho = shear_reduction_rho(shear_force=shear_force, shear_capacity=shear_capacity)
    w_pl = plastic_modulus.to("mm^3").magnitude
    aw_mm2 = web_area.to("mm^2").magnitude
    tw_mm = web_thickness.to("mm").magnitude
    fy_mpa = yield_strength.to("MPa").magnitude
    reduced = w_pl - rho * aw_mm2**2 / (4.0 * tw_mm)
    unreduced = w_pl
    return Quantity(magnitude=min(reduced, unreduced) * fy_mpa / m0, unit="N*mm")


def axial_reduction_negligible(
    *,
    axial_force: Quantity,
    plastic_axial_resistance: Quantity,
) -> bool:
    """Whether EN 1993-1-1 §6.2.9.1(4) lets the axial force's effect on bending be neglected.

    True when N_Ed ≤ 0,25·N_pl,Rd, which is the condition the source states and works: its
    example computes 0,25·5726,2 = 1431,5 kN and, finding N_Ed = 1704,0 kN above it, goes on
    to reduce the moment.

    Clause 6.2.9.1(4) carries a **second** condition as well, on the web's own share of the
    axial force, which the source does not state and which was therefore not read. So a
    False here means only that the first condition does not excuse the reduction; it does
    not mean the clause requires it.
    """
    _quantity(axial_force, "[force]", "axial_force", source=_FORCE_SOURCE)
    _quantity(
        plastic_axial_resistance, "[force]", "plastic_axial_resistance", source=_SECTION_SOURCE
    )
    share = axial_force.to("N").magnitude / plastic_axial_resistance.to("N").magnitude
    return share <= _NEGLIGIBLE_AXIAL_SHARE


def _axial_ratio(axial_force: Quantity, plastic_axial_resistance: Quantity) -> float:
    """n = N_Ed/N_pl,Rd, as the source's worked examples compute it."""
    _quantity(axial_force, "[force]", "axial_force", source=_FORCE_SOURCE)
    _quantity(
        plastic_axial_resistance, "[force]", "plastic_axial_resistance", source=_SECTION_SOURCE
    )
    n = axial_force.to("N").magnitude / plastic_axial_resistance.to("N").magnitude
    if n > 1.0:
        raise _refuse(
            f"n = N_Ed/N_pl,Rd comes out {n:.4g}: the axial force alone exceeds the plastic "
            f"axial resistance, so there is no moment left to reduce",
            subject="axial_force",
            source=_FORCE_SOURCE,
        )
    return n


def _capped_area_ratio(area_ratio: float) -> float:
    """a, capped at 0,5 by clause 6.2.9.1(5) whatever the flanges work out to."""
    require_finite(area_ratio, name="area_ratio")
    if not 0.0 <= area_ratio <= 1.0:
        raise _refuse(
            f"area_ratio is (A − 2·b·t_f)/A and lies in [0, 1]; got {area_ratio}",
            subject="area_ratio",
            source=_SECTION_SOURCE,
        )
    return min(float(area_ratio), _MAX_AREA_RATIO)


def reduced_plastic_moment_major(
    *,
    plastic_moment: Quantity,
    axial_force: Quantity,
    plastic_axial_resistance: Quantity,
    area_ratio: float,
) -> Quantity:
    """M_N,y,Rd = M_pl,y,Rd·(1−n)/(1−0,5a), capped (EN 1993-1-1 §6.2.9.1(5), Eq. 1.62).

    For an I or H section, rolled or welded, with equal flanges and no fastener holes
    accounted for. ``area_ratio`` is a = (A − 2·b·t_f)/A — the share of the area that is not
    flange — and clause 6.2.9.1(5) caps it at 0,5. The source's second worked example is
    exactly that case: its ratio comes out 0,55 and is used as 0,5.

    The source also applies this form to a **rectangular hollow section** with
    a_w = (A − 2·b·t)/A, which is why the ratio is a plain argument here rather than derived
    from flange dimensions: one formula, two ways of measuring the ratio, and which one
    applies is a fact about the shape.

    The cap at M_pl,y,Rd is the clause's own ``but``. It binds when n is small enough that
    (1−n)/(1−0,5a) exceeds 1 — a low axial force must not be allowed to *increase* the
    moment resistance.
    """
    _quantity(plastic_moment, "[energy]", "plastic_moment", source=_SECTION_SOURCE)
    n = _axial_ratio(axial_force, plastic_axial_resistance)
    a = _capped_area_ratio(area_ratio)
    scaled = plastic_moment.magnitude * (1.0 - n) / (1.0 - 0.5 * a)
    return Quantity(magnitude=min(scaled, plastic_moment.magnitude), unit=plastic_moment.unit)


def reduced_plastic_moment_minor(
    *,
    plastic_moment: Quantity,
    axial_force: Quantity,
    plastic_axial_resistance: Quantity,
    area_ratio: float,
) -> Quantity:
    """M_N,z,Rd about the minor axis (EN 1993-1-1 §6.2.9.1(5), Eqs. 1.63 and 1.64).

    ``M_pl,z,Rd`` unchanged while n ≤ a, and ``M_pl,z,Rd·[1 − ((n−a)/(1−a))²]`` above it.
    The minor axis is unaffected until the axial force has consumed the web, which is what
    n ≤ a says: the web is the part that is not flange, and bending about z is carried by
    the flanges.

    At a = 0,5 and n = 1 the bracket is 0, so a section squashed by axial force alone has no
    minor-axis moment resistance left, which is the check that the formula is the right way
    round.
    """
    _quantity(plastic_moment, "[energy]", "plastic_moment", source=_SECTION_SOURCE)
    n = _axial_ratio(axial_force, plastic_axial_resistance)
    a = _capped_area_ratio(area_ratio)
    if n <= a:
        return plastic_moment
    reduction = 1.0 - ((n - a) / (1.0 - a)) ** 2
    return Quantity(magnitude=plastic_moment.magnitude * max(reduction, 0.0),
                    unit=plastic_moment.unit)  # fmt: skip


def biaxial_bending_utilisation(
    *,
    moment_y: Quantity,
    resistance_y: Quantity,
    moment_z: Quantity,
    resistance_z: Quantity,
    alpha: float = 1.0,
    beta: float = 1.0,
) -> float:
    """Biaxial bending utilisation to EN 1993-1-1 §6.2.9 Eq. (1.50); it must not exceed 1.

    For class 1 or 2 sections. ``alpha`` and ``beta`` depend on the shape and clause
    6.2.9(6) gives them as α = 2 and β = 1 for I or H sections, α = β = 2 for circular
    hollow sections and α = β = 1,66 for rectangular hollow ones; both **may conservatively
    be taken as 1,0**, which is the default here because 1,0 is the safe reading and a
    shape-specific exponent is a claim about the shape.

    Returns the utilisation; a caller compares it with 1,00. The exponents are what make
    this worth a function: with α = 2 a section at 70% of its major-axis resistance has
    spent 49% of its interaction, not 70%.
    """
    _quantity(resistance_y, "[energy]", "resistance_y", source=_SECTION_SOURCE)
    _quantity(resistance_z, "[energy]", "resistance_z", source=_SECTION_SOURCE)
    for value, name in ((moment_y, "moment_y"), (moment_z, "moment_z")):
        magnitude = _moment(value, "[energy]", name)
        if magnitude < 0:
            raise _refuse(
                f"{name} is a magnitude here; got {value}. Eq. (1.50) sums utilisations and a "
                f"negative one would subtract from the other axis",
                subject=name,
                source=_FORCE_SOURCE,
            )
    exponent_y = _exponent(alpha, "alpha")
    exponent_z = _exponent(beta, "beta")
    ratio_y = moment_y.to("N*mm").magnitude / resistance_y.to("N*mm").magnitude
    ratio_z = moment_z.to("N*mm").magnitude / resistance_z.to("N*mm").magnitude
    return ratio_y**exponent_y + ratio_z**exponent_z
