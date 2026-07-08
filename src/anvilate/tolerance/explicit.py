"""Explicit, per-dimension tolerances declared on a spec's dimensions.

Where a general tolerance class governs every untoleranced dimension, an explicit
tolerance overrides it for one dimension. This module gives the three typed forms
a spec can declare — a symmetric ``±`` band, an asymmetric upper/lower limit pair,
and an ISO 286 fit designation (``H7``) resolved from the encoded tables — a
common resolution: each ``resolve(nominal)`` yields a :class:`ResolvedTolerance`
with the same signed deviations and feature-size bounds, so a drawing or DFM layer
reads a dimension's permitted band the same way regardless of how it was declared.

The discriminated ``Tolerance`` union is the field type a Spec IR dimension will
carry; wiring it onto the IR's dimensioned fields is a separate step.
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, model_validator

from ..units import Quantity, require_dimension
from .iso286 import zone_limits

__all__ = [
    "ResolvedTolerance",
    "SymmetricTolerance",
    "LimitTolerance",
    "FitTolerance",
    "Tolerance",
]

_Length = Annotated[Quantity, AfterValidator(require_dimension("[length]", name="tolerance"))]


class _Base(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ResolvedTolerance(BaseModel):
    """A resolved explicit tolerance: signed deviations and feature-size bounds.

    ``upper`` and ``lower`` are the signed deviations from the basic size; the
    permitted feature size runs from ``nominal + lower`` to ``nominal + upper``.
    This is the general drawing-callout form; :class:`LimitDeviations` is the
    ISO-286-specific resolution a :class:`FitTolerance` resolves through.
    """

    model_config = ConfigDict(frozen=True)

    nominal: Quantity
    upper: Quantity  # signed deviation, a length
    lower: Quantity  # signed deviation, a length
    label: str  # human designation, e.g. "±0.100 mm" or "H7"
    source: str | None  # citation for a fit; None for a user-declared band

    @property
    def width(self) -> Quantity:
        """The total width of the tolerance zone (``upper - lower``)."""
        return Quantity(
            magnitude=self.upper.to("mm").magnitude - self.lower.to("mm").magnitude,
            unit="mm",
        )

    @property
    def min_size(self) -> Quantity:
        """The smallest permitted feature size (``nominal + lower``)."""
        return Quantity(
            magnitude=self.nominal.to("mm").magnitude + self.lower.to("mm").magnitude,
            unit="mm",
        )

    @property
    def max_size(self) -> Quantity:
        """The largest permitted feature size (``nominal + upper``)."""
        return Quantity(
            magnitude=self.nominal.to("mm").magnitude + self.upper.to("mm").magnitude,
            unit="mm",
        )

    def __str__(self) -> str:
        u = self.upper.to("mm").magnitude
        low = self.lower.to("mm").magnitude
        return f"{self.nominal} {self.label} ({u:+.3f} / {low:+.3f} mm)"


class SymmetricTolerance(_Base):
    """A symmetric ± tolerance, e.g. ``±0.1 mm``."""

    type: Literal["symmetric"] = "symmetric"
    plus_minus: _Length

    @model_validator(mode="after")
    def _non_negative(self) -> SymmetricTolerance:
        if self.plus_minus.to("mm").magnitude < 0:
            raise ValueError(f"a symmetric ± tolerance must be non-negative; got {self.plus_minus}")
        return self

    def resolve(self, nominal: Quantity) -> ResolvedTolerance:
        pm = self.plus_minus.to("mm").magnitude
        return ResolvedTolerance(
            nominal=nominal,
            upper=Quantity(magnitude=pm, unit="mm"),
            lower=Quantity(magnitude=-pm, unit="mm"),
            label=f"±{pm:.3f} mm",
            source=None,
        )


class LimitTolerance(_Base):
    """An asymmetric tolerance given as signed upper/lower limit deviations."""

    type: Literal["limits"] = "limits"
    upper: _Length  # signed deviation from the basic size
    lower: _Length  # signed deviation from the basic size

    @model_validator(mode="after")
    def _ordered(self) -> LimitTolerance:
        if self.upper.to("mm").magnitude < self.lower.to("mm").magnitude:
            raise ValueError(
                f"upper deviation {self.upper} must be at least the lower deviation {self.lower}"
            )
        return self

    def resolve(self, nominal: Quantity) -> ResolvedTolerance:
        u = self.upper.to("mm").magnitude
        low = self.lower.to("mm").magnitude
        return ResolvedTolerance(
            nominal=nominal,
            upper=Quantity(magnitude=u, unit="mm"),
            lower=Quantity(magnitude=low, unit="mm"),
            label=f"{u:+.3f}/{low:+.3f} mm",
            source=None,
        )


class FitTolerance(_Base):
    """An ISO 286 fit designation for a single feature, e.g. ``H7`` or ``g6``."""

    type: Literal["fit"] = "fit"
    designation: str

    def resolve(self, nominal: Quantity) -> ResolvedTolerance:
        ld = zone_limits(self.designation, nominal)
        return ResolvedTolerance(
            nominal=nominal,
            upper=ld.upper,
            lower=ld.lower,
            label=ld.designation,
            source=ld.source,
        )


Tolerance = Annotated[
    SymmetricTolerance | LimitTolerance | FitTolerance,
    Field(discriminator="type"),
]
