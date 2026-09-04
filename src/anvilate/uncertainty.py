"""Uncertainty-aware margins: input scatter turned into a margin distribution.

A nominal safety factor computed from a load the user only knows to ±20% can hide
a one-in-five chance of falling short — the exact silent green this library exists
to catch. This module takes a caller's response function (a safety factor, or any
margin, computed from named inputs) and a distribution for each input, and reports
the sampled distribution of the response: the chance it falls below the required
value, a percentile band, and which input drives the scatter.

The sampler is deliberately generic and unit-agnostic — it works on plain floats
through a ``response`` callable — so it wraps any analysis function without this
module importing the analysis layer. Sampling is seeded (a run is reproducible)
and input names are sorted before drawing, so the result never depends on the
order a caller happened to build the input mapping in.

This is screening, not certified reliability: the probability is only as good as
the distributions the caller asserts, and first-order sensitivity assumes the
response is locally smooth. Full FORM/SORM treatment stays out of scope.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from math import isfinite, sqrt
from random import Random
from typing import Literal

from pydantic import ConfigDict, model_validator

from ._models import Named, Provenance, RevalidatedModel

__all__ = [
    "Normal",
    "Uniform",
    "Symmetric",
    "InputDistribution",
    "Sensitivity",
    "MarginUncertainty",
    "sample_margin",
    "MONTE_CARLO_CITATION",
]

MONTE_CARLO_CITATION = (
    "Monte Carlo propagation of input distributions; first-order (Taylor) variance "
    "sensitivity. Screening only — not a certified reliability analysis."
)


class Normal(RevalidatedModel):
    """A Gaussian input: a mean and a standard deviation (``std`` ≥ 0)."""

    model_config = ConfigDict(frozen=True)

    mean: float
    std: float

    @model_validator(mode="after")
    def _non_negative_std(self) -> Normal:
        if self.std < 0:
            raise ValueError(f"std must be non-negative; got {self.std}")
        return self

    def sample(self, rng: Random) -> float:
        return self.mean if self.std == 0 else rng.gauss(self.mean, self.std)


class Uniform(RevalidatedModel):
    """A flat input spread evenly across ``[low, high]`` (``low`` ≤ ``high``)."""

    model_config = ConfigDict(frozen=True)

    low: float
    high: float

    @model_validator(mode="after")
    def _ordered(self) -> Uniform:
        if self.low > self.high:
            raise ValueError(f"low ({self.low}) must not exceed high ({self.high})")
        return self

    @property
    def mean(self) -> float:
        return (self.low + self.high) / 2.0

    @property
    def std(self) -> float:
        # Variance of a uniform over a width w is w**2 / 12.
        return (self.high - self.low) / sqrt(12.0)

    def sample(self, rng: Random) -> float:
        return self.low if self.low == self.high else rng.uniform(self.low, self.high)


class Symmetric(RevalidatedModel):
    """A ± input, the tolerance-style vocabulary: a nominal and a half-width.

    ``distribution`` sets how the half-width is read: ``"normal"`` (default) treats
    it as ``sigma_level`` standard deviations from the nominal — the ±X = ±3σ
    convention shared with the tolerance stack-up — while ``"uniform"`` spreads it
    flat across ``nominal ± half_width``.
    """

    model_config = ConfigDict(frozen=True)

    nominal: float
    half_width: float
    distribution: Literal["normal", "uniform"] = "normal"
    sigma_level: float = 3.0

    @model_validator(mode="after")
    def _well_formed(self) -> Symmetric:
        if self.half_width < 0:
            raise ValueError(f"half_width must be non-negative; got {self.half_width}")
        if self.sigma_level <= 0:
            raise ValueError(f"sigma_level must be positive; got {self.sigma_level}")
        return self

    @property
    def mean(self) -> float:
        return self.nominal

    @property
    def std(self) -> float:
        if self.distribution == "normal":
            return self.half_width / self.sigma_level
        return self.half_width / sqrt(3.0)  # uniform over ±half_width

    def sample(self, rng: Random) -> float:
        if self.half_width == 0:
            return self.nominal
        if self.distribution == "normal":
            return rng.gauss(self.nominal, self.std)
        return rng.uniform(self.nominal - self.half_width, self.nominal + self.half_width)


InputDistribution = Normal | Uniform | Symmetric


class Sensitivity(RevalidatedModel):
    """One input's share of the response variance, first-order (Taylor)."""

    model_config = ConfigDict(frozen=True)

    name: Named
    variance_share: float  # 0..1, the fraction of the response variance this input drives


class MarginUncertainty(RevalidatedModel):
    """A sampled margin: the chance it falls short, its band, and what drives it.

    ``shortfall_probability`` is the fraction of samples whose response fell below
    ``required`` — the number a nominal pass can hide. ``lower`` and ``upper`` bound
    the central ``coverage`` fraction of the sampled response. ``sensitivities``
    ranks the inputs by their first-order share of the response variance, largest
    first. Everything is reproducible from ``seed``.
    """

    model_config = ConfigDict(frozen=True)

    method: Literal["monte_carlo"] = "monte_carlo"
    samples: int
    seed: int
    required: float
    mean: float
    std: float
    shortfall_probability: float
    lower: float
    upper: float
    coverage: float
    sensitivities: tuple[Sensitivity, ...]
    citation: Provenance = MONTE_CARLO_CITATION

    def is_fragile(self, threshold: float = 0.05) -> bool:
        """Whether the shortfall probability exceeds ``threshold`` (default 5%).

        A nominal pass that is fragile under the asserted input scatter — the
        no-silent-green trigger for an uncertainty warning.
        """
        return self.shortfall_probability > threshold

    def dominant(self) -> Sensitivity | None:
        """The input driving the most response variance, or ``None`` if none do."""
        return self.sensitivities[0] if self.sensitivities else None

    def __str__(self) -> str:
        pct = self.shortfall_probability * 100.0
        return (
            f"margin {self.mean:.2f} ± {self.std:.2f}, "
            f"P(below {self.required:.2f}) = {pct:.1f}% over {self.samples} samples"
        )


