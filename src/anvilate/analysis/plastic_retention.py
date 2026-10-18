"""T1 plastic retention after time at temperature: a fixed deflection held by a creeping modulus.

A snap-fit, a boss holding a screw and a press fit all retain their parts by a deflection
fixed at assembly. The force that deflection produces is the part's stiffness times it,
and the stiffness of a deflected beam or ring is proportional to the material's modulus
(Roark, *Formulas for Stress and Strain*). A thermoplastic's modulus relaxes under that
held strain: after hours at temperature the same deflection pushes back with the creep
(apparent) modulus E_c(T, t) rather than the short-term E₀, so the retained force is

    F(T, t) = F₀ · E_c(T, t) / E₀.

The creep modulus is the material record's, at the service temperature: a curve of
(hours, modulus) the caller declares with its source. Between two declared times it is
interpolated linearly in log time, the scale creep data are plotted and fitted on; a time
before the first point or after the last, or a temperature the record does not state, is
not evaluated, and the module never extrapolates. Out of scope: the retention lost to
moisture, to chemical attack, and to the stress relaxation of a part that also yields.
"""

from __future__ import annotations

from collections.abc import Sequence
from math import log

from pydantic import BaseModel, ConfigDict

from .._models import Provenance, RevalidatedModel, each_one
from ..refusal import RefusalError, Remedy
from ..units import Quantity, require_finite

__all__ = [
    "CreepModulusPoint",
    "CreepModulusRecord",
    "PlasticRetention",
    "retention_after_creep",
]

_RECORD_SOURCE = "the material record's creep (apparent) modulus curve at temperature"


class _PlasticRetentionInputError(RefusalError, ValueError):
    """A plastic-retention input that cannot be used without correction."""


def _refusal(
    message: str, *, subject: str, source: str = _RECORD_SOURCE
) -> _PlasticRetentionInputError:
    return _PlasticRetentionInputError(
        message, remedies=(Remedy(action="replace", subject=subject, source=source),)
    )


def _positive(value: Quantity, dimension: str, unit: str, name: str) -> float:
    # ``dimension`` is stated for the reader and the probe binder; ``unit`` converts.
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


class CreepModulusPoint(BaseModel):
    """One point of a creep-modulus curve: the hours under load and the modulus then (Roark)."""

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    hours: float
    modulus: Quantity


class CreepModulusRecord(RevalidatedModel):
    """A material's creep-modulus curve at one temperature, and where it was read (Roark)."""

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    temperature: Quantity
    points: tuple[CreepModulusPoint, ...]
    source: Provenance


class PlasticRetention(BaseModel):
    """The retained force after time at temperature, or why it was not evaluated (Roark).

    ``force`` is in N and ``fraction`` is E_c/E₀; both are None when the record does not
    cover the service temperature and time, with ``reason`` saying what is missing.
    """

    model_config = ConfigDict(frozen=True)

    force: float | None
    fraction: float | None
    creep_modulus: float | None
    source: Provenance | None
    reason: str | None = None

    def __str__(self) -> str:
        if self.force is None:
            return f"retention not evaluated — {self.reason}"
        return (
            f"retained {self.force:.4g} N ({self.fraction:.1%} of initial) at a creep modulus "
            f"of {self.creep_modulus:.4g} MPa ({self.source})"
        )


def retention_after_creep(
    *,
    initial_force: Quantity,
    short_term_modulus: Quantity,
    temperature: Quantity,
    hours: float,
    records: Sequence[CreepModulusRecord],
) -> PlasticRetention:
    """The force a fixed deflection keeps after ``hours`` at ``temperature`` (Roark: F ∝ E).

    ``initial_force`` is the retention at assembly with ``short_term_modulus`` E₀.
    ``records`` are the material's creep-modulus curves, each at one temperature; the one
    at ``temperature`` (within 0.5 K) is used, interpolated in log time between its points.
    No record at the temperature, or a time outside the curve, is not evaluated — never
    extrapolated.
    """
    f0 = _positive(initial_force, "[force]", "N", "initial_force")
    e0 = _positive(short_term_modulus, "[pressure]", "MPa", "short_term_modulus")
    t_k = _positive(temperature, "[temperature]", "K", "temperature")
    h = require_finite(hours, name="hours")
    if h <= 0:
        raise _refusal(f"hours is {h}; time at temperature is positive", subject="hours",
                       source="the duty cycle's time at temperature")  # fmt: skip
    declared = each_one(records, CreepModulusRecord, named="records")
    matching = [r for r in declared if abs(_positive(r.temperature, "[temperature]", "K",
                                                     "records") - t_k) <= 0.5]  # fmt: skip
    if not matching:
        stated = sorted(f"{r.temperature.to('degC').magnitude:g} °C" for r in declared)
        return PlasticRetention(
            force=None, fraction=None, creep_modulus=None, source=None,
            reason=f"no creep-modulus record at {t_k - 273.15:g} °C (records at "
            f"{', '.join(stated) or 'none'}); declare one, as no temperature is extrapolated",
        )  # fmt: skip
    record = matching[0]
    points = sorted(
        ((require_finite(p.hours, name="records"), _positive(p.modulus, "[pressure]", "MPa",
                                                             "records")) for p in record.points),
    )  # fmt: skip
    if len(points) < 1 or any(hp <= 0 for hp, _ in points):
        raise _refusal("a creep-modulus record holds points at positive hours", subject="records")
    first, last = points[0][0], points[-1][0]
    if not first <= h <= last:
        return PlasticRetention(
            force=None, fraction=None, creep_modulus=None, source=record.source,
            reason=f"{h:g} h is outside the record's {first:g}–{last:g} h; declare data that "
            "reach it, as no time is extrapolated",
        )  # fmt: skip
    modulus = points[0][1]
    for (h1, e1), (h2, e2) in zip(points, points[1:], strict=False):
        if h1 <= h <= h2:
            modulus = e1 if h2 == h1 else e1 + (e2 - e1) * log(h / h1) / log(h2 / h1)
            break
    if modulus > e0:
        raise _refusal(
            f"the creep modulus {modulus:g} MPa exceeds the short-term modulus {e0:g} MPa; "
            "a modulus does not stiffen under held strain",
            subject="records",
        )
    fraction = modulus / e0
    return PlasticRetention(force=f0 * fraction, fraction=fraction, creep_modulus=modulus,
                            source=record.source)  # fmt: skip
