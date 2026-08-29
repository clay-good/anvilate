"""T1 analytical battery Peukert-effect checks (closed-form).

A battery delivers less than its rated capacity when discharged quickly: internal losses rise with
current, so a cell rated for a slow 20-hour drain gives noticeably fewer amp-hours at a fast rate.
Peukert's law captures this with a single exponent, and it is what separates a battery's nameplate
capacity from the runtime it actually gives a heavy load. This is the discharge-rate physics behind
the bank sizing of :mod:`anvilate.analysis.energy_storage`, which assumes the rated capacity.

Relative to a rated current I_r at which the battery gives its rated capacity C (over a rated time
C/I_r), discharging at a higher current I shortens the runtime to t = (C/I_r) * (I_r/I)^k, where the
Peukert exponent k is 1 for an ideal battery and about 1.1-1.3 for lead-acid (higher is worse). The
capacity actually delivered is then C_eff = I * t = C * (I_r/I)^(k-1), which falls below C as the
current rises. Measuring runtime at two currents recovers the exponent, k = ln(t1/t2)/ln(I2/I1).
"""

from __future__ import annotations

from math import log

from ..units import Quantity

__all__ = [
    "peukert_effective_capacity",
    "peukert_exponent_from_two_rates",
    "peukert_runtime",
]


def peukert_runtime(
    *,
    rated_capacity: Quantity,
    rated_current: Quantity,
    discharge_current: Quantity,
    peukert_exponent: float,
) -> Quantity:
    """The runtime at a discharge current, t = (C/I_r) * (I_r/I)^k.

    How long a battery of ``rated_capacity`` C (given at the ``rated_current`` I_r) lasts when
    drained at a ``discharge_current`` I, with the ``peukert_exponent`` k: t = (C/I_r) * (I_r/I)^k.
    A higher current shortens the runtime faster than the simple C/I would predict, and the more so
    the larger k is. Returns the runtime in hours.
    """
    _check(rated_capacity, "[current]*[time]", "rated_capacity")
    _check(rated_current, "[current]", "rated_current")
    _check(discharge_current, "[current]", "discharge_current")
    c = rated_capacity.to("A*hr").magnitude
    i_r = rated_current.to("A").magnitude
    i = discharge_current.to("A").magnitude
    if c <= 0:
        raise ValueError("rated_capacity must be positive")
    if i_r <= 0:
        raise ValueError("rated_current must be positive")
    if i <= 0:
        raise ValueError("discharge_current must be positive")
    if peukert_exponent < 1.0:
        raise ValueError("peukert_exponent must be at least 1")
    return Quantity(magnitude=(c / i_r) * (i_r / i) ** peukert_exponent, unit="hr")


def peukert_effective_capacity(
    *,
    rated_capacity: Quantity,
    rated_current: Quantity,
    discharge_current: Quantity,
    peukert_exponent: float,
) -> Quantity:
    """The capacity delivered at a discharge current, C_eff = C * (I_r/I)^(k-1).

    The amp-hours a battery of ``rated_capacity`` C (at ``rated_current`` I_r) actually delivers at
    a ``discharge_current`` I, with ``peukert_exponent`` k: C_eff = C * (I_r/I)^(k-1). It equals the
    rated capacity at the rated current and falls below it as the current rises — the usable
    capacity a heavy load really sees. Returns the effective capacity in A*hr.
    """
    _check(rated_capacity, "[current]*[time]", "rated_capacity")
    _check(rated_current, "[current]", "rated_current")
    _check(discharge_current, "[current]", "discharge_current")
    c = rated_capacity.to("A*hr").magnitude
    i_r = rated_current.to("A").magnitude
    i = discharge_current.to("A").magnitude
    if c <= 0:
        raise ValueError("rated_capacity must be positive")
    if i_r <= 0:
        raise ValueError("rated_current must be positive")
    if i <= 0:
        raise ValueError("discharge_current must be positive")
    if peukert_exponent < 1.0:
        raise ValueError("peukert_exponent must be at least 1")
    return Quantity(magnitude=c * (i_r / i) ** (peukert_exponent - 1.0), unit="A*hr")


def peukert_exponent_from_two_rates(
    *,
    current_low: Quantity,
    runtime_low: Quantity,
    current_high: Quantity,
    runtime_high: Quantity,
) -> float:
    """The Peukert exponent from two discharge tests, k = ln(t1/t2)/ln(I2/I1).

    Fits the ``peukert_exponent`` from a low-current test (``current_low`` I1 lasting
    ``runtime_low`` t1) and a high-current test (``current_high`` I2 lasting ``runtime_high`` t2):
    k = ln(t1/t2)/ln(I2/I1). It characterizes a battery chemistry (near 1 is good, well above 1 is
    poor) from two measurements. Returns the exponent as a plain float.
    """
    _check(current_low, "[current]", "current_low")
    _check(runtime_low, "[time]", "runtime_low")
    _check(current_high, "[current]", "current_high")
    _check(runtime_high, "[time]", "runtime_high")
    i1 = current_low.to("A").magnitude
    t1 = runtime_low.to("hr").magnitude
    i2 = current_high.to("A").magnitude
    t2 = runtime_high.to("hr").magnitude
    if i1 <= 0 or i2 <= 0:
        raise ValueError("currents must be positive")
    if t1 <= 0 or t2 <= 0:
        raise ValueError("runtimes must be positive")
    if i2 <= i1:
        raise ValueError("current_high must exceed current_low")
    exponent = log(t1 / t2) / log(i2 / i1)
    # The two functions that CONSUME an exponent both refuse k < 1, but the one that fits it
    # from measurements did not, so a mis-paired test (the higher current apparently lasting
    # longer) handed back a k that the rest of the module rejects.
    if exponent < 1.0:
        raise ValueError(
            f"the two tests fit a Peukert exponent of {exponent:.4f}, below the k >= 1 floor "
            f"the rest of this module enforces: the higher current did not shorten the runtime "
            f"enough. Check that runtime_low pairs with current_low and runtime_high with "
            f"current_high."
        )
    return exponent


def _check(value: Quantity, expected: str, name: str) -> None:
    if not isinstance(value, Quantity):
        raise ValueError(f"{name} must be a {expected} quantity; got {value!r}")
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )
