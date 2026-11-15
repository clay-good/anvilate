"""NDS reference design values as records, and the factor chain each one actually takes.

A reference design value is a number with four things attached, and a table that carries
only the number is how the wrong one gets used:

1. **Which property it is.** F_b, F_t, F_v, F_c, F_c⊥, E and E_min are seven different
   numbers for the same piece of wood, and they do not take the same adjustments.
2. **The species and grade.** Southern Pine No. 2 and Douglas Fir-Larch No. 2 are
   different values from different tables.
3. **The size classification.** Dimension lumber, beams and stringers, and posts and
   timbers are graded to different rules, and the size factor works differently for each.
4. **The standard and its edition.** Reference values move between editions; a 2018 value
   in a 2024 calculation is a number nobody published for that calculation.

So :class:`TimberDesignValue` carries all four and refuses to be built without them.

**The refusal that matters is the factor chain.** NDS Table 4.3.1 says which adjustment
applies to which value, and the two that catch people are that **the load duration factor
C_D does not apply to compression perpendicular to grain or to either modulus**, and that
**the size factor C_F does not apply to shear or to the moduli**. The library's own
docstring has always said the caller "simply omits" those from the chain — which is a rule
stated in prose and enforced by nobody. :meth:`TimberDesignValue.adjusted` enforces it:
hand it a C_D on an E and it refuses, naming the factor and the property.

Applying C_D to a modulus is not a small error. On a snow load it is a 15% stiffer beam
than the standard allows, and deflection is usually what governs a timber beam — so the
mistake shows up as a member that passes the check it was going to fail.

A connection is the same idea one table over. :class:`ConnectionDesignValue` carries a
reference lateral (Z), withdrawal (W) or head pull-through (W_H) value, and the factors it
takes are NDS Table 11.3.1's — a different set, with two footnote rules a chain composed
by hand loses: C_D is capped at 1.6 for a connection where a member takes 2.0 on impact,
and the wet service factor does not apply to a toe-nail loaded in withdrawal.

Sources: NDS (National Design Specification for Wood Construction) §4.3, Table 4.3.1 —
the applicability of each adjustment factor to each reference design value; §11.3,
Table 11.3.1 — the same for connections, with its footnotes 1 and 2.
"""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum
from math import isfinite
from typing import TYPE_CHECKING

from pydantic import ConfigDict, model_validator

from .._models import RevalidatedModel, cited
from ..refusal import RefusalError, Remedy
from ..units import Quantity

_TIMBER_RECORD_SOURCE = (
    "the grade stamp, material certificate, cited NDS Supplement table, or project specification"
)
_TIMBER_FACTOR_SOURCE = "the governing NDS edition, Table 4.3.1, and selected conditions"


class _TimberRecordError(RefusalError, ValueError):
    """Invalid timber reference-value input with a machine-readable repair."""


def _timber_record_refusal(message: str, *, subject: str, source: str) -> _TimberRecordError:
    return _TimberRecordError(
        message,
        remedies=(Remedy(action="replace", subject=subject, source=source),),
    )


__all__ = [
    "MAX_CONNECTION_LOAD_DURATION",
    "NDS_APPLICABLE_FACTORS",
    "NDS_CONNECTION_FACTORS",
    "ConnectionDesignValue",
    "ConnectionLoad",
    "SizeClassification",
    "TimberDesignValue",
    "TimberProperty",
]


class TimberProperty(StrEnum):
    """Which reference design value a number is.

    Seven different numbers for the same piece of wood, and the reason this enum exists
    rather than a string: the factor chain each one takes is different, and the difference
    is not visible in the number.
    """

    BENDING = "F_b"
    TENSION = "F_t"
    SHEAR = "F_v"
    COMPRESSION_PARALLEL = "F_c"
    COMPRESSION_PERPENDICULAR = "F_c_perp"
    MODULUS = "E"
    MODULUS_MIN = "E_min"


class SizeClassification(StrEnum):
    """How the piece was graded, which decides how the size factor behaves.

    Dimension lumber (nominal 2 to 4 in thick) is graded to one set of rules and takes the
    tabulated C_F; beams and stringers and posts and timbers are 5 in and thicker, graded
    to another, and take C_F = (12/d)^(1/9) once the depth exceeds 12 in. A value read from
    the dimension-lumber table and adjusted as a timber is two mistakes, not one.
    """

    DIMENSION_LUMBER = "dimension lumber"
    BEAMS_AND_STRINGERS = "beams and stringers"
    POSTS_AND_TIMBERS = "posts and timbers"
    BOARDS = "boards"


# NDS Table 4.3.1 — which adjustment factor applies to which reference design value, for
# sawn lumber. Read off the published applicability equations rather than recalled:
#
#   F'_b   = F_b · C_D · C_M · C_t · C_L · C_F · C_fu · C_i · C_r
#   F'_t   = F_t · C_D · C_M · C_t · C_F · C_i
#   F'_v   = F_v · C_D · C_M · C_t · C_i
#   F'_c⊥  = F_c⊥ · C_M · C_t · C_i · C_b
#   F'_c   = F_c · C_D · C_M · C_t · C_F · C_i · C_P
#   E'     = E · C_M · C_t · C_i
#   E'_min = E_min · C_M · C_t · C_i · C_T
#
# The two absences that matter: C_D is missing from F_c⊥, E and E_min, and C_F is missing
# from F_v, F_c⊥, E and E_min.
NDS_APPLICABLE_FACTORS: dict[TimberProperty, frozenset[str]] = {
    TimberProperty.BENDING: frozenset({"C_D", "C_M", "C_t", "C_L", "C_F", "C_fu", "C_i", "C_r"}),
    TimberProperty.TENSION: frozenset({"C_D", "C_M", "C_t", "C_F", "C_i"}),
    TimberProperty.SHEAR: frozenset({"C_D", "C_M", "C_t", "C_i"}),
    TimberProperty.COMPRESSION_PERPENDICULAR: frozenset({"C_M", "C_t", "C_i", "C_b"}),
    TimberProperty.COMPRESSION_PARALLEL: frozenset({"C_D", "C_M", "C_t", "C_F", "C_i", "C_P"}),
    TimberProperty.MODULUS: frozenset({"C_M", "C_t", "C_i"}),
    TimberProperty.MODULUS_MIN: frozenset({"C_M", "C_t", "C_i", "C_T"}),
}

# The dimension a property carries. The moduli are stiffnesses and the rest are strengths;
# both are [pressure], which is exactly why the record has to say which it is.
_MODULI = (TimberProperty.MODULUS, TimberProperty.MODULUS_MIN)


if TYPE_CHECKING:
    _TimberStandard = str
else:
    _TimberStandard = cited(
        "the standard this design value comes from; the number alone does not say which "
        "piece of wood it describes"
    )


if TYPE_CHECKING:
    _TimberEdition = str
else:
    _TimberEdition = cited(
        "the edition this design value comes from; the number alone does not say which "
        "piece of wood it describes"
    )


