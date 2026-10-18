"""T1 analytical O-ring gland checks (closed-form squeeze, fill, and stretch).

An O-ring seals because its round cross-section is squeezed between a groove bottom and
a sealing face, and the whole design reduces to three geometric ratios that a groove
must land inside. **Squeeze** is how much the cross-section is flattened,
(CS − E)/CS for a free cross-section ``CS`` and a radial gland depth ``E`` — too little
and it leaks, too much and it takes a compression set; static seals aim for roughly
15–30 %. **Gland fill** is the fraction of the groove the rubber occupies,
(π·CS²/4)/(E·G) for a groove width ``G`` — the groove must never fill completely
(target ≈ 60–85 %), because rubber is nearly incompressible and thermal expansion or
fluid swell needs somewhere to go, or it extrudes and blows the seal. **Stretch** is how
far the ring's inner diameter is opened to fit its groove, (D_groove − ID)/ID — a little
(under ~5 %) holds it in place, too much thins the cross-section and shortens its life.

The design screen is simply: does the chosen groove put all three ratios in band? These
are pure geometry — every input is a dimension-checked
:class:`~anvilate.units.Quantity`, and every result is a dimensionless fraction (multiply
by 100 for a percentage).

Sources: the Parker *O-Ring Handbook* — the squeeze fraction a gland depth applies to a cord,
the gland fill fraction the cord occupies, and the stretch fraction an inside diameter imposes.
"""

from __future__ import annotations

from math import pi

from pydantic import BaseModel, ConfigDict

from .._models import ItemCollection, Named, Provenance, RevalidatedModel
from ..refusal import RefusalError, Remedy
from ..units import Quantity, require_finite

_O_RING_SIZE_SOURCE = "the O-ring manufacturer catalogue or verified seal size record"
_O_RING_GLAND_SOURCE = "the seal gland drawing or approved gland-design table"
_O_RING_SERVICE_SOURCE = "the seal's service conditions and elastomer record"


class _ORingInputError(RefusalError, ValueError):
    """An O-ring input that cannot be used without correction."""


def _o_ring_refusal(message: str, *, subject: str, source: str) -> _ORingInputError:
    return _ORingInputError(
        message,
        remedies=(Remedy(action="replace", subject=subject, source=source),),
    )


def _o_ring_input_source(name: str) -> str:
    if name in {"cross_section_diameter", "inner_diameter"}:
        return _O_RING_SIZE_SOURCE
    return _O_RING_GLAND_SOURCE


__all__ = [
    "o_ring_squeeze_fraction",
    "o_ring_gland_fill_fraction",
    "o_ring_stretch_fraction",
    "SealCondition",
    "SealScreen",
    "o_ring_seal_screen",
]


def _positive_mm(value: Quantity, name: str) -> float:
    require_finite(value, name=name)
    if not isinstance(value, Quantity):
        raise _o_ring_refusal(
            f"{name} must be a [length] quantity; got {value!r}",
            subject=name,
            source=_o_ring_input_source(name),
        )
    if not value.has_dimension("[length]"):
        raise _o_ring_refusal(
            f"{name} must be a [length] quantity; got {value.dimensionality} ({value})",
            subject=name,
            source=_o_ring_input_source(name),
        )
    magnitude = value.to("mm").magnitude
    if magnitude <= 0:
        raise _o_ring_refusal(
            f"{name} must be positive; got {value}",
            subject=name,
            source=_o_ring_input_source(name),
        )
    return magnitude


