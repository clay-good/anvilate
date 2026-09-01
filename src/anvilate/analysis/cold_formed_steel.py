"""AISI cold-formed steel: the effective width of a thin compression element.

A thin cold-formed element does not carry uniform stress up to yield — it buckles
locally well before, and the middle of the element sheds load to the stiffer edges.
The AISI S100 effective-width method (Winter's formula) captures this by replacing
the full flat width with a reduced *effective* width that carries the edge stress
uniformly. That reduction is the defining calculation of cold-formed design: a wide,
thin flange can be barely half effective, and its section properties must be
recomputed on the effective section, not the gross one.

Anvilate evaluates the Winter formula from the element geometry and the applied
edge stress; the yield strength and modulus are the caller's material inputs. The
plate-buckling coefficient k is caller-supplied (4.0 for a stiffened element, 0.43
for an unstiffened one, or a computed value for an edge- or intermediately-stiffened
element).
"""

from __future__ import annotations

from enum import StrEnum
from math import sqrt

from pydantic import BaseModel, ConfigDict, model_validator

from .._models import Provenance, RevalidatedModel
from ..scorecard import CheckStatus, ScorecardEntry
from ..units import Quantity, require_finite

__all__ = [
    "aisi_plate_slenderness",
    "aisi_effective_width",
    "DSMLimitState",
    "ElasticBuckling",
    "DSMStrength",
    "dsm_compression_strength",
    "dsm_flexural_strength",
    "dsm_scorecard",
    "PREQUALIFIED_LIPPED_CHANNEL",
    "PrequalifiedLimits",
]

# AISI S100 slenderness limit below which an element is fully effective, and the
# coefficient of Winter's slenderness expression.
_AISI_SLENDERNESS_LIMIT = 0.673
_AISI_WINTER_COEFFICIENT = 1.052


def aisi_plate_slenderness(
    *,
    flat_width: Quantity,
    thickness: Quantity,
    stress: Quantity,
    elastic_modulus: Quantity,
    plate_buckling_coefficient: float = 4.0,
) -> float:
    """The AISI S100 plate slenderness λ = (1.052/√k)·(w/t)·√(f/E).

    The dimensionless slenderness that decides whether a compression element is fully
    effective: ``flat_width`` w and ``thickness`` t are the element's flat dimensions,
    ``stress`` f the applied edge (compression) stress, ``elastic_modulus`` E the
    steel's modulus, and ``plate_buckling_coefficient`` k the element's buckling
    coefficient (4.0 stiffened, 0.43 unstiffened). At λ ≤ 0.673 the element is fully
    effective; above it, it sheds load. Returns the dimensionless λ.
    """
    if not isinstance(flat_width, Quantity):
        raise ValueError(f"flat_width must be a [length] quantity; got {flat_width!r}")
    if not flat_width.has_dimension("[length]"):
        raise ValueError(f"flat_width must be a [length] quantity; got {flat_width}")
    if not isinstance(thickness, Quantity):
        raise ValueError(f"thickness must be a [length] quantity; got {thickness!r}")
    if not thickness.has_dimension("[length]"):
        raise ValueError(f"thickness must be a [length] quantity; got {thickness}")
    if not isinstance(stress, Quantity):
        raise ValueError(f"stress must be a [pressure] quantity; got {stress!r}")
    if not stress.has_dimension("[pressure]"):
        raise ValueError(f"stress must be a [pressure] quantity; got {stress}")
    if not isinstance(elastic_modulus, Quantity):
        raise ValueError(f"elastic_modulus must be a [pressure] quantity; got {elastic_modulus!r}")
    if not elastic_modulus.has_dimension("[pressure]"):
        raise ValueError(f"elastic_modulus must be a [pressure] quantity; got {elastic_modulus}")
    w = flat_width.to("mm").magnitude
    t = thickness.to("mm").magnitude
    f = stress.to("MPa").magnitude
    e = elastic_modulus.to("MPa").magnitude
    if w <= 0 or t <= 0 or f <= 0 or e <= 0:
        raise ValueError("flat_width, thickness, stress, and elastic_modulus must be positive")
    if plate_buckling_coefficient <= 0:
        raise ValueError(
            f"plate_buckling_coefficient must be positive; got {plate_buckling_coefficient}"
        )
    return (_AISI_WINTER_COEFFICIENT / sqrt(plate_buckling_coefficient)) * (w / t) * sqrt(f / e)