class TimberDesignValue(RevalidatedModel):
    """One NDS reference design value, with what it is a value *of*.

    ``value`` is the tabulated reference number — before any adjustment. What it becomes
    is :meth:`adjusted`, and the factors it will accept are the ones NDS Table 4.3.1 lists
    for its :attr:`property`.
    """

    model_config = ConfigDict(frozen=True)

    standard: _TimberStandard
    edition: _TimberEdition
    table: str
    species: str
    grade: str
    size_classification: SizeClassification
    property: TimberProperty
    value: Quantity

    @model_validator(mode="after")
    def _well_formed(self) -> TimberDesignValue:
        for field, text in (
            ("table", self.table),
            ("species", self.species),
            ("grade", self.grade),
        ):
            if not text.strip():
                raise _timber_record_refusal(
                    f"a timber design value must state its {field}; the number alone does "
                    f"not say which piece of wood it describes",
                    subject=field,
                    source=_TIMBER_RECORD_SOURCE,
                )
        if not self.value.has_dimension("[pressure]"):
            raise _timber_record_refusal(
                f"a design value is a stress or a modulus; got {self.value}",
                subject="value",
                source=_TIMBER_RECORD_SOURCE,
            )
        magnitude = self.value.to("MPa").magnitude
        if not isfinite(magnitude) or magnitude <= 0:
            raise _timber_record_refusal(
                f"a design value must be positive and finite; got {self.value}",
                subject="value",
                source=_TIMBER_RECORD_SOURCE,
            )
        return self

    @property
    def applicable_factors(self) -> frozenset[str]:
        """The adjustment factors NDS Table 4.3.1 lists for this property."""
        return NDS_APPLICABLE_FACTORS[self.property]

    def adjusted(self, factors: Mapping[str, float]) -> Quantity:
        """The adjusted design value F' = value · ∏ Cᵢ, refusing a factor that does not apply.

        The strict path, and the short one. :func:`~anvilate.analysis.nds_timber.
        nds_adjusted_design_value` multiplies whatever it is given, which is right for a
        caller composing a chain by hand and wrong for one who has a record saying what the
        number is a value *of*.

        **The two refusals that catch people**: C_D on compression perpendicular to grain
        or on either modulus, and C_F on shear or on either modulus. Applying C_D to a
        modulus at a snow load is a 15% stiffer beam than the standard allows, and
        deflection is usually what governs — so the mistake shows up as a member passing
        the check it was about to fail.
        """
        allowed = self.applicable_factors
        offered = set(factors)
        inapplicable = sorted(offered - allowed)
        if inapplicable:
            raise _timber_record_refusal(
                f"NDS Table 4.3.1 does not apply {inapplicable} to {self.property.value}; "
                f"it takes {sorted(allowed)}. A factor the table omits is not a "
                f"conservative extra — applying C_D to a modulus, for one, makes the "
                f"member stiffer than the standard allows on exactly the check deflection "
                f"governs",
                subject="adjustment factors",
                source=_TIMBER_FACTOR_SOURCE,
            )
        for name, factor in factors.items():
            if not isfinite(factor) or factor <= 0:
                raise _timber_record_refusal(
                    f"the adjustment factor {name} must be positive and finite; got {factor}",
                    subject=f"adjustment factor {name}",
                    source=_TIMBER_FACTOR_SOURCE,
                )
        product = 1.0
        for factor in factors.values():
            product *= factor
        return Quantity(magnitude=self.value.magnitude * product, unit=self.value.unit)

    def __str__(self) -> str:
        kind = "modulus" if self.property in _MODULI else "stress"
        return (
            f"{self.standard}:{self.edition} {self.table} — {self.species} {self.grade} "
            f"({self.size_classification.value}), {self.property.value} = {self.value} "
            f"[{kind}]"
        )


class ConnectionLoad(StrEnum):
    """What a connection's reference design value is a value *of*, per NDS Table 11.3.1.

    Three numbers for the same fastener, and they take three different factor chains: the
    group action and geometry factors reduce a lateral value and have nothing to do with a
    withdrawal one, which is a difference no spreadsheet column shows.
    """

    LATERAL = "Z"
    WITHDRAWAL = "W"
    PULL_THROUGH = "W_H"


# NDS Table 11.3.1 — which adjustment factor applies to which connection design value,
# read off the published table rather than recalled:
#
#   Z'   = Z   · C_D · C_M · C_t · C_g · C_Δ · C_eg · C_di · C_tn   (dowel-type fasteners)
#   W'   = W   · C_D · C_M · C_t ·             C_eg ·        C_tn
#   W'_H = W_H · C_D · C_M · C_t
#
# The absences that matter: **no group action and no geometry factor on a withdrawal
# value**. Both describe how a row of fasteners shares a load across a shear plane, and a
# fastener pulled straight out has no shear plane to share.
#
# Split rings, shear plates, timber rivets and spike grids are rows of the same table with
# their own factors (C_d, C_st); they are not covered here, so their rows are not claimed.
NDS_CONNECTION_FACTORS: dict[ConnectionLoad, frozenset[str]] = {
    ConnectionLoad.LATERAL: frozenset(
        {"C_D", "C_M", "C_t", "C_g", "C_Delta", "C_eg", "C_di", "C_tn"}
    ),
    ConnectionLoad.WITHDRAWAL: frozenset({"C_D", "C_M", "C_t", "C_eg", "C_tn"}),
    ConnectionLoad.PULL_THROUGH: frozenset({"C_D", "C_M", "C_t"}),
}

