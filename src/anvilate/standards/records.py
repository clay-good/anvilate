"""Shared building blocks for the standards databases.

A database record is a set of provenance-tagged property values. Materials,
components, and fastener tables all reuse the same pieces: a citation
(:class:`PropertyCitation`), a dimensional value plus its citation
(:class:`QuantityProperty`), a dimensionless value plus its citation
(:class:`ScalarProperty`), and the :func:`dimensioned` helper that pins a
property's dimension at validation time.
"""

from __future__ import annotations

from pydantic import AfterValidator, BaseModel, ConfigDict, model_validator

from ..units import DimensionError, Quantity

__all__ = [
    "PropertyCitation",
    "QuantityProperty",
    "ScalarProperty",
    "dimensioned",
]


class _Base(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class PropertyCitation(_Base):
    """Where a single property value came from and under what condition.

    ``estimated`` marks a value derived from other properties rather than
    measured (e.g. an endurance limit estimated from ultimate strength); such a
    value must name the ``method`` so any check consuming it can carry the
    caveat into its report.
    """

    source: str
    condition: str  # temper and/or test condition, e.g. "T6 temper, room temperature"
    license: str
    retrieved: str  # ISO date the value was recorded
    estimated: bool = False
    method: str | None = None

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
