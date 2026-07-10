"""T1 analytical flat-plate bending under uniform pressure.

Flat plates — covers, manway blanks, tank lids, access panels — are the plate
counterpart of the beam screening checks, in both plan shapes and both edge
conditions:

* **rectangle, simply supported** — the exact Kirchhoff Navier double series,
  evaluated directly (no coefficient table to bundle or trust; it reproduces
  the classic handbook values, e.g. α = 0.0444, β = 0.2874 for a square at
  ν = 0.3);
* **rectangle, clamped** — no closed form exists, so the standard Roark
  Table 11.4 coefficients (ν = 0.3), whose strip limit is the exact
  fixed-fixed beam and whose interior values were confirmed by an independent
  finite-difference biharmonic solve;
* **circle, simply supported and clamped** — the exact Timoshenko polynomial
  closed forms.

These are screening checks: linear-elastic thin-plate theory, small
deflections (w ≲ t/2), uniform pressure. Every input and output is a
dimension-checked :class:`~anvilate.units.Quantity`.
"""

from __future__ import annotations

from math import pi

from pydantic import BaseModel, ConfigDict

from ..units import Quantity

__all__ = [
    "PlateBendingResult",
    "simply_supported_plate_uniform_load",
    "clamped_plate_uniform_load",
    "simply_supported_circular_plate_uniform_load",
    "clamped_circular_plate_uniform_load",
]

# Odd-harmonic cap for the Navier series. Deflection terms fall off as 1/(mn)·
# 1/(m²+n²)², moments as 1/(mn)·1/(m²+n²) — at 399 the center moment is within
# ~2e-4 of converged, far inside screening tolerance.
_SERIES_MAX_HARMONIC = 399

# Default Poisson's ratio when none is supplied (typical for steel/aluminum).
DEFAULT_POISSON_RATIO = 0.3

# Clamped rectangle coefficients (Roark Table 11.4, all edges fixed, uniform
# load, ν = 0.3): w = α·q·b⁴/(E·t³) at the centre and σ = β·q·b²/t² at the
# midpoint of the long edge, keyed by b/a (short/long side, so 0 is the
# infinite strip). The strip endpoint is exact — a fixed-fixed unit-width beam
# gives M = q·b²/12 (β = 0.5) and w = q·b⁴/(384·D) (α = 12·(1−0.3²)/384 =
# 0.0284). All interior values verified against an independent finite-
# difference biharmonic solve (α to <0.5%; β to ~1% after Richardson
# extrapolation of the O(h) edge-moment error).
_CLAMPED_COEFFICIENTS = (
    # (b/a, alpha, beta)
    (0.0, 0.0284, 0.5000),
    (1 / 2.0, 0.0277, 0.4974),
    (1 / 1.8, 0.0267, 0.4872),
    (1 / 1.6, 0.0251, 0.4680),
    (1 / 1.4, 0.0226, 0.4356),
    (1 / 1.2, 0.0188, 0.3834),
    (1.0, 0.0138, 0.3078),
)


def _require(value: Quantity, expected: str, name: str) -> None:
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )


class PlateBendingResult(BaseModel):
    """The result of a closed-form plate bending check.

    ``max_bending_stress`` is the peak surface bending stress (6·M/t² from the
    larger centre bending moment) and ``max_deflection`` the centre deflection
    — both at the plate centre for a simply-supported rectangle under uniform
    pressure. Screening estimates for a thin linear-elastic plate under small
    deflections.
    """

    model_config = ConfigDict(frozen=True)

    max_bending_stress: Quantity
    max_deflection: Quantity

    def bending_safety_factor(self, yield_strength: Quantity) -> float:
        """The factor of safety against surface yielding: yield / peak stress."""
        _require(yield_strength, "[pressure]", "yield_strength")
        sy = yield_strength.to("MPa").magnitude
        sigma = self.max_bending_stress.to("MPa").magnitude
        return sy / sigma

    def __str__(self) -> str:
        return (
            f"plate: sigma_max {self.max_bending_stress.to('MPa')}, "
            f"delta_max {self.max_deflection.to('mm')}"
        )