#: NDS Table 11.3.1 footnote 1: the load duration factor does not exceed 1.6 for a
#: connection. A member under an impact load takes C_D = 2.0 (Table 2.3.2) and the
#: connection joining it does not, so one load case carries two different C_D values and
#: the connection's is the one a chain copied from the member gets wrong.
MAX_CONNECTION_LOAD_DURATION = 1.6

#: The dimension each kind of value carries. A withdrawal value is per inch of thread
#: penetration, and multiplying it by a penetration is the step that makes it a force.
_CONNECTION_DIMENSIONS: dict[ConnectionLoad, str] = {
    ConnectionLoad.LATERAL: "[force]",
    ConnectionLoad.WITHDRAWAL: "[force] / [length]",
    ConnectionLoad.PULL_THROUGH: "[force]",
}

_CONNECTION_RECORD_SOURCE = (
    "the fastener schedule and the cited NDS connection table for this fastener and species"
)
_CONNECTION_FACTOR_SOURCE = (
    "the governing NDS edition, Table 11.3.1, and the connection's conditions"
)


class ConnectionDesignValue(RevalidatedModel):
    """One NDS reference connection design value, with what it is a value *of*.

    ``value`` is the tabulated reference number before adjustment — Z in pounds, W in
    pounds per inch of penetration. What it becomes is :meth:`adjusted`, and the factors
    it accepts are NDS Table 11.3.1's for its :attr:`load`.

    ``toe_nailed`` is declared rather than inferred because footnote 2 turns on it: the
    wet service factor does not apply to a toe-nail loaded in withdrawal, and a chain that
    carries C_M anyway is wetter wood counted twice.
    """

    model_config = ConfigDict(frozen=True)

    standard: _TimberStandard
    edition: _TimberEdition
    table: str
    fastener: str
    load: ConnectionLoad
    value: Quantity
    toe_nailed: bool = False

    @model_validator(mode="after")
    def _well_formed(self) -> ConnectionDesignValue:
        for field, text in (("table", self.table), ("fastener", self.fastener)):
            if not text.strip():
                raise _timber_record_refusal(
                    f"a connection design value must state its {field}; the number alone "
                    f"does not say which fastener in which member it describes",
                    subject=field,
                    source=_CONNECTION_RECORD_SOURCE,
                )
        wanted = _CONNECTION_DIMENSIONS[self.load]
        if not self.value.has_dimension(wanted):
            raise _timber_record_refusal(
                f"a {self.load.value} value is a {wanted}; got {self.value}. A withdrawal "
                f"value is per inch of penetration and a lateral one is not, so the two "
                f"cannot be told apart by their number",
                subject="value",
                source=_CONNECTION_RECORD_SOURCE,
            )
        if not isfinite(self.value.magnitude) or self.value.magnitude <= 0:
            raise _timber_record_refusal(
                f"a connection design value must be positive and finite; got {self.value}",
                subject="value",
                source=_CONNECTION_RECORD_SOURCE,
            )
        if self.toe_nailed and self.load is ConnectionLoad.PULL_THROUGH:
            raise _timber_record_refusal(
                "head pull-through is not a toe-nail condition; NDS §12.5.4 gives the "
                "toe-nail factor for lateral and withdrawal values only",
                subject="toe_nailed",
                source=_CONNECTION_RECORD_SOURCE,
            )
        return self

    @property
    def applicable_factors(self) -> frozenset[str]:
        """The adjustment factors NDS Table 11.3.1 lists for this kind of value."""
        return NDS_CONNECTION_FACTORS[self.load]

    def adjusted(self, factors: Mapping[str, float]) -> Quantity:
        """The adjusted connection value Z' (or W', W'_H), refusing what does not apply.

        Three refusals, all of them from Table 11.3.1 and its footnotes:

        - **A factor the row does not list.** The group action factor C_g and the geometry
          factor C_Δ are on the lateral row and not the withdrawal one. Both describe how
          fasteners share a load across a shear plane, and a fastener pulled straight out
          has none; applying them to a withdrawal value reduces it for a mechanism that is
          not acting.
        - **C_D above 1.6** (footnote 1). A member under an impact load takes C_D = 2.0 and
          the connection joining it does not. One load case, two different factors, and a
          chain copied across from the member overstates the connection by 25%.
        - **C_M on a toe-nail in withdrawal** (footnote 2). The tabulated toe-nail
          withdrawal value already accounts for the condition.
        """
        allowed = self.applicable_factors
        inapplicable = sorted(set(factors) - allowed)
        if inapplicable:
            raise _timber_record_refusal(
                f"NDS Table 11.3.1 does not apply {inapplicable} to a {self.load.value} "
                f"value; it takes {sorted(allowed)}. The group action and geometry factors "
                f"describe fasteners sharing a load across a shear plane, and a fastener "
                f"loaded in withdrawal has none",
                subject="adjustment factors",
                source=_CONNECTION_FACTOR_SOURCE,
            )
        for name, factor in factors.items():
            if not isfinite(factor) or factor <= 0:
                raise _timber_record_refusal(
                    f"the adjustment factor {name} must be positive and finite; got {factor}",
                    subject=f"adjustment factor {name}",
                    source=_CONNECTION_FACTOR_SOURCE,
                )
        duration = factors.get("C_D")
        if duration is not None and duration > MAX_CONNECTION_LOAD_DURATION:
            raise _timber_record_refusal(
                f"NDS Table 11.3.1 footnote 1 caps C_D at {MAX_CONNECTION_LOAD_DURATION} "
                f"for a connection; got {duration}. The member it joins may take 2.0 under "
                f"an impact load, and copying that across overstates the connection",
                subject="adjustment factors",
                source=_CONNECTION_FACTOR_SOURCE,
            )
        if self.toe_nailed and self.load is ConnectionLoad.WITHDRAWAL and "C_M" in factors:
            raise _timber_record_refusal(
                "NDS Table 11.3.1 footnote 2 (and §12.5.4.1): the wet service factor does "
                "not apply to a toe-nail loaded in withdrawal; the tabulated value already "
                "accounts for the condition",
                subject="adjustment factors",
                source=_CONNECTION_FACTOR_SOURCE,
            )
        product = 1.0
        for factor in factors.values():
            product *= factor
        return Quantity(magnitude=self.value.magnitude * product, unit=self.value.unit)

    def withdrawal_capacity(self, penetration: Quantity, factors: Mapping[str, float]) -> Quantity:
        """W' · p — the adjusted withdrawal value times the thread penetration.

        The one step between a withdrawal table and a force. The tabulated W is per inch
        of penetration into the main member, and the penetration is the *threaded* length
        in that member, not the fastener's overall length.
        """
        if self.load is not ConnectionLoad.WITHDRAWAL:
            raise _timber_record_refusal(
                f"withdrawal capacity needs a withdrawal value; this record is "
                f"{self.load.value}, which is already a force",
                subject="load",
                source=_CONNECTION_RECORD_SOURCE,
            )
        if not isinstance(penetration, Quantity) or not penetration.has_dimension("[length]"):
            raise _timber_record_refusal(
                f"penetration is a [length]; got {penetration!r}",
                subject="penetration",
                source="the fastener schedule: the threaded length in the main member",
            )
        if not isfinite(penetration.magnitude) or penetration.magnitude <= 0:
            raise _timber_record_refusal(
                f"penetration must be positive and finite; got {penetration}",
                subject="penetration",
                source="the fastener schedule: the threaded length in the main member",
            )
        # `Quantity` does not define `*` between two quantities, deliberately: the unit
        # the product is in has to be written down somewhere, and here it is pounds.
        adjusted = self.adjusted(factors).to("lbf/inch").magnitude
        return Quantity(magnitude=adjusted * penetration.to("inch").magnitude, unit="lbf")

    def __str__(self) -> str:
        toe = ", toe-nailed" if self.toe_nailed else ""
        return (
            f"{self.standard}:{self.edition} {self.table} — {self.fastener}{toe}, "
            f"{self.load.value} = {self.value}"
        )
