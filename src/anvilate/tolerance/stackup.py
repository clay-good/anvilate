"""One-dimensional tolerance stack-up analysis over a dimension chain.

A stack-up sums a chain of directed dimensions into a resulting gap and asks how
much the gap can vary once each dimension flexes within its tolerance. Each
contributor's resolved tolerance is recentred on its own mean and reduced to an
equal-bilateral half-width, so an asymmetric zone stacks correctly:

* the **worst-case** band adds every half-width — the gap can reach it, but only
  when every dimension is simultaneously at its extreme, which is rare;
* the **root-sum-square** band adds the half-widths in quadrature — the realistic
  spread when the dimensions vary independently.

A **Monte Carlo** simulation samples each dimension from an assumed distribution
(normal, with the tolerance band read as ``±sigma_level`` sigmas, or uniform
across the band) and reports the resulting gap's mean, spread, and a coverage
band empirically — plus the predicted yield against a required clearance, which
neither worst-case nor RSS can give.

Both analytic methods report each dimension's share of the variation, ranked, so
the widest contributor is obvious. Wiring these onto the Spec IR as scorecard
checks lands as it is built out (see openspec/specs/tolerance-management/).
"""

from __future__ import annotations

from bisect import bisect_left, bisect_right
from math import floor, sqrt
from random import Random
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from ..units import Quantity
from .explicit import ResolvedTolerance

__all__ = [
    "StackContributor",
    "Contribution",
    "StackResult",
    "MonteCarloResult",
    "StackUp",
]


def _mm(magnitude: float) -> Quantity:
    return Quantity(magnitude=magnitude, unit="mm")


def _quantile(sorted_vals: tuple[float, ...], q: float) -> float:
    """The ``q``-quantile (0..1) of an already-sorted sequence, interpolated."""
    n = len(sorted_vals)
    if n == 1:
        return sorted_vals[0]
    pos = q * (n - 1)
    lo = floor(pos)
    hi = min(lo + 1, n - 1)
    frac = pos - lo
    return sorted_vals[lo] * (1.0 - frac) + sorted_vals[hi] * frac


class StackContributor(BaseModel):
    """One dimension in a stack-up chain: a resolved tolerance and its direction.

    ``direction`` is ``+1`` when the feature growing widens the resulting gap and
    ``-1`` when it narrows it; the chain sums directed sizes into the gap. The
    tolerance's own asymmetry is handled by the analysis — a contributor only
    needs its resolved band and which way it points.

    ``distribution`` is how a Monte Carlo run treats the dimension: ``"normal"``
    (the default) centres a Gaussian on the mean with the half-width read as a
    number of sigmas, while ``"uniform"`` spreads it flat across the band. It has
    no effect on the worst-case or RSS analyses.
    """

    model_config = ConfigDict(frozen=True)

    name: str
    tolerance: ResolvedTolerance
    direction: Literal[1, -1] = 1
    distribution: Literal["normal", "uniform"] = "normal"

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

    def _variance_mm2(self, sigma_level: float) -> float:
        """The contributor's variance in mm^2 under its distribution."""
        if self.distribution == "normal":
            sigma = self._half_mm / sigma_level
            return sigma * sigma
        # Uniform over a full width 2*half: variance (2*half)^2 / 12.
        return (self._half_mm * self._half_mm) / 3.0


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


class MonteCarloResult(BaseModel):
    """A Monte Carlo stack-up: the gap's sampled statistics and predicted yield.

    ``nominal`` is the analytic gap at every dimension's mean; ``mean`` and ``std``
    are the sampled gap's centre and spread; ``lower`` and ``upper`` bound the
    central ``coverage`` fraction of samples (e.g. 0.9973 for a ±3σ band).
    ``contributions`` rank each dimension's share of the total variance.

    The sorted per-sample gaps are kept so :meth:`yield_fraction` can score any
    required clearance band after the fact.
    """

    model_config = ConfigDict(frozen=True)

    method: Literal["monte_carlo"] = "monte_carlo"
    samples: int
    nominal: Quantity
    mean: Quantity
    std: Quantity
    lower: Quantity
    upper: Quantity
    coverage: float
    contributions: tuple[Contribution, ...]
    sorted_gaps_mm: tuple[float, ...] = Field(repr=False)

    @property
    def width(self) -> Quantity:
        """The width of the coverage band (``upper - lower``)."""
        return _mm(self.upper.to("mm").magnitude - self.lower.to("mm").magnitude)

    def yield_fraction(self, min_required: Quantity, max_required: Quantity) -> float:
        """The fraction of sampled assemblies whose gap falls within a band, 0..1.

        This is the predicted yield: the share of parts that would pass the
        required clearance if each dimension varies as assumed. Both bounds must
        be lengths, else :class:`ValueError`.
        """
        for bound in (min_required, max_required):
            if not bound.has_dimension("[length]"):
                raise ValueError(
                    f"gap requirement must be a length; got {bound.dimensionality} ({bound})"
                )
        lo = min_required.to("mm").magnitude
        hi = max_required.to("mm").magnitude
        left = bisect_left(self.sorted_gaps_mm, lo)
        right = bisect_right(self.sorted_gaps_mm, hi)
        return (right - left) / len(self.sorted_gaps_mm)

    def __str__(self) -> str:
        lo = self.lower.to("mm").magnitude
        hi = self.upper.to("mm").magnitude
        pct = self.coverage * 100.0
        return f"{self.method} gap {self.nominal} ({lo:+.3f} to {hi:+.3f} mm @ {pct:.2f}%)"


