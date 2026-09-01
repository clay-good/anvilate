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

Sources: NDS (National Design Specification for Wood Construction) §4.3, Table 4.3.1 —
the applicability of each adjustment factor to each reference design value.
"""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum
from math import isfinite

from pydantic import ConfigDict, model_validator

from .._models import RevalidatedModel, cited
from ..units import Quantity

__all__ = [
    "NDS_APPLICABLE_FACTORS",
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


class TimberDesignValue(RevalidatedModel):
    """One NDS reference design value, with what it is a value *of*.

    ``value`` is the tabulated reference number — before any adjustment. What it becomes
    is :meth:`adjusted`, and the factors it will accept are the ones NDS Table 4.3.1 lists
    for its :attr:`property`.
    """

    model_config = ConfigDict(frozen=True)

    standard: cited(
        "the standard this design value comes from; the number alone does not say which "
        "piece of wood it describes"
    )
    edition: cited(
        "the edition this design value comes from; the number alone does not say which "
        "piece of wood it describes"
    )
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
                raise ValueError(
                    f"a timber design value must state its {field}; the number alone does "
                    f"not say which piece of wood it describes"
                )
        if not self.value.has_dimension("[pressure]"):
            raise ValueError(f"a design value is a stress or a modulus; got {self.value}")
        magnitude = self.value.to("MPa").magnitude
        if not isfinite(magnitude) or magnitude <= 0:
            raise ValueError(f"a design value must be positive and finite; got {self.value}")
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
            raise ValueError(
                f"NDS Table 4.3.1 does not apply {inapplicable} to {self.property.value}; "
                f"it takes {sorted(allowed)}. A factor the table omits is not a "
                f"conservative extra — applying C_D to a modulus, for one, makes the "
                f"member stiffer than the standard allows on exactly the check deflection "
                f"governs"
            )
        for name, factor in factors.items():
            if not isfinite(factor) or factor <= 0:
                raise ValueError(
                    f"the adjustment factor {name} must be positive and finite; got {factor}"
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
