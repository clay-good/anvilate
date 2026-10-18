"""T1 preloaded bolted joints to NASA-STD-5020B: preload bounds, separation, strength, slip.

A preloaded joint's margins rest on a preload nobody measures in service. NASA-STD-5020B
(*Requirements for Threaded Fastening Systems in Spaceflight Hardware*, revision B,
approved 2021-08-06, revalidated without change 2026-01-05) bounds it:

    Pp-max = c_max(1 + Γ)·Ppi-nom + PΔt-max                       (Eqs. 1, 3)
    Pp-min = c_min(1 − Γ)·Ppi-nom − Ppr − Ppc − PΔt-min           (Eqs. 2, 4)

with Γ the preload uncertainty of the tightening method, c the torque tolerance, Ppr the
short-term relaxation (5% of the minimum initial preload for an all-metallic clamp,
Table 1), Ppc creep and PΔt the thermal change. For slip, and for the separation of a
joint that is not separation-critical, Γ is divided by √n_f (Eq. 5): what matters is
the scatter of the joint's total preload, not one bolt's.

Γ comes from the tightening method. Table 3 gives defaults for a joint that is not
separation-critical — 25% torque-controlled lubricated, 35% torque-controlled dry or
as-received, 25% turn-of-nut, 10% bolt stretch — as the greater of the default and the
measured variation. A separation-critical joint has no default: it needs torque-tension
test data (Table 2) and the envelope of its 90/95 statistical variation and its measured
variation. :func:`preload_uncertainty_from_tests` reduces a test sample the way
Appendix A.2 does, with the two-sided 90/95 tolerance factors of Table 5.

The margins, with FF the fitting factor and the factors of safety the program's:

    separation   MS = Pp-min / (FF·FS_sep·P_tL) − 1                          (Eq. 19)
    ultimate     MS = Ptu-allow / (FF·FS_u·P_tL) − 1  separation first        (Eq. 6)
                 MS = P′tu / (FF·FS_u·P_tL) − 1        rupture first          (Eq. 7)
    yield        the same with Pty-allow and P′ty                         (Eqs. 15–17)
    slip         MS = μ·Pp-min / (FF·FS·(P_sL + μ·P_tL)) − 1, per fastener    (Eq. 86)

where P′tu = (Ptu-allow − Pp-max)/(nφ) is the applied load at which the bolt ruptures
before the joint opens and P′sep = Pp-max/(1 − nφ) the load at which it opens (Eqs. 10,
11): separation comes first when P′sep < P′tu. n is the load-introduction factor, which
the standard gives no default for, and φ = k_b/(k_b + k_c) the stiffness factor (Eq. 9);
both are the caller's. Friction is never credited at ultimate (TFSR 8b), and without test
data μ is at most 0.20 on cleaned, uncoated, unlubricated metal and 0.10 on anything else
(TFSR 13–14).

The standard itself carries three typographical slips, recorded so nobody "corrects" this
module toward them: Eq. 33 prints "= 1" where its worked example uses "− 1"; Figure 8
points to Eqs. 10 and 11 where §4.4.1 means Eqs. 6 and 7; and p. 62 states "Ec < Eb/3"
where Figure 8 and Appendix A.5 use "Ec > Eb/3".
"""

from __future__ import annotations

from collections.abc import Sequence
from enum import StrEnum
from math import isfinite, sqrt

from pydantic import BaseModel, ConfigDict

from .._models import each_one
from ..refusal import RefusalError, Remedy
from ..units import Quantity, require_finite

__all__ = [
    "TighteningMethod",
    "FayingSurface",
    "PreloadUncertainty",
    "PreloadBounds",
    "JointMargins",
    "preload_uncertainty_from_tests",
    "preload_bounds",
    "preloaded_joint_margins",
    "joint_slip_margin",
]

_TEST_SOURCE = "the torque-tension test record for this fastening system (NASA-STD-5020B Table 2)"
_JOINT_SOURCE = "the joint's design: preload, stiffness, load introduction and applied loads"
_PROGRAM_SOURCE = "the program's levied factors of safety and fitting factor"

