"""An example third-party discipline module: a threaded hanger rod in tension.

Not part of Anvilate. It shows the contract a module from outside the repository meets: a
`MANIFEST` and one `screen_<element_type>` function per element type it covers, taking the
document's `element_params` as plain JSON and returning plain JSON entries. Enable it by
path, for example `anvilate check rod.yaml --module examples/third_party_module/hanger_rod.py`.
Every entry it contributes is marked unverified-origin.

The check: tensile stress on the thread's stress area, A_s = (pi/4)(d - 0.9382 P)^2 for an
ISO metric thread (ISO 898-1 clause 9.1.6.1), against the rod's yield strength.
"""

import math

MANIFEST = {
    "id": "example_hanger_rods",
    "namespace": "example_hanger_rods",
    "version": "0.1.0",
    "unit_default": "SI",
    "standards": ["ISO 898-1:2013"],
    "tiers": ["T1_analytical"],
    "screens": ["screen_hanger_rod"],
    "covers": ["hanger_rod"],
    "summary": "Threaded hanger rods in axial tension (an example third-party module).",
}

_TO_MM = {"mm": 1.0, "in": 25.4}
_TO_N = {"N": 1.0, "kN": 1000.0, "lbf": 4.448222}
_TO_MPA = {"MPa": 1.0, "ksi": 6.894757}


def _value(params, name, table):
    quantity = params[name]
    unit = quantity["unit"]
    if unit not in table:
        raise ValueError(f"{name} must be in one of {sorted(table)}; got {unit!r}")
    return float(quantity["magnitude"]) * table[unit]


def screen_hanger_rod(params, required_safety_factor=None):
    """One check: thread stress-area tension against yield."""
    diameter = _value(params, "diameter", _TO_MM)
    pitch = _value(params, "pitch", _TO_MM)
    load = _value(params, "load", _TO_N)
    yield_strength = _value(params, "yield_strength", _TO_MPA)
    stress_area = math.pi / 4 * (diameter - 0.9382 * pitch) ** 2
    stress = load / stress_area
    factor = yield_strength / stress
    required = required_safety_factor or 1.0
    return [
        {
            "name": "hanger rod tension",
            "status": "pass" if factor >= required else "fail",
            "detail": (
                f"safety factor {factor:.2f} vs required minimum {required:.2f}: "
                f"{stress:.1f} MPa on a stress area of {stress_area:.1f} mm²"
            ),
            "reference": "ISO 898-1:2013 cl. 9.1.6.1 (tensile stress area)",
            "safety_factor": round(factor, 6),
            "required_safety_factor": required,
        }
    ]
