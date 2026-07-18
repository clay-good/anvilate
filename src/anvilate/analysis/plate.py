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
  closed forms;
* **annulus (a circle with a free-edged concentric hole), outer edge simply
  supported or clamped** — the exact axisymmetric general solution
  w = q·r⁴/64D + C₁ + C₂·r² + C₃·ln r + C₄·r²·ln r with the constants solved
  from the boundary conditions at runtime (verified against an independent
  finite-difference solve of the plate ODE).

These are screening checks: linear-elastic thin-plate theory, small
deflections (w ≲ t/2), uniform pressure. Every input and output is a
dimension-checked :class:`~anvilate.units.Quantity`.
"""

from __future__ import annotations

from math import log, pi, sin, sqrt

from pydantic import BaseModel, ConfigDict

from ..units import Quantity

__all__ = [
    "PlateBendingResult",
    "simply_supported_plate_uniform_load",
    "simply_supported_plate_center_patch_load",
    "clamped_plate_uniform_load",
    "simply_supported_circular_plate_uniform_load",
    "clamped_circular_plate_uniform_load",
    "simply_supported_circular_plate_center_load_deflection",
    "clamped_circular_plate_center_load_deflection",
    "simply_supported_annular_plate_uniform_load",
    "clamped_annular_plate_uniform_load",
    "clamped_circular_plate_thickness_for_pressure",
    "plate_buckling_stress",
    "plate_shear_buckling_coefficient",
    "plate_compression_buckling_coefficient",
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


def simply_supported_plate_center_patch_load(
    *,
    pressure: Quantity,
    patch_length: Quantity,
    patch_width: Quantity,
    length: Quantity,
    width: Quantity,
    thickness: Quantity,
    elastic_modulus: Quantity,
    poisson_ratio: float = DEFAULT_POISSON_RATIO,
) -> PlateBendingResult:
    """The simply-supported plate loaded over a centred patch (Navier).

    A thin flat plate of plan ``length`` a × ``width`` b, simply supported on
    all edges, carrying ``pressure`` q₀ over a centred ``patch_length`` u ×
    ``patch_width`` v footprint only — a machine foot, a pedestal, a stacked
    load on a panel. Solved by the same exact Navier series as
    :func:`simply_supported_plate_uniform_load` with the patch Fourier load
    coefficient q_mn = (16·q₀/π²mn)·sin(mπu/2a)·sin(nπv/2b); at u = a, v = b
    the two functions agree term-for-term. Peak stress and deflection are at
    the plate centre. Shrinking the patch at fixed total load drives the
    centre stress up without bound (the point-load moment singularity) —
    declaring the real footprint is what keeps the screen honest.

    Thin-plate screening limits apply (trustworthy while w ≲ t/2). Every
    quantity argument is dimension-checked; the patch must fit inside the
    plate and ν must lie in (0, 0.5).
    """
    _require(pressure, "[pressure]", "pressure")
    _require(patch_length, "[length]", "patch_length")
    _require(patch_width, "[length]", "patch_width")
    _require(length, "[length]", "length")
    _require(width, "[length]", "width")
    _require(thickness, "[length]", "thickness")
    _require(elastic_modulus, "[pressure]", "elastic_modulus")
    if not 0 < poisson_ratio < 0.5:
        raise ValueError(f"poisson_ratio must lie in (0, 0.5); got {poisson_ratio}")

    q = pressure.to("MPa").magnitude
    a = length.to("mm").magnitude
    b = width.to("mm").magnitude
    u = patch_length.to("mm").magnitude
    v = patch_width.to("mm").magnitude
    t = thickness.to("mm").magnitude
    e = elastic_modulus.to("MPa").magnitude
    if min(q, a, b, t, e) <= 0:
        raise ValueError("pressure, plan dimensions, thickness, and E must be positive")
    if not 0 < u <= a or not 0 < v <= b:
        raise ValueError(
            f"the patch ({patch_length} x {patch_width}) must fit inside the "
            f"plate ({length} x {width})"
        )

    rigidity = e * t**3 / (12 * (1 - poisson_ratio**2))

    w_sum = mx_sum = my_sum = 0.0
    for m in range(1, _SERIES_MAX_HARMONIC + 1, 2):
        s_u = sin(m * pi * u / (2 * a))
        for n in range(1, _SERIES_MAX_HARMONIC + 1, 2):
            # The load-position factor sin(m*pi/2) equals the centre evaluation
            # factor, squaring to +1 for odd harmonics.
            s = s_u * sin(n * pi * v / (2 * b))
            k = m**2 / a**2 + n**2 / b**2
            coef = 16 * s / (pi**2 * m * n)
            w_sum += coef / (pi**4 * k**2)
            mx_sum += coef * (m**2 / a**2 + poisson_ratio * n**2 / b**2) / (pi**2 * k**2)
            my_sum += coef * (poisson_ratio * m**2 / a**2 + n**2 / b**2) / (pi**2 * k**2)

    deflection = q / rigidity * w_sum
    moment = q * max(mx_sum, my_sum)
    stress = 6 * moment / t**2
    return PlateBendingResult(
        max_bending_stress=Quantity(magnitude=stress, unit="MPa"),
        max_deflection=Quantity(magnitude=deflection, unit="mm"),
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


def _circular_plate_point_inputs(
    force: Quantity,
    diameter: Quantity,
    thickness: Quantity,
    elastic_modulus: Quantity,
    poisson_ratio: float,
) -> tuple[float, float, float]:
    """Validate a centrally-point-loaded circular plate -> (P N, R mm, D N·mm)."""
    _require(force, "[force]", "force")
    _require(diameter, "[length]", "diameter")
    _require(thickness, "[length]", "thickness")
    _require(elastic_modulus, "[pressure]", "elastic_modulus")
    if not 0 < poisson_ratio < 0.5:
        raise ValueError(f"poisson_ratio must lie in (0, 0.5); got {poisson_ratio}")
    p = force.to("N").magnitude
    radius = diameter.to("mm").magnitude / 2
    t = thickness.to("mm").magnitude
    e = elastic_modulus.to("MPa").magnitude
    if min(p, radius, t, e) <= 0:
        raise ValueError("force, diameter, thickness, and E must be positive")
    rigidity = e * t**3 / (12 * (1 - poisson_ratio**2))
    return p, radius, rigidity


def simply_supported_circular_plate_center_load_deflection(
    *,
    force: Quantity,
    diameter: Quantity,
    thickness: Quantity,
    elastic_modulus: Quantity,
    poisson_ratio: float = DEFAULT_POISSON_RATIO,
) -> Quantity:
    """The centre deflection of a simply-supported circular plate under a central
    point load (Roark / Timoshenko).

    A round plate of ``diameter`` 2R and ``thickness`` t, simply supported at its
    rim, carrying a concentrated ``force`` P at its centre — a strut bearing on a
    cover, a jack pad. The centre deflects

        w = P·R²·(3 + ν) / (16·π·D·(1 + ν)),

    with the flexural rigidity D = E·t³/(12(1 − ν²)). Only the deflection is
    returned: under a mathematically concentrated load the centre *bending stress*
    is logarithmically singular, so a usable stress needs the load spread over a
    finite radius (Roark), which this screen does not model. Thin-plate limits apply
    (trustworthy while w ≲ t/2). Every quantity is dimension-checked; ν ∈ (0, 0.5).
    Returns the centre deflection in millimetres.
    """
    p, radius, rigidity = _circular_plate_point_inputs(
        force, diameter, thickness, elastic_modulus, poisson_ratio
    )
    deflection = p * radius**2 * (3 + poisson_ratio) / (16 * pi * rigidity * (1 + poisson_ratio))
    return Quantity(magnitude=deflection, unit="mm")


def clamped_circular_plate_center_load_deflection(
    *,
    force: Quantity,
    diameter: Quantity,
    thickness: Quantity,
    elastic_modulus: Quantity,
    poisson_ratio: float = DEFAULT_POISSON_RATIO,
) -> Quantity:
    """The centre deflection of a clamped circular plate under a central point load
    (Roark / Timoshenko).

    The clamped-rim counterpart of
    :func:`simply_supported_circular_plate_center_load_deflection`: with the edge
    fully fixed the same concentrated ``force`` P at the centre deflects only

        w = P·R² / (16·π·D),

    exactly (1 + ν)/(3 + ν) of the simply-supported value (≈ 0.39× at ν = 0.3) —
    clamping stiffens the plate against a point load just as it does against
    pressure. As with the simply-supported case only the deflection is returned (the
    centre stress is singular for a true point load; the finite radial bending lives
    at the clamped edge and needs a load radius to pin the centre). Thin-plate limits
    apply. Every quantity is dimension-checked; ν ∈ (0, 0.5). Returns the centre
    deflection in millimetres.
    """
    p, radius, rigidity = _circular_plate_point_inputs(
        force, diameter, thickness, elastic_modulus, poisson_ratio
    )
    deflection = p * radius**2 / (16 * pi * rigidity)
    return Quantity(magnitude=deflection, unit="mm")


def clamped_circular_plate_thickness_for_pressure(
    *,
    pressure: Quantity,
    diameter: Quantity,
    allowable_stress: Quantity,
    required_safety_factor: float = 1.0,
) -> Quantity:
    """The least thickness of a clamped circular cover to hold ``pressure`` within
    an allowable bending stress.

    The inverse of :func:`clamped_circular_plate_uniform_load`'s governing rim
    stress σ = 3·q·R²/(4·t²): demanding it stay within σ_allow/n gives
    t_min = R·√(3·n·q/(4·σ_allow)) — the sizing step for a round pressure cover or
    blind flange with a stiffly held (welded/bolted) rim. ``pressure`` q is the
    uniform pressure, ``diameter`` 2R the plate diameter, ``allowable_stress``
    σ_allow the material's allowable bending stress, and ``required_safety_factor``
    n the margin on it (default 1.0). Returns the minimum thickness in mm; a
    strength (stress) size — re-check the deflection separately if stiffness
    governs. The pressure/diameter/stress are dimension-checked and ``n`` /
    ``allowable_stress`` must be positive.
    """
    _require(pressure, "[pressure]", "pressure")
    _require(diameter, "[length]", "diameter")
    _require(allowable_stress, "[pressure]", "allowable_stress")
    if required_safety_factor <= 0:
        raise ValueError(f"required_safety_factor must be positive; got {required_safety_factor}")
    q = pressure.to("MPa").magnitude
    radius = diameter.to("mm").magnitude / 2
    sigma = allowable_stress.to("MPa").magnitude
    if radius <= 0:
        raise ValueError(f"diameter must be positive; got {diameter}")
    if sigma <= 0:
        raise ValueError(f"allowable_stress must be positive; got {allowable_stress}")
    t_min = radius * sqrt(3 * required_safety_factor * q / (4 * sigma))
    return Quantity(magnitude=t_min, unit="mm")


def _annular_plate_uniform_load(
    *,
    pressure: Quantity,
    diameter: Quantity,
    hole_diameter: Quantity,
    thickness: Quantity,
    elastic_modulus: Quantity,
    poisson_ratio: float,
    clamped: bool,
) -> PlateBendingResult:
    """The exact axisymmetric annular-plate solution, outer edge SS or clamped.

    General solution w = q·r⁴/64D + C₁ + C₂·r² + C₃·ln(r/a) + C₄·r²·ln(r/a).
    Vertical equilibrium at the free inner edge (the Kirchhoff shear of the
    C₄ term is −4D·C₄/r) pins C₄ = −q·b²/8D; Mr(b) = 0 and the outer-edge
    condition give C₂ and C₃ as a 2×2 solve; w(a) = 0 gives C₁. Peak stress
    and deflection are then scanned over the radius.
    """
    q, a, t, rigidity = _circular_plate_inputs(
        pressure, diameter, thickness, elastic_modulus, poisson_ratio
    )
    _require(hole_diameter, "[length]", "hole_diameter")
    b = hole_diameter.to("mm").magnitude / 2
    if not 0 < b < a:
        raise ValueError(f"the hole ({hole_diameter}) must be smaller than the plate ({diameter})")
    nu = poisson_ratio
    c4 = -q * b**2 / (8 * rigidity)

    # Mr ∝ w'' + ν·w'/r = P(r) + 2(1+ν)·C₂ + (ν−1)/r²·C₃, with P the
    # particular-plus-C₄ part.
    def p_term(r: float) -> float:
        ln = log(r / a)
        return q * r**2 * (3 + nu) / (16 * rigidity) + c4 * (2 * (1 + nu) * ln + 3 + nu)

    # Rows (coef_C2, coef_C3, rhs): the free inner edge, then the outer edge.
    a11, a12, r1 = 2 * (1 + nu), (nu - 1) / b**2, -p_term(b)
    if clamped:
        # w'(a) = 0: q·a³/16D + 2·C₂·a + C₃/a + C₄·a = 0
        a21, a22, r2 = 2 * a, 1 / a, -(q * a**3 / (16 * rigidity) + c4 * a)
    else:
        a21, a22, r2 = 2 * (1 + nu), (nu - 1) / a**2, -p_term(a)
    det = a11 * a22 - a12 * a21
    c2 = (r1 * a22 - a12 * r2) / det
    c3 = (a11 * r2 - r1 * a21) / det
    c1 = -(q * a**4 / (64 * rigidity) + c2 * a**2)  # w(a) = 0; ln(a/a) = 0

    deflection = 0.0
    moment = 0.0
    steps = 1000
    for i in range(steps + 1):
        r = b + (a - b) * i / steps
        ln = log(r / a)
        w = q * r**4 / (64 * rigidity) + c1 + c2 * r**2 + c3 * ln + c4 * r**2 * ln
        wp = q * r**3 / (16 * rigidity) + 2 * c2 * r + c3 / r + c4 * (2 * r * ln + r)
        wpp = 3 * q * r**2 / (16 * rigidity) + 2 * c2 - c3 / r**2 + c4 * (2 * ln + 3)
        m_r = -rigidity * (wpp + nu * wp / r)
        m_t = -rigidity * (nu * wpp + wp / r)
        deflection = max(deflection, abs(w))
        moment = max(moment, abs(m_r), abs(m_t))

    stress = 6 * moment / t**2
    return PlateBendingResult(
        max_bending_stress=Quantity(magnitude=stress, unit="MPa"),
        max_deflection=Quantity(magnitude=deflection, unit="mm"),
    )


def simply_supported_annular_plate_uniform_load(
    *,
    pressure: Quantity,
    diameter: Quantity,
    hole_diameter: Quantity,
    thickness: Quantity,
    elastic_modulus: Quantity,
    poisson_ratio: float = DEFAULT_POISSON_RATIO,
) -> PlateBendingResult:
    """The simply-supported annular plate (free-edged centre hole) under pressure.

    A round cover of ``diameter`` 2a with a concentric free-edged hole of
    ``hole_diameter`` 2b — a blind with a sight port, a seal gland, a spacer
    ring — simply supported at its rim, carrying uniform ``pressure`` q over
    the annulus. Solved exactly at runtime from the axisymmetric general
    solution (verified against an independent finite-difference solve). The
    peak stress is the TANGENTIAL bending at the hole edge — cutting the hole
    concentrates hoop bending there (1.77× the solid plate's centre stress at
    b/a = 0.2), and shrinking the hole does not shed it: the deflection
    recovers the solid plate's but the hole-edge stress concentration
    persists, which is why the hole must be declared. Thin-plate screening
    limits apply (trustworthy while w ≲ t/2). Every quantity argument is
    dimension-checked; ν must lie in (0, 0.5).
    """
    return _annular_plate_uniform_load(
        pressure=pressure,
        diameter=diameter,
        hole_diameter=hole_diameter,
        thickness=thickness,
        elastic_modulus=elastic_modulus,
        poisson_ratio=poisson_ratio,
        clamped=False,
    )


def clamped_annular_plate_uniform_load(
    *,
    pressure: Quantity,
    diameter: Quantity,
    hole_diameter: Quantity,
    thickness: Quantity,
    elastic_modulus: Quantity,
    poisson_ratio: float = DEFAULT_POISSON_RATIO,
) -> PlateBendingResult:
    """The clamped-rim annular plate (free-edged centre hole) under pressure.

    A round plate of ``diameter`` 2a with a concentric free-edged hole of
    ``hole_diameter`` 2b, its outer rim built in — welded all around, or
    bolted stiffly enough to hold the edge slope — under uniform ``pressure``
    q over the annulus. Solved exactly at runtime from the axisymmetric
    general solution (verified against an independent finite-difference
    solve). Unlike the simply-supported annulus, the governing stress stays
    the RADIAL bending at the clamped rim (the weld or bolt circle carries
    it); the hole mainly costs deflection. Thin-plate screening limits apply
    (trustworthy while w ≲ t/2). Every quantity argument is
    dimension-checked; ν must lie in (0, 0.5).
    """
    return _annular_plate_uniform_load(
        pressure=pressure,
        diameter=diameter,
        hole_diameter=hole_diameter,
        thickness=thickness,
        elastic_modulus=elastic_modulus,
        poisson_ratio=poisson_ratio,
        clamped=True,
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


def plate_buckling_stress(
    *,
    buckling_coefficient: float,
    elastic_modulus: Quantity,
    thickness: Quantity,
    width: Quantity,
    poisson_ratio: float = DEFAULT_POISSON_RATIO,
) -> Quantity:
    """The elastic critical buckling stress of a flat plate in in-plane compression.

    A thin plate or beam web loaded edgewise buckles out of plane long before it
    squashes, at σ_cr = k·π²·E/(12·(1−ν²))·(t/b)². ``buckling_coefficient`` k rolls
    up the edge support and aspect ratio (k ≈ 4.0 for a long simply-supported plate,
    6.97 clamped on the unloaded edges, 0.425 with one edge free — read from a
    table, so supplied as an argument); ``elastic_modulus`` E is the material's,
    ``thickness`` t the plate thickness, ``width`` b the loaded-edge width (the
    dimension across the buckle), and ``poisson_ratio`` ν. The stress goes as
    (t/b)², so a slender plate buckles far below yield — the reason webs and thin
    covers need stiffeners. k, E, t, b must be positive and ν in (0, 0.5). Returns
    the critical stress in MPa.
    """
    _require(elastic_modulus, "[pressure]", "elastic_modulus")
    _require(thickness, "[length]", "thickness")
    _require(width, "[length]", "width")
    if buckling_coefficient <= 0:
        raise ValueError(f"buckling_coefficient must be positive; got {buckling_coefficient}")
    if not 0 < poisson_ratio < 0.5:
        raise ValueError(f"poisson_ratio must lie in (0, 0.5); got {poisson_ratio}")
    e = elastic_modulus.to("MPa").magnitude
    t = thickness.to("mm").magnitude
    b = width.to("mm").magnitude
    if t <= 0 or b <= 0:
        raise ValueError("thickness and width must be positive")
    sigma = buckling_coefficient * pi**2 * e / (12.0 * (1.0 - poisson_ratio**2)) * (t / b) ** 2
    return Quantity(magnitude=sigma, unit="MPa")


def plate_shear_buckling_coefficient(*, aspect_ratio: float) -> float:
    """The shear-buckling coefficient k_s of a simply-supported rectangular plate.

    A plate loaded in edge *shear* (a beam web under shear, say) buckles in a
    diagonal pattern at a critical stress k_s·π²·E/(12(1−ν²))·(t/b)² — the same form
    as :func:`plate_buckling_stress`, but with the shear coefficient in place of the
    compression one. For a simply-supported plate that coefficient has a closed form
    in the panel aspect ratio a/b (long side over short side, ≥ 1):

        k_s = 5.34 + 4·(b/a)²   (a ≥ b)

    so a very long panel tends to k_s = 5.34 and a square one to 9.34 — closer web
    stiffeners (smaller a/b) raise the buckling stress. Pass the result as the
    ``buckling_coefficient`` to :func:`plate_buckling_stress`. ``aspect_ratio`` a/b
    must be at least 1 (orient the panel so the loaded pair is the longer). Returns
    the dimensionless k_s.
    """
    if aspect_ratio < 1:
        raise ValueError(
            f"aspect_ratio (long side / short side) must be at least 1; got {aspect_ratio}"
        )
    return 5.34 + 4.0 / aspect_ratio**2


def plate_compression_buckling_coefficient(*, aspect_ratio: float) -> float:
    """The compression-buckling coefficient k of a simply-supported plate.

    A rectangular plate simply supported on all edges and pushed edgewise buckles
    into m half-waves along its loaded length; the critical coefficient is the value
    of (m·b/a + a/(m·b))² for the integer m that minimises it — the plate picks the
    wave count that buckles soonest. For a loaded length a and unloaded width b
    (``aspect_ratio`` γ = a/b), k = min over m of (m/γ + γ/m)². The minimum touches
    4 whenever γ is an integer (the plate buckles into γ square-ish cells) and rises
    only slightly between, so a long plate sits essentially at k = 4. Pass the result
    as the ``buckling_coefficient`` to :func:`plate_buckling_stress`. ``aspect_ratio``
    must be positive. Returns the dimensionless k (≥ 4).
    """
    if aspect_ratio <= 0:
        raise ValueError(f"aspect_ratio must be positive; got {aspect_ratio}")
    gamma = aspect_ratio
    # k(m) = (m/gamma + gamma/m)^2 is minimised near m = gamma; scan the integers
    # bracketing it (one below, one above) and take the least.
    lower = max(1, int(gamma))
    best = min((m / gamma + gamma / m) ** 2 for m in (lower, lower + 1))
    return best
