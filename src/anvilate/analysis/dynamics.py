"""T1 analytical modal screening (fundamental frequency, closed-form).

Resonance is a screening concern: a part whose fundamental natural frequency sits
near an operating excitation amplifies vibration. The closed forms cover the
common cases:

* a single-degree-of-freedom system (a mass ``m`` on a support of stiffness
  ``k``) resonates at ``f_n = (1/2π)·√(k/m)``;
* a structure that deflects ``δ`` under its own weight has a fundamental frequency
  estimated by the Rayleigh relation ``f_n = (1/2π)·√(g/δ)`` — no separate mass or
  stiffness needed;
* a prismatic beam with distributed mass has the exact Euler-Bernoulli
  fundamental ``f₁ = (λ₁²/2π)·√(E·I/(m̄·L⁴))``, one eigenvalue λ₁ per support
  condition (Blevins/Roark);
* a thin flat plate has the Kirchhoff fundamental ``f₁ = (γ/2π)·√(D/(μ·L⁴))``
  on the plate rigidity D and mass per area μ — γ exact for the
  simply-supported rectangle, solved at runtime from the Bessel
  characteristic equations for circles, and from finite-difference-verified
  tables for the clamped rectangle and the free-holed annulus.

Inputs are dimension-checked :class:`~anvilate.units.Quantity` values; results are
returned in hertz.
"""

from __future__ import annotations

from math import pi, sqrt

from ..scorecard import CheckStatus, ScorecardEntry
from ..units import Quantity
from .plate import DEFAULT_POISSON_RATIO

__all__ = [
    "STANDARD_GRAVITY",
    "natural_frequency",
    "natural_frequency_from_deflection",
    "string_natural_frequency",
    "dunkerley_fundamental_frequency",
    "cantilever_fundamental_frequency",
    "simply_supported_fundamental_frequency",
    "fixed_fixed_fundamental_frequency",
    "fixed_pinned_fundamental_frequency",
    "simply_supported_plate_fundamental_frequency",
    "clamped_plate_fundamental_frequency",
    "simply_supported_circular_plate_fundamental_frequency",
    "clamped_circular_plate_fundamental_frequency",
    "simply_supported_annular_plate_fundamental_frequency",
    "clamped_annular_plate_fundamental_frequency",
    "torsional_natural_frequency",
    "solid_disc_polar_mass_moment",
    "spring_surge_frequency",
    "frequency_scorecard",
]

# Standard gravitational acceleration (m/s²), for the Rayleigh self-weight estimate.
STANDARD_GRAVITY = Quantity(magnitude=9.80665, unit="m/s**2")

# First-mode Euler-Bernoulli eigenvalues λ₁², one per support condition, each the
# first root of the characteristic transcendental equation (verified by bisection
# to machine precision): cantilever cos·cosh = −1, simply supported sin = 0 (π),
# fixed-fixed cos·cosh = 1, fixed-pinned tan = tanh.
_LAMBDA_SQ_CANTILEVER = 3.5160152685
_LAMBDA_SQ_SIMPLY_SUPPORTED = pi**2
_LAMBDA_SQ_FIXED_FIXED = 22.3732854481
_LAMBDA_SQ_FIXED_PINNED = 15.4182057170


def _require(value: Quantity, expected: str, name: str) -> None:
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )


def natural_frequency(*, stiffness: Quantity, mass: Quantity) -> Quantity:
    """The undamped natural frequency f_n = (1/2π)·√(k/m) of a mass-on-spring system.

    ``stiffness`` is the support stiffness k (force per unit length, e.g. a beam's
    load over its deflection); ``mass`` the supported mass m. Both must be
    positive. Returns the frequency in hertz.
    """
    _require(stiffness, "[force] / [length]", "stiffness")
    _require(mass, "[mass]", "mass")
    k = stiffness.to("N/m").magnitude
    m = mass.to("kg").magnitude
    if k <= 0 or m <= 0:
        raise ValueError("stiffness and mass must be positive")
    return Quantity(magnitude=sqrt(k / m) / (2 * pi), unit="Hz")