# Table 5: two-sided 90/95 tolerance limit factors for a normal distribution (Odeh and Owen,
# 1980), as NASA-STD-5020B reprints them.
_TABLE_5 = {
    2: 31.092, 3: 8.306, 4: 5.368, 5: 4.291, 6: 3.733, 7: 3.390, 8: 3.156, 9: 2.986,
    10: 2.856, 11: 2.754, 12: 2.670, 13: 2.601, 14: 2.542, 15: 2.492, 16: 2.449, 17: 2.410,
    18: 2.376, 19: 2.346, 20: 2.319, 21: 2.294, 22: 2.272, 23: 2.251, 24: 2.232, 25: 2.215,
    26: 2.199, 27: 2.184, 28: 2.170, 29: 2.157, 30: 2.145, 35: 2.094, 40: 2.055, 45: 2.024,
    50: 1.999, 55: 1.978, 60: 1.960, 65: 1.944, 70: 1.931, 80: 1.908, 90: 1.890, 100: 1.875,
}  # fmt: skip


class _PreloadedJointInputError(RefusalError, ValueError):
    """A preloaded-joint input that cannot be used without correction."""


def _refusal(message: str, *, subject: str, source: str) -> _PreloadedJointInputError:
    return _PreloadedJointInputError(
        message, remedies=(Remedy(action="replace", subject=subject, source=source),)
    )


class TighteningMethod(StrEnum):
    """How the preload is applied; NASA-STD-5020B Table 3 gives each a default Γ."""

    TORQUE_LUBRICATED = "torque_lubricated"
    TORQUE_DRY = "torque_dry"
    TURN_OF_NUT = "turn_of_nut"
    BOLT_STRETCH = "bolt_stretch"


# Table 3, option b: the default preload uncertainty for a joint that is not
# separation-critical. "Lubricated" means lubricant on the threads and the turning bearing
# surface (p. 26); dry includes as-received.
_DEFAULT_GAMMA = {
    TighteningMethod.TORQUE_LUBRICATED: 0.25,
    TighteningMethod.TORQUE_DRY: 0.35,
    TighteningMethod.TURN_OF_NUT: 0.25,
    TighteningMethod.BOLT_STRETCH: 0.10,
}


class FayingSurface(StrEnum):
    """The clamped surfaces, which set the most friction NASA-STD-5020B lets be credited."""

    CLEANED_UNCOATED_METAL = "cleaned_uncoated_metal"
    OTHER = "other"


_MAX_FRICTION = {FayingSurface.CLEANED_UNCOATED_METAL: 0.20, FayingSurface.OTHER: 0.10}


class PreloadUncertainty(BaseModel):
    """A torque-tension test sample reduced as NASA-STD-5020B Appendix A.2 reduces it.

    ``nominal`` is the sample mean in N; ``gamma_above`` and ``gamma_below`` are the
    largest measured excursions above and below it as fractions (Γa-max, Γa-min);
    ``gamma_90_95`` is s·σ/mean with the Table 5 factor for ``sample_size`` (Eq. 36).
    """

    model_config = ConfigDict(frozen=True)

    sample_size: int
    nominal: float
    standard_deviation: float
    tolerance_factor: float
    gamma_above: float
    gamma_below: float
    gamma_90_95: float


