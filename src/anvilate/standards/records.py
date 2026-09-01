"""Shared building blocks for the standards databases.

A database record is a set of provenance-tagged property values. Materials,
components, and fastener tables all reuse the same pieces: a citation
(:class:`PropertyCitation`), a dimensional value plus its citation
(:class:`QuantityProperty`), a dimensionless value plus its citation
(:class:`ScalarProperty`), and the :func:`dimensioned` helper that pins a
property's dimension at validation time.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import AfterValidator, ConfigDict, model_validator

from .._models import Provenance, RevalidatedModel
from ..units import DimensionError, Quantity

__all__ = [
    "AllowableBasis",
    "InsufficientBasis",
    "PropertyCitation",
    "QuantityProperty",
    "ScalarProperty",
    "dimensioned",
    "require_basis",
]


class _Base(RevalidatedModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class AllowableBasis(StrEnum):
    """How much of the population a strength value is guaranteed to cover.

    The distinction MIL-HDBK-5 draws, and the one that decides whether a number may be
    used as a *design allowable* at all. A typical value is the middle of the scatter:
    roughly half the material is weaker than it. A specification minimum is the floor the
    producer guarantees. A- and B-basis are statistical lower tolerance bounds — 99% and
    90% of the population exceed them, each at 95% confidence — and aerospace primary
    structure requires them.

    Using a typical value where a code demands a minimum is the whole reason this exists.
    It is not a small error: for 6061-T6 the ASM typical yield is 276 MPa against the
    240 MPa the aluminum specification guarantees, so a screen built on the typical value
    reports 15% more capacity than the material is sold with.
    """

    TYPICAL = "typical"  # handbook mean; about half the population is weaker
    SPECIFICATION_MINIMUM = "specification_minimum"  # the floor the producer guarantees
    B_BASIS = "b_basis"  # 90% of the population exceeds it, 95% confidence
    A_BASIS = "a_basis"  # 99% of the population exceeds it, 95% confidence


# Weakest claim first. A requirement for a basis is satisfied by anything at or above it,
# so the ordering is the whole semantics of `meets_basis` and is written down once.
_BASIS_ORDER: tuple[AllowableBasis, ...] = (
    AllowableBasis.TYPICAL,
    AllowableBasis.SPECIFICATION_MINIMUM,
    AllowableBasis.B_BASIS,
    AllowableBasis.A_BASIS,
)


class PropertyCitation(_Base):
    """Where a single property value came from and under what condition.

    ``estimated`` marks a value derived from other properties rather than
    measured (e.g. an endurance limit estimated from ultimate strength); such a
    value must name the ``method`` so any check consuming it can carry the
    caveat into its report.

    ``basis`` says which population claim the value carries, for the properties where
    that is a meaningful question — strengths, essentially. ``None`` means *unclassified*,
    which is deliberately not the same as ``TYPICAL``: an unclassified value cannot
    satisfy any basis requirement, so a record nobody has looked at fails a check that
    demands a minimum rather than passing as though somebody had.
    """

    source: Provenance
    condition: str  # temper and/or test condition, e.g. "T6 temper, room temperature"
    license: Provenance
    retrieved: str  # ISO date the value was recorded
    estimated: bool = False
    method: str | None = None
    basis: AllowableBasis | None = None

    def meets_basis(self, required: AllowableBasis) -> bool:
        """Whether this value's basis is at least ``required``. Unclassified never is."""
        if self.basis is None:
            return False
        return _BASIS_ORDER.index(self.basis) >= _BASIS_ORDER.index(required)

    @model_validator(mode="after")
    def _estimate_names_method(self) -> PropertyCitation:
        if self.estimated and not self.method:
            raise ValueError("an estimated property must name the estimation method")
        return self


class QuantityProperty(_Base):
    """A dimensional property: a :class:`Quantity` plus its citation."""

    quantity: Quantity
    citation: PropertyCitation


class ScalarProperty(_Base):
    """A dimensionless property (e.g. Poisson's ratio) plus its citation."""

    value: float
    citation: PropertyCitation


def dimensioned(expected: str, name: str) -> AfterValidator:
    """A validator pinning the dimension of a :class:`QuantityProperty`.

    On mismatch it raises a :class:`~anvilate.units.DimensionError` naming the
    property and the received and expected dimensions; Pydantic supplies the
    offending field path.
    """

    def _check(prop: QuantityProperty) -> QuantityProperty:
        if not prop.quantity.has_dimension(expected):
            raise DimensionError(
                f"{name} expects a {expected} quantity "
                f"but received {prop.quantity.dimensionality} ({prop.quantity})"
            )
        return prop

    return AfterValidator(_check)


class InsufficientBasis(ValueError):
    """A strength value's population claim is weaker than the check demands.

    Raised rather than returned so a check cannot proceed on it by accident. The message
    names the record, the property, what it carries, and what was asked for, because the
    fix is a data decision — find a value on the right basis, or drop the requirement and
    say why — and neither can be made from "insufficient basis".
    """


def require_basis(
    prop: QuantityProperty, required: AllowableBasis, *, material_id: str, name: str
) -> Quantity:
    """The property's quantity, having checked its basis is at least ``required``.

    A check whose code demands a design allowable calls this instead of reading
    ``.quantity`` directly. An *unclassified* value fails: a record nobody has looked at
    cannot satisfy a basis requirement by default, or the requirement means nothing.
    """
    if prop.citation.meets_basis(required):
        return prop.quantity
    carried = "unclassified" if prop.citation.basis is None else prop.citation.basis.value
    raise InsufficientBasis(
        f"{material_id} {name} is {carried} ({prop.citation.source}), and this check "
        f"requires at least {required.value}. A typical value sits in the middle of the "
        f"scatter, so roughly half the material is weaker than it; using one where a code "
        f"demands a minimum overstates the capacity the material is sold with"
    )
