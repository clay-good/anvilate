"""T1 analytical riveted-joint strength and efficiency (closed-form).

A riveted (or bolted lap) joint in a plate can fail three ways over one pitch p of
its rivet row, and the weakest governs:

- **tearing** of the plate across the section weakened by a hole:
  P_t = (p − d)·t·σ_t
- **shearing** of the rivets: P_s = n·(π/4·d²)·τ
- **crushing** (bearing) of the rivet against the hole: P_c = n·d·t·σ_c

with d the rivet diameter, t the plate thickness, and n the rivets per pitch (per
row). The joint's strength is the smallest of the three, and its *efficiency* is
that strength as a fraction of the unpierced plate, P_solid = p·t·σ_t — the number
that says how much of the plate's capacity the joint keeps (a good design balances
the three modes so none is wasted).

These are the classic riveted-joint forms (boiler/structural practice). The
allowable stresses are supplied as arguments, the same as any material allowable.
Geometry and stress inputs are dimension-checked
:class:`~anvilate.units.Quantity` values.
"""

from __future__ import annotations

from math import pi

from pydantic import BaseModel, ConfigDict

from ..units import Quantity

__all__ = [
    "RivetedJointStrength",
    "riveted_joint_efficiency",
]


def _require(value: Quantity, expected: str, name: str) -> None:
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )


class RivetedJointStrength(BaseModel):
    """The per-pitch strengths of a riveted joint and its efficiency.

    ``tearing_strength``, ``shearing_strength``, and ``crushing_strength`` are the
    loads that trigger each failure mode over one pitch; ``solid_plate_strength`` is
    the unpierced plate's. ``joint_strength`` is the smallest of the three failure
    loads, ``governing_mode`` names it ("tearing" / "shearing" / "crushing"), and
    ``efficiency`` is joint_strength / solid_plate_strength (0 to 1).
    """

    model_config = ConfigDict(frozen=True)

    tearing_strength: Quantity
    shearing_strength: Quantity
    crushing_strength: Quantity
    solid_plate_strength: Quantity
    joint_strength: Quantity
    governing_mode: str
    efficiency: float

    def __str__(self) -> str:
        return (
            f"riveted joint: efficiency {self.efficiency:.1%} (governed by {self.governing_mode})"
        )


def riveted_joint_efficiency(
    *,
    pitch: Quantity,
    rivet_diameter: Quantity,
    plate_thickness: Quantity,
    allowable_tension: Quantity,
    allowable_shear: Quantity,
    allowable_bearing: Quantity,
    rivets_per_pitch: int = 1,
) -> RivetedJointStrength:
    """Screen a riveted joint's three failure modes and its efficiency.

    Over one ``pitch`` p of the row, compares plate tearing (p − d)·t·σ_t, rivet
    shearing n·(π/4·d²)·τ, and rivet crushing n·d·t·σ_c against the solid plate
    p·t·σ_t. ``rivet_diameter`` d, ``plate_thickness`` t, ``allowable_tension`` σ_t,
    ``allowable_shear`` τ, ``allowable_bearing`` σ_c, and ``rivets_per_pitch`` n
    (single shear per rivet) describe the joint. Requires p > d (a hole cannot fill
    the pitch) and n ≥ 1. Returns a :class:`RivetedJointStrength` with the governing
    mode and efficiency.
    """
    _require(pitch, "[length]", "pitch")
    _require(rivet_diameter, "[length]", "rivet_diameter")
    _require(plate_thickness, "[length]", "plate_thickness")
    _require(allowable_tension, "[pressure]", "allowable_tension")
    _require(allowable_shear, "[pressure]", "allowable_shear")
    _require(allowable_bearing, "[pressure]", "allowable_bearing")
    if rivets_per_pitch < 1:
        raise ValueError(f"rivets_per_pitch must be a positive integer; got {rivets_per_pitch}")
    p = pitch.to("mm").magnitude
    d = rivet_diameter.to("mm").magnitude
    t = plate_thickness.to("mm").magnitude
    if d <= 0 or t <= 0:
        raise ValueError("rivet_diameter and plate_thickness must be positive")
    if p <= d:
        raise ValueError(f"pitch ({pitch}) must exceed rivet_diameter ({rivet_diameter})")
    st = allowable_tension.to("MPa").magnitude
    tau = allowable_shear.to("MPa").magnitude
    sc = allowable_bearing.to("MPa").magnitude
    for value, name in (
        (st, "allowable_tension"),
        (tau, "allowable_shear"),
        (sc, "allowable_bearing"),
    ):
        if value <= 0:
            raise ValueError(f"{name} must be positive")
    n = rivets_per_pitch
    tearing = (p - d) * t * st  # N
    shearing = n * (pi / 4.0) * d**2 * tau
    crushing = n * d * t * sc
    solid = p * t * st
    modes = {"tearing": tearing, "shearing": shearing, "crushing": crushing}
    governing_mode = min(modes, key=modes.__getitem__)
    joint = modes[governing_mode]
    return RivetedJointStrength(
        tearing_strength=Quantity(magnitude=tearing, unit="N"),
        shearing_strength=Quantity(magnitude=shearing, unit="N"),
        crushing_strength=Quantity(magnitude=crushing, unit="N"),
        solid_plate_strength=Quantity(magnitude=solid, unit="N"),
        joint_strength=Quantity(magnitude=joint, unit="N"),
        governing_mode=governing_mode,
        efficiency=joint / solid,
    )