def aisi_effective_width(
    *,
    flat_width: Quantity,
    thickness: Quantity,
    stress: Quantity,
    elastic_modulus: Quantity,
    plate_buckling_coefficient: float = 4.0,
) -> Quantity:
    """The AISI S100 effective width b of a compression element (Winter's formula).

    Below the slenderness limit (:func:`aisi_plate_slenderness` λ ≤ 0.673) the element
    is fully effective and b = w. Above it, the reduction factor ρ = (1 − 0.22/λ)/λ
    gives the effective width b = ρ·w — the width that, carrying the edge stress
    uniformly, matches the real post-buckling capacity. Recompute the section's area
    and modulus on the effective section. Arguments are as in
    :func:`aisi_plate_slenderness`. Returns the effective width in mm.
    """
    lam = aisi_plate_slenderness(
        flat_width=flat_width,
        thickness=thickness,
        stress=stress,
        elastic_modulus=elastic_modulus,
        plate_buckling_coefficient=plate_buckling_coefficient,
    )
    w = flat_width.to("mm").magnitude
    if lam <= _AISI_SLENDERNESS_LIMIT:
        return Quantity(magnitude=w, unit="mm")  # fully effective
    rho = (1.0 - 0.22 / lam) / lam
    return Quantity(magnitude=rho * w, unit="mm")


# --- Direct Strength Method (AISI S100 Appendix 1) -------------------------
#
# The effective-width method above reduces each element and rebuilds the section. The
# Direct Strength Method takes the opposite route: it works from the *whole section's*
# elastic buckling loads — local, distortional and global — and maps each to a strength
# with its own empirical curve. It needs no effective section at all, which is why it is
# the method for shapes the effective-width rules do not cover.
#
# The price is that the elastic buckling loads are not closed-form for a real cold-formed
# shape: they come from a finite-strip or finite-element analysis (CUFSM and its kin).
# Anvilate does not compute them and does not guess them. They are caller-supplied,
# provenance-tagged, and a screen without them reports NOT_EVALUATED.

# AISI S100 Appendix 1 curve constants, per limit state.
_DSM_GLOBAL_SLENDERNESS_SPLIT = 1.5  # lambda_c at which the column curve changes branch
_DSM_LOCAL_SLENDERNESS_LIMIT = 0.776  # below this, local buckling does not reduce
_DSM_LOCAL_EXPONENT = 0.4
_DSM_LOCAL_COEFFICIENT = 0.15
_DSM_DIST_COMPRESSION_LIMIT = 0.561
_DSM_DIST_COMPRESSION_EXPONENT = 0.6
_DSM_DIST_COMPRESSION_COEFFICIENT = 0.25
_DSM_DIST_FLEXURE_LIMIT = 0.673
_DSM_DIST_FLEXURE_EXPONENT = 0.5
_DSM_DIST_FLEXURE_COEFFICIENT = 0.22
# The lateral-torsional branch points of the flexural global curve, in M_cre/M_y.
_DSM_FLEXURE_ELASTIC_LIMIT = 0.56
_DSM_FLEXURE_PLASTIC_LIMIT = 2.78

_CLAUSE_DSM = "AISI S100 Appendix 1 (Direct Strength Method)"


class DSMLimitState(StrEnum):
    """Which of the three DSM buckling modes governs a member's strength.

    The point of reporting it is that the repair differs by mode and the modes respond to
    opposite changes: a local failure is fixed by thicker material or a narrower flat, a
    distortional one by a better lip or an intermediate stiffener, and a global one by
    bracing or a shorter unbraced length. A bare capacity cannot tell them apart.
    """

    LOCAL = "local"
    DISTORTIONAL = "distortional"
    GLOBAL = "global"


class ElasticBuckling(RevalidatedModel):
    """The elastic buckling loads a DSM check runs on, and where they came from.

    ``local``, ``distortional`` and ``global_`` are the elastic critical loads (for a
    compression check) or moments (for a flexural check) of the whole section in each
    mode. They are **not** computed here: for a real cold-formed shape they come from a
    finite-strip analysis (CUFSM and its kin), and inventing them would be the worst kind
    of silent green — a plausible capacity resting on a buckling load nobody ran.

    ``source`` records where they came from, so the report cites the analysis rather than
    presenting the numbers as Anvilate's own. ``distortional`` may be ``None`` for a
    section with no distortional mode (an unlipped angle, a round tube); that is a
    declaration, not a default, and it removes the mode from the governing set rather
    than treating it as infinitely strong by accident.
    """

    model_config = ConfigDict(frozen=True)

    local: Quantity
    global_: Quantity
    source: Provenance
    distortional: Quantity | None = None

    @model_validator(mode="after")
    def _well_formed(self) -> ElasticBuckling:
        for value, name in (
            (self.local, "local"),
            (self.global_, "global_"),
            (self.distortional, "distortional"),
        ):
            if value is None:
                continue
            # The DSM nominal is the minimum of three modes, and `min()` drops a NaN rather
            # than propagating it: a non-finite distortional load left the nominal reported
            # as LOCAL-governed with the distortional mode simply gone from the envelope.
            # With one mode unknown there is no minimum.
            require_finite(value, name=f"{name} elastic buckling value")
            if value.magnitude <= 0:
                raise ValueError(f"{name} elastic buckling value must be positive; got {value}")
        if not self.source.strip():
            raise ValueError(
                "source must record where the elastic buckling values came from — the "
                "finite-strip run, the software and version, or the reference"
            )
        return self


class DSMStrength(BaseModel):
    """A DSM result: the strength in each mode, and which one governs.

    ``global_strength``, ``local_strength`` and ``distortional_strength`` are the nominal
    strengths the three DSM curves give (``distortional_strength`` is ``None`` when the
    section declares no distortional mode). ``nominal`` is the smallest of them and
    ``governing`` names which — the number and the reason, together, because they call
    for different repairs.
    """

    model_config = ConfigDict(frozen=True)

    global_strength: Quantity
    local_strength: Quantity
    nominal: Quantity
    governing: DSMLimitState
    distortional_strength: Quantity | None = None

    def __str__(self) -> str:
        return f"DSM nominal {self.nominal} governed by {self.governing.value} buckling"


class PrequalifiedLimits(BaseModel):
    """A geometry range over which the DSM curves are calibrated (AISI S100 §1.1.1.1).

    DSM's empirical curves were fitted to tested sections, and the standard lists the
    geometry each was fitted over. A section outside those limits is not forbidden — it is
    outside the calibration, and AISI requires a more conservative resistance factor for
    it. :meth:`check` returns the ratios that fall outside, so a screen can say which
    dimension took the section out rather than reporting an unqualified pass.
    """

    model_config = ConfigDict(frozen=True)

    name: str
    web_flat_to_thickness_max: float
    flange_flat_to_thickness_max: float
    lip_flat_to_thickness_max: float
    web_to_flange_ratio_max: float
    lip_to_flange_ratio_range: tuple[float, float]

    def check(
        self,
        *,
        web_flat_to_thickness: float,
        flange_flat_to_thickness: float,
        lip_flat_to_thickness: float,
        web_to_flange: float,
        lip_to_flange: float,
    ) -> tuple[str, ...]:
        """The prequalification limits this geometry falls outside, named. Empty = inside."""
        outside: list[str] = []
        for value, limit, label in (
            (web_flat_to_thickness, self.web_flat_to_thickness_max, "web h/t"),
            (flange_flat_to_thickness, self.flange_flat_to_thickness_max, "flange b/t"),
            (lip_flat_to_thickness, self.lip_flat_to_thickness_max, "lip d/t"),
            (web_to_flange, self.web_to_flange_ratio_max, "web/flange h/b"),
        ):
            if value > limit:
                outside.append(f"{label} = {value:.4g} exceeds {limit:.4g}")
        low, high = self.lip_to_flange_ratio_range
        if not low <= lip_to_flange <= high:
            outside.append(f"lip/flange d/b = {lip_to_flange:.4g} outside [{low:.4g}, {high:.4g}]")
        return tuple(outside)