def o_ring_squeeze_fraction(*, cross_section_diameter: Quantity, gland_depth: Quantity) -> float:
    """The squeeze fraction (CS − E)/CS of an O-ring in its gland.

    How much the round cross-section is flattened: the free ``cross_section_diameter``
    CS less the radial ``gland_depth`` E (groove bottom to sealing face), over CS. A
    static seal aims for roughly 0.15–0.30; too little leaks, too much sets. The gland
    must be shallower than the cross-section (E < CS) or there is no squeeze. Returns
    the dimensionless fraction.
    """
    cs = _positive_mm(cross_section_diameter, "cross_section_diameter")
    e = _positive_mm(gland_depth, "gland_depth")
    if e >= cs:
        raise _o_ring_refusal(
            f"gland_depth ({e} mm) must be less than cross_section_diameter ({cs} mm) "
            "for the O-ring to be squeezed",
            subject="gland_depth and cross_section_diameter",
            source=_O_RING_GLAND_SOURCE,
        )
    return (cs - e) / cs


def o_ring_gland_fill_fraction(
    *, cross_section_diameter: Quantity, gland_depth: Quantity, groove_width: Quantity
) -> float:
    """The gland fill fraction (π·CS²/4)/(E·G) of the groove the O-ring occupies.

    The rubber cross-section area π·CS²/4 over the groove's cross-section area E·G
    (radial ``gland_depth`` E times axial ``groove_width`` G). Rubber is nearly
    incompressible, so the groove must leave room (target ≈ 0.60–0.85) for thermal
    expansion and fluid swell; a fill at or above 1 cannot physically assemble and will
    extrude. ``cross_section_diameter`` is CS. Returns the dimensionless fraction.
    """
    cs = _positive_mm(cross_section_diameter, "cross_section_diameter")
    e = _positive_mm(gland_depth, "gland_depth")
    g = _positive_mm(groove_width, "groove_width")
    return (pi * cs**2 / 4.0) / (e * g)


def o_ring_stretch_fraction(*, inner_diameter: Quantity, groove_diameter: Quantity) -> float:
    """The stretch fraction (D_groove − ID)/ID an O-ring takes to fit its groove.

    How far the ring's free ``inner_diameter`` ID is opened to seat on the
    ``groove_diameter`` D_groove (the groove bottom it stretches around, e.g. a piston
    OD). A little stretch (under ~0.05) keeps the ring seated; too much thins the
    cross-section and shortens life. The groove must be at least as large as the ID.
    Returns the dimensionless fraction (0 when the ring just fits unstretched).
    """
    id_ = _positive_mm(inner_diameter, "inner_diameter")
    groove = _positive_mm(groove_diameter, "groove_diameter")
    if groove < id_:
        raise _o_ring_refusal(
            f"groove_diameter ({groove} mm) must be at least the O-ring inner_diameter ({id_} mm)",
            subject="groove_diameter and inner_diameter",
            source=_O_RING_GLAND_SOURCE,
        )
    return (groove - id_) / id_


class SealCondition(RevalidatedModel):
    """One condition of an O-ring seal screen (Parker O-Ring Handbook practice).

    ``state`` is "pass", "fail" or "not evaluated"; ``value`` and ``limit`` are what was
    compared, and ``source`` is where the limit came from — the caller's cited record.
    """

    model_config = ConfigDict(frozen=True)

    condition: Named
    state: str
    value: float | None
    limit: float | None
    source: Provenance | None
    detail: str


class SealScreen(ItemCollection, BaseModel):
    """An O-ring seal across its temperature range, pressure and life (Parker O-Ring Handbook).

    ``conditions`` are each check's result; ``passes`` is True only when every condition
    passes, and a condition not evaluated keeps the screen from passing.
    """

    model_config = ConfigDict(frozen=True)

    conditions: tuple[SealCondition, ...]

    @property
    def passes(self) -> bool:
        """Every condition passed; one not evaluated is not a pass."""
        return all(c.state == "pass" for c in self.conditions)

    def __str__(self) -> str:
        head = "seal passes" if self.passes else "seal does not pass"
        return "\n".join(
            [f"O-ring {head} (Parker O-Ring Handbook practice)"]
            + [f"  [{c.state}] {c.condition}: {c.detail}" for c in self.conditions]
        )


