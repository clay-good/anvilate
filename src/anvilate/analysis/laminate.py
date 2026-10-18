"""T1 classical lamination theory: the ABD matrix, ply stresses, and first-ply failure.

A laminate is a stack of unidirectional plies, each stiff along its fibres and soft across
them, laid at different angles. Classical lamination theory (Kirchhoff plate kinematics,
each ply in plane stress) turns the stack into one relation between the running loads and
the mid-plane deformation::

    {N}   [A B] {ε⁰}
    {M} = [B D] {κ }

``A`` is the in-plane stiffness, ``D`` the bending stiffness, and ``B`` couples the two —
zero for a laminate symmetric about its mid-plane, and the reason an unsymmetric laminate
warps when it is only stretched. Inverting it gives the mid-plane strains and curvatures;
the strain at any depth is ε⁰ + z·κ, and each ply's stiffness turns that into its stress.

Conventions, stated because each is a place two textbooks differ:

- Plies are listed **from the bottom surface (z = −h/2) upward**, and z is positive
  upward, as in the Astronautic Structures Manual (NASA TM X-73305 §F1). NASA RP-1351
  lists from the top down, so its [0/+45]T is [+45, 0] here.
- Shear strain is the engineering strain γ = 2ε₁₂, and Q₆₆ = G₁₂.
- An angle is positive counter-clockwise from the laminate x axis to the fibre, which is
  the convention under which Q̄₁₆ is positive for a +45° ply.
- The minor Poisson ratio is the reciprocal one, ν₂₁ = ν₁₂·E₂/E₁. RP-1351's examples
  round it to 0.02 where the reciprocal is 0.0195, which moves Q₁₁ by 0.015%.

First-ply failure is reported by three criteria, each as a **strength ratio** R: the
factor on the applied running loads at which the ply reaches the criterion (R < 1 means it
already has). Maximum stress and maximum strain compare each component with its own
allowable; Tsai-Wu (Tsai & Wu, 1971) is the interactive quadratic, with the normalised
interaction coefficient F₁₂* = −0.5 by default (Tsai & Hahn), stated on every result.
Strengths are the caller's: a lamina with no strengths gives stresses and no failure
verdict, and every verdict carries the basis its strengths were declared on.

Out of scope here: hygrothermal (residual) strains, interlaminar stresses at free edges,
and progressive failure after the first ply.

Sources: NASA RP-1351, Nettles, *Basic Mechanics of Laminated Composite Plates* (1994)
for the stiffness relations and the worked examples the tests reproduce; NASA TM X-73305
§F1; Daniel & Ishai, *Engineering Mechanics of Composite Materials*, for the failure
criteria.
"""

from __future__ import annotations

from collections.abc import Sequence
from math import cos, inf, isfinite, radians, sin, sqrt

from pydantic import BaseModel, ConfigDict, model_validator

from .._models import RevalidatedModel, each_one
from ..refusal import RefusalError, Remedy
from ..units import Quantity, require_finite

__all__ = [
    "Lamina",
    "Ply",
    "LaminateStiffness",
    "PlyResult",
    "LaminateResponse",
    "PlyFailure",
    "FirstPlyFailure",
    "reduced_stiffness",
    "transformed_reduced_stiffness",
    "laminate_stiffness",
    "laminate_response",
    "first_ply_failure",
]

_LAMINA_SOURCE = "the lamina record: the ply manufacturer's qualified properties"
_LAYUP_SOURCE = "the laminate stacking sequence from the layup specification"
_LOAD_SOURCE = "the running loads per unit width from the load case"

#: Tsai & Hahn's normalised interaction coefficient, F₁₂ = F₁₂*·√(F₁₁·F₂₂).
_DEFAULT_TSAI_WU_INTERACTION = -0.5

Matrix = tuple[tuple[float, float, float], tuple[float, float, float], tuple[float, float, float]]


class _LaminateInputError(RefusalError, ValueError):
    """A laminate input that cannot be used without correction."""


def _refusal(message: str, *, subject: str, source: str) -> _LaminateInputError:
    return _LaminateInputError(
        message, remedies=(Remedy(action="replace", subject=subject, source=source),)
    )