def preload_uncertainty_from_tests(preloads: Sequence[Quantity]) -> PreloadUncertainty:
    """Γa-max, Γa-min and Γ90/95 of a torque-tension sample (NASA-STD-5020B Eqs. 31–36).

    ``preloads`` are the measured initial preloads at one effective torque, at least two.
    The standard deviation is the unbiased sample one (Eq. 35). Table 5 lists s for some
    sample sizes; between them the next smaller listed size is used, whose s is larger, and
    above 100 the s for 100 — both conservative, and neither a value the table does not
    state.
    """
    values = []
    for i, p in enumerate(each_one(preloads, Quantity, named="preloads")):
        magnitude = _force(p, f"preloads[{i}]", source=_TEST_SOURCE)
        if magnitude <= 0:
            raise _refusal(f"preloads[{i}] is {magnitude:g} N; a measured preload is positive",
                           subject=f"preloads[{i}]", source=_TEST_SOURCE)  # fmt: skip
        values.append(magnitude)
    m = len(values)
    if m < 2:
        raise _refusal(f"{m} preload measurement is no sample; Table 5 starts at two",
                       subject="preloads", source=_TEST_SOURCE)  # fmt: skip
    mean = sum(values) / m
    sigma = sqrt(sum((v - mean) ** 2 for v in values) / (m - 1))
    s = _TABLE_5[max(k for k in _TABLE_5 if k <= min(m, 100))]
    return PreloadUncertainty(
        sample_size=m,
        nominal=mean,
        standard_deviation=sigma,
        tolerance_factor=s,
        gamma_above=max(values) / mean - 1,
        gamma_below=1 - min(values) / mean,
        gamma_90_95=s * sigma / mean,
    )


def _force(value: Quantity, name: str, *, source: str) -> float:
    if not isinstance(value, Quantity):
        raise _refusal(f"{name} must be a force quantity; got {value!r}", subject=name,
                       source=source)  # fmt: skip
    try:
        magnitude = value.to("N").magnitude
    except Exception as error:
        raise _refusal(f"{name} is {value}, which is not a force", subject=name,
                       source=source) from error  # fmt: skip
    return require_finite(magnitude, name=name)


def _fraction(value: float, name: str, *, upper: float, source: str) -> float:
    v = require_finite(value, name=name)
    if not 0 <= v < upper:
        raise _refusal(f"{name} is {v}; it is a fraction in [0, {upper:g})", subject=name,
                       source=source)  # fmt: skip
    return v


class PreloadBounds(BaseModel):
    """The maximum and minimum preloads of NASA-STD-5020B §4.3.1, in N, and their basis.

    ``minimum`` is for the separation of a separation-critical joint (Eq. 4) and
    ``minimum_for_slip`` for slip and the separation of any other joint (Eq. 5);
    ``gamma_basis`` says whether Γ is the Table 3 default, a measured value, or the
    envelope Table 3 requires of a separation-critical joint.
    """

    model_config = ConfigDict(frozen=True)

    nominal: float
    maximum: float
    minimum: float
    minimum_for_slip: float
    gamma_for_maximum: float
    gamma_for_minimum: float
    gamma_basis: str
    relaxation: float
    separation_critical: bool
    fastener_count: int

    def __str__(self) -> str:
        return (
            f"preload {self.minimum:.4g} to {self.maximum:.4g} N about {self.nominal:.4g} N "
            f"(Γ {self.gamma_for_minimum:.3g} below, {self.gamma_for_maximum:.3g} above: "
            f"{self.gamma_basis}; NASA-STD-5020B Eqs. 1–5)"
        )