def clamped_plate_uniform_load(
    *,
    pressure: Quantity,
    length: Quantity,
    width: Quantity,
    thickness: Quantity,
    elastic_modulus: Quantity,
) -> PlateBendingResult:
    """The rectangular plate with all edges clamped under uniform pressure (Roark).

    A thin flat plate of plan ``length`` × ``width`` and ``thickness`` t with
    all four edges built in — welded all around, or bolted stiffly enough to
    hold the edge slope — under uniform ``pressure`` q. The clamped rectangle
    has no closed-form series, so this uses the standard Roark Table 11.4
    coefficients (ν = 0.3, interpolated linearly in the side ratio): the
    centre deflects w = α·q·b⁴/(E·t³) and the peak stress is the bending at
    the midpoint of the LONG edge, σ = β·q·b²/t², with b the short side —
    clamping cuts the deflection ~3× against the simply-supported plate but
    parks the peak stress on the edge weld. The long-strip end of the table
    is exact (a fixed-fixed beam: β = 0.5, α = 0.0284), and the interior
    values are verified in the test suite against an independent
    finite-difference biharmonic solve. Thin-plate screening limits apply
    (trustworthy while w ≲ t/2); ν is fixed at the table's 0.3. Every
    quantity argument is dimension-checked.
    """
    _require(pressure, "[pressure]", "pressure")
    _require(length, "[length]", "length")
    _require(width, "[length]", "width")
    _require(thickness, "[length]", "thickness")
    _require(elastic_modulus, "[pressure]", "elastic_modulus")

    q = pressure.to("MPa").magnitude
    a = length.to("mm").magnitude
    b = width.to("mm").magnitude
    t = thickness.to("mm").magnitude
    e = elastic_modulus.to("MPa").magnitude
    if min(q, a, b, t, e) <= 0:
        raise ValueError("pressure, plan dimensions, thickness, and E must be positive")
    if b > a:
        a, b = b, a  # b is the short side; the result is orientation-blind

    ratio = b / a
    for (r_lo, alpha_lo, beta_lo), (r_hi, alpha_hi, beta_hi) in zip(
        _CLAMPED_COEFFICIENTS, _CLAMPED_COEFFICIENTS[1:], strict=False
    ):
        if ratio <= r_hi:
            frac = (ratio - r_lo) / (r_hi - r_lo)
            alpha = alpha_lo + frac * (alpha_hi - alpha_lo)
            beta = beta_lo + frac * (beta_hi - beta_lo)
            break

    stress = beta * q * b**2 / t**2
    deflection = alpha * q * b**4 / (e * t**3)
    return PlateBendingResult(
        max_bending_stress=Quantity(magnitude=stress, unit="MPa"),
        max_deflection=Quantity(magnitude=deflection, unit="mm"),
    )


def _circular_plate_inputs(
    pressure: Quantity,
    diameter: Quantity,
    thickness: Quantity,
    elastic_modulus: Quantity,
    poisson_ratio: float,
) -> tuple[float, float, float, float]:
    """Validate and unpack circular-plate arguments -> (q MPa, R mm, t mm, D N·mm)."""
    _require(pressure, "[pressure]", "pressure")
    _require(diameter, "[length]", "diameter")
    _require(thickness, "[length]", "thickness")
    _require(elastic_modulus, "[pressure]", "elastic_modulus")
    if not 0 < poisson_ratio < 0.5:
        raise ValueError(f"poisson_ratio must lie in (0, 0.5); got {poisson_ratio}")
    q = pressure.to("MPa").magnitude
    radius = diameter.to("mm").magnitude / 2
    t = thickness.to("mm").magnitude
    e = elastic_modulus.to("MPa").magnitude
    if min(q, radius, t, e) <= 0:
        raise ValueError("pressure, diameter, thickness, and E must be positive")
    rigidity = e * t**3 / (12 * (1 - poisson_ratio**2))
    return q, radius, t, rigidity


def simply_supported_circular_plate_uniform_load(
    *,
    pressure: Quantity,
    diameter: Quantity,
    thickness: Quantity,
    elastic_modulus: Quantity,
    poisson_ratio: float = DEFAULT_POISSON_RATIO,
) -> PlateBendingResult:
    """The simply-supported circular plate under uniform pressure (Timoshenko).

    A round cover of ``diameter`` 2R and ``thickness`` t, simply supported at
    its rim, under uniform ``pressure`` q — a round manway blank, a sight-glass
    blank, a drum head. Exact thin-plate closed form: the centre carries the
    peak stress σ = 3·(3 + ν)·q·R²/(8·t²) and deflects
    w = (5 + ν)/(1 + ν)·q·R⁴/(64·D) — exactly (5 + ν)/(1 + ν) ≈ 4.08× the
    clamped plate's, at (3 + ν)/2 ≈ 1.65× its stress. Thin-plate screening
    limits apply (trustworthy while w ≲ t/2). Every quantity argument is
    dimension-checked; ν must lie in (0, 0.5).
    """
    q, radius, t, rigidity = _circular_plate_inputs(
        pressure, diameter, thickness, elastic_modulus, poisson_ratio
    )
    stress = 3 * (3 + poisson_ratio) * q * radius**2 / (8 * t**2)
    deflection = (5 + poisson_ratio) / (1 + poisson_ratio) * q * radius**4 / (64 * rigidity)
    return PlateBendingResult(
        max_bending_stress=Quantity(magnitude=stress, unit="MPa"),
        max_deflection=Quantity(magnitude=deflection, unit="mm"),
    )