def _magnitude(value: Quantity, unit: str, name: str, *, source: str) -> float:
    if not isinstance(value, Quantity):
        raise _refusal(f"{name} must be a quantity in {unit} or alike; got {value!r}",
                       subject=name, source=source)  # fmt: skip
    try:
        magnitude = value.to(unit).magnitude
    except Exception as error:  # a wrong dimension, named as the field
        raise _refusal(f"{name} is {value}, which is not convertible to {unit}",
                       subject=name, source=source) from error  # fmt: skip
    return require_finite(magnitude, name=name)


class Lamina(RevalidatedModel):
    """One unidirectional ply material, as NASA RP-1351 §2 describes a lamina.

    Its four elastic constants, thickness and strengths.

    Strengths are optional and come together: a lamina carries all five (Xt, Xc, Yt, Yc,
    S, each as a positive magnitude) with the ``strength_basis`` they were declared on, or
    none, in which case stresses are computed and failure is not evaluated.
    """

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    longitudinal_modulus: Quantity
    transverse_modulus: Quantity
    shear_modulus: Quantity
    major_poisson_ratio: float
    thickness: Quantity
    longitudinal_tensile_strength: Quantity | None = None
    longitudinal_compressive_strength: Quantity | None = None
    transverse_tensile_strength: Quantity | None = None
    transverse_compressive_strength: Quantity | None = None
    shear_strength: Quantity | None = None
    strength_basis: str | None = None

    @model_validator(mode="after")
    def _a_lamina(self) -> Lamina:
        for name in ("longitudinal_modulus", "transverse_modulus", "shear_modulus"):
            if _magnitude(getattr(self, name), "Pa", name, source=_LAMINA_SOURCE) <= 0:
                raise _refusal(f"{name} must be positive", subject=name, source=_LAMINA_SOURCE)
        if _magnitude(self.thickness, "m", "thickness", source=_LAMINA_SOURCE) <= 0:
            raise _refusal("thickness must be positive", subject="thickness",
                           source=_LAMINA_SOURCE)  # fmt: skip
        nu12 = self.major_poisson_ratio
        e1, e2 = self.e1, self.e2
        # Positive-definite compliance needs ν₁₂² < E₁/E₂ (Jones §2.4); outside it the
        # "material" returns energy when loaded.
        if not (isfinite(nu12) and nu12**2 < e1 / e2):
            raise _refusal(
                f"major_poisson_ratio {nu12} with E1/E2 = {e1 / e2:.4g} is not a material: "
                "a lamina's compliance is positive definite only for ν₁₂² < E₁/E₂",
                subject="major_poisson_ratio",
                source=_LAMINA_SOURCE,
            )
        strengths = self._strengths_or_none()
        if strengths is None and self.strength_basis is not None:
            raise _refusal("strength_basis is stated with no strengths to qualify",
                           subject="strength_basis", source=_LAMINA_SOURCE)  # fmt: skip
        return self

    def _strengths_or_none(self) -> tuple[float, float, float, float, float] | None:
        names = (
            "longitudinal_tensile_strength",
            "longitudinal_compressive_strength",
            "transverse_tensile_strength",
            "transverse_compressive_strength",
            "shear_strength",
        )
        given = [getattr(self, name) for name in names]
        if all(value is None for value in given):
            return None
        missing = [name for name, value in zip(names, given, strict=True) if value is None]
        if missing:
            raise _refusal(
                f"the lamina states some strengths and not {missing}; first-ply failure needs "
                "all five, and a criterion run on four would read the fifth as infinite",
                subject=missing[0],
                source=_LAMINA_SOURCE,
            )
        if not (self.strength_basis or "").strip():
            raise _refusal(
                "the lamina states strengths with no strength_basis; every failure verdict "
                "names the basis (A, B, mean, or a test report) its strengths were read on",
                subject="strength_basis",
                source=_LAMINA_SOURCE,
            )
        values = []
        for name, value in zip(names, given, strict=True):
            magnitude = _magnitude(value, "Pa", name, source=_LAMINA_SOURCE)
            if magnitude <= 0:
                raise _refusal(f"{name} is a positive magnitude, compressive ones included",
                               subject=name, source=_LAMINA_SOURCE)  # fmt: skip
            values.append(magnitude)
        return (values[0], values[1], values[2], values[3], values[4])

    @property
    def e1(self) -> float:
        return float(self.longitudinal_modulus.to("Pa").magnitude)

    @property
    def e2(self) -> float:
        return float(self.transverse_modulus.to("Pa").magnitude)

    @property
    def g12(self) -> float:
        return float(self.shear_modulus.to("Pa").magnitude)

    @property
    def t(self) -> float:
        return float(self.thickness.to("m").magnitude)