def natural_frequency_from_deflection(
    static_deflection: Quantity,
    *,
    gravity: Quantity = STANDARD_GRAVITY,
) -> Quantity:
    """The Rayleigh fundamental-frequency estimate f_n = (1/2π)·√(g/δ).

    ``static_deflection`` δ is the deflection the structure takes under its own
    weight; ``gravity`` defaults to standard g. Returns the frequency in hertz.
    The deflection must be positive.
    """
    _require(static_deflection, "[length]", "static_deflection")
    _require(gravity, "[acceleration]", "gravity")
    delta = static_deflection.to("m").magnitude
    g = gravity.to("m/s**2").magnitude
    if delta <= 0:
        raise ValueError(f"static_deflection must be positive; got {static_deflection}")
    return Quantity(magnitude=sqrt(g / delta) / (2 * pi), unit="Hz")


def string_natural_frequency(
    *,
    tension: Quantity,
    length: Quantity,
    mass_per_length: Quantity,
    mode: int = 1,
) -> Quantity:
    """The transverse natural frequency f_n = (n/2L)·√(T/μ) of a taut string.

    A stretched string or cable — a guitar string, a guyed cable, a transmission
    line — vibrates laterally at frequencies set by its tension, not its bending
    stiffness: f_n = (n/2L)·√(T/μ). ``tension`` T is the axial pull, ``length`` L the
    span between the fixed ends, ``mass_per_length`` μ the mass per unit length, and
    ``mode`` n the harmonic (1 for the fundamental, 2, 3, … for the overtones). The
    wave speed √(T/μ) rises with tension, so tightening a string sharpens its pitch;
    the overtones are exact integer multiples of the fundamental. All quantities must
    be positive and ``mode`` a positive whole number. Returns the frequency in hertz.
    """
    _require(tension, "[force]", "tension")
    _require(length, "[length]", "length")
    _require(mass_per_length, "[mass] / [length]", "mass_per_length")
    n = int(mode)
    if n != mode or n <= 0:
        raise ValueError(f"mode must be a positive whole number; got {mode}")
    t = tension.to("N").magnitude
    ell = length.to("m").magnitude
    mu = mass_per_length.to("kg/m").magnitude
    if t <= 0:
        raise ValueError(f"tension must be positive; got {tension}")
    if ell <= 0:
        raise ValueError(f"length must be positive; got {length}")
    if mu <= 0:
        raise ValueError(f"mass_per_length must be positive; got {mass_per_length}")
    return Quantity(magnitude=n / (2.0 * ell) * sqrt(t / mu), unit="Hz")


def dunkerley_fundamental_frequency(individual_frequencies: list[Quantity]) -> Quantity:
    """The Dunkerley fundamental-frequency estimate for a multi-mass system,
    1/f² = Σ 1/fᵢ².

    A shaft or beam carrying several masses vibrates slower than any single mass
    would alone. Dunkerley's method combines each mass's stand-alone frequency fᵢ
    (the frequency the system would have with only that mass present, from
    :func:`natural_frequency` or :func:`natural_frequency_from_deflection`) into a
    lower-bound estimate of the true fundamental — the standard hand estimate for a
    shaft's first critical (whirl) speed with multiple discs. ``individual_
    frequencies`` is the non-empty list of the fᵢ, each a positive frequency.
    Returns the combined frequency in hertz; it always falls below the lowest fᵢ.
    """
    if not individual_frequencies:
        raise ValueError("individual_frequencies must be a non-empty list")
    inverse_squares = 0.0
    for i, freq in enumerate(individual_frequencies):
        _require(freq, "[frequency]", f"individual_frequencies[{i}]")
        f = freq.to("Hz").magnitude
        if f <= 0:
            raise ValueError(f"each individual frequency must be positive; got {freq}")
        inverse_squares += 1.0 / f**2
    return Quantity(magnitude=1.0 / sqrt(inverse_squares), unit="Hz")


