"""T1 durability screens: modes kept clear of declared excitation, and drops onto a surface.

**Modal separation.** A mode sitting inside an excitation band resonates; one near it is
amplified. A program states which bands its product sees (a motor's order, a road's
wheel-hop, a fan's blade pass) and how far a mode must stay from each, and the screen
holds every estimated mode below a declared ceiling to that. For a mode at f and a band
from f_lo to f_hi, the separation is f/f_hi above the band and f_lo/f below it; a mode
inside the band has none. What the separation guards against is the single-degree-of-
freedom magnification near resonance (Timoshenko;
:func:`~anvilate.analysis.dynamics.dynamic_magnification_factor`). The bands, the ceiling
and the target ratio are the caller's, each with its source: this module bundles none.

**Drop.** A body of mass m dropped from height h onto a surface of contact stiffness k
lands at v = √(2gh) carrying E = mgh, and a linear contact turns that into a half-sine
deceleration pulse (Timoshenko, *Vibration Problems in Engineering*, the impact of a mass
on a spring):

    peak deceleration   a = v·√(k/m)
    pulse duration      τ = π·√(m/k)

with no rebound loss, which is the conservative reading for the peak. What a mounted item
inside feels depends on its own natural frequency: the pulse's peak times the half-sine
shock amplification at τ·f_n (:func:`~anvilate.analysis.dynamics.half_sine_shock_amplification`),
or times one where the item is declared rigid. The contact stiffness is the weakest input
and the caller's; every result is labelled an estimate, not a measurement.
"""

from __future__ import annotations

from collections.abc import Sequence
from math import pi, sqrt

from pydantic import BaseModel, ConfigDict

from .._models import Named, Provenance, RevalidatedModel, each_one
from ..refusal import RefusalError, Remedy
from ..units import Quantity, require_finite
from .dynamics import half_sine_shock_amplification

__all__ = [
    "ExcitationBand",
    "ModeSeparation",
    "modal_separation",
    "MountedItem",
    "MountedItemLoad",
    "DropScreen",
    "drop_screen",
]

_G = 9.80665
_BAND_SOURCE = "the program's excitation bands and separation target, with their source"
_DROP_SOURCE = "the drop requirement: height, contact surface and its stiffness"


class _DurabilityInputError(RefusalError, ValueError):
    """A durability input that cannot be used without correction."""


def _refusal(message: str, *, subject: str, source: str) -> _DurabilityInputError:
    return _DurabilityInputError(
        message, remedies=(Remedy(action="replace", subject=subject, source=source),)
    )


def _positive(value: Quantity, dimension: str, unit: str, name: str, source: str) -> float:
    # ``dimension`` is stated for the reader and for the probe that binds a quantity of the
    # right dimension to each parameter (tests/test_fraction_guards.py); ``unit`` converts.
    if not isinstance(value, Quantity):
        raise _refusal(f"{name} must be a quantity in {unit}; got {value!r}", subject=name,
                       source=source)  # fmt: skip
    try:
        converted = value.to(unit).magnitude
    except Exception as error:
        raise _refusal(f"{name} is {value}, which is not convertible to {unit}", subject=name,
                       source=source) from error  # fmt: skip
    magnitude = require_finite(converted, name=name)
    if magnitude <= 0:
        raise _refusal(f"{name} must be positive; got {value}", subject=name, source=source)
    return magnitude


class ExcitationBand(RevalidatedModel):
    """A declared excitation band and its source, kept clear of resonance (Timoshenko)."""

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    name: Named
    low: Quantity
    high: Quantity
    source: Provenance

    def bounds_hz(self) -> tuple[float, float]:
        """The band's edges in Hz, low first, refusing a band that is not one."""
        lo = _positive(self.low, "1/[time]", "Hz", "low", _BAND_SOURCE)
        hi = _positive(self.high, "1/[time]", "Hz", "high", _BAND_SOURCE)
        if hi < lo:
            raise _refusal(f"band '{self.name}' has its high edge, {hi:g} Hz, below its low "
                           f"edge, {lo:g} Hz",
                           subject="high", source=_BAND_SOURCE)  # fmt: skip
        return lo, hi


class ModeSeparation(RevalidatedModel):
    """One mode against one band: the separation ratio, the target, and the verdict.

    ``ratio`` is f/f_hi above the band or f_lo/f below it, 1.0 inside it; the pair passes
    when the ratio reaches ``required``, the separation the program declares to keep the
    mode off resonance (Timoshenko).
    """

    model_config = ConfigDict(frozen=True)

    mode: Named
    frequency: float
    band: Named
    ratio: float
    required: float
    passes: bool

    def __str__(self) -> str:
        verdict = "clear" if self.passes else "TOO CLOSE"
        return (
            f"[{verdict}] {self.mode} at {self.frequency:.4g} Hz vs '{self.band}': separation "
            f"{self.ratio:.3f}, required {self.required:g}"
        )


