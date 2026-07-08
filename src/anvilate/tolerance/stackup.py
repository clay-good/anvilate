"""One-dimensional tolerance stack-up analysis over a dimension chain.

A stack-up sums a chain of directed dimensions into a resulting gap and asks how
much the gap can vary once each dimension flexes within its tolerance. Each
contributor's resolved tolerance is recentred on its own mean and reduced to an
equal-bilateral half-width, so an asymmetric zone stacks correctly:

* the **worst-case** band adds every half-width — the gap can reach it, but only
  when every dimension is simultaneously at its extreme, which is rare;
* the **root-sum-square** band adds the half-widths in quadrature — the realistic
  spread when the dimensions vary independently.

Both report each dimension's share of the variation, ranked, so the widest
contributor is obvious. Monte Carlo simulation and wiring these onto the Spec IR
as scorecard checks land as they are built out (see
openspec/specs/tolerance-management/).
"""

from __future__ import annotations

from math import sqrt
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from ..units import Quantity
from .explicit import ResolvedTolerance

__all__ = [
    "StackContributor",
    "Contribution",
    "StackResult",
    "StackUp",
]


def _mm(magnitude: float) -> Quantity:
    return Quantity(magnitude=magnitude, unit="mm")


class StackContributor(BaseModel):
    """One dimension in a stack-up chain: a resolved tolerance and its direction.

    ``direction`` is ``+1`` when the feature growing widens the resulting gap and
    ``-1`` when it narrows it; the chain sums directed sizes into the gap. The
    tolerance's own asymmetry is handled by the analysis — a contributor only
    needs its resolved band and which way it points.
    """

    model_config = ConfigDict(frozen=True)

    name: str
    tolerance: ResolvedTolerance
    direction: Literal[1, -1] = 1

    @property
    def _mean_mm(self) -> float:
        """The mean feature size in mm (the tolerance zone's midpoint)."""
        t = self.tolerance
        upper = t.upper.to("mm").magnitude
        lower = t.lower.to("mm").magnitude
        return t.nominal.to("mm").magnitude + (upper + lower) / 2.0

    @property
    def _half_mm(self) -> float:
        """The equal-bilateral half-width in mm (half the zone's total width)."""
        return self.tolerance.width.to("mm").magnitude / 2.0


class Contribution(BaseModel):
    """One dimension's share of the stack-up's total variation.

    ``share`` runs 0..1; the shares over a result sum to 1. It is computed for the
    method that produced it — a linear split for worst-case, a squared split for
    root-sum-square — so the same contributor can carry different shares in the
    two results.
    """

    model_config = ConfigDict(frozen=True)

    name: str
    share: float
    half_width: Quantity  # the contributor's own equal-bilateral half-width


class StackResult(BaseModel):
    """A resolved stack-up: the gap's mean, its bounds, and ranked contributions.

    ``nominal`` is the gap at every dimension's mean; ``lower`` and ``upper`` are
    the gap's bounds under the chosen ``method``. ``contributions`` are ordered
    widest share first.
    """

    model_config = ConfigDict(frozen=True)

    method: Literal["worst_case", "rss"]
    nominal: Quantity
    lower: Quantity
    upper: Quantity
    contributions: tuple[Contribution, ...]

    @property
    def width(self) -> Quantity:
        """The total width of the gap band (``upper - lower``)."""
        return _mm(self.upper.to("mm").magnitude - self.lower.to("mm").magnitude)

    def satisfies(self, min_required: Quantity, max_required: Quantity) -> bool:
        """Whether the whole gap band falls within a required range.

        Passes only when the band's worst cases both fit: its ``lower`` bound is at
        least ``min_required`` and its ``upper`` bound is at most ``max_required``.
        Both bounds must be lengths, else :class:`ValueError`.
        """
        for bound in (min_required, max_required):
            if not bound.has_dimension("[length]"):
                raise ValueError(
                    f"gap requirement must be a length; got {bound.dimensionality} ({bound})"
                )
        lo = self.lower.to("mm").magnitude
        hi = self.upper.to("mm").magnitude
        return min_required.to("mm").magnitude <= lo and hi <= max_required.to("mm").magnitude

    def __str__(self) -> str:
        lo = self.lower.to("mm").magnitude
        hi = self.upper.to("mm").magnitude
        return f"{self.method} gap {self.nominal} ({lo:+.3f} to {hi:+.3f} mm)"


class StackUp(BaseModel):
    """A one-dimensional stack-up over an ordered chain of contributors."""

    model_config = ConfigDict(frozen=True)

    contributors: tuple[StackContributor, ...] = Field(min_length=1)

    @property
    def _mean_gap_mm(self) -> float:
        return sum(c.direction * c._mean_mm for c in self.contributors)

    def _result(
        self, method: Literal["worst_case", "rss"], half_gap: float, weights: list[float]
    ) -> StackResult:
        total = sum(weights)
        mean = self._mean_gap_mm
        contributions = tuple(
            sorted(
                (
                    Contribution(
                        name=c.name,
                        share=(w / total if total else 0.0),
                        half_width=_mm(c._half_mm),
                    )
                    for c, w in zip(self.contributors, weights, strict=True)
                ),
                key=lambda c: c.share,
                reverse=True,
            )
        )
        return StackResult(
            method=method,
            nominal=_mm(mean),
            lower=_mm(mean - half_gap),
            upper=_mm(mean + half_gap),
            contributions=contributions,
        )

    def worst_case(self) -> StackResult:
        """The worst-case gap: every half-width added linearly.

        The band the gap can reach only when every dimension sits at its extreme
        at once. Each contributor's share is its half-width over the total.
        """
        halves = [c._half_mm for c in self.contributors]
        return self._result("worst_case", sum(halves), halves)

    def rss(self) -> StackResult:
        """The root-sum-square gap: half-widths added in quadrature.

        The realistic spread when the dimensions vary independently. Each
        contributor's share is its squared half-width over the sum of squares,
        so the widest dimension dominates faster than under worst-case.
        """
        halves = [c._half_mm for c in self.contributors]
        squares = [h * h for h in halves]
        return self._result("rss", sqrt(sum(squares)), squares)