# AISI S100 §1.1.1.1 prequalified geometry for a lipped channel in compression.
PREQUALIFIED_LIPPED_CHANNEL = PrequalifiedLimits(
    name="lipped channel (AISI S100 §1.1.1.1, compression)",
    web_flat_to_thickness_max=472.0,
    flange_flat_to_thickness_max=159.0,
    lip_flat_to_thickness_max=33.0,
    web_to_flange_ratio_max=10.0,
    lip_to_flange_ratio_range=(0.14, 0.87),
)


def _dsm_global_compression(yield_load: float, elastic_global: float) -> float:
    """AISI S100 Eq. 1.2.1-2/3: the column curve, P_ne, from P_y and P_cre."""
    lambda_c = sqrt(yield_load / elastic_global)
    if lambda_c <= _DSM_GLOBAL_SLENDERNESS_SPLIT:
        return 0.658 ** (lambda_c**2) * yield_load
    return (0.877 / lambda_c**2) * yield_load


def _dsm_reduced(anchor: float, elastic: float, limit: float, coeff: float, expo: float) -> float:
    """The shared DSM reduction shape: below ``limit`` slenderness nothing is lost, above
    it the strength falls as [1 − coeff·(P_cr/P_anchor)^expo]·(P_cr/P_anchor)^expo·P_anchor."""
    slenderness = sqrt(anchor / elastic)
    if slenderness <= limit:
        return anchor
    ratio = (elastic / anchor) ** expo
    return (1.0 - coeff * ratio) * ratio * anchor


def _governing(candidates: dict[DSMLimitState, float]) -> tuple[DSMLimitState, float]:
    state = min(candidates, key=lambda k: candidates[k])
    return state, candidates[state]


def dsm_compression_strength(
    *, yield_load: Quantity, elastic_buckling: ElasticBuckling
) -> DSMStrength:
    """The DSM nominal compressive strength of a cold-formed member (AISI S100 §1.2.1).

    Three curves, three modes, and the smallest governs:

    * **Global** — λ_c = √(P_y/P_cre); P_ne = 0.658^(λ_c²)·P_y up to λ_c = 1.5, then
      (0.877/λ_c²)·P_y. The familiar column curve.
    * **Local** — λ_l = √(P_ne/P_crl); no reduction below λ_l = 0.776, then
      [1 − 0.15·(P_crl/P_ne)^0.4]·(P_crl/P_ne)^0.4·P_ne. Note it is anchored on **P_ne**,
      not P_y: local buckling interacts with the global mode, so a long column's local
      strength is measured against the load global buckling already left it.
    * **Distortional** — λ_d = √(P_y/P_crd); no reduction below λ_d = 0.561, then
      [1 − 0.25·(P_crd/P_y)^0.6]·(P_crd/P_y)^0.6·P_y. Anchored on **P_y**, because the
      distortional mode does *not* interact with the global one.

    ``yield_load`` P_y = A_g·F_y, and ``elastic_buckling`` carries P_crl, P_crd and P_cre
    with their provenance. Returns a :class:`DSMStrength` naming the governing mode, since
    local, distortional and global failures call for different repairs.
    """
    if not isinstance(yield_load, Quantity):
        raise ValueError(f"yield_load must be a [force] quantity; got {yield_load!r}")
    if not yield_load.has_dimension("[force]"):
        raise ValueError(f"yield_load must be a [force] quantity; got {yield_load}")
    for value, name in (
        (elastic_buckling.local, "local"),
        (elastic_buckling.global_, "global_"),
        (elastic_buckling.distortional, "distortional"),
    ):
        if value is not None and not value.has_dimension("[force]"):
            raise ValueError(
                f"a compression check needs {name} as a [force] quantity; got {value}. "
                f"(A moment belongs to dsm_flexural_strength.)"
            )
    py = yield_load.to("kN").magnitude
    if py <= 0:
        raise ValueError(f"yield_load must be positive; got {yield_load}")
    p_ne = _dsm_global_compression(py, elastic_buckling.global_.to("kN").magnitude)
    p_nl = _dsm_reduced(
        p_ne,
        elastic_buckling.local.to("kN").magnitude,
        _DSM_LOCAL_SLENDERNESS_LIMIT,
        _DSM_LOCAL_COEFFICIENT,
        _DSM_LOCAL_EXPONENT,
    )
    candidates = {DSMLimitState.GLOBAL: p_ne, DSMLimitState.LOCAL: p_nl}
    p_nd = None
    if elastic_buckling.distortional is not None:
        p_nd = _dsm_reduced(
            py,
            elastic_buckling.distortional.to("kN").magnitude,
            _DSM_DIST_COMPRESSION_LIMIT,
            _DSM_DIST_COMPRESSION_COEFFICIENT,
            _DSM_DIST_COMPRESSION_EXPONENT,
        )
        candidates[DSMLimitState.DISTORTIONAL] = p_nd
    state, nominal = _governing(candidates)
    return DSMStrength(
        global_strength=Quantity(magnitude=p_ne, unit="kN"),
        local_strength=Quantity(magnitude=p_nl, unit="kN"),
        distortional_strength=None if p_nd is None else Quantity(magnitude=p_nd, unit="kN"),
        nominal=Quantity(magnitude=nominal, unit="kN"),
        governing=state,
    )