class Ply(RevalidatedModel):
    """A lamina laid at ``angle`` degrees, counter-clockwise from the laminate x axis.

    The angle convention under which Q̄₁₆ is positive at +45°, as in NASA RP-1351 eq. 22.
    """

    model_config = ConfigDict(frozen=True)

    lamina: Lamina
    angle: float

    @model_validator(mode="after")
    def _an_angle(self) -> Ply:
        if not (isfinite(self.angle) and -360 <= self.angle <= 360):
            raise _refusal(f"angle {self.angle} is not a ply angle in degrees",
                           subject="angle", source=_LAYUP_SOURCE)  # fmt: skip
        return self


def _q(lamina: Lamina) -> Matrix:
    e1, e2, g12, nu12 = lamina.e1, lamina.e2, lamina.g12, lamina.major_poisson_ratio
    nu21 = nu12 * e2 / e1
    d = 1.0 - nu12 * nu21
    return (
        (e1 / d, nu12 * e2 / d, 0.0),
        (nu12 * e2 / d, e2 / d, 0.0),
        (0.0, 0.0, g12),
    )


def _qbar(lamina: Lamina, angle: float) -> Matrix:
    (q11, q12, _), (_, q22, _), (_, _, q66) = _q(lamina)
    c, s = cos(radians(angle)), sin(radians(angle))
    c2, s2 = c * c, s * s
    b11 = q11 * c2 * c2 + 2 * (q12 + 2 * q66) * s2 * c2 + q22 * s2 * s2
    b12 = (q11 + q22 - 4 * q66) * s2 * c2 + q12 * (s2 * s2 + c2 * c2)
    b22 = q11 * s2 * s2 + 2 * (q12 + 2 * q66) * s2 * c2 + q22 * c2 * c2
    b16 = (q11 - q12 - 2 * q66) * s * c2 * c + (q12 - q22 + 2 * q66) * s2 * s * c
    b26 = (q11 - q12 - 2 * q66) * s2 * s * c + (q12 - q22 + 2 * q66) * s * c2 * c
    b66 = (q11 + q22 - 2 * q12 - 2 * q66) * s2 * c2 + q66 * (s2 * s2 + c2 * c2)
    return ((b11, b12, b16), (b12, b22, b26), (b16, b26, b66))


def _as_pa(matrix: Matrix) -> tuple[tuple[Quantity, ...], ...]:
    return tuple(tuple(Quantity(magnitude=v, unit="Pa") for v in row) for row in matrix)


def reduced_stiffness(lamina: Lamina) -> tuple[tuple[Quantity, ...], ...]:
    """The lamina's plane-stress reduced stiffness [Q] in its own axes (NASA RP-1351 eq. 14).

    Q₁₁ = E₁/(1 − ν₁₂ν₂₁), Q₁₂ = ν₁₂E₂/(1 − ν₁₂ν₂₁), Q₂₂ = E₂/(1 − ν₁₂ν₂₁), Q₆₆ = G₁₂,
    with the reciprocal ν₂₁ = ν₁₂E₂/E₁. Returned as a 3 × 3 matrix in Pa.
    """
    return _as_pa(_q(_lamina(lamina)))


def transformed_reduced_stiffness(lamina: Lamina, angle: float) -> tuple[tuple[Quantity, ...], ...]:
    """The ply's stiffness [Q̄] in laminate axes at ``angle`` degrees (NASA RP-1351 eq. 22).

    The fourth-power rotation of [Q]; Q̄₁₆ and Q̄₂₆ are the shear-extension couplings an
    off-axis ply carries and a 0° or 90° ply does not. Returned as a 3 × 3 matrix in Pa.
    """
    ply = Ply(lamina=_lamina(lamina), angle=angle)
    return _as_pa(_qbar(ply.lamina, ply.angle))


def _lamina(value: object) -> Lamina:
    if not isinstance(value, Lamina):
        raise _refusal(f"lamina must be a Lamina; got {type(value).__name__}",
                       subject="lamina", source=_LAMINA_SOURCE)  # fmt: skip
    return value


def _plies(plies: Sequence[Ply]) -> tuple[Ply, ...]:
    stack = each_one(plies, Ply, named="plies")
    if not stack:
        raise _refusal("a laminate has at least one ply", subject="plies", source=_LAYUP_SOURCE)
    return stack


def _bounds(stack: tuple[Ply, ...]) -> list[tuple[float, float]]:
    h = sum(p.lamina.t for p in stack)
    z, out = -h / 2, []
    for ply in stack:
        out.append((z, z + ply.lamina.t))
        z += ply.lamina.t
    return out


def _abd(stack: tuple[Ply, ...]) -> tuple[Matrix, Matrix, Matrix]:
    a = [[0.0] * 3 for _ in range(3)]
    b = [[0.0] * 3 for _ in range(3)]
    d = [[0.0] * 3 for _ in range(3)]
    for ply, (z0, z1) in zip(stack, _bounds(stack), strict=True):
        q = _qbar(ply.lamina, ply.angle)
        for i in range(3):
            for j in range(3):
                a[i][j] += q[i][j] * (z1 - z0)
                b[i][j] += q[i][j] * (z1**2 - z0**2) / 2
                d[i][j] += q[i][j] * (z1**3 - z0**3) / 3
    return _matrix(a), _matrix(b), _matrix(d)


def _matrix(rows: list[list[float]]) -> Matrix:
    return (
        (rows[0][0], rows[0][1], rows[0][2]),
        (rows[1][0], rows[1][1], rows[1][2]),
        (rows[2][0], rows[2][1], rows[2][2]),
    )


class LaminateStiffness(BaseModel):
    """A laminate's [A], [B] and [D] matrices (NASA RP-1351 §4), thickness, effective moduli.

    ``a`` is in N/m, ``b`` in N, ``d`` in N·m, each a 3 × 3 matrix over (x, y, xy). The
    effective in-plane moduli are those of the laminate stretched with no moment — for an
    unsymmetric laminate that is the honest one, with the bending coupling included.
    """

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    a: tuple[tuple[Quantity, ...], ...]
    b: tuple[tuple[Quantity, ...], ...]
    d: tuple[tuple[Quantity, ...], ...]
    thickness: Quantity
    effective_longitudinal_modulus: Quantity
    effective_transverse_modulus: Quantity
    effective_shear_modulus: Quantity

    @property
    def is_symmetric(self) -> bool:
        """Whether [B] vanishes, to 1e-9 of the largest [A] term times the thickness."""
        scale = max(abs(q.magnitude) for row in self.a for q in row) * self.thickness.magnitude
        return all(abs(q.magnitude) <= 1e-9 * scale for row in self.b for q in row)


def _solve(matrix: list[list[float]], rhs: list[float]) -> list[float]:
    """Gaussian elimination with partial pivoting; refuses a singular system."""
    n = len(rhs)
    m = [list(row) + [value] for row, value in zip(matrix, rhs, strict=True)]
    scale = max(abs(v) for row in matrix for v in row) or 1.0
    for col in range(n):
        pivot = max(range(col, n), key=lambda r: abs(m[r][col]))
        if abs(m[pivot][col]) <= 1e-14 * scale:
            raise _refusal("the laminate's ABD matrix is singular; it has no stiffness in some "
                           "direction", subject="plies", source=_LAYUP_SOURCE)  # fmt: skip
        m[col], m[pivot] = m[pivot], m[col]
        for r in range(n):
            if r != col:
                f = m[r][col] / m[col][col]
                for k in range(col, n + 1):
                    m[r][k] -= f * m[col][k]
    return [m[i][n] / m[i][i] for i in range(n)]


def _full(a: Matrix, b: Matrix, d: Matrix) -> list[list[float]]:
    return [list(a[i]) + list(b[i]) for i in range(3)] + [list(b[i]) + list(d[i]) for i in range(3)]