def _kelvin(value: Quantity, name: str) -> float:
    if not isinstance(value, Quantity):
        raise _o_ring_refusal(f"{name} must be a temperature quantity; got {value!r}",
                              subject=name, source=_O_RING_SERVICE_SOURCE)  # fmt: skip
    try:
        kelvin = value.to("K").magnitude
    except Exception as error:
        raise _o_ring_refusal(f"{name} is {value}, which is not a temperature", subject=name,
                              source=_O_RING_SERVICE_SOURCE) from error  # fmt: skip
    return require_finite(kelvin, name=name)


def _fraction(value: float, name: str, *, source: str) -> float:
    v = require_finite(value, name=name)
    if not 0 <= v < 1:
        raise _o_ring_refusal(f"{name} is {v}; it is a fraction in [0, 1)", subject=name,
                              source=source)  # fmt: skip
    return v


def _expansion(value: float, name: str) -> float:
    v = require_finite(value, name=name)
    if not 0 <= v < 1e-2:
        raise _o_ring_refusal(
            f"{name} is {v} per kelvin; a linear expansion coefficient is a small positive "
            "number, about 2e-4 for an elastomer and 1e-5 to 2.5e-5 for a metal gland",
            subject=name,
            source=_O_RING_SERVICE_SOURCE,
        )
    return v