def preload_bounds(
    *,
    nominal_preload: Quantity,
    method: TighteningMethod,
    torque_tolerance: float,
    separation_critical: bool,
    fastener_count: int,
    all_metallic_clamp: bool,
    tests: PreloadUncertainty | None = None,
    relaxation: Quantity | None = None,
    creep_loss: Quantity | None = None,
    thermal_increase: Quantity | None = None,
    thermal_decrease: Quantity | None = None,
) -> PreloadBounds:
    """Maximum and minimum preload by NASA-STD-5020B Eqs. 1–5 and Tables 1 and 3.

    ``torque_tolerance`` is the specified torque's tolerance as a fraction (40 ± 2 N·m is
    0.05, so c_max = 1.05 and c_min = 0.95); use 0 for a method with no torque. Γ is, for
    a joint that is not separation-critical, the greater of the Table 3 default and the
    measured variation — with the 90/95 value accepted in place of a larger measured
    excursion, as Appendix A.2's example does. A separation-critical joint needs ``tests``
    and takes the envelope of Γ90/95 and the measured excursion below the mean.
    ``relaxation`` defaults to 5% of the minimum initial preload for an all-metallic clamp
    (Table 1) and must be declared otherwise. The losses and the thermal changes are
    positive forces, zero when absent.
    """
    if not isinstance(method, TighteningMethod):
        raise _refusal(f"method must be a TighteningMethod; got {method!r}", subject="method",
                       source="the installation procedure's tightening method")  # fmt: skip
    nominal = _force(nominal_preload, "nominal_preload", source=_JOINT_SOURCE)
    if nominal <= 0:
        raise _refusal("nominal_preload must be positive", subject="nominal_preload",
                       source=_JOINT_SOURCE)  # fmt: skip
    tol = _fraction(torque_tolerance, "torque_tolerance", upper=1.0, source=_JOINT_SOURCE)
    if (
        isinstance(fastener_count, bool)
        or not isinstance(fastener_count, int)
        or fastener_count < 1
    ):
        raise _refusal(f"fastener_count is {fastener_count!r}; a joint has at least one",
                       subject="fastener_count", source=_JOINT_SOURCE)  # fmt: skip
    default = _DEFAULT_GAMMA[method]
    if separation_critical:
        if tests is None:
            raise _refusal(
                "a separation-critical joint has no default preload uncertainty: NASA-STD-5020B "
                "Table 3 requires the envelope of the 90/95 statistical variation and the "
                "measured variation from torque-tension tests (Table 2)",
                subject="tests",
                source=_TEST_SOURCE,
            )
        g_max = max(default, min(tests.gamma_above, tests.gamma_90_95))
        g_min = max(tests.gamma_90_95, tests.gamma_below)
        basis = f"envelope of Γ90/95 and measured variation, {tests.sample_size} tests (Table 3)"
    elif tests is None:
        g_max = g_min = default
        basis = f"Table 3 default for {method.value.replace('_', ' ')} (a default, not measured)"
    else:
        g_max = max(default, min(tests.gamma_above, tests.gamma_90_95))
        g_min = max(default, min(tests.gamma_below, tests.gamma_90_95))
        basis = f"greater of the Table 3 default and {tests.sample_size} tests"
    if g_min >= 1:
        raise _refusal(
            f"a preload uncertainty of {g_min:.3g} leaves no minimum preload; the test scatter "
            "is larger than the preload itself",
            subject="tests",
            source=_TEST_SOURCE,
        )
    losses = []
    for name, value in (("creep_loss", creep_loss), ("thermal_increase", thermal_increase),
                        ("thermal_decrease", thermal_decrease)):  # fmt: skip
        magnitude = 0.0 if value is None else _force(value, name, source=_JOINT_SOURCE)
        if magnitude < 0:
            raise _refusal(f"{name} is entered as a positive force", subject=name,
                           source=_JOINT_SOURCE)  # fmt: skip
        losses.append(magnitude)
    creep, rise, drop = losses
    initial_min = (1 - tol) * (1 - g_min) * nominal
    initial_min_slip = (1 - tol) * (1 - g_min / sqrt(fastener_count)) * nominal
    if relaxation is not None:
        ppr = _force(relaxation, "relaxation", source=_TEST_SOURCE)
        if ppr < 0:
            raise _refusal("relaxation is entered as a positive force", subject="relaxation",
                           source=_TEST_SOURCE)  # fmt: skip
        ppr_slip = ppr
    elif all_metallic_clamp:
        # 5% of the minimum initial preload (Table 1) — of each equation's own minimum.
        ppr = 0.05 * initial_min
        ppr_slip = 0.05 * initial_min_slip
    else:
        raise _refusal(
            "the clamp is not all-metallic, so NASA-STD-5020B Table 1 gives no default "
            "short-term relaxation; declare the tested loss as `relaxation`",
            subject="relaxation",
            source=_TEST_SOURCE,
        )
    return PreloadBounds(
        nominal=nominal,
        maximum=(1 + tol) * (1 + g_max) * nominal + rise,
        minimum=initial_min - ppr - creep - drop,
        minimum_for_slip=initial_min_slip - ppr_slip - creep - drop,
        gamma_for_maximum=g_max,
        gamma_for_minimum=g_min,
        gamma_basis=basis,
        relaxation=ppr,
        separation_critical=separation_critical,
        fastener_count=fastener_count,
    )