def dsm_flexural_strength(
    *, yield_moment: Quantity, elastic_buckling: ElasticBuckling
) -> DSMStrength:
    """The DSM nominal flexural strength of a cold-formed member (AISI S100 §1.2.2).

    The same three-mode structure as :func:`dsm_compression_strength`, with the global
    curve replaced by the lateral-torsional one, which is written in M_cre/M_y directly
    rather than through a slenderness:

    * **Global** — M_ne = M_cre below M_cre = 0.56·M_y (fully elastic LTB); M_ne = M_y
      above M_cre = 2.78·M_y (LTB does not govern); and between them the inelastic
      transition M_ne = (10/9)·M_y·(1 − 10·M_y/(36·M_cre)).
    * **Local** — anchored on M_ne, limit 0.776, the same 0.15/0.4 curve as compression.
    * **Distortional** — anchored on M_y, limit 0.673, with its own 0.22/0.5 curve. Note
      the constants differ from the compression distortional curve; they are separate
      fits, not one curve reused.

    ``yield_moment`` M_y = S_f·F_y on the gross section, and ``elastic_buckling`` carries
    M_crl, M_crd and M_cre. Returns a :class:`DSMStrength` naming the governing mode.
    """
    if not isinstance(yield_moment, Quantity):
        raise ValueError(
            f"yield_moment must be a [force] * [length] quantity; got {yield_moment!r}"
        )
    if not yield_moment.has_dimension("[force] * [length]"):
        raise ValueError(f"yield_moment must be a moment quantity; got {yield_moment}")
    for value, name in (
        (elastic_buckling.local, "local"),
        (elastic_buckling.global_, "global_"),
        (elastic_buckling.distortional, "distortional"),
    ):
        if value is not None and not value.has_dimension("[force] * [length]"):
            raise ValueError(
                f"a flexural check needs {name} as a moment quantity; got {value}. "
                f"(A force belongs to dsm_compression_strength.)"
            )
    my = yield_moment.to("kN*m").magnitude
    if my <= 0:
        raise ValueError(f"yield_moment must be positive; got {yield_moment}")
    m_cre = elastic_buckling.global_.to("kN*m").magnitude
    if m_cre < _DSM_FLEXURE_ELASTIC_LIMIT * my:
        m_ne = m_cre
    elif m_cre > _DSM_FLEXURE_PLASTIC_LIMIT * my:
        m_ne = my
    else:
        m_ne = (10.0 / 9.0) * my * (1.0 - 10.0 * my / (36.0 * m_cre))
    m_nl = _dsm_reduced(
        m_ne,
        elastic_buckling.local.to("kN*m").magnitude,
        _DSM_LOCAL_SLENDERNESS_LIMIT,
        _DSM_LOCAL_COEFFICIENT,
        _DSM_LOCAL_EXPONENT,
    )
    candidates = {DSMLimitState.GLOBAL: m_ne, DSMLimitState.LOCAL: m_nl}
    m_nd = None
    if elastic_buckling.distortional is not None:
        m_nd = _dsm_reduced(
            my,
            elastic_buckling.distortional.to("kN*m").magnitude,
            _DSM_DIST_FLEXURE_LIMIT,
            _DSM_DIST_FLEXURE_COEFFICIENT,
            _DSM_DIST_FLEXURE_EXPONENT,
        )
        candidates[DSMLimitState.DISTORTIONAL] = m_nd
    state, nominal = _governing(candidates)
    return DSMStrength(
        global_strength=Quantity(magnitude=m_ne, unit="kN*m"),
        local_strength=Quantity(magnitude=m_nl, unit="kN*m"),
        distortional_strength=None if m_nd is None else Quantity(magnitude=m_nd, unit="kN*m"),
        nominal=Quantity(magnitude=nominal, unit="kN*m"),
        governing=state,
    )