def _beam_fundamental(
    lambda_sq: float,
    *,
    mass_per_length: Quantity,
    length: Quantity,
    second_moment: Quantity,
    elastic_modulus: Quantity,
) -> Quantity:
    _require(mass_per_length, "[mass] / [length]", "mass_per_length")
    _require(length, "[length]", "length")
    _require(second_moment, "[length]**4", "second_moment")
    _require(elastic_modulus, "[pressure]", "elastic_modulus")
    m = mass_per_length.to("kg/m").magnitude
    length_m = length.to("m").magnitude
    inertia = second_moment.to("m**4").magnitude
    e = elastic_modulus.to("Pa").magnitude
    if m <= 0 or length_m <= 0 or inertia <= 0 or e <= 0:
        raise ValueError("mass_per_length, length, second_moment, and E must be positive")
    return Quantity(
        magnitude=lambda_sq * sqrt(e * inertia / (m * length_m**4)) / (2 * pi), unit="Hz"
    )


def cantilever_fundamental_frequency(
    *,
    mass_per_length: Quantity,
    length: Quantity,
    second_moment: Quantity,
    elastic_modulus: Quantity,
) -> Quantity:
    """The fundamental frequency of a cantilever with distributed mass (Blevins).

    Exact Euler-Bernoulli first mode f₁ = (λ₁²/2π)·√(E·I/(m̄·L⁴)) with
    λ₁² = 3.51602 (the first root of cos λ·cosh λ = −1). ``mass_per_length``
    m̄ is the beam's mass per unit length, self-weight plus any smeared
    attachments. Returns hertz; every argument is dimension-checked.
    """
    return _beam_fundamental(
        _LAMBDA_SQ_CANTILEVER,
        mass_per_length=mass_per_length,
        length=length,
        second_moment=second_moment,
        elastic_modulus=elastic_modulus,
    )


def simply_supported_fundamental_frequency(
    *,
    mass_per_length: Quantity,
    length: Quantity,
    second_moment: Quantity,
    elastic_modulus: Quantity,
) -> Quantity:
    """The fundamental frequency of a simply-supported beam with distributed mass.

    Exact Euler-Bernoulli first mode f₁ = (π²/2π)·√(E·I/(m̄·L⁴)) — the one
    support with a clean closed-form eigenvalue (λ₁ = π). Exceeds the Rayleigh
    self-weight estimate from the mid-span deflection by exactly
    π²/√(384/5) ≈ 1.126. Returns hertz; every argument is dimension-checked.
    """
    return _beam_fundamental(
        _LAMBDA_SQ_SIMPLY_SUPPORTED,
        mass_per_length=mass_per_length,
        length=length,
        second_moment=second_moment,
        elastic_modulus=elastic_modulus,
    )


def fixed_fixed_fundamental_frequency(
    *,
    mass_per_length: Quantity,
    length: Quantity,
    second_moment: Quantity,
    elastic_modulus: Quantity,
) -> Quantity:
    """The fundamental frequency of a fixed-fixed beam with distributed mass.

    Exact Euler-Bernoulli first mode with λ₁² = 22.37329 (the first root of
    cos λ·cosh λ = 1) — building in both ends raises the fundamental 2.27×
    over the simply-supported span. Returns hertz; every argument is
    dimension-checked.
    """
    return _beam_fundamental(
        _LAMBDA_SQ_FIXED_FIXED,
        mass_per_length=mass_per_length,
        length=length,
        second_moment=second_moment,
        elastic_modulus=elastic_modulus,
    )


def fixed_pinned_fundamental_frequency(
    *,
    mass_per_length: Quantity,
    length: Quantity,
    second_moment: Quantity,
    elastic_modulus: Quantity,
) -> Quantity:
    """The fundamental frequency of a propped cantilever with distributed mass.

    Exact Euler-Bernoulli first mode with λ₁² = 15.41821 (the first root of
    tan λ = tanh λ), between the simply-supported and fixed-fixed values.
    Returns hertz; every argument is dimension-checked.
    """
    return _beam_fundamental(
        _LAMBDA_SQ_FIXED_PINNED,
        mass_per_length=mass_per_length,
        length=length,
        second_moment=second_moment,
        elastic_modulus=elastic_modulus,
    )