class JointMargins(BaseModel):
    """Separation, ultimate and yield margins of one bolt (NASA-STD-5020B §4.4).

    ``rupture_before_separation`` is True when the applied load that ruptures the bolt,
    ``rupture_load`` (P′tu), is below the one that opens the joint, ``separation_load``
    (P′sep): then preload stays in the bolt to failure and the ultimate margin uses Eq. 7.
    Loads are in N.
    """

    model_config = ConfigDict(frozen=True)

    separation_margin: float
    ultimate_margin: float
    yield_margin: float
    separation_load: float
    rupture_load: float
    rupture_before_separation: bool
    ultimate_equation: str

    def __str__(self) -> str:
        order = (
            f"the bolt ruptures at {self.rupture_load:.4g} N before the joint opens at "
            f"{self.separation_load:.4g} N"
            if self.rupture_before_separation
            else f"the joint opens at {self.separation_load:.4g} N before the bolt ruptures "
            f"at {self.rupture_load:.4g} N"
        )
        return (
            f"MS separation {self.separation_margin:+.2f}, ultimate {self.ultimate_margin:+.2f} "
            f"({self.ultimate_equation}), yield {self.yield_margin:+.2f}; {order} "
            "(NASA-STD-5020B)"
        )


def _factor(value: float, name: str) -> float:
    v = require_finite(value, name=name)
    if v < 1.0:
        raise _refusal(f"{name} is {v}; a factor of safety or fitting factor is at least 1",
                       subject=name, source=_PROGRAM_SOURCE)  # fmt: skip
    return v


def preloaded_joint_margins(
    *,
    bounds: PreloadBounds,
    limit_tension: Quantity,
    ultimate_allowable: Quantity,
    yield_allowable: Quantity,
    load_introduction_factor: float,
    stiffness_factor: float,
    fitting_factor: float,
    ultimate_factor: float,
    yield_factor: float,
    separation_factor: float,
) -> JointMargins:
    """One bolt's separation, ultimate and yield margins (NASA-STD-5020B Eqs. 6–19).

    ``limit_tension`` P_tL is the bolt's share of the applied tensile limit load;
    ``ultimate_allowable`` and ``yield_allowable`` are the bolt's tensile allowables
    (Pty-allow may be taken as (Fty/Ftu)·Ptu-allow, Eq. 18, by the caller).
    ``load_introduction_factor`` n and ``stiffness_factor`` φ are in (0, 1]; the factors
    of safety are the program's, ``separation_factor`` chosen by the Figure 1 hazard tree,
    and ``fitting_factor`` at least 1.15 where a fitting factor applies (p. 19). The
    separation margin uses ``bounds.minimum`` for a separation-critical joint and
    ``bounds.minimum_for_slip`` otherwise, as Eqs. 4 and 5 assign them.
    """
    if not isinstance(bounds, PreloadBounds):
        raise _refusal("bounds must come from preload_bounds", subject="bounds",
                       source=_JOINT_SOURCE)  # fmt: skip
    p_tl = _force(limit_tension, "limit_tension", source=_JOINT_SOURCE)
    ptu = _force(ultimate_allowable, "ultimate_allowable", source=_JOINT_SOURCE)
    pty = _force(yield_allowable, "yield_allowable", source=_JOINT_SOURCE)
    if p_tl <= 0 or ptu <= 0 or pty <= 0:
        raise _refusal(
            "limit_tension and both allowables must be positive; a joint with no tensile "
            "load has no separation or tensile margin to report",
            subject="limit_tension" if p_tl <= 0 else "ultimate_allowable",
            source=_JOINT_SOURCE,
        )
    if pty > ptu:
        raise _refusal("yield_allowable exceeds ultimate_allowable", subject="yield_allowable",
                       source=_JOINT_SOURCE)  # fmt: skip
    n = require_finite(load_introduction_factor, name="load_introduction_factor")
    phi = require_finite(stiffness_factor, name="stiffness_factor")
    for name, value in (("load_introduction_factor", n), ("stiffness_factor", phi)):
        if not 0 < value <= 1:
            raise _refusal(f"{name} is {value}; it lies in (0, 1] (NASA-STD-5020B A.4)",
                           subject=name, source=_JOINT_SOURCE)  # fmt: skip
    ff = _factor(fitting_factor, "fitting_factor")
    fs_u = _factor(ultimate_factor, "ultimate_factor")
    fs_y = _factor(yield_factor, "yield_factor")
    fs_sep = _factor(separation_factor, "separation_factor")
    n_phi = n * phi
    p_max = bounds.maximum
    p_min = bounds.minimum if bounds.separation_critical else bounds.minimum_for_slip
    rupture = (ptu - p_max) / n_phi
    separation = p_max / (1 - n_phi) if n_phi < 1 else float("inf")
    rupture_first = not separation < rupture
    if rupture_first:
        ultimate = rupture / (ff * fs_u * p_tl) - 1
        equation = "Eq. 7, rupture before separation"
    else:
        ultimate = ptu / (ff * fs_u * p_tl) - 1
        equation = "Eq. 6, separation before rupture"
    # Yield is decided the same way, against P′ty (Eqs. 15–17).
    yield_load = (pty - p_max) / n_phi
    yielding = (yield_load if not separation < yield_load else pty) / (ff * fs_y * p_tl) - 1
    return JointMargins(
        separation_margin=p_min / (ff * fs_sep * p_tl) - 1,
        ultimate_margin=ultimate,
        yield_margin=yielding,
        separation_load=separation,
        rupture_load=rupture,
        rupture_before_separation=rupture_first,
        ultimate_equation=equation,
    )


