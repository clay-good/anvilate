"""T1 crippling of thin-walled sections by Gerard's method (NACA TN 3784).

A short formed or extruded section in compression does not buckle as a column and does
not stop at its first local buckle: the flat elements buckle, the corners keep carrying
load, and the section fails — cripples — at an average stress σ̄f between the local
buckling stress and the yield stress. Gerard (NACA TN 3784, *Handbook of Structural
Stability Part IV: Failure of Plates and Composite Elements*, 1957) correlated that
average stress with the section's corners and flanges in closed form:

    one-corner (angles, tees, cruciforms)
        σ̄f/σcy = β_f·[(f·t²/A)·(E/σcy)^(1/2)]^m                   (TN 3784 A6, Table 13)
    two-corner (Z, channel, J)
        σ̄f/σcy = β·[(t²/A)·(E/σcy)^(1/3)]^0.75                    (TN 3784 eq. 61, Table 14)
    multicorner (tubes, multi-web sections)
        σ̄f/σcy = β_c·[(c·t²/A)·(E/σcy)^(1/2)]^0.85                (TN 3784 p. 47, Table 15)

with t the wall thickness, A the section area, f the number of flanges, c the number of
corners, σcy the compressive yield stress and E the modulus. A formed section's β grows
with the corner yield it gains in forming (σ̄cy/σcy); the tables list it at a few ratios
and this module takes the listed ratio at or below the one declared, whose β is the
smaller — never a value between rows.

Each form holds only up to a cutoff on σ̄f/σcy (0.92 for formed angles that gained more
than 25% corner yield, 3/4 for the other one-corner sections, A7 for two-corner sections,
0.7 for square tubes, 0.9 for β_c = 1.3 and 3/4 otherwise). Above it the crippling stress
is the elements' local buckling stress itself (TN 3784 eq. 73), which this module does
not compute, so a result above the cutoff is refused rather than reported.

Out of scope: clad sheet (the cladding factor η̄ needs the local buckling stress), the
H-section and curved-plate forms, and the Astronautic Structures Manual's b/t element
method, whose per-element allowable exists only as a chart (NASA TM X-73306 Fig.
C1.3.1-13) and is not digitized here.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict

from ..refusal import RefusalError, Remedy
from ..units import Quantity, require_finite

__all__ = [
    "CripplingSection",
    "CripplingStress",
    "gerard_crippling_stress",
]

_SECTION_SOURCE = "the section's drawing: wall thickness, area, corners and flanges"
_MATERIAL_SOURCE = "the material's compressive yield stress and modulus"


class _CripplingInputError(RefusalError, ValueError):
    """A crippling input that cannot be used without correction."""


def _refusal(message: str, *, subject: str, source: str) -> _CripplingInputError:
    return _CripplingInputError(
        message, remedies=(Remedy(action="replace", subject=subject, source=source),)
    )


class CripplingSection(StrEnum):
    """The section families NACA TN 3784 Tables 13–15 give constants for."""

    FORMED_ANGLE = "formed_angle"
    EXTRUDED_ANGLE = "extruded_angle"
    T_EXTRUSION = "t_extrusion"
    CRUCIFORM_EXTRUSION = "cruciform_extrusion"
    FORMED_TWO_CORNER = "formed_two_corner"
    EXTRUDED_TWO_CORNER = "extruded_two_corner"
    FORMED_MULTICORNER = "formed_multicorner"
    EXTRUDED_MULTICORNER = "extruded_multicorner"
    EXTRUDED_SQUARE_TUBE = "extruded_square_tube"


# (family, {corner yield ratio: β} or β, m, the exponent on E/σcy, cutoff on σ̄f/σcy)
# The tables' "estimated" rows are kept, as the tables keep them.
_ONE, _TWO, _MULTI = "one-corner", "two-corner", "multicorner"
_TABLE: dict[CripplingSection, tuple[str, dict[float, float], float, float]] = {
    CripplingSection.FORMED_ANGLE: (
        _ONE, {1.0: 0.59, 1.1: 0.62, 1.2: 0.65, 1.25: 0.66}, 0.85, 0.5
    ),
    CripplingSection.EXTRUDED_ANGLE: (_ONE, {1.0: 0.57}, 0.85, 0.5),
    CripplingSection.T_EXTRUSION: (_ONE, {1.0: 0.67}, 0.40, 0.5),
    CripplingSection.CRUCIFORM_EXTRUSION: (_ONE, {1.0: 0.67}, 0.40, 0.5),
    CripplingSection.FORMED_TWO_CORNER: (
        _TWO, {1.0: 3.3, 1.1: 3.5, 1.2: 3.8, 1.25: 4.0}, 0.75, 1 / 3
    ),
    CripplingSection.EXTRUDED_TWO_CORNER: (_TWO, {1.0: 3.6}, 0.75, 1 / 3),
    CripplingSection.FORMED_MULTICORNER: (_MULTI, {1.0: 1.1, 1.1: 1.2, 1.25: 1.3}, 0.85, 0.5),
    CripplingSection.EXTRUDED_MULTICORNER: (_MULTI, {1.0: 1.2}, 0.85, 0.5),
    CripplingSection.EXTRUDED_SQUARE_TUBE: (_MULTI, {1.0: 1.4}, 0.85, 0.5),
}  # fmt: skip

_TABLE_NAME = {_ONE: "Table 13", _TWO: "Table 14", _MULTI: "Table 15"}


class CripplingStress(BaseModel):
    """A section's crippling stress by NACA TN 3784, with the constants that produced it.

    ``stress`` is σ̄f in MPa; ``ratio`` is σ̄f/σcy; ``cutoff`` is the largest ratio the
    form holds to for this section.
    """

    model_config = ConfigDict(frozen=True)

    stress: float
    ratio: float
    cutoff: float
    beta: float
    exponent: float
    family: str
    table: str

    def __str__(self) -> str:
        return (
            f"crippling {self.stress:.4g} MPa = {self.ratio:.3f} σcy (cutoff {self.cutoff:.3g}; "
            f"{self.family}, β {self.beta:g}, m {self.exponent:g}, NACA TN 3784 {self.table})"
        )


def _magnitude(value: Quantity, unit: str, name: str, source: str) -> float:
    if not isinstance(value, Quantity):
        raise _refusal(f"{name} must be a quantity in {unit}; got {value!r}", subject=name,
                       source=source)  # fmt: skip
    try:
        magnitude = value.to(unit).magnitude
    except Exception as error:
        raise _refusal(f"{name} is {value}, which is not convertible to {unit}", subject=name,
                       source=source) from error  # fmt: skip
    magnitude = require_finite(magnitude, name=name)
    if magnitude <= 0:
        raise _refusal(f"{name} must be positive; got {value}", subject=name, source=source)
    return magnitude


def gerard_crippling_stress(
    *,
    section: CripplingSection,
    thickness: Quantity,
    area: Quantity,
    compressive_yield: Quantity,
    elastic_modulus: Quantity,
    count: int,
    corner_yield_ratio: float = 1.0,
    web_width: Quantity | None = None,
) -> CripplingStress:
    """The crippling stress σ̄f of a bare thin-walled section by Gerard (NACA TN 3784).

    ``count`` is the number of flanges f for a one-corner section, the number of corners c
    for a multicorner one, and ignored (enter 2) for a two-corner section. A formed section
    may declare ``corner_yield_ratio`` σ̄cy/σcy ≥ 1 — the corner's raised yield over the
    flat sheet's — and takes the β tabulated at the listed ratio at or below it. A
    two-corner section needs ``web_width`` b_w for its cutoff (TN 3784 A7). A result above
    the form's cutoff is refused: there the crippling stress is the local buckling stress
    (eq. 73), not this form's answer. Returned with its constants; stress in MPa.
    """
    if not isinstance(section, CripplingSection):
        raise _refusal(f"section must be a CripplingSection; got {section!r}",
                       subject="section", source=_SECTION_SOURCE)  # fmt: skip
    t = _magnitude(thickness, "mm", "thickness", _SECTION_SOURCE)
    a = _magnitude(area, "mm**2", "area", _SECTION_SOURCE)
    fcy = _magnitude(compressive_yield, "MPa", "compressive_yield", _MATERIAL_SOURCE)
    e = _magnitude(elastic_modulus, "MPa", "elastic_modulus", _MATERIAL_SOURCE)
    ratio_cy = require_finite(corner_yield_ratio, name="corner_yield_ratio")
    if ratio_cy < 1.0:
        raise _refusal(
            f"corner_yield_ratio is {ratio_cy}; forming raises the corner's yield, so the "
            "ratio of corner to flat yield is at least 1",
            subject="corner_yield_ratio",
            source=_MATERIAL_SOURCE,
        )
    if isinstance(count, bool) or not isinstance(count, int) or count < 1:
        raise _refusal(f"count is {count!r}; it is a whole number of flanges or corners",
                       subject="count", source=_SECTION_SOURCE)  # fmt: skip
    if t * t * count >= a:
        raise _refusal(
            f"count × t² = {count * t * t:.4g} mm² is not below the area {a:.4g} mm²; the "
            "section is not thin-walled, and crippling is a thin-wall failure",
            subject="area",
            source=_SECTION_SOURCE,
        )
    family, betas, m, power = _TABLE[section]
    listed = max(k for k in betas if k <= ratio_cy)
    beta = betas[listed]
    slenderness = (e / fcy) ** power
    if family == _TWO:
        parameter = t * t / a * slenderness
    else:
        parameter = count * t * t / a * slenderness
    ratio = beta * parameter**m
    if family == _ONE:
        cutoff = 0.92 if section is CripplingSection.FORMED_ANGLE and listed >= 1.25 else 0.75
    elif family == _TWO:
        if web_width is None:
            raise _refusal(
                "a two-corner section's cutoff depends on its web width (NACA TN 3784 A7); "
                "declare `web_width`, the flat width of the web",
                subject="web_width",
                source=_SECTION_SOURCE,
            )
        bw = _magnitude(web_width, "mm", "web_width", _SECTION_SOURCE)
        cutoff = ((beta / 2.14) * (t / bw) ** 0.25) ** (4 / 3)
    elif section is CripplingSection.EXTRUDED_SQUARE_TUBE:
        cutoff = 0.7
    else:
        cutoff = 0.9 if beta == 1.3 else 0.75
    if ratio > cutoff:
        raise _refusal(
            f"σ̄f/σcy = {ratio:.3f} is above this form's cutoff of {cutoff:.3f}; there the "
            "section cripples at its elements' local buckling stress (NACA TN 3784 eq. 73), "
            "which this screen does not compute",
            subject="thickness",
            source=_SECTION_SOURCE,
        )
    return CripplingStress(
        stress=ratio * fcy,
        ratio=ratio,
        cutoff=cutoff,
        beta=beta,
        exponent=m,
        family=family,
        table=_TABLE_NAME[family],
    )