def clamped_circular_plate_uniform_load(
    *,
    pressure: Quantity,
    diameter: Quantity,
    thickness: Quantity,
    elastic_modulus: Quantity,
    poisson_ratio: float = DEFAULT_POISSON_RATIO,
) -> PlateBendingResult:
    """The clamped (built-in edge) circular plate under uniform pressure.

    A round plate of ``diameter`` 2R and ``thickness`` t with its rim fully
    fixed — welded all around, or bolted stiffly enough to hold the edge slope
    — under uniform ``pressure`` q. Exact thin-plate closed form
    w = q·(R² − r²)²/(64·D): the centre deflects w = q·R⁴/(64·D) and the peak
    stress is the RADIAL bending at the clamped rim, σ = 3·q·R²/(4·t²) (the
    centre carries only (1 + ν)/2 of it) — clamping trades deflection for an
    edge stress the weld or bolt circle must carry. Thin-plate screening
    limits apply (trustworthy while w ≲ t/2). Every quantity argument is
    dimension-checked; ν must lie in (0, 0.5).
    """
    q, radius, t, rigidity = _circular_plate_inputs(
        pressure, diameter, thickness, elastic_modulus, poisson_ratio
    )
    stress = 3 * q * radius**2 / (4 * t**2)
    deflection = q * radius**4 / (64 * rigidity)
    return PlateBendingResult(
        max_bending_stress=Quantity(magnitude=stress, unit="MPa"),
        max_deflection=Quantity(magnitude=deflection, unit="mm"),
    )


def simply_supported_plate_uniform_load(
    *,
    pressure: Quantity,
    length: Quantity,
    width: Quantity,
    thickness: Quantity,
    elastic_modulus: Quantity,
    poisson_ratio: float = DEFAULT_POISSON_RATIO,
) -> PlateBendingResult:
    """The simply-supported rectangular plate under uniform pressure (Navier).

    A thin flat plate of plan ``length`` a × ``width`` b and ``thickness`` t,
    simply supported on all four edges, carrying a uniform ``pressure`` q — a
    bolted cover, a tank lid, an access panel. Solved by the exact Navier
    series on the plate rigidity D = E·t³/(12·(1 − ν²)): the centre deflection
    w = (16q/π⁶D)·ΣΣ 1/(mn·(m²/a² + n²/b²)²) and centre bending moments
    Mx, My (per unit width), the larger of which sets the peak surface stress
    σ = 6·M/t². For a square at ν = 0.3 this reproduces the handbook
    coefficients w = 0.0444·q·b⁴/(E·t³) and σ = 0.2874·q·b²/t².

    Thin-plate screening limits apply: the result is trustworthy while the
    deflection stays below about half the thickness (beyond that membrane
    action stiffens the real plate and this check is conservative). Every
    quantity argument is dimension-checked; ν must lie in (0, 0.5).
    """
    _require(pressure, "[pressure]", "pressure")
    _require(length, "[length]", "length")
    _require(width, "[length]", "width")
    _require(thickness, "[length]", "thickness")
    _require(elastic_modulus, "[pressure]", "elastic_modulus")
    if not 0 < poisson_ratio < 0.5:
        raise ValueError(f"poisson_ratio must lie in (0, 0.5); got {poisson_ratio}")

    q = pressure.to("MPa").magnitude
    a = length.to("mm").magnitude
    b = width.to("mm").magnitude
    t = thickness.to("mm").magnitude
    e = elastic_modulus.to("MPa").magnitude
    if min(q, a, b, t, e) <= 0:
        raise ValueError("pressure, plan dimensions, thickness, and E must be positive")

    rigidity = e * t**3 / (12 * (1 - poisson_ratio**2))

    w_sum = mx_sum = my_sum = 0.0
    for m in range(1, _SERIES_MAX_HARMONIC + 1, 2):
        sign_m = 1.0 if (m - 1) % 4 == 0 else -1.0  # sin(m*pi/2) for odd m
        for n in range(1, _SERIES_MAX_HARMONIC + 1, 2):
            sign = sign_m * (1.0 if (n - 1) % 4 == 0 else -1.0)
            k = m**2 / a**2 + n**2 / b**2
            denom = m * n * k**2
            w_sum += sign / denom
            mx_sum += sign * (m**2 / a**2 + poisson_ratio * n**2 / b**2) / denom
            my_sum += sign * (poisson_ratio * m**2 / a**2 + n**2 / b**2) / denom

    deflection = 16 * q / (pi**6 * rigidity) * w_sum
    moment = 16 * q / pi**4 * max(mx_sum, my_sum)  # per unit width
    stress = 6 * moment / t**2
    return PlateBendingResult(
        max_bending_stress=Quantity(magnitude=stress, unit="MPa"),
        max_deflection=Quantity(magnitude=deflection, unit="mm"),
    )