def laminate_stiffness(plies: Sequence[Ply]) -> LaminateStiffness:
    """The [A], [B], [D] matrices of a stack of plies, bottom first (NASA RP-1351 eq. 35-37).

    A = Σ Q̄ (z_k − z_{k−1}), B = ½ Σ Q̄ (z_k² − z_{k−1}²), D = ⅓ Σ Q̄ (z_k³ − z_{k−1}³), with
    z measured from the mid-plane, positive upward. The effective moduli are 1/(h·a*ᵢᵢ)
    from the inverse of the full 6 × 6 matrix, so bending coupling is included.
    """
    stack = _plies(plies)
    a, b, d = _abd(stack)
    h = sum(p.lamina.t for p in stack)
    full = _full(a, b, d)
    compliance = [_solve(full, [1.0 if k == i else 0.0 for k in range(6)]) for i in range(3)]
    ex, ey, gxy = (1.0 / (h * compliance[i][i]) for i in range(3))

    def q(matrix: Matrix, unit: str) -> tuple[tuple[Quantity, ...], ...]:
        return tuple(tuple(Quantity(magnitude=v, unit=unit) for v in row) for row in matrix)

    return LaminateStiffness(
        a=q(a, "N/m"),
        b=q(b, "N"),
        d=q(d, "N*m"),
        thickness=Quantity(magnitude=h, unit="m"),
        effective_longitudinal_modulus=Quantity(magnitude=ex, unit="Pa"),
        effective_transverse_modulus=Quantity(magnitude=ey, unit="Pa"),
        effective_shear_modulus=Quantity(magnitude=gxy, unit="Pa"),
    )


class PlyResult(BaseModel):
    """One ply at one surface: its depth, strains and stresses in both axis systems.

    Strain at depth z is ε⁰ + z·κ (Kirchhoff kinematics, NASA RP-1351 eq. 29).

    Strains are dimensionless (γ engineering); stresses in Pa. ``surface`` is "bottom" or
    "top" of the ply; ``index`` counts from the bottom ply, starting at 1.
    """

    model_config = ConfigDict(frozen=True)

    index: int
    angle: float
    surface: str
    z: float
    strain_xy: tuple[float, float, float]
    strain_12: tuple[float, float, float]
    stress_xy: tuple[float, float, float]
    stress_12: tuple[float, float, float]


class LaminateResponse(BaseModel):
    """The laminate's mid-plane strains (ε⁰) and curvatures (κ, 1/m), NASA RP-1351 §5.

    Each ply's results at both surfaces follow from them by Kirchhoff kinematics.
    """

    model_config = ConfigDict(frozen=True)

    midplane_strain: tuple[float, float, float]
    curvature: tuple[float, float, float]
    plies: tuple[PlyResult, ...]
    stack: tuple[Ply, ...]


def _three(values: Sequence[Quantity] | None, unit: str, name: str) -> list[float]:
    if values is None:
        return [0.0, 0.0, 0.0]
    items = list(values)
    if len(items) != 3:
        raise _refusal(f"{name} has {len(items)} components; it is (x, y, xy)",
                       subject=name, source=_LOAD_SOURCE)  # fmt: skip
    return [_magnitude(v, unit, f"{name}[{i}]", source=_LOAD_SOURCE) for i, v in enumerate(items)]


