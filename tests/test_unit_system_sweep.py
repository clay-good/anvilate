"""The same call in US customary units must give the same physical answer.

The guard sweep (tests/test_guard_sweep.py) builds a call that succeeds for each of about
1,500 public analysis functions. This replays each with every Quantity restated in US
units (feet, psi, lbf, pounds, °R, BTU, horsepower, and the base-unit conversion of
anything compound) and compares the results physically: numbers to 1e-6, Quantities in
base units, verdicts exactly.

Its first run found three designs on an exact boundary whose verdict depended on the unit
they were written in: a hull with V = L·B·T, a turbine producing exactly its rated
energy, and a change-point four-bar (s + l = p + q). Each was accepted in metres and
refused, or classified differently, in feet, because converting to the function's working
unit is exact only for metric inputs.
"""

from __future__ import annotations

import inspect
import math

from pydantic import BaseModel

from anvilate import analysis
from anvilate.scorecard import Scorecard, ScorecardEntry
from anvilate.units import Quantity
from test_guard_sweep import _baseline, _checked_dimensions, _discovered, _succeeding

_US = {
    "[length]": "ft",
    "[pressure]": "psi",
    "[force]": "lbf",
    "[mass]": "lb",
    "[temperature]": "degR",
    "[energy]": "BTU",
    "[power]": "hp",
    "[area]": "ft**2",
    "[volume]": "ft**3",
    "[velocity]": "ft/s",
    "[density]": "lb/ft**3",
    "[torque]": "lbf*ft",
}


def _in_us_units(value: Quantity) -> Quantity | None:
    for dimension, unit in _US.items():
        if value.has_dimension(dimension):
            return Quantity(magnitude=value.to(unit).magnitude, unit=unit)
    try:
        base = str(value.pint.to_base_units().units)
        unit = base.replace("meter", "foot").replace("kilogram", "pound")
        return Quantity(magnitude=float(value.pint.to(unit).magnitude), unit=unit)
    except Exception:  # noqa: BLE001 - a unit with no US spelling is compared in SI only
        return None


def _physical(result: object, depth: int = 0) -> object:
    """A result reduced to what a unit system cannot change."""
    if depth > 4:
        return None
    if isinstance(result, bool | str) or result is None:
        return result
    if isinstance(result, int | float):
        return float(result)
    if isinstance(result, Quantity):
        base = result.pint.to_base_units()
        return (float(base.magnitude), str(base.units))
    if isinstance(result, ScorecardEntry):
        return (result.status.value, result.safety_factor)
    if isinstance(result, Scorecard):
        return (result.status.value, tuple(_physical(e, depth + 1) for e in result.entries))
    if isinstance(result, tuple | list):
        return tuple(_physical(item, depth + 1) for item in result)
    if isinstance(result, dict):
        return tuple((key, _physical(result[key], depth + 1)) for key in sorted(result, key=str))
    if isinstance(result, BaseModel):
        return tuple(_physical(getattr(result, f), depth + 1) for f in type(result).model_fields)
    return type(result).__name__


def _same(a: object, b: object) -> bool:
    if isinstance(a, float) and isinstance(b, float):
        if math.isnan(a) or math.isnan(b):
            return math.isnan(a) and math.isnan(b)
        return math.isclose(a, b, rel_tol=1e-6, abs_tol=1e-12)
    if isinstance(a, tuple) and isinstance(b, tuple):
        return len(a) == len(b) and all(_same(x, y) for x, y in zip(a, b, strict=True))
    return a == b


def test_every_swept_function_answers_the_same_in_us_units() -> None:
    dimensions = _checked_dimensions()
    compared, differences = 0, []
    for name in sorted(analysis.__all__):
        function = getattr(analysis, name)
        if not inspect.isfunction(function) or name not in dimensions:
            continue
        kwargs = _baseline(function, dimensions[name])
        if kwargs is not None:
            kwargs = _succeeding(function, kwargs, dimensions[name])
        if kwargs is None:
            kwargs = _discovered(function)
        if kwargs is None:
            continue
        us = {k: _in_us_units(v) if isinstance(v, Quantity) else v for k, v in kwargs.items()}
        if any(value is None for value in us.values()):
            continue
        si_result = _physical(function(**kwargs))
        compared += 1
        try:
            us_result = _physical(function(**us))
        except Exception as refusal:  # noqa: BLE001 - a refusal in one system only is the finding
            differences.append(f"{name}: SI answered, US refused: {str(refusal)[:90]}")
            continue
        if not _same(si_result, us_result):
            differences.append(f"{name}: SI {str(si_result)[:60]} vs US {str(us_result)[:60]}")

    # The floor goes first: a binder that stopped building calls compares nothing.
    assert compared > 1_400, f"only {compared} functions compared"
    assert not differences, "\n".join(differences)


def test_a_change_point_linkage_is_one_in_feet_as_in_metres() -> None:
    from anvilate.analysis import fourbar_type, is_grashof

    for unit in ("m", "ft", "in"):
        links = {
            "ground": Quantity(magnitude=3.0, unit=unit),
            "input_link": Quantity(magnitude=1.0, unit=unit),
            "coupler": Quantity(magnitude=3.0, unit=unit),
            "output_link": Quantity(magnitude=1.0, unit=unit),
        }
        assert is_grashof(**links), unit
        assert fourbar_type(**links) == "change-point", unit