def _quantile(sorted_vals: list[float], q: float) -> float:
    """Linear-interpolated quantile of an ascending list (q in 0..1)."""
    if not sorted_vals:
        raise ValueError("no samples to take a quantile of")
    if len(sorted_vals) == 1:
        return sorted_vals[0]
    pos = q * (len(sorted_vals) - 1)
    lo = int(pos)
    hi = min(lo + 1, len(sorted_vals) - 1)
    frac = pos - lo
    return sorted_vals[lo] * (1.0 - frac) + sorted_vals[hi] * frac


def _sensitivities(
    response: Callable[[Mapping[str, float]], float],
    names: list[str],
    dists: dict[str, InputDistribution],
) -> tuple[Sensitivity, ...]:
    """First-order variance shares: perturb each input by its own σ at the mean.

    For a response f, the local variance contribution of input i is (∂f/∂x_i · σ_i)²,
    which a one-sided step of σ_i estimates as (f(μ + σ_i·e_i) − f(μ))². Shares are
    normalized to sum to 1; an input with zero spread contributes nothing.
    """
    mean_point = {name: dists[name].mean for name in names}
    base = response(mean_point)
    contributions: dict[str, float] = {}
    for name in names:
        sigma = dists[name].std
        if sigma == 0:
            contributions[name] = 0.0
            continue
        perturbed = dict(mean_point)
        perturbed[name] = mean_point[name] + sigma
        delta = response(perturbed) - base
        contributions[name] = delta * delta
    total = sum(contributions.values())
    ranked = sorted(names, key=lambda n: contributions[n], reverse=True)
    return tuple(
        Sensitivity(name=n, variance_share=(contributions[n] / total) if total > 0 else 0.0)
        for n in ranked
    )


def sample_margin(
    response: Callable[[Mapping[str, float]], float],
    inputs: Mapping[str, InputDistribution],
    *,
    required: float,
    seed: int,
    samples: int = 10000,
    coverage: float = 0.90,
) -> MarginUncertainty:
    """Sample a ``response`` (a safety factor or margin) under input scatter.

    ``response`` maps a name→value mapping to a single float — the safety factor,
    utilization, or any margin whose fall below ``required`` is a failure.
    ``inputs`` gives a distribution per name; every name the response reads must be
    present. Returns a :class:`MarginUncertainty` with the shortfall probability,
    the central ``coverage`` band, and the first-order sensitivity ranking.

    ``seed`` is required so a run is reproducible; input names are drawn in sorted
    order so the result is independent of the mapping's construction order.

    A response that returns NaN or infinity for some samples is refused outright.
    Refusing matters because NaN compares ``False`` against everything, so a NaN
    sample would silently fall on the *passing* side of ``r < required`` — the same
    trap :meth:`ScorecardEntry.from_safety_factor` already guards. It is easy to hit:
    a response taking ``sqrt`` of a sampled thickness, or dividing by a sampled load,
    goes non-finite as soon as the tail of the distribution crosses zero, and the run
    would report a confident low shortfall probability computed from the finite
    samples alone while ``mean`` and the coverage band come back NaN.
    """
    if samples < 2:
        raise ValueError(f"a Monte Carlo run needs at least 2 samples; got {samples}")
    if not 0.0 < coverage < 1.0:
        raise ValueError(f"coverage must be between 0 and 1 exclusive; got {coverage}")
    if not inputs:
        raise ValueError("sample_margin needs at least one input distribution")

    dists = dict(inputs)
    names = sorted(dists)
    rng = Random(seed)

    drawn = [response({name: dists[name].sample(rng) for name in names}) for _ in range(samples)]
    nonfinite = sum(1 for r in drawn if not isfinite(r))
    if nonfinite:
        raise ValueError(
            f"the response returned a non-finite value on {nonfinite} of {samples} samples; "
            "a NaN sorts as neither above nor below `required` and would be counted as a pass. "
            "Restrict the input distributions to the response's valid domain, or have the "
            "response raise on inputs it cannot evaluate."
        )
    # Guard the OTHER operand of the same comparison. A NaN `required` makes every
    # `r < required` False, so the shortfall probability comes back a confident 0.0% and
    # `is_fragile()` reports False — the silent green this function's response guard above
    # exists to prevent, arriving through the door it left open.
    if not isfinite(required):
        raise ValueError(
            f"required must be a finite number; got {required}. A non-finite requirement "
            "makes every `r < required` comparison False, which reads as a 0% chance of "
            "falling short rather than as a comparison that was never made."
        )
    responses = sorted(drawn)
    mean = sum(responses) / samples
    variance = sum((r - mean) ** 2 for r in responses) / (samples - 1)
    below = sum(1 for r in responses if r < required)
    tail = (1.0 - coverage) / 2.0

    return MarginUncertainty(
        samples=samples,
        seed=seed,
        required=required,
        mean=mean,
        std=sqrt(variance),
        shortfall_probability=below / samples,
        lower=_quantile(responses, tail),
        upper=_quantile(responses, 1.0 - tail),
        coverage=coverage,
        sensitivities=_sensitivities(response, names, dists),
    )