def laminate_response(
    plies: Sequence[Ply],
    *,
    running_load: Sequence[Quantity] | None = None,
    running_moment: Sequence[Quantity] | None = None,
) -> LaminateResponse:
    """Mid-plane strains, curvatures, and each ply's strains and stresses (Kirchhoff).

    ``running_load`` is (Nx, Ny, Nxy) as force per unit width and ``running_moment`` is
    (Mx, My, Mxy) as moment per unit width (force); either may be omitted as zero. The
    strain at depth z is ε⁰ + z·κ (NASA RP-1351 eq. 29); a ply's stress is Q̄ times that
    strain, rotated into fibre axes. Both surfaces of every ply are reported, because the
    largest stress in a bent ply is at one of them.
    """
    stack = _plies(plies)
    n = _three(running_load, "N/m", "running_load")
    m = _three(running_moment, "N", "running_moment")
    a, b, d = _abd(stack)
    solution = _solve(_full(a, b, d), n + m)
    e0, k = solution[:3], solution[3:]
    results = []
    for index, (ply, (z0, z1)) in enumerate(zip(stack, _bounds(stack), strict=True), start=1):
        q = _qbar(ply.lamina, ply.angle)
        c, s = cos(radians(ply.angle)), sin(radians(ply.angle))
        for surface, z in (("bottom", z0), ("top", z1)):
            ex, ey, gxy = (e0[i] + z * k[i] for i in range(3))
            sx, sy, txy = (q[i][0] * ex + q[i][1] * ey + q[i][2] * gxy for i in range(3))
            e1 = c * c * ex + s * s * ey + s * c * gxy
            e2 = s * s * ex + c * c * ey - s * c * gxy
            g12 = 2 * s * c * (ey - ex) + (c * c - s * s) * gxy
            s1 = c * c * sx + s * s * sy + 2 * s * c * txy
            s2 = s * s * sx + c * c * sy - 2 * s * c * txy
            t12 = s * c * (sy - sx) + (c * c - s * s) * txy
            results.append(
                PlyResult(index=index, angle=ply.angle, surface=surface, z=z,
                          strain_xy=(ex, ey, gxy), strain_12=(e1, e2, g12),
                          stress_xy=(sx, sy, txy), stress_12=(s1, s2, t12))
            )  # fmt: skip
    return LaminateResponse(
        midplane_strain=(e0[0], e0[1], e0[2]),
        curvature=(k[0], k[1], k[2]),
        plies=tuple(results),
        stack=stack,
    )


class PlyFailure(BaseModel):
    """One ply surface's strength ratio by maximum stress, maximum strain and Tsai-Wu.

    A ratio is infinite where the surface is unloaded (Daniel & Ishai §6).
    """

    model_config = ConfigDict(frozen=True)

    index: int
    angle: float
    surface: str
    max_stress: float
    max_strain: float
    tsai_wu: float
    max_stress_mode: str
    max_strain_mode: str


class FirstPlyFailure(BaseModel):
    """The first ply to fail, by which criterion (maximum stress, maximum strain, Tsai-Wu).

    And at what factor on the applied loads.

    ``strength_ratio`` is the lowest ratio over every ply surface and criterion; below 1 the
    laminate has already failed its first ply. ``evaluated`` is False with ``reason`` when
    any ply's lamina states no strengths — no criterion is run on part of a stack.
    """

    model_config = ConfigDict(frozen=True)

    evaluated: bool
    reason: str | None = None
    strength_ratio: float | None = None
    governing_ply: int | None = None
    governing_surface: str | None = None
    governing_criterion: str | None = None
    governing_mode: str | None = None
    strength_basis: tuple[str, ...] = ()
    tsai_wu_interaction: float = _DEFAULT_TSAI_WU_INTERACTION
    plies: tuple[PlyFailure, ...] = ()

    def __str__(self) -> str:
        if not self.evaluated:
            return f"first-ply failure not evaluated — {self.reason}"
        return (
            f"first-ply failure at {self.strength_ratio:.3g} x the applied loads: ply "
            f"{self.governing_ply} ({self.governing_surface}) by {self.governing_criterion} "
            f"({self.governing_mode}); strengths on {', '.join(self.strength_basis)} basis, "
            f"Tsai-Wu F12* = {self.tsai_wu_interaction:g}"
        )


def _component_ratio(value: float, tension: float, compression: float) -> float:
    if value > 0:
        return tension / value
    if value < 0:
        return compression / -value
    return inf


