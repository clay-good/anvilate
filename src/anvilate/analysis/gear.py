"""T1 analytical spur-gear tooth bending (Lewis equation, closed-form).

A spur-gear tooth is a short cantilever loaded at its tip by the transmitted
tangential force W_t. The Lewis equation treats it as a beam of parabolic
uniform strength and gives the root bending stress

    σ = W_t / (F · m · Y)

where F is the face width, m the module (pitch diameter ÷ number of teeth), and Y
the Lewis form factor — a dimensionless number that captures the tooth's shape and
grows with the number of teeth (about 0.29 at 15 teeth, 0.34 at 20, 0.41 at 40 for
a 20° full-depth tooth). Y is read from a table for the tooth count and pressure
angle, so it is supplied as an argument, the same way a material allowable is.

The transmitted tangential load itself comes from the torque, W_t = 2·T/d over the
pitch diameter d. This is the classic static Lewis screen (Shigley); a real gear
also applies a velocity factor for dynamic load and the AGMA geometry/stress-cycle
factors on top. Inputs are dimension-checked
:class:`~anvilate.units.Quantity` values; Y is a positive dimensionless float.
"""

from __future__ import annotations

from ..units import Quantity

__all__ = [
    "gear_tangential_load",
    "lewis_bending_stress",
]


def _require(value: Quantity, expected: str, name: str) -> None:
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )


def gear_tangential_load(*, torque: Quantity, pitch_diameter: Quantity) -> Quantity:
    """The tangential (transmitted) load W_t = 2·T/d on a gear tooth.

    A gear carrying ``torque`` T on a pitch circle of diameter ``pitch_diameter`` d
    transmits the tangential force W_t = 2·T/d at the pitch line — the load the
    Lewis screen bends the tooth with, and the radial/separating load derives from
    it via the pressure angle. ``torque`` must be a torque and ``pitch_diameter`` a
    positive length. Returns the force in newtons.
    """
    _require(torque, "[force] * [length]", "torque")
    _require(pitch_diameter, "[length]", "pitch_diameter")
    if pitch_diameter.to("mm").magnitude <= 0:
        raise ValueError(f"pitch_diameter must be positive; got {pitch_diameter}")
    force = 2.0 * torque.pint / pitch_diameter.pint
    return Quantity(magnitude=float(force.to("N").magnitude), unit="N")


def lewis_bending_stress(
    *,
    tangential_load: Quantity,
    module: Quantity,
    face_width: Quantity,
    form_factor: float,
) -> Quantity:
    """The Lewis tooth-root bending stress σ = W_t/(F·m·Y).

    ``tangential_load`` W_t is the transmitted tangential force (from
    :func:`gear_tangential_load`), ``module`` m the gear module (pitch diameter ÷
    tooth count), ``face_width`` F the tooth width along the axis, and
    ``form_factor`` Y the Lewis form factor for the tooth count and pressure angle
    (from a table). Screen the result against the material's allowable bending
    stress. The load is a force, the module and face width positive lengths, and Y a
    positive dimensionless number. Returns the bending stress in MPa.
    """
    _require(tangential_load, "[force]", "tangential_load")
    _require(module, "[length]", "module")
    _require(face_width, "[length]", "face_width")
    if module.to("mm").magnitude <= 0:
        raise ValueError(f"module must be positive; got {module}")
    if face_width.to("mm").magnitude <= 0:
        raise ValueError(f"face_width must be positive; got {face_width}")
    if form_factor <= 0:
        raise ValueError(f"form_factor (Lewis Y) must be positive; got {form_factor}")
    stress = tangential_load.pint / (face_width.pint * module.pint * form_factor)
    return Quantity(magnitude=float(stress.to("MPa").magnitude), unit="MPa")
