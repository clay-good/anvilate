"""T1 analytical shot-peening coverage checks (closed-form).

Shot peening blasts a surface with a stream of small hard shot, each impact leaving a shallow dimple
that cold-works a thin skin into compression. That residual compression is what fights fatigue: a
crack cannot open through metal already squeezed shut, so peened springs, gears, and shafts last far
longer. But the benefit only holds where the surface has actually been hit, and impacts land at
random — so the governing question of a peening process is *coverage*: what fraction of the surface
has been dimpled after a given exposure.

Coverage follows the Avrami statistics of random overlapping impacts. Each impact covers a dimple of
area a = π·d²/4, and impacts arrive at a flux φ (per unit area per unit time), so fresh surface is
covered at a rate λ = a·φ. Because later impacts increasingly fall on already-dimpled metal,
coverage approaches totality exponentially, C = 1 − exp(−λ·t), and never quite reaches 100% — which
is why the industry defines "full coverage" as 98% and quotes heavier peening as a multiple of the
time to reach it (200% is twice that time). Inverting the law gives the exposure a target needs,
t = −ln(1 − C)/λ — the number that sets the cycle time of the operation.

Sources: SAE J2277 and SAE J443 (shot peening coverage and Almen strip test) — the exponential
Avrami approach to full coverage, the coverage a stated exposure reaches, and the time a target
coverage requires.
"""

from __future__ import annotations

from math import exp, log, pi

from ..refusal import RefusalError, Remedy
from ..units import Quantity, require_finite

_PEENING_SETUP_SOURCE = "the qualified shot-peening procedure or calibrated media-flow record"
_PEENING_COVERAGE_SOURCE = "the peening specification or verified coverage test record"


class _ShotPeeningInputError(RefusalError, ValueError):
    """A shot-peening input that cannot be used without correction."""


def _shot_peening_refusal(message: str, *, subject: str, source: str) -> _ShotPeeningInputError:
    return _ShotPeeningInputError(
        message,
        remedies=(Remedy(action="replace", subject=subject, source=source),),
    )


def _shot_peening_input_source(name: str) -> str:
    if name in {"dimple_diameter", "impact_flux"}:
        return _PEENING_SETUP_SOURCE
    return _PEENING_COVERAGE_SOURCE


__all__ = [
    "peening_coverage",
    "peening_impact_coverage_rate",
    "peening_time_for_coverage",
]


def peening_impact_coverage_rate(*, dimple_diameter: Quantity, impact_flux: Quantity) -> Quantity:
    """The coverage rate, λ = (π·d²/4)·φ.

    The rate at which fresh surface would be dimpled if no impact ever overlapped another: the area
    a = π·d²/4 of a single dimple of ``dimple_diameter`` d, times the ``impact_flux`` φ (the number
    of impacts landing per unit area per unit time), λ = (π·d²/4)·φ. It is the time constant of the
    coverage law (:func:`peening_coverage`): a finer, faster shot stream covers quicker. Returns the
    coverage rate in 1/s.
    """
    _check(dimple_diameter, "[length]", "dimple_diameter")
    _check(impact_flux, "1/([area]*[time])", "impact_flux")
    d = dimple_diameter.to("mm").magnitude
    phi = impact_flux.to("1/(mm**2*s)").magnitude
    if d <= 0:
        raise _shot_peening_refusal(
            "dimple_diameter must be positive",
            subject="dimple_diameter",
            source=_PEENING_SETUP_SOURCE,
        )
    if phi <= 0:
        raise _shot_peening_refusal(
            "impact_flux must be positive", subject="impact_flux", source=_PEENING_SETUP_SOURCE
        )
    lam = pi * d * d / 4.0 * phi
    return Quantity(magnitude=lam, unit="1/s")


def peening_coverage(*, coverage_rate: Quantity, exposure_time: Quantity) -> float:
    """The peening coverage, C = 1 − exp(−λ·t).

    The fraction of the surface dimpled after an exposure: from the ``coverage_rate`` λ (from
    :func:`peening_impact_coverage_rate`) and the ``exposure_time`` t, C = 1 − exp(−λ·t), the Avrami
    law for random overlapping impacts. Coverage rises fast at first, then crawls as impacts land on
    already-peened metal, approaching but never reaching 100% — the reason "full coverage" is set
    at 98%. Returns the coverage as a fraction (0 to 1).
    """
    _check(coverage_rate, "1/[time]", "coverage_rate")
    _check(exposure_time, "[time]", "exposure_time")
    lam = coverage_rate.to("1/s").magnitude
    t = exposure_time.to("s").magnitude
    if lam <= 0:
        raise _shot_peening_refusal(
            "coverage_rate must be positive",
            subject="coverage_rate",
            source=_PEENING_COVERAGE_SOURCE,
        )
    if t < 0:
        raise _shot_peening_refusal(
            "exposure_time must be non-negative",
            subject="exposure_time",
            source=_PEENING_COVERAGE_SOURCE,
        )
    return 1.0 - exp(-lam * t)


def peening_time_for_coverage(*, coverage_rate: Quantity, target_coverage: float) -> Quantity:
    """The exposure for a target coverage, t = −ln(1 − C)/λ.

    Inverting the coverage law (:func:`peening_coverage`) for time: the exposure needed to reach a
    ``target_coverage`` C at a ``coverage_rate`` λ, t = −ln(1 − C)/λ. Because the term diverges as C
    approaches 1, 100% coverage would take infinite time — so specs call 98% "full coverage" and
    quote heavier peening as a multiple of the time to reach it. Returns the exposure time in s.
    """
    require_finite(target_coverage, name="target_coverage")
    _check(coverage_rate, "1/[time]", "coverage_rate")
    lam = coverage_rate.to("1/s").magnitude
    if lam <= 0:
        raise _shot_peening_refusal(
            "coverage_rate must be positive",
            subject="coverage_rate",
            source=_PEENING_COVERAGE_SOURCE,
        )
    if not 0.0 < target_coverage < 1.0:
        raise _shot_peening_refusal(
            "target_coverage must be a fraction in (0, 1); 100% coverage is unreachable",
            subject="target_coverage",
            source=_PEENING_COVERAGE_SOURCE,
        )
    t = -log(1.0 - target_coverage) / lam
    return Quantity(magnitude=t, unit="s")


def _check(value: Quantity, expected: str, name: str) -> None:
    if not isinstance(value, Quantity):
        raise _shot_peening_refusal(
            f"{name} must be a {expected} quantity; got {value!r}",
            subject=name,
            source=_shot_peening_input_source(name),
        )
    if not value.has_dimension(expected):
        raise _shot_peening_refusal(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})",
            subject=name,
            source=_shot_peening_input_source(name),
        )
    # The dimension is the easy half. Every comparison with NaN is False, so a NaN walks
    # past whatever `<= 0` guard follows; an infinity passes it too and then divides to
    # zero or overflows an `int()`. The `_require` helper in forty-eight sibling modules
    # has called this since it was written and this one, in a hundred and sixty-four, did
    # not — the same helper in two generations.
    require_finite(value, name=name)