class StackUp(BaseModel):
    """A one-dimensional stack-up over an ordered chain of contributors."""

    model_config = ConfigDict(frozen=True)

    contributors: tuple[StackContributor, ...] = Field(min_length=1)

    @property
    def _mean_gap_mm(self) -> float:
        return sum(c.direction * c._mean_mm for c in self.contributors)

    def _rank_contributions(self, weights: list[float]) -> tuple[Contribution, ...]:
        """Each contributor's normalized share of ``weights``, ranked widest first."""
        total = sum(weights)
        return tuple(
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

    def _result(
        self, method: Literal["worst_case", "rss"], half_gap: float, weights: list[float]
    ) -> StackResult:
        mean = self._mean_gap_mm
        return StackResult(
            method=method,
            nominal=_mm(mean),
            lower=_mm(mean - half_gap),
            upper=_mm(mean + half_gap),
            contributions=self._rank_contributions(weights),
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

    def monte_carlo(
        self,
        samples: int = 10000,
        *,
        seed: int,
        sigma_level: float = 3.0,
        coverage: float = 0.9973,
    ) -> MonteCarloResult:
        """Sample the gap ``samples`` times and report its distribution and yield.

        Each dimension is drawn from its own ``distribution`` — a normal centred on
        its mean with the half-width read as ``sigma_level`` sigmas, or a uniform
        spread across the band. ``coverage`` (0..1) sets the central fraction the
        reported ``lower``/``upper`` band spans. ``seed`` is required so a run is
        reproducible. Contributions rank each dimension's share of the variance.
        """
        if samples < 2:
            raise ValueError(f"a Monte Carlo run needs at least 2 samples; got {samples}")
        if sigma_level <= 0:
            raise ValueError(f"sigma_level must be positive; got {sigma_level}")
        if not 0.0 < coverage < 1.0:
            raise ValueError(f"coverage must be between 0 and 1 exclusive; got {coverage}")

        rng = Random(seed)
        # Resolve each contributor's mean and half-width to plain mm floats once,
        # up front — pint conversions inside the sample loop would dominate runtime.
        # Each entry is (direction, mean, low, high, sigma, is_normal).
        drawn = [
            (
                float(c.direction),
                c._mean_mm,
                c._mean_mm - c._half_mm,
                c._mean_mm + c._half_mm,
                c._half_mm / sigma_level,
                c.distribution == "normal",
            )
            for c in self.contributors
        ]
        gaps = sorted(
            sum(
                d * (rng.gauss(mean, sigma) if is_normal else rng.uniform(low, high))
                for d, mean, low, high, sigma, is_normal in drawn
            )
            for _ in range(samples)
        )
        mean = sum(gaps) / samples
        variance = sum((g - mean) ** 2 for g in gaps) / (samples - 1)
        std = sqrt(variance)
        tail = (1.0 - coverage) / 2.0
        weights = [c._variance_mm2(sigma_level) for c in self.contributors]
        return MonteCarloResult(
            samples=samples,
            nominal=_mm(self._mean_gap_mm),
            mean=_mm(mean),
            std=_mm(std),
            lower=_mm(_quantile(tuple(gaps), tail)),
            upper=_mm(_quantile(tuple(gaps), 1.0 - tail)),
            coverage=coverage,
            contributions=self._rank_contributions(weights),
            sorted_gaps_mm=tuple(gaps),
        )