def dsm_scorecard(
    name: str,
    *,
    demand: Quantity,
    strength: DSMStrength | None,
    required: float = 1.0,
    outside_prequalified: tuple[str, ...] = (),
) -> ScorecardEntry:
    """Screen a demand against a DSM nominal strength → a :class:`ScorecardEntry`.

    The safety factor is the nominal strength over the ``demand``, judged against
    ``required``. The detail names the governing buckling mode, because that is what says
    which way to move the section — thicker material for a local failure, a better lip for
    a distortional one, bracing for a global one.

    ``strength`` of ``None`` — no elastic buckling analysis supplied — is
    ``NOT_EVALUATED``, never a silent pass: DSM cannot be run without those numbers, and
    Anvilate will not invent them.

    ``outside_prequalified`` is whatever :meth:`PrequalifiedLimits.check` returned. A
    section outside the calibrated geometry is **not** failed — AISI permits it with a
    more conservative resistance factor — but it cannot be reported as a plain pass
    either, so it is surfaced in the detail and the entry is downgraded to
    ``NOT_EVALUATED`` when it would otherwise have passed.
    """
    if strength is not None and not isinstance(strength, DSMStrength):
        raise ValueError(f"strength must be a DSMStrength; got {strength!r}")
    if strength is None:
        return ScorecardEntry(
            name=name,
            status=CheckStatus.NOT_EVALUATED,
            detail=(
                "not evaluated — no elastic buckling analysis supplied. DSM runs on the "
                "section's local, distortional and global elastic buckling values, which "
                "come from a finite-strip analysis, not from this library."
            ),
            reference=_CLAUSE_DSM,
        )
    demand_value = abs(demand.to(strength.nominal.unit).magnitude)
    computed = None if demand_value == 0 else strength.nominal.magnitude / demand_value
    entry = ScorecardEntry.from_safety_factor(name, computed=computed, required=required)
    detail = (
        f"{strength.governing.value} buckling governs: nominal {strength.nominal.magnitude:.3g} "
        f"{strength.nominal.unit} against a demand of {demand_value:.3g} {strength.nominal.unit}"
    )
    if outside_prequalified:
        detail = (
            f"outside the AISI S100 §1.1.1.1 prequalified geometry "
            f"({'; '.join(outside_prequalified)}) — the DSM curves are not calibrated here "
            f"and a more conservative resistance factor is required. {detail}"
        )
        if entry.status is CheckStatus.PASS:
            return entry.model_copy(
                update={
                    "status": CheckStatus.NOT_EVALUATED,
                    "detail": detail,
                    "reference": _CLAUSE_DSM,
                    "safety_factor": None,
                }
            )
    return entry.model_copy(update={"detail": detail, "reference": _CLAUSE_DSM})