def modal_separation(
    *,
    modes: Sequence[tuple[str, Quantity]],
    bands: Sequence[ExcitationBand],
    required_ratio: float,
    ceiling: Quantity,
) -> tuple[ModeSeparation, ...]:
    """Every estimated mode below ``ceiling`` against every declared band (Timoshenko).

    ``modes`` are (name, natural frequency) pairs; ``required_ratio`` (≥ 1) is the
    separation the program demands, applied on both sides of each band. Returns one result
    per mode and band; modes above the ceiling are left out, as the program declared them
    out of scope.
    """
    target = require_finite(required_ratio, name="required_ratio")
    if target < 1:
        raise _refusal(f"required_ratio is {target}; a separation ratio is at least 1",
                       subject="required_ratio", source=_BAND_SOURCE)  # fmt: skip
    top = _positive(ceiling, "1/[time]", "Hz", "ceiling", _BAND_SOURCE)
    declared = each_one(bands, ExcitationBand, named="bands")
    if not declared:
        raise _refusal("no excitation band is declared, so there is nothing to separate from",
                       subject="bands", source=_BAND_SOURCE)  # fmt: skip
    if isinstance(modes, (str, bytes)):
        raise _refusal("modes is a sequence of (name, frequency) pairs", subject="modes",
                       source="the modal estimate")  # fmt: skip
    results = []
    for name, frequency in modes:
        f = _positive(frequency, "1/[time]", "Hz", f"modes[{name}]", "the modal estimate")
        if f > top:
            continue
        for band in declared:
            lo, hi = band.bounds_hz()
            ratio = f / hi if f > hi else (lo / f if f < lo else 1.0)
            results.append(
                ModeSeparation(mode=name, frequency=f, band=band.name, ratio=ratio,
                               required=target, passes=ratio >= target)
            )  # fmt: skip
    return tuple(results)


class MountedItem(RevalidatedModel):
    """An item inside the dropped body, rigid or on a mount of its own frequency (Timoshenko)."""

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    name: Named
    mass: Quantity
    natural_frequency: Quantity | None = None


class MountedItemLoad(RevalidatedModel):
    """The estimated peak load on a mounted item, and the amplification used (Timoshenko)."""

    model_config = ConfigDict(frozen=True)

    name: Named
    amplification: float
    peak_acceleration_g: float
    load: float


class DropScreen(BaseModel):
    """A drop's energy, landing speed, half-sine pulse (Timoshenko) and mounted-item loads.

    SI throughout: J, m/s, g (standard gravities), s, N. ``estimated`` is always True: the
    contact stiffness is declared, not measured, and the loads follow from it.
    """

    model_config = ConfigDict(frozen=True)

    energy: float
    impact_velocity: float
    peak_deceleration_g: float
    pulse_duration: float
    items: tuple[MountedItemLoad, ...]
    estimated: bool = True

    def __str__(self) -> str:
        lines = [
            f"drop: {self.energy:.3g} J at {self.impact_velocity:.3g} m/s; estimated peak "
            f"{self.peak_deceleration_g:.4g} g over {self.pulse_duration * 1000:.3g} ms "
            "(linear contact, no rebound loss; Timoshenko)"
        ]
        lines += [
            f"  {i.name}: {i.load:.4g} N ({i.peak_acceleration_g:.4g} g, amplification "
            f"{i.amplification:.3g})"
            for i in self.items
        ]
        return "\n".join(lines)


def drop_screen(
    *,
    mass: Quantity,
    height: Quantity,
    contact_stiffness: Quantity,
    items: Sequence[MountedItem] = (),
) -> DropScreen:
    """A drop onto a linear contact (Timoshenko): energy mgh, a = v√(k/m), τ = π√(m/k).

    ``contact_stiffness`` k is the surface-and-housing stiffness the body lands on, the
    caller's estimate with its source. Each mounted item feels the pulse's peak times the
    half-sine shock amplification at its natural frequency, or the peak itself if it is
    declared rigid (no natural frequency).
    """
    m = _positive(mass, "[mass]", "kg", "mass", _DROP_SOURCE)
    h = _positive(height, "[length]", "m", "height", _DROP_SOURCE)
    k = _positive(contact_stiffness, "[mass]/[time]**2", "N/m", "contact_stiffness", _DROP_SOURCE)
    carried = each_one(items, MountedItem, named="items")
    v = sqrt(2 * _G * h)
    peak = v * sqrt(k / m)
    tau = pi * sqrt(m / k)
    loads = []
    for item in carried:
        item_mass = _positive(item.mass, "[mass]", "kg", "mass", "the mounted item's record")
        if item.natural_frequency is None:
            amplification = 1.0
        else:
            amplification = half_sine_shock_amplification(
                pulse_duration=Quantity(magnitude=tau, unit="s"),
                natural_frequency=item.natural_frequency,
            )
        loads.append(
            MountedItemLoad(name=item.name, amplification=amplification,
                            peak_acceleration_g=peak * amplification / _G,
                            load=item_mass * peak * amplification)
        )  # fmt: skip
    return DropScreen(
        energy=m * _G * h,
        impact_velocity=v,
        peak_deceleration_g=peak / _G,
        pulse_duration=tau,
        items=tuple(loads),
    )