def joint_slip_margin(
    *,
    bounds: PreloadBounds,
    limit_shear: Quantity,
    limit_tension: Quantity,
    surface: FayingSurface,
    factor_of_safety: float,
    fitting_factor: float,
    friction: float | None = None,
) -> float:
    """One fastener's slip margin at limit or yield load (NASA-STD-5020B Eq. 86).

    MS = μ·Pp-min / (FF·FS·(P_sL + μ·P_tL)) − 1 with the slip minimum preload of Eq. 5.
    ``friction`` defaults to the most the standard credits without test data for
    ``surface``, 0.20 or 0.10, and may not exceed it here: a higher coefficient needs the
    test the standard asks for, which is the caller's record, not this function's input.
    Never use this at ultimate, where the standard credits no friction (TFSR 8b).
    """
    if not isinstance(bounds, PreloadBounds):
        raise _refusal("bounds must come from preload_bounds", subject="bounds",
                       source=_JOINT_SOURCE)  # fmt: skip
    if not isinstance(surface, FayingSurface):
        raise _refusal(f"surface must be a FayingSurface; got {surface!r}", subject="surface",
                       source=_JOINT_SOURCE)  # fmt: skip
    ceiling = _MAX_FRICTION[surface]
    mu = ceiling if friction is None else require_finite(friction, name="friction")
    if not 0 < mu <= ceiling:
        raise _refusal(
            f"friction {mu} is outside (0, {ceiling:g}], the most NASA-STD-5020B credits on "
            f"{surface.value.replace('_', ' ')} surfaces without test data",
            subject="friction",
            source="a friction test of the joint's faying surfaces",
        )
    shear = _force(limit_shear, "limit_shear", source=_JOINT_SOURCE)
    tension = _force(limit_tension, "limit_tension", source=_JOINT_SOURCE)
    if shear < 0 or tension < 0 or not isfinite(shear + tension) or shear + tension == 0:
        raise _refusal("limit_shear and limit_tension are non-negative and not both zero",
                       subject="limit_shear", source=_JOINT_SOURCE)  # fmt: skip
    ff = _factor(fitting_factor, "fitting_factor")
    fs = _factor(factor_of_safety, "factor_of_safety")
    return mu * bounds.minimum_for_slip / (ff * fs * (shear + mu * tension)) - 1
