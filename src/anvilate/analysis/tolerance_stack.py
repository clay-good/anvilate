"""T1 analytical assembly tolerance-stackup checks (closed-form).

When several toleranced parts stack up in a chain — spacers on a shaft, plates in a bolted joint,
features across a housing — the variations accumulate, and how they accumulate decides how tight a
final gap or fit can be guaranteed. Two closed-form methods bound the answer, and the truth for a
real production run sits between them.

The worst-case stack simply adds the magnitudes of the individual tolerances, T_wc = Σ|tᵢ|. It
assumes every part is simultaneously at its worst extreme in the same direction — a 100% guarantee
that no assembly ever exceeds it, but a pessimistic and often expensive bound, because that
simultaneous alignment is astronomically unlikely for many parts.

The statistical (root-sum-square) stack combines them in quadrature, T_rss = √(Σtᵢ²), which is the
standard deviation of the assembly when the parts vary independently about their centres. It is far
tighter than the worst-case sum — the benefit of statistics — and is the realistic spread for a
capable process, but a small fraction of assemblies can fall outside it, so it is paired with a
process-capability target (see :mod:`anvilate.analysis.process_capability`). Tolerances are
dimension-checked :class:`~anvilate.units.Quantity` lengths; pass the ± half-tolerance of each part.

Sources: Fischer, *Mechanical Tolerance Stackup and Analysis* — the worst-case sum of a chain's
tolerances and the root-sum-square combination, with the assumptions each rests on.
"""

from __future__ import annotations

from collections.abc import Sequence

from ..units import Quantity

__all__ = [
    "rss_tolerance_stack",
    "worst_case_tolerance_stack",
]


def worst_case_tolerance_stack(tolerances: Sequence[Quantity]) -> Quantity:
    """The worst-case assembly tolerance, T_wc = Σ|tᵢ|.

    The arithmetic sum of the individual part ``tolerances`` (each a ± half-tolerance): every part
    is assumed at its worst limit at once, so the assembly can never vary more than T_wc = Σ|tᵢ|. It
    is the 100%-guaranteed bound used for safety-critical fits and short stacks, but it grows
    linearly with the number of parts and quickly demands tolerances tighter (and costlier) than a
    statistical view would. Pass at least one tolerance. Returns the worst-case stack in mm.
    """
    if not isinstance(tolerances, Sequence):
        raise ValueError(f"tolerances must be a sequence, not a single value; got {tolerances!r}")
    values = _tolerances_in_mm(tolerances)
    return Quantity(magnitude=sum(abs(t) for t in values), unit="mm")


def rss_tolerance_stack(tolerances: Sequence[Quantity]) -> Quantity:
    """The statistical (root-sum-square) assembly tolerance, T_rss = √(Σtᵢ²).

    The quadrature combination of the individual part ``tolerances`` (each a ± half-tolerance),
    T_rss = √(Σtᵢ²): when the parts vary independently about their nominal, their variations add as
    variances, so the assembly spread is the root-sum-square, not the plain sum. It is always at or
    below :func:`worst_case_tolerance_stack` (equal only for a single part) and drops well below it
    as parts are added — the statistical dividend that lets a designer open up individual tolerances
    while holding the assembly spread. Valid when the contributors are independent and roughly
    normal; it describes one standard deviation of the assembly, so pair it with a
    process-capability margin. Pass at least one tolerance. Returns the RSS stack in mm.
    """
    if not isinstance(tolerances, Sequence):
        raise ValueError(f"tolerances must be a sequence, not a single value; got {tolerances!r}")
    values = _tolerances_in_mm(tolerances)
    return Quantity(magnitude=sum(t * t for t in values) ** 0.5, unit="mm")


def _tolerances_in_mm(tolerances: Sequence[Quantity]) -> list[float]:
    if len(tolerances) == 0:
        raise ValueError("tolerances must contain at least one part tolerance")
    values: list[float] = []
    for idx, tol in enumerate(tolerances):
        _check(tol, "[length]", f"tolerances[{idx}]")
        values.append(tol.to("mm").magnitude)
    return values


def _check(value: Quantity, expected: str, name: str) -> None:
    if not isinstance(value, Quantity):
        raise ValueError(f"{name} must be a {expected} quantity; got {value!r}")
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )
