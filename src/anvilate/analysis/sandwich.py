"""T1 sandwich panels: the local modes a thin-faced panel fails in before its global ones.

A sandwich panel's strength in compression is usually not its facings' yield. Its thin
faces buckle locally first, into the core (wrinkling) or into the cells of a honeycomb
(intracell dimpling), or the core shears out under the face load (shear crimping). The
closed forms are NASA CR-1457 (Sullins, Smith and Spier, *Manual for Structural Stability
Analysis of Sandwich Plates and Shells*, 1969), which follows MIL-HDBK-23:

    intracell dimpling       σ = 2.0·E_f/(1 − ν_f²)·(t_f/s)²                       (Eq. 2.1-4)
    wrinkling, solid core    σ = 0.50·[E_f·E_c·G_c/(1 − ν_f²)]^(1/3)                (Eq. 2.2-5)
    wrinkling, honeycomb     σ = 0.82·E_f·√(E_c·t_f/(E_f·t_c)) / (1 + 0.64·K_δ)     (Eq. 2.2-12)
                             with K_δ = δ·E_c/(t_c·F_c), or the lower bound
                             σ = 0.33·E_f·√(E_c·t_f/(E_f·t_c)) without the waviness  (Eq. 2.2-14)
    shear crimping           σ = h²/((t₁ + t₂)·t_c)·G_c                              (Eq. 2.3-11)

with s the diameter of the largest circle inscribed in a cell, E_c the core's modulus
normal to the faces, G_c its transverse shear modulus in the plane of the load, δ the
initial waviness amplitude, F_c the lowest of the core's flatwise compressive and tensile
and the bond strength, and h the distance between the facings' middle surfaces. The
facings are elastic (η = 1): above their proportional limit these overstate.

The coefficients are not equally conservative and the module says so. K = 2.0 for dimpling
is Norris's fit, which "does not provide a lower bound" (CR-1457 p. 2-2), and dimpling is
not failure — the cells keep carrying load. Q = 0.50 for a solid core is recommended for a
lower bound. 0.33 for honeycomb is the 0.82 fit with a knockdown of about 0.4 for an
unknown waviness. Shear crimping needs no knockdown.

The core's shear stress under a transverse load is the shear per unit width over h, as the
Astronautic Structures Manual's circular-panel form p·r/(2h) is (NASA TM X-73306 §B9,
Eq. 77). An insert's pull-out has no public closed form; it is held to a declared,
test-derived allowable.
"""

from __future__ import annotations

from enum import StrEnum
from math import sqrt

from pydantic import BaseModel, ConfigDict, model_validator

from .._models import Named, RevalidatedModel
from ..refusal import RefusalError, Remedy
from ..units import Quantity, require_finite

__all__ = [
    "CoreKind",
    "SandwichPanel",
    "SandwichMode",
    "SandwichScreen",
    "sandwich_local_modes",
]

_PANEL_SOURCE = "the sandwich panel's drawing and its facing and core records"


class _SandwichInputError(RefusalError, ValueError):
    """A sandwich-panel input that cannot be used without correction."""


def _refusal(message: str, *, subject: str, source: str = _PANEL_SOURCE) -> _SandwichInputError:
    return _SandwichInputError(
        message, remedies=(Remedy(action="replace", subject=subject, source=source),)
    )


class CoreKind(StrEnum):
    """Which NASA CR-1457 wrinkling form applies: antisymmetric (solid) or symmetric."""

    SOLID_OR_FOAM = "solid_or_foam"
    HONEYCOMB = "honeycomb"


def _value(value: Quantity | None, unit: str, name: str) -> float | None:
    if value is None:
        return None
    if not isinstance(value, Quantity):
        raise _refusal(f"{name} must be a quantity in {unit}; got {value!r}", subject=name)
    try:
        converted = value.to(unit).magnitude
    except Exception as error:
        raise _refusal(f"{name} is {value}, which is not convertible to {unit}",
                       subject=name) from error  # fmt: skip
    magnitude = require_finite(converted, name=name)
    if magnitude <= 0:
        raise _refusal(f"{name} must be positive; got {value}", subject=name)
    return magnitude


class SandwichPanel(RevalidatedModel):
    """A sandwich panel's facings and core, as NASA CR-1457 needs them for its local modes.

    Every property but the facings' modulus and thickness and the core thickness may be
    left out; a mode whose inputs are missing is not evaluated, and names what it needs.
    Stresses and moduli are quantities convertible to MPa, lengths to mm.
    """

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    facing_modulus: Quantity
    facing_poisson: float
    facing_thickness: Quantity
    core_thickness: Quantity
    core_kind: CoreKind
    other_facing_thickness: Quantity | None = None
    core_normal_modulus: Quantity | None = None
    core_shear_modulus: Quantity | None = None
    cell_size: Quantity | None = None
    waviness: Quantity | None = None
    core_flatwise_strength: Quantity | None = None
    core_shear_strength: Quantity | None = None
    insert_pull_out_allowable: Quantity | None = None

    @model_validator(mode="after")
    def _a_panel(self) -> SandwichPanel:
        nu = require_finite(self.facing_poisson, name="facing_poisson")
        if not 0 <= nu < 0.5:
            raise _refusal(f"facing_poisson is {nu}; it lies in [0, 0.5)",
                           subject="facing_poisson")  # fmt: skip
        for name, unit in (("facing_modulus", "MPa"), ("facing_thickness", "mm"),
                           ("core_thickness", "mm"), ("other_facing_thickness", "mm"),
                           ("core_normal_modulus", "MPa"), ("core_shear_modulus", "MPa"),
                           ("cell_size", "mm"), ("waviness", "mm"),
                           ("core_flatwise_strength", "MPa"), ("core_shear_strength", "MPa"),
                           ("insert_pull_out_allowable", "N")):  # fmt: skip
            _value(getattr(self, name), unit, name)
        return self


class SandwichMode(RevalidatedModel):
    """One local mode: its allowable, the applied value, and the ratio, or why not evaluated.

    ``allowable`` and ``applied`` are in MPa (N for insert pull-out); ``ratio`` is applied
    over allowable, so above 1 the mode is reached. ``basis`` says how conservative the
    coefficient is, as NASA CR-1457 states it.
    """

    model_config = ConfigDict(frozen=True)

    mode: Named
    allowable: float | None
    applied: float | None
    ratio: float | None
    basis: str
    equation: str
    reason: str | None = None


class SandwichScreen(BaseModel):
    """Every local mode, and the governing one among those evaluated (NASA CR-1457)."""

    model_config = ConfigDict(frozen=True)

    modes: tuple[SandwichMode, ...]
    governing: str | None

    def __str__(self) -> str:
        lines = []
        for m in self.modes:
            if m.ratio is None:
                lines.append(f"  {m.mode}: not evaluated — {m.reason}")
            else:
                lines.append(
                    f"  {m.mode}: {m.applied:.4g} of {m.allowable:.4g} (ratio {m.ratio:.3f}; "
                    f"{m.equation}, {m.basis})"
                )
        head = f"governing: {self.governing}" if self.governing else "no mode evaluated"
        return "\n".join([f"sandwich local modes (NASA CR-1457), {head}", *lines])


def _mode(name: str, allowable: float | None, applied: float | None, *, basis: str,
          equation: str, needs: str) -> SandwichMode:  # fmt: skip
    if allowable is None:
        return SandwichMode(mode=name, allowable=None, applied=applied, ratio=None,
                            basis=basis, equation=equation, reason=f"declare {needs}")  # fmt: skip
    if applied is None:
        return SandwichMode(mode=name, allowable=allowable, applied=None, ratio=None,
                            basis=basis, equation=equation,
                            reason="no applied load of this kind was declared")  # fmt: skip
    return SandwichMode(mode=name, allowable=allowable, applied=applied,
                        ratio=applied / allowable, basis=basis, equation=equation)  # fmt: skip


def sandwich_local_modes(
    panel: SandwichPanel,
    *,
    facing_stress: Quantity | None = None,
    transverse_shear: Quantity | None = None,
    insert_load: Quantity | None = None,
) -> SandwichScreen:
    """Screen a panel's local modes against its applied loads (NASA CR-1457 §2).

    ``facing_stress`` is the compressive stress in the more loaded facing; the face
    modes and shear crimping (as a facing stress, (t₁ + t₂)·σ_crimp shared by the two) are
    held to it. ``transverse_shear`` is the shear force per unit width; the core shear
    stress is it over h. ``insert_load`` is an insert's pull-out load. A mode missing
    its inputs is not evaluated and names them; the governing mode is the highest ratio
    among those evaluated.
    """
    if not isinstance(panel, SandwichPanel):
        raise _refusal("panel must be a SandwichPanel", subject="panel")
    ef = float(panel.facing_modulus.to("MPa").magnitude)
    nu = panel.facing_poisson
    tf = float(panel.facing_thickness.to("mm").magnitude)
    t2 = _value(panel.other_facing_thickness, "mm", "other_facing_thickness") or tf
    tc = float(panel.core_thickness.to("mm").magnitude)
    ec = _value(panel.core_normal_modulus, "MPa", "core_normal_modulus")
    gc = _value(panel.core_shear_modulus, "MPa", "core_shear_modulus")
    s = _value(panel.cell_size, "mm", "cell_size")
    delta = _value(panel.waviness, "mm", "waviness")
    fc = _value(panel.core_flatwise_strength, "MPa", "core_flatwise_strength")
    tau_allow = _value(panel.core_shear_strength, "MPa", "core_shear_strength")
    insert_allow = _value(panel.insert_pull_out_allowable, "N", "insert_pull_out_allowable")
    sigma = _value(facing_stress, "MPa", "facing_stress")
    shear = _value(transverse_shear, "N/mm", "transverse_shear")
    pull = _value(insert_load, "N", "insert_load")
    h = tc + (tf + t2) / 2

    modes = []
    if panel.core_kind is CoreKind.HONEYCOMB:
        dimpling = None if s is None else 2.0 * ef / (1 - nu**2) * (tf / s) ** 2
        modes.append(_mode("intracell dimpling", dimpling, sigma,
                           basis="Norris's fit, not a lower bound; dimpling is not failure",
                           equation="Eq. 2.1-4", needs="cell_size"))  # fmt: skip
        if ec is None:
            wrinkling, basis = None, ""
        else:
            stiffness = ef * sqrt(ec * tf / (ef * tc))
            if delta is not None and fc is not None:
                k_delta = delta * ec / (tc * fc)
                wrinkling = 0.82 * stiffness / (1 + 0.64 * k_delta)
                basis = f"with the declared waviness, K_δ = {k_delta:.3g}"
            else:
                wrinkling = 0.33 * stiffness
                basis = "lower bound for an unknown waviness (about 0.4 of the 0.82 fit)"
        modes.append(_mode("face wrinkling", wrinkling, sigma, basis=basis or "symmetric form",
                           equation="Eq. 2.2-12" if "declared" in basis else "Eq. 2.2-14",
                           needs="core_normal_modulus"))  # fmt: skip
    else:
        wrinkling = (
            None if ec is None or gc is None
            else 0.50 * (ef * ec * gc / (1 - nu**2)) ** (1 / 3)
        )  # fmt: skip
        modes.append(_mode("face wrinkling", wrinkling, sigma,
                           basis="Q = 0.50, recommended for a lower bound",
                           equation="Eq. 2.2-5",
                           needs="core_normal_modulus and core_shear_modulus"))  # fmt: skip
    crimping = None if gc is None else h * h / ((tf + t2) * tc) * gc
    modes.append(_mode("shear crimping", crimping, sigma, basis="no knockdown required",
                       equation="Eq. 2.3-11", needs="core_shear_modulus"))  # fmt: skip
    modes.append(_mode("core shear", tau_allow, None if shear is None else shear / h,
                       basis="the core's declared shear strength",
                       equation="V/h (NASA TM X-73306 §B9 Eq. 77 form)",
                       needs="core_shear_strength"))  # fmt: skip
    modes.append(_mode("insert pull-out", insert_allow, pull,
                       basis="a declared, test-derived allowable; no public closed form",
                       equation="declared", needs="insert_pull_out_allowable"))  # fmt: skip
    evaluated = [m for m in modes if m.ratio is not None]
    governing = max(evaluated, key=lambda m: m.ratio or 0.0).mode if evaluated else None
    return SandwichScreen(modes=tuple(modes), governing=governing)