# Clamped-rectangle fundamental coefficients γ = ω·b²·√(μ/D), keyed by b/a
# (short/long side, so 0 is the infinite strip — exactly the fixed-fixed beam
# eigenvalue, the plate stiffening entering only through D's 1/(1−ν²)).
# Interior values from our own finite-difference biharmonic eigensolve
# (13-point stencil, ghost-point clamped edges, Richardson extrapolation over
# paired grids; two independent grid pairs agree to ≤0.02%, and the square
# matches the published Leissa value 35.992 to 0.03%). The knots are denser
# at the slender end, where the approach to the strip limit is from above and
# curved.
_CLAMPED_PLATE_GAMMA = (
    # (b/a, gamma)
    (0.0, _LAMBDA_SQ_FIXED_FIXED),
    (0.2, 22.632),
    (0.25, 22.798),
    (1 / 3.0, 23.196),
    (0.4, 23.643),
    (0.5, 24.577),
    (1 / 1.8, 25.254),
    (1 / 1.6, 26.282),
    (1 / 1.4, 27.930),
    (1 / 1.2, 30.751),
    (1.0, 35.982),
)


def _bessel_j0_j1_i0_i1(x: float) -> tuple[float, float, float, float]:
    """(J₀, J₁, I₀, I₁) by power series — machine-precision for the x ≲ 4 used here."""
    j0 = j1 = i0 = i1 = 0.0
    half = x / 2
    term0 = 1.0  # (x/2)^(2k) / (k!)² at k = 0
    for k in range(40):
        term1 = term0 * half / (k + 1)  # (x/2)^(2k+1) / (k!·(k+1)!)
        sign = -1.0 if k % 2 else 1.0
        j0 += sign * term0
        i0 += term0
        j1 += sign * term1
        i1 += term1
        term0 *= half * half / (k + 1) ** 2
    return j0, j1, i0, i1


def _circular_plate_lambda_sq(*, clamped: bool, poisson_ratio: float) -> float:
    """The first eigenvalue λ² = ω·R²·√(μ/D) of a circular plate, by bisection.

    The mode shape A·J₀(λr/R) + B·I₀(λr/R) gives the exact characteristic
    equations J₀(λ)·I₁(λ) + I₀(λ)·J₁(λ) = 0 for a clamped rim (first root
    λ² = 10.2158, ν-independent) and J₁/J₀ + I₁/I₀ = 2λ/(1 − ν) for a simply
    supported one (λ² = 4.935 at ν = 0.3) — solved here rather than read from
    a table.
    """
    if clamped:

        def f(lam: float) -> float:
            j0, j1, i0, i1 = _bessel_j0_j1_i0_i1(lam)
            return j0 * i1 + i0 * j1

        lo, hi = 2.5, 3.5
    else:
        # The root always lies below J₀'s first zero (2.40483), where J₁/J₀
        # blows up positive; at λ → 0⁺ the left side trails 2λ/(1 − ν).
        def f(lam: float) -> float:
            j0, j1, i0, i1 = _bessel_j0_j1_i0_i1(lam)
            return j1 / j0 + i1 / i0 - 2 * lam / (1 - poisson_ratio)

        lo, hi = 1e-6, 2.4048
    f_lo = f(lo)
    for _ in range(100):
        mid = (lo + hi) / 2
        f_mid = f(mid)
        if f_lo * f_mid <= 0:
            hi = mid
        else:
            lo, f_lo = mid, f_mid
    return ((lo + hi) / 2) ** 2


def _plate_mass_and_rigidity(
    mass_per_area: Quantity,
    thickness: Quantity,
    elastic_modulus: Quantity,
    poisson_ratio: float,
) -> tuple[float, float]:
    """Validate the shared plate-modal arguments -> (μ kg/m², D N·m)."""
    _require(mass_per_area, "[mass] / [length] ** 2", "mass_per_area")
    _require(thickness, "[length]", "thickness")
    _require(elastic_modulus, "[pressure]", "elastic_modulus")
    if not 0 < poisson_ratio < 0.5:
        raise ValueError(f"poisson_ratio must lie in (0, 0.5); got {poisson_ratio}")
    mu = mass_per_area.to("kg/m**2").magnitude
    t = thickness.to("m").magnitude
    e = elastic_modulus.to("Pa").magnitude
    if mu <= 0 or t <= 0 or e <= 0:
        raise ValueError("mass_per_area, thickness, and E must be positive")
    return mu, e * t**3 / (12 * (1 - poisson_ratio**2))


def _rect_plate_sides(length: Quantity, width: Quantity) -> tuple[float, float]:
    """Validate rectangular plan sides -> (a, b) in metres with b the short side."""
    _require(length, "[length]", "length")
    _require(width, "[length]", "width")
    a = length.to("m").magnitude
    b = width.to("m").magnitude
    if a <= 0 or b <= 0:
        raise ValueError("length and width must be positive")
    return (a, b) if a >= b else (b, a)


def simply_supported_plate_fundamental_frequency(
    *,
    mass_per_area: Quantity,
    length: Quantity,
    width: Quantity,
    thickness: Quantity,
    elastic_modulus: Quantity,
    poisson_ratio: float = DEFAULT_POISSON_RATIO,
) -> Quantity:
    """The fundamental frequency of a simply-supported rectangular plate (exact).

    A thin flat plate of plan ``length`` a × ``width`` b, simply supported on
    all edges, with ``mass_per_area`` μ (self-weight ρ·t plus any smeared
    attachments) — the one plate with a clean closed-form eigenvalue:
    f₁ = (π/2)·(1/a² + 1/b²)·√(D/μ) on the rigidity D = E·t³/(12·(1 − ν²)).
    A wide strip recovers the simply-supported beam's π² eigenvalue, stiffened
    by exactly 1/√(1 − ν²) through D. Returns hertz; every quantity argument
    is dimension-checked and ν must lie in (0, 0.5).
    """
    mu, rigidity = _plate_mass_and_rigidity(
        mass_per_area, thickness, elastic_modulus, poisson_ratio
    )
    a, b = _rect_plate_sides(length, width)
    return Quantity(magnitude=(pi / 2) * (1 / a**2 + 1 / b**2) * sqrt(rigidity / mu), unit="Hz")


def clamped_plate_fundamental_frequency(
    *,
    mass_per_area: Quantity,
    length: Quantity,
    width: Quantity,
    thickness: Quantity,
    elastic_modulus: Quantity,
    poisson_ratio: float = DEFAULT_POISSON_RATIO,
) -> Quantity:
    """The fundamental frequency of a rectangular plate with all edges clamped.

    A thin flat plate of plan ``length`` × ``width`` with all four edges built
    in and ``mass_per_area`` μ: f₁ = (γ/2π)·√(D/(μ·b⁴)) with b the short side
    and γ interpolated from a finite-difference-verified eigenvalue table
    (22.373, the exact fixed-fixed beam value, at the strip limit; 35.98 for
    the square — clamping raises the square's fundamental 1.82× over simply
    supported). Returns hertz; every quantity argument is dimension-checked
    and ν must lie in (0, 0.5).
    """
    mu, rigidity = _plate_mass_and_rigidity(
        mass_per_area, thickness, elastic_modulus, poisson_ratio
    )
    a, b = _rect_plate_sides(length, width)
    ratio = b / a
    for (r_lo, g_lo), (r_hi, g_hi) in zip(
        _CLAMPED_PLATE_GAMMA, _CLAMPED_PLATE_GAMMA[1:], strict=False
    ):
        if ratio <= r_hi:
            gamma = g_lo + (ratio - r_lo) / (r_hi - r_lo) * (g_hi - g_lo)
            break
    return Quantity(magnitude=gamma / (2 * pi) * sqrt(rigidity / (mu * b**4)), unit="Hz")


def simply_supported_circular_plate_fundamental_frequency(
    *,
    mass_per_area: Quantity,
    diameter: Quantity,
    thickness: Quantity,
    elastic_modulus: Quantity,
    poisson_ratio: float = DEFAULT_POISSON_RATIO,
) -> Quantity:
    """The fundamental frequency of a circular plate simply supported at its rim.

    A round plate of ``diameter`` 2R resting on a gasket or ledge, with
    ``mass_per_area`` μ: f₁ = (λ²/2π)·√(D/(μ·R⁴)), λ² solved at runtime from
    the exact Bessel characteristic equation J₁/J₀ + I₁/I₀ = 2λ/(1 − ν)
    (λ² = 4.935 at ν = 0.3 — some handbooks print 4.977, which our Rayleigh
    bound rules out). Returns hertz; every quantity argument is
    dimension-checked and ν must lie in (0, 0.5).
    """
    mu, rigidity = _plate_mass_and_rigidity(
        mass_per_area, thickness, elastic_modulus, poisson_ratio
    )
    radius = _positive_radius(diameter)
    lam_sq = _circular_plate_lambda_sq(clamped=False, poisson_ratio=poisson_ratio)
    return Quantity(magnitude=lam_sq / (2 * pi) * sqrt(rigidity / (mu * radius**4)), unit="Hz")


def clamped_circular_plate_fundamental_frequency(
    *,
    mass_per_area: Quantity,
    diameter: Quantity,
    thickness: Quantity,
    elastic_modulus: Quantity,
    poisson_ratio: float = DEFAULT_POISSON_RATIO,
) -> Quantity:
    """The fundamental frequency of a circular plate clamped at its rim.

    A round plate of ``diameter`` 2R welded or stiffly bolted all around, with
    ``mass_per_area`` μ: f₁ = (λ²/2π)·√(D/(μ·R⁴)), λ² = 10.2158 solved at
    runtime from the exact characteristic equation J₀·I₁ + I₀·J₁ = 0 — the
    eigenvalue is ν-independent (ν enters only through D), and clamping the
    rim raises the fundamental 2.07× over the gasketed plate at ν = 0.3.
    Returns hertz; every quantity argument is dimension-checked and ν must
    lie in (0, 0.5).
    """
    mu, rigidity = _plate_mass_and_rigidity(
        mass_per_area, thickness, elastic_modulus, poisson_ratio
    )
    radius = _positive_radius(diameter)
    lam_sq = _circular_plate_lambda_sq(clamped=True, poisson_ratio=poisson_ratio)
    return Quantity(magnitude=lam_sq / (2 * pi) * sqrt(rigidity / (mu * radius**4)), unit="Hz")


def _positive_radius(diameter: Quantity) -> float:
    """Validate a plate diameter -> radius in metres."""
    _require(diameter, "[length]", "diameter")
    radius = diameter.to("m").magnitude / 2
    if radius <= 0:
        raise ValueError(f"diameter must be positive; got {diameter}")
    return radius


# Annular-plate (free inner edge) fundamental coefficients γ = ω·R²·√(μ/D)
# with R the OUTER radius, keyed by the hole ratio b/a, at ν = 0.3 (the free
# inner edge's moment condition makes the eigenvalue ν-dependent, so the
# table pins the same ν the static tables use). Values from our own
# finite-difference eigensolve of the axisymmetric plate ODE (ghost-point
# BCs, Richardson over paired grids; the n = 150/300 and n = 400/800 pairs
# agree to ≤0.02%, and b/a → 0 approaches the exact solid-plate roots that
# open each table). Both families are NON-monotonic near small holes — a
# mid-size hole removes mass faster than stiffness and LOWERS the
# simply-supported fundamental below the solid plate's.
_ANNULAR_PLATE_GAMMA_SS = (
    # (b/a, gamma)
    (0.0, 4.9351),
    (0.05, 4.912),
    (0.1, 4.853),
    (0.15, 4.782),
    (0.2, 4.718),
    (0.25, 4.675),
    (0.3, 4.664),
    (0.35, 4.692),
    (0.4, 4.764),
    (0.45, 4.889),
    (0.5, 5.076),
    (0.55, 5.344),
    (0.6, 5.710),
    (0.65, 6.220),
    (0.7, 6.930),
    (0.75, 7.962),
    (0.8, 9.548),
)
_ANNULAR_PLATE_GAMMA_CLAMPED = (
    (0.0, 10.2158),
    (0.05, 10.189),
    (0.1, 10.159),
    (0.15, 10.210),
    (0.2, 10.408),
    (0.25, 10.799),
    (0.3, 11.424),
    (0.35, 12.334),
    (0.4, 13.602),
    (0.45, 15.339),
    (0.5, 17.714),
    (0.55, 21.006),
    (0.6, 25.674),
    (0.65, 32.537),
    (0.7, 43.142),
    (0.75, 60.730),
    (0.8, 93.035),
)


def _annular_plate_fundamental(
    table: tuple[tuple[float, float], ...],
    *,
    mass_per_area: Quantity,
    diameter: Quantity,
    hole_diameter: Quantity,
    thickness: Quantity,
    elastic_modulus: Quantity,
) -> Quantity:
    # The table is computed at ν = 0.3, so the rigidity pins the same value.
    mu, rigidity = _plate_mass_and_rigidity(
        mass_per_area, thickness, elastic_modulus, DEFAULT_POISSON_RATIO
    )
    radius = _positive_radius(diameter)
    _require(hole_diameter, "[length]", "hole_diameter")
    hole_radius = hole_diameter.to("m").magnitude / 2
    ratio = hole_radius / radius
    if not 0 < ratio <= table[-1][0]:
        raise ValueError(
            f"the hole ratio {ratio:.2f} must lie in (0, {table[-1][0]}] — "
            "the encoded eigenvalue range"
        )
    for (r_lo, g_lo), (r_hi, g_hi) in zip(table, table[1:], strict=False):
        if ratio <= r_hi:
            gamma = g_lo + (ratio - r_lo) / (r_hi - r_lo) * (g_hi - g_lo)
            break
    return Quantity(magnitude=gamma / (2 * pi) * sqrt(rigidity / (mu * radius**4)), unit="Hz")


def simply_supported_annular_plate_fundamental_frequency(
    *,
    mass_per_area: Quantity,
    diameter: Quantity,
    hole_diameter: Quantity,
    thickness: Quantity,
    elastic_modulus: Quantity,
) -> Quantity:
    """The fundamental frequency of a simply-supported annular plate (free hole).

    A round plate of ``diameter`` 2R with a concentric free-edged hole of
    ``hole_diameter`` 2b, simply supported at its rim, with ``mass_per_area``
    μ: f₁ = (γ/2π)·√(D/(μ·R⁴)), γ interpolated from our
    finite-difference-verified eigenvalue table (ν = 0.3, hole ratio up to
    0.8). Counter-intuitively a mid-size hole LOWERS the fundamental (γ dips
    to 4.66 at b/a = 0.3 against the solid plate's 4.94) — the hole sheds
    mass faster than bending stiffness until it starts crowding the rim.
    Returns hertz; every quantity argument is dimension-checked.
    """
    return _annular_plate_fundamental(
        _ANNULAR_PLATE_GAMMA_SS,
        mass_per_area=mass_per_area,
        diameter=diameter,
        hole_diameter=hole_diameter,
        thickness=thickness,
        elastic_modulus=elastic_modulus,
    )


def clamped_annular_plate_fundamental_frequency(
    *,
    mass_per_area: Quantity,
    diameter: Quantity,
    hole_diameter: Quantity,
    thickness: Quantity,
    elastic_modulus: Quantity,
) -> Quantity:
    """The fundamental frequency of a clamped-rim annular plate (free hole).

    A round plate of ``diameter`` 2R with a concentric free-edged hole of
    ``hole_diameter`` 2b, its outer rim built in, with ``mass_per_area`` μ:
    f₁ = (γ/2π)·√(D/(μ·R⁴)), γ interpolated from our
    finite-difference-verified eigenvalue table (ν = 0.3, hole ratio up to
    0.8; 10.2158 at the solid limit, rising steeply once the hole crowds the
    clamped rim — 4.2× the solid eigenvalue at b/a = 0.7). Returns hertz;
    every quantity argument is dimension-checked.
    """
    return _annular_plate_fundamental(
        _ANNULAR_PLATE_GAMMA_CLAMPED,
        mass_per_area=mass_per_area,
        diameter=diameter,
        hole_diameter=hole_diameter,
        thickness=thickness,
        elastic_modulus=elastic_modulus,
    )


def solid_disc_polar_mass_moment(*, mass: Quantity, diameter: Quantity) -> Quantity:
    """The polar mass moment of inertia I = m·d²/8 (= m·r²/2) of a solid disc.

    The rotary inertia of a flywheel, coupling, or brake disc about the shaft
    axis — the mass term of a torsional resonance. ``mass`` and ``diameter``
    must be positive. Returns kg·m²; both arguments are dimension-checked.
    """
    _require(mass, "[mass]", "mass")
    _require(diameter, "[length]", "diameter")
    m = mass.to("kg").magnitude
    d = diameter.to("m").magnitude
    if m <= 0 or d <= 0:
        raise ValueError("mass and diameter must be positive")
    return Quantity(magnitude=m * d**2 / 8, unit="kg*m**2")


def torsional_natural_frequency(
    *,
    torsional_stiffness: Quantity,
    polar_mass_moment: Quantity,
) -> Quantity:
    """The torsional natural frequency f_n = (1/2π)·√(k_t/I) of a disc on a shaft.

    The rotational counterpart of :func:`natural_frequency`: a rotary inertia
    ``polar_mass_moment`` I (e.g. :func:`solid_disc_polar_mass_moment`) on a
    shaft of ``torsional_stiffness`` k_t (torque per radian of twist, e.g.
    :func:`anvilate.analysis.shaft_torsional_stiffness`) resonates in twist at
    f_n — the drivetrain mode that torque pulsation (engine firing, VFD
    ripple) excites. Both must be positive. Returns hertz.
    """
    _require(torsional_stiffness, "[force] * [length]", "torsional_stiffness")
    _require(polar_mass_moment, "[mass] * [length]**2", "polar_mass_moment")
    k = torsional_stiffness.to("N*m").magnitude
    inertia = polar_mass_moment.to("kg*m**2").magnitude
    if k <= 0 or inertia <= 0:
        raise ValueError("torsional_stiffness and polar_mass_moment must be positive")
    return Quantity(magnitude=sqrt(k / inertia) / (2 * pi), unit="Hz")


def spring_surge_frequency(*, spring_rate: Quantity, spring_mass: Quantity) -> Quantity:
    """The spring surge (axial resonance) frequency f₁ = (1/2)·√(k/m).

    A helical compression spring between parallel seats is a distributed
    elastic rod fixed at both ends, so its first axial mode is exactly
    f₁ = (1/2)·√(k/m) on its ``spring_rate`` k and its OWN ``spring_mass`` m —
    exactly π× the SDOF (1/2π)·√(k/m) shortcut. A cam lobe or load pulsation
    near f₁ (or a strong harmonic of the drive landing on it) makes the coils
    surge and the spring momentarily lose control of what it holds. Returns
    hertz; both arguments are dimension-checked and must be positive.
    """
    _require(spring_rate, "[force] / [length]", "spring_rate")
    _require(spring_mass, "[mass]", "spring_mass")
    k = spring_rate.to("N/m").magnitude
    m = spring_mass.to("kg").magnitude
    if k <= 0 or m <= 0:
        raise ValueError("spring_rate and spring_mass must be positive")
    return Quantity(magnitude=sqrt(k / m) / 2, unit="Hz")


def frequency_scorecard(
    name: str,
    *,
    frequency: Quantity,
    min_frequency: Quantity | None,
) -> ScorecardEntry:
    """Screen a fundamental ``frequency`` against a required minimum for resonance.

    To avoid resonance a part's fundamental frequency should sit above the highest
    operating excitation, so this is ``PASS`` when ``frequency`` is at least
    ``min_frequency`` and ``FAIL`` below it. When ``min_frequency`` is ``None`` — no
    excitation requirement was declared — the entry is ``NOT_EVALUATED`` rather than
    a silent pass. Both quantities must be frequencies.
    """
    _require(frequency, "[frequency]", "frequency")
    if min_frequency is None:
        return ScorecardEntry(
            name=name,
            status=CheckStatus.NOT_EVALUATED,
            detail="not evaluated — minimum frequency unavailable",
        )
    _require(min_frequency, "[frequency]", "min_frequency")
    fn = frequency.to("Hz").magnitude
    floor = min_frequency.to("Hz").magnitude
    status = CheckStatus.PASS if fn >= floor else CheckStatus.FAIL
    return ScorecardEntry(
        name=name,
        status=status,
        detail=f"fundamental {fn:.1f} Hz vs required minimum {floor:.1f} Hz",
    )