def o_ring_seal_screen(
    *,
    cross_section_diameter: Quantity,
    gland_depth: Quantity,
    groove_width: Quantity,
    reference_temperature: Quantity,
    minimum_temperature: Quantity,
    maximum_temperature: Quantity,
    seal_expansion: float,
    gland_expansion: float,
    minimum_squeeze: float,
    maximum_fill: float,
    limits_source: str,
    diametral_gap: Quantity | None = None,
    extrusion_gap_limit: Quantity | None = None,
    compression_set: float | None = None,
    compression_set_source: str | None = None,
    fluid_compatible: bool | None = None,
) -> SealScreen:
    """An O-ring across its temperature extremes, pressure and life (Parker O-Ring Handbook).

    The cross-section grows with ``seal_expansion`` and the gland with ``gland_expansion``
    (both per kelvin) from ``reference_temperature``, where the drawing's dimensions hold:
    an elastomer expands about ten times as fast as a metal gland, so squeeze is lowest at
    the cold extreme and fill highest at the hot one. Squeeze is held to
    ``minimum_squeeze`` and fill to ``maximum_fill``, both from ``limits_source``. The
    ``diametral_gap`` is held to the ``extrusion_gap_limit`` the caller read for this
    pressure and hardness. ``compression_set`` C, from the elastomer record over the life
    and temperature, leaves a squeeze of S·(1 − C) at the cold extreme. ``fluid_compatible``
    is the elastomer record's attribute for the fluid; undeclared, it is not evaluated.
    Glass transition and low-temperature stiffening are not modelled: a declared minimum
    temperature below the elastomer's rating is the caller's to refuse.
    """
    if not isinstance(limits_source, str) or not limits_source.strip():
        raise _o_ring_refusal("limits_source must name where the squeeze and fill limits come "
                              "from", subject="limits_source",
                              source=_O_RING_SERVICE_SOURCE)  # fmt: skip
    cs = _positive_mm(cross_section_diameter, "cross_section_diameter")
    e = _positive_mm(gland_depth, "gland_depth")
    g = _positive_mm(groove_width, "groove_width")
    t_ref = _kelvin(reference_temperature, "reference_temperature")
    t_min = _kelvin(minimum_temperature, "minimum_temperature")
    t_max = _kelvin(maximum_temperature, "maximum_temperature")
    if not t_min <= t_ref <= t_max:
        raise _o_ring_refusal(
            "reference_temperature must lie between minimum_temperature and "
            "maximum_temperature, so the extremes are each side of the drawing's state",
            subject="reference_temperature",
            source=_O_RING_SERVICE_SOURCE,
        )
    a_s = _expansion(seal_expansion, "seal_expansion")
    a_g = _expansion(gland_expansion, "gland_expansion")
    s_min = _fraction(minimum_squeeze, "minimum_squeeze", source=limits_source)
    f_max = require_finite(maximum_fill, name="maximum_fill")
    if not 0 < f_max <= 1:
        raise _o_ring_refusal(f"maximum_fill is {f_max}; a fill limit lies in (0, 1]",
                              subject="maximum_fill", source=limits_source)  # fmt: skip

    def state_at(t: float) -> tuple[float, float]:
        dt = t - t_ref
        cs_t, e_t, g_t = cs * (1 + a_s * dt), e * (1 + a_g * dt), g * (1 + a_g * dt)
        return (cs_t - e_t) / cs_t, (pi * cs_t**2 / 4) / (e_t * g_t)

    squeeze_cold, _ = state_at(t_min)
    _, fill_hot = state_at(t_max)
    cold_c = t_min - 273.15
    hot_c = t_max - 273.15
    conditions = [
        SealCondition(
            condition=f"squeeze at the cold extreme ({cold_c:.4g} °C)",
            state="pass" if squeeze_cold >= s_min else "fail",
            value=squeeze_cold, limit=s_min, source=limits_source,
            detail=f"{squeeze_cold:.1%} against a minimum of {s_min:.1%}",
        ),
        SealCondition(
            condition=f"gland fill at the hot extreme ({hot_c:.4g} °C)",
            state="pass" if fill_hot <= f_max else "fail",
            value=fill_hot, limit=f_max, source=limits_source,
            detail=f"{fill_hot:.1%} against a maximum of {f_max:.1%}",
        ),
    ]  # fmt: skip
    if diametral_gap is None or extrusion_gap_limit is None:
        conditions.append(SealCondition(
            condition="extrusion gap", state="not evaluated", value=None, limit=None,
            source=None, detail="declare diametral_gap and the extrusion_gap_limit read for "
            "this pressure and hardness, with its source in limits_source",
        ))  # fmt: skip
    else:
        gap = _positive_mm(diametral_gap, "diametral_gap")
        limit = _positive_mm(extrusion_gap_limit, "extrusion_gap_limit")
        conditions.append(SealCondition(
            condition="extrusion gap", state="pass" if gap <= limit else "fail", value=gap,
            limit=limit, source=limits_source,
            detail=f"diametral gap {gap:.4g} mm against a limit of {limit:.4g} mm "
            f"({limits_source})",
        ))  # fmt: skip
    if compression_set is None:
        conditions.append(SealCondition(
            condition="squeeze left after compression set", state="not evaluated", value=None,
            limit=s_min, source=None, detail="declare compression_set from the elastomer record "
            "for the life and temperature, with compression_set_source",
        ))  # fmt: skip
    else:
        if not isinstance(compression_set_source, str) or not compression_set_source.strip():
            raise _o_ring_refusal("compression_set needs compression_set_source, the elastomer "
                                  "record it was read from", subject="compression_set_source",
                                  source=_O_RING_SERVICE_SOURCE)  # fmt: skip
        c = _fraction(compression_set, "compression_set", source=compression_set_source)
        left = squeeze_cold * (1 - c)
        conditions.append(SealCondition(
            condition="squeeze left after compression set", state="pass" if left >= s_min
            else "fail", value=left, limit=s_min, source=compression_set_source,
            detail=f"{left:.1%} at the cold extreme after {c:.0%} set, against {s_min:.1%}",
        ))  # fmt: skip
    conditions.append(SealCondition(
        condition="fluid compatibility",
        state="not evaluated" if fluid_compatible is None
        else ("pass" if fluid_compatible else "fail"),
        value=None, limit=None, source="the elastomer record",
        detail="declare the elastomer record's compatibility with the fluid"
        if fluid_compatible is None
        else ("compatible" if fluid_compatible else "not compatible"),
    ))  # fmt: skip
    return SealScreen(conditions=tuple(conditions))