def first_ply_failure(
    response: LaminateResponse,
    *,
    tsai_wu_interaction: float = _DEFAULT_TSAI_WU_INTERACTION,
) -> FirstPlyFailure:
    """First-ply failure by maximum stress, maximum strain and Tsai-Wu (Daniel & Ishai §6).

    Each criterion gives a strength ratio R, the factor on the applied running loads at
    which a ply surface reaches it. Maximum stress: R = min over σ₁, σ₂, τ₁₂ of strength /
    |stress|, taking Xt or Xc, Yt or Yc by sign. Maximum strain: the same against strain
    allowables strength/modulus (ε₁ᵗ = Xt/E₁, …, γ₁₂ = S/G₁₂). Tsai-Wu: the positive root
    of a·R² + b·R − 1 = 0, with a = F₁₁σ₁² + F₂₂σ₂² + F₆₆τ² + 2F₁₂σ₁σ₂ and b = F₁σ₁ + F₂σ₂,
    F₁ = 1/Xt − 1/Xc, F₁₁ = 1/(Xt·Xc), F₆₆ = 1/S², F₁₂ = F₁₂*·√(F₁₁F₂₂). Under pure σ₁ it
    fails at exactly Xt or −Xc, which is the check the tests make.
    """
    if not isinstance(response, LaminateResponse):
        raise _refusal("response must be a LaminateResponse from laminate_response",
                       subject="response", source=_LAYUP_SOURCE)  # fmt: skip
    if not (isfinite(tsai_wu_interaction) and -1.0 <= tsai_wu_interaction <= 1.0):
        raise _refusal(
            f"tsai_wu_interaction is {tsai_wu_interaction}; F12* is bounded by ±1 for the "
            "quadratic to be a closed failure surface",
            subject="tsai_wu_interaction",
            source="the material's biaxial test data, or Tsai & Hahn's -0.5",
        )
    for index, ply in enumerate(response.stack, start=1):
        if ply.lamina._strengths_or_none() is None:
            return FirstPlyFailure(
                evaluated=False,
                tsai_wu_interaction=tsai_wu_interaction,
                reason=f"ply {index}'s lamina states no strengths; declare Xt, Xc, Yt, Yc "
                "and S with their basis",
            )
    failures = []
    for result in response.plies:
        lamina = response.stack[result.index - 1].lamina
        xt, xc, yt, yc, s = lamina._strengths_or_none()  # type: ignore[misc]
        s1, s2, t12 = result.stress_12
        e1, e2, g12 = result.strain_12
        stress = {
            "fibre": _component_ratio(s1, xt, xc),
            "transverse": _component_ratio(s2, yt, yc),
            "shear": _component_ratio(abs(t12), s, s),
        }
        strain = {
            "fibre": _component_ratio(e1, xt / lamina.e1, xc / lamina.e1),
            "transverse": _component_ratio(e2, yt / lamina.e2, yc / lamina.e2),
            "shear": _component_ratio(abs(g12), s / lamina.g12, s / lamina.g12),
        }
        f1, f2 = 1 / xt - 1 / xc, 1 / yt - 1 / yc
        f11, f22, f66 = 1 / (xt * xc), 1 / (yt * yc), 1 / s**2
        f12 = tsai_wu_interaction * sqrt(f11 * f22)
        qa = f11 * s1 * s1 + f22 * s2 * s2 + f66 * t12 * t12 + 2 * f12 * s1 * s2
        qb = f1 * s1 + f2 * s2
        if qa > 0:
            tsai = (-qb + sqrt(qb * qb + 4 * qa)) / (2 * qa)
        else:
            tsai = 1 / qb if qb > 0 else inf
        stress_mode = min(stress, key=stress.__getitem__)
        strain_mode = min(strain, key=strain.__getitem__)
        failures.append(
            PlyFailure(index=result.index, angle=result.angle, surface=result.surface,
                       max_stress=stress[stress_mode], max_strain=strain[strain_mode],
                       tsai_wu=tsai, max_stress_mode=stress_mode,
                       max_strain_mode=strain_mode)
        )  # fmt: skip
    candidates = []
    for f in failures:
        candidates += [
            (f.max_stress, f, "maximum stress", f.max_stress_mode),
            (f.max_strain, f, "maximum strain", f.max_strain_mode),
            (f.tsai_wu, f, "Tsai-Wu", "interactive"),
        ]
    ratio, worst, criterion, mode = min(candidates, key=lambda c: c[0])
    bases = tuple(dict.fromkeys(p.lamina.strength_basis or "" for p in response.stack))
    return FirstPlyFailure(
        evaluated=True,
        strength_ratio=ratio,
        governing_ply=worst.index,
        governing_surface=worst.surface,
        governing_criterion=criterion,
        governing_mode=mode,
        strength_basis=bases,
        tsai_wu_interaction=tsai_wu_interaction,
        plies=tuple(failures),
    )
