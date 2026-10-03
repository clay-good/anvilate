"""Push every argument of every public analysis function out of range, one at a time.

The front-door probe binds every argument to ``1.0`` and so reaches only the first type
check. This sweep builds a call that *succeeds* — each Quantity argument in the SI unit of
the dimension its function checks it against, read from the function's own
``_check``/``_require`` calls, and each plain number a small positive value — and then
moves one argument at a time to -1, 0 and NaN.

Whatever the function does with that is allowed except three things:

- raising anything that is not a structured refusal (a ``ZeroDivisionError``, a
  ``math domain error``, a complex number handed to a Quantity);
- refusing with a remedy whose subject names none of the function's parameters;
- accepting a NaN, or refusing one without naming the argument that carried it.

Its first run found sixteen crashes and 164 NaN arguments answered with a NaN result.
"""

from __future__ import annotations

import ast
import inspect
import math
import re
from collections import Counter
from pathlib import Path

from anvilate import analysis
from anvilate.refusal import RefusalError
from anvilate.units import Quantity
from conftest import parsed_source

_ANALYSIS = Path(__file__).parents[1] / "src/anvilate/analysis"
_SI = {
    "[length]": "m",
    "[time]": "s",
    "[mass]": "kg",
    "[temperature]": "K",
    "[current]": "A",
    "[substance]": "mol",
    "[luminosity]": "cd",
    "[force]": "N",
    "[pressure]": "Pa",
    "[energy]": "J",
    "[power]": "W",
    "[area]": "m**2",
    "[volume]": "m**3",
    "[frequency]": "Hz",
    "[velocity]": "m/s",
    "[speed]": "m/s",
    "[acceleration]": "m/s**2",
    "[density]": "kg/m**3",
    "[torque]": "N*m",
    "[charge]": "C",
    "[electric_potential]": "V",
    "[resistance]": "ohm",
    "[capacitance]": "F",
    "[inductance]": "H",
    "[magnetic_flux]": "Wb",
    "[magnetic_field]": "T",
    "[magnetic_flux_density]": "T",
    "[viscosity]": "Pa*s",
    "[kinematic_viscosity]": "m**2/s",
    "[angle]": "rad",
    "[luminous_flux]": "lm",
    "[illuminance]": "lx",
}
_PLAIN = {"float": 0.5, "int": 2, "bool": False}


def _quantity(dimension: str, magnitude: float) -> Quantity | None:
    unit = dimension
    for token in sorted(_SI, key=len, reverse=True):
        unit = unit.replace(token, f"({_SI[token]})")
    if "[" in unit:
        return None
    try:
        value = Quantity(magnitude=magnitude, unit=unit or "dimensionless")
    except ValueError:
        return None
    return value if value.has_dimension(dimension) else None


def _checked_dimensions() -> dict[str, dict[str, str]]:
    """Each public function's ``param -> dimension``, from its own dimension checks."""
    found: dict[str, dict[str, str]] = {}
    for path in sorted(_ANALYSIS.glob("*.py")):
        for function in parsed_source(path).body:
            if not isinstance(function, ast.FunctionDef) or function.name.startswith("_"):
                continue
            arguments = {a.arg for a in function.args.args + function.args.kwonlyargs}
            dimensions: dict[str, str] = {}
            for call in ast.walk(function):
                if not isinstance(call, ast.Call):
                    continue
                names = [a.id for a in call.args if isinstance(a, ast.Name) and a.id in arguments]
                texts = [
                    a.value
                    for a in call.args
                    if isinstance(a, ast.Constant) and isinstance(a.value, str) and "[" in a.value
                ]
                if len(names) == 1 and len(texts) == 1:
                    dimensions[names[0]] = texts[0]
            found[function.name] = dimensions
    return found


def _baseline(function, dimensions: dict[str, str]) -> dict[str, object] | None:
    kwargs: dict[str, object] = {}
    for parameter in inspect.signature(function).parameters.values():
        if parameter.default is not inspect.Parameter.empty:
            continue
        if parameter.kind in (parameter.VAR_POSITIONAL, parameter.VAR_KEYWORD):
            return None
        if parameter.name in dimensions:
            value = _quantity(dimensions[parameter.name], 1.0)
            if value is None:
                return None
            kwargs[parameter.name] = value
        elif parameter.annotation in _PLAIN:
            kwargs[parameter.name] = _PLAIN[parameter.annotation]
        else:
            return None
    return kwargs


def _moved(value: object, dimension: str | None, magnitude: float) -> object | None:
    if dimension is not None:
        return _quantity(dimension, magnitude)
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return None if math.isnan(magnitude) else int(magnitude)
    return magnitude


def test_every_out_of_range_argument_meets_a_structured_refusal_or_a_number() -> None:
    dimensions = _checked_dimensions()
    tally: Counter[str] = Counter()
    failures: list[str] = []
    for name in sorted(analysis.__all__):
        function = getattr(analysis, name)
        if not inspect.isfunction(function) or name not in dimensions:
            continue
        kwargs = _baseline(function, dimensions[name])
        if kwargs is None:
            tally["unbuildable"] += 1
            continue
        try:
            function(**kwargs)
        except Exception:  # noqa: BLE001 - a baseline the binder cannot satisfy is skipped
            tally["baseline refused"] += 1
            continue
        tally["swept"] += 1
        parameters = set(inspect.signature(function).parameters)
        for argument, value in kwargs.items():
            for magnitude in (-1.0, 0.0, math.nan):
                moved = _moved(value, dimensions[name].get(argument), magnitude)
                if moved is None:
                    continue
                label = f"{name}({argument}={magnitude})"
                try:
                    result = function(**{**kwargs, argument: moved})
                except RefusalError as refusal:
                    tally["refused"] += 1
                    named = set(re.findall(r"\w+", " ".join(r.subject for r in refusal.remedies)))
                    if not named & parameters:
                        failures.append(f"{label}: remedy names no parameter: {named}")
                    elif math.isnan(magnitude) and argument not in named:
                        failures.append(f"{label}: NaN refused without naming {argument}")
                except Exception as slip:  # noqa: BLE001 - the class is the thing under test
                    failures.append(f"{label}: {type(slip).__name__}: {str(slip)[:80]}")
                else:
                    tally["accepted"] += 1
                    if math.isnan(magnitude):
                        failures.append(f"{label}: NaN accepted, returned {result!r:.80}")

    # The floor goes first: a binder that stopped building calls would pass with nothing swept.
    assert tally["swept"] > 900, tally
    assert tally["refused"] > 7_000, tally
    assert not failures, f"{len(failures)} of {sum(tally.values())}:\n" + "\n".join(failures)
