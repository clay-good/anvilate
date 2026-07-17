"""T1 analytical spur-gear tooth bending (Lewis equation) and train kinematics.

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

The kinematics half covers gear *trains*: the signed train value
e = ±∏(driver teeth)/∏(driven teeth) of a simple or compound train, and the
planetary (epicyclic) sun/carrier/ring speed relation via the Willis equation
N_r·ω_r + N_s·ω_s = (N_r + N_s)·ω_c, together with the whole-tooth planet size
N_p = (N_r − N_s)/2 and the equal-spacing assembly condition
(N_s + N_r) divisible by the planet count (Shigley ch. 13).
"""

from __future__ import annotations

from collections.abc import Sequence
from math import cos, prod, radians, sin, sqrt, tan

from pydantic import BaseModel, ConfigDict

from ..units import Quantity
from .contact import hertz_cylinder_contact

# Barth velocity-factor constants Kv = (A + f(V))/A, by tooth manufacturing quality:
# cut/milled uses V, hobbed/shaped and precision ground/shaved use sqrt(V) (V m/s).
_BARTH_FACTORS = {
    "cut": (6.1, False),
    "hobbed": (3.56, True),
    "precision": (5.56, True),
}

__all__ = [
    "gear_tangential_load",
    "gear_radial_load",
    "gear_normal_load",
    "pitch_line_velocity",
    "barth_velocity_factor",
    "lewis_bending_stress",
    "gear_contact_stress",
    "gear_train_value",
    "planetary_planet_teeth",
    "planetary_can_assemble",
    "planetary_speed",
    "PlanetaryTorques",
    "planetary_torques",
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


def _check_pressure_angle(pressure_angle: float) -> float:
    if not 0 < pressure_angle < 90:
        raise ValueError(f"pressure_angle (degrees) must lie in (0, 90); got {pressure_angle}")
    return radians(pressure_angle)


def gear_radial_load(*, tangential_load: Quantity, pressure_angle: float) -> Quantity:
    """The radial (separating) load W_r = W_t·tan(φ) on a spur-gear mesh.

    The pressure angle tilts the tooth contact force off the tangent, producing a
    radial component that pushes the gears apart and bends their shafts.
    ``tangential_load`` W_t is the transmitted force (from
    :func:`gear_tangential_load`) and ``pressure_angle`` φ the gear pressure angle
    **in degrees** (20° is the modern standard; 14.5° and 25° also occur — the units
    layer does not carry angles, so φ is a plain degree value). φ must lie in
    (0, 90). Returns the radial load in newtons — add it to the other shaft loads
    when sizing the bearings.
    """
    _require(tangential_load, "[force]", "tangential_load")
    phi = _check_pressure_angle(pressure_angle)
    return Quantity(magnitude=tangential_load.to("N").magnitude * tan(phi), unit="N")


def gear_normal_load(*, tangential_load: Quantity, pressure_angle: float) -> Quantity:
    """The total normal tooth load W_n = W_t/cos(φ) on a spur-gear mesh.

    The full force pressed along the line of action between the teeth — the
    resultant of the tangential and radial components. ``tangential_load`` W_t and
    ``pressure_angle`` φ (degrees, in (0, 90)) are as in :func:`gear_radial_load`.
    Returns the normal load in newtons; it always exceeds W_t.
    """
    _require(tangential_load, "[force]", "tangential_load")
    phi = _check_pressure_angle(pressure_angle)
    return Quantity(magnitude=tangential_load.to("N").magnitude / cos(phi), unit="N")


def pitch_line_velocity(*, pitch_diameter: Quantity, rotational_speed: Quantity) -> Quantity:
    """The pitch-line velocity V = π·d·n of a gear.

    The linear speed of the teeth at the pitch circle, which sets the dynamic load
    a gear tooth feels. ``pitch_diameter`` d is the pitch diameter and
    ``rotational_speed`` n the gear speed (rpm or rad/s — a rotational frequency).
    Both must be positive. Returns the velocity in m/s, ready for
    :func:`barth_velocity_factor`.
    """
    _require(pitch_diameter, "[length]", "pitch_diameter")
    if not rotational_speed.has_dimension("[frequency]"):
        raise ValueError(
            f"rotational_speed must be a [frequency] quantity; got "
            f"{rotational_speed.dimensionality} ({rotational_speed})"
        )
    d = pitch_diameter.to("m").magnitude
    omega = rotational_speed.to("rad/s").magnitude  # V = omega * r = pi * d * n
    if d <= 0:
        raise ValueError(f"pitch_diameter must be positive; got {pitch_diameter}")
    if omega <= 0:
        raise ValueError(f"rotational_speed must be positive; got {rotational_speed}")
    return Quantity(magnitude=omega * d / 2.0, unit="m/s")


def barth_velocity_factor(*, pitch_line_velocity: Quantity, quality: str = "cut") -> float:
    """The Barth dynamic velocity factor K_v that amplifies a gear's tooth load.

    A gear tooth at speed carries more than the static transmitted load because of
    meshing impact; the Barth factor K_v = (A + f(V))/A estimates the increase, with
    the constant A and whether it uses V or √V set by the tooth ``quality``:
    ``"cut"`` (commercial cut/milled, A = 6.1, linear V), ``"hobbed"`` (A = 3.56,
    √V), or ``"precision"`` (shaved/ground, A = 5.56, √V) — finer teeth amplify
    less. ``pitch_line_velocity`` V is from :func:`pitch_line_velocity` (a velocity).
    Multiply the transmitted load by K_v before the :func:`lewis_bending_stress`
    screen. Returns the dimensionless K_v (≥ 1).
    """
    if not pitch_line_velocity.has_dimension("[velocity]"):
        raise ValueError(
            f"pitch_line_velocity must be a [velocity] quantity; got "
            f"{pitch_line_velocity.dimensionality} ({pitch_line_velocity})"
        )
    if quality not in _BARTH_FACTORS:
        raise ValueError(f"quality must be one of {sorted(_BARTH_FACTORS)}; got {quality!r}")
    v = pitch_line_velocity.to("m/s").magnitude
    if v < 0:
        raise ValueError(f"pitch_line_velocity must be non-negative; got {pitch_line_velocity}")
    a, use_sqrt = _BARTH_FACTORS[quality]
    return (a + (sqrt(v) if use_sqrt else v)) / a


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


def gear_contact_stress(
    *,
    tangential_load: Quantity,
    pinion_pitch_diameter: Quantity,
    gear_pitch_diameter: Quantity,
    pressure_angle: float,
    face_width: Quantity,
    modulus_pinion: Quantity,
    modulus_gear: Quantity,
    poisson_pinion: float = 0.3,
    poisson_gear: float = 0.3,
) -> Quantity:
    """The Hertzian (Buckingham) surface contact stress at a spur-gear pitch point.

    Gears also fail by surface pitting, a rolling-contact-fatigue problem set by the
    peak Hertz pressure where the tooth flanks touch. At the pitch point the involute
    flanks curve like two cylinders of diameter d·sin(φ), pressed by the normal load
    W_t/cos(φ) over the ``face_width``. This derives that geometry and delegates to
    the verified line-contact solver
    (:func:`~anvilate.analysis.hertz_cylinder_contact`).
    ``tangential_load`` W_t, ``pinion_pitch_diameter`` d₁ and
    ``gear_pitch_diameter`` d₂, ``pressure_angle`` φ (degrees), ``face_width``, and
    each body's elastic ``modulus``/``poisson`` describe the mesh. Screen the result
    against the material's allowable contact (surface-fatigue) stress. Returns the
    peak contact stress in MPa.
    """
    _require(tangential_load, "[force]", "tangential_load")
    _require(pinion_pitch_diameter, "[length]", "pinion_pitch_diameter")
    _require(gear_pitch_diameter, "[length]", "gear_pitch_diameter")
    phi = _check_pressure_angle(pressure_angle)
    d1 = pinion_pitch_diameter.to("mm").magnitude
    d2 = gear_pitch_diameter.to("mm").magnitude
    if d1 <= 0 or d2 <= 0:
        raise ValueError("pinion_pitch_diameter and gear_pitch_diameter must be positive")
    normal_load = tangential_load.to("N").magnitude / cos(phi)
    result = hertz_cylinder_contact(
        force=Quantity(magnitude=normal_load, unit="N"),
        length=face_width,
        diameter1=Quantity(magnitude=d1 * sin(phi), unit="mm"),
        modulus1=modulus_pinion,
        poisson1=poisson_pinion,
        modulus2=modulus_gear,
        poisson2=poisson_gear,
        diameter2=Quantity(magnitude=d2 * sin(phi), unit="mm"),
    )
    return result.max_contact_pressure


def _check_tooth_count(count: int, name: str) -> int:
    whole = int(count)
    if whole != count or whole <= 0:
        raise ValueError(f"{name} must be a positive whole number of teeth; got {count}")
    return whole


def gear_train_value(
    *,
    driver_teeth: Sequence[int],
    driven_teeth: Sequence[int],
    internal_meshes: int = 0,
) -> float:
    """The signed train value e = ω_out/ω_in of a simple or compound gear train.

    Each mesh in the train pairs one driving gear with one driven gear, and the
    overall speed ratio is e = ±∏(driver teeth)/∏(driven teeth): a small gear
    driving a big one slows the shaft down by their tooth ratio, and stages
    multiply. The sign carries direction — every *external* mesh reverses
    rotation, so e is negative for an odd number of external meshes. An idler
    appears in both lists (it is driven by one gear and drives the next): it
    cancels out of the magnitude but still contributes its reversal, which is
    exactly what an idler is for. ``driver_teeth`` and ``driven_teeth`` list the
    tooth counts mesh by mesh (equal length, positive whole numbers);
    ``internal_meshes`` counts how many of the meshes are internal (ring-gear)
    engagements, which do *not* reverse. Returns the dimensionless signed e —
    multiply the input speed by it to get the output speed, and divide an ideal
    (loss-free) torque by |e| to get the output torque.
    """
    if len(driver_teeth) == 0 or len(driver_teeth) != len(driven_teeth):
        raise ValueError(
            f"driver_teeth and driven_teeth must be non-empty and equal length "
            f"(one entry per mesh); got {len(driver_teeth)} drivers and "
            f"{len(driven_teeth)} driven"
        )
    drivers = [_check_tooth_count(n, "driver_teeth entry") for n in driver_teeth]
    driven = [_check_tooth_count(n, "driven_teeth entry") for n in driven_teeth]
    mesh_count = len(driven)
    if not 0 <= internal_meshes <= mesh_count:
        raise ValueError(
            f"internal_meshes must lie in [0, {mesh_count}] for a {mesh_count}-mesh "
            f"train; got {internal_meshes}"
        )
    sign = -1.0 if (mesh_count - internal_meshes) % 2 else 1.0
    return sign * prod(drivers) / prod(driven)


def planetary_planet_teeth(*, sun_teeth: int, ring_teeth: int) -> int:
    """The planet tooth count N_p = (N_r − N_s)/2 forced by planetary geometry.

    In an epicyclic train the planet must span the radial gap between the sun
    and the ring, so its pitch diameter — and with a shared module, its tooth
    count — is fixed at N_p = (N_r − N_s)/2. If N_r − N_s is odd there is no
    whole-tooth planet: that sun/ring pair simply cannot be cut, however good
    its ratio looks, and this raises rather than returning half a tooth.
    ``sun_teeth`` N_s and ``ring_teeth`` N_r are positive whole tooth counts
    with N_r > N_s. Returns the whole planet tooth count.
    """
    sun = _check_tooth_count(sun_teeth, "sun_teeth")
    ring = _check_tooth_count(ring_teeth, "ring_teeth")
    if ring <= sun:
        raise ValueError(
            f"ring_teeth must exceed sun_teeth (the ring encloses the sun); "
            f"got ring {ring} vs sun {sun}"
        )
    if (ring - sun) % 2:
        raise ValueError(
            f"no whole-tooth planet fits: ring_teeth - sun_teeth = {ring - sun} is odd, "
            f"so N_p = (N_r - N_s)/2 is not a whole number"
        )
    return (ring - sun) // 2


def planetary_can_assemble(*, sun_teeth: int, ring_teeth: int, planet_count: int) -> bool:
    """Whether equally spaced planets can actually be assembled into the train.

    Planets are spaced equally to cancel the radial mesh loads, but the teeth
    only line up at every planet position when (N_s + N_r) is divisible by the
    planet count — otherwise the second planet arrives at its slot half a tooth
    out of phase and will not drop in. ``sun_teeth``, ``ring_teeth``, and
    ``planet_count`` are positive whole numbers with N_r > N_s. Returns True
    when the train assembles.
    """
    sun = _check_tooth_count(sun_teeth, "sun_teeth")
    ring = _check_tooth_count(ring_teeth, "ring_teeth")
    count = _check_tooth_count(planet_count, "planet_count")
    if ring <= sun:
        raise ValueError(
            f"ring_teeth must exceed sun_teeth (the ring encloses the sun); "
            f"got ring {ring} vs sun {sun}"
        )
    return (sun + ring) % count == 0


def _check_speed(value: Quantity, name: str) -> float:
    if not value.has_dimension("[frequency]"):
        raise ValueError(
            f"{name} must be a rotational-speed ([frequency]) quantity; got "
            f"{value.dimensionality} ({value})"
        )
    return value.to("rpm").magnitude


def planetary_speed(
    *,
    sun_teeth: int,
    ring_teeth: int,
    sun_speed: Quantity | None = None,
    carrier_speed: Quantity | None = None,
    ring_speed: Quantity | None = None,
) -> Quantity:
    """Solve the Willis equation for the missing planetary-train member speed.

    An epicyclic train's three coaxial members — sun, planet carrier, and ring —
    obey one linear relation (the Willis equation, from the train value
    −N_s/N_r seen by an observer riding the carrier):

        N_r·ω_r + N_s·ω_s = (N_r + N_s)·ω_c

    Fix any member and the other two are geared together; drive two and the
    third follows. Pass exactly two of ``sun_speed``, ``carrier_speed``, and
    ``ring_speed`` as *signed* rotational speeds (rpm or rad/s; opposite
    directions get opposite signs, and a held member is simply 0 rpm) and leave
    the unknown as ``None``. The classic reducer — ring held, sun driven —
    returns the carrier speed ω_c = ω_s·N_s/(N_s + N_r), an
    (1 + N_r/N_s):1 reduction with no direction reversal. ``sun_teeth`` and
    ``ring_teeth`` are positive whole tooth counts with N_r > N_s. Returns the
    solved speed in rpm, signed.
    """
    sun = _check_tooth_count(sun_teeth, "sun_teeth")
    ring = _check_tooth_count(ring_teeth, "ring_teeth")
    if ring <= sun:
        raise ValueError(
            f"ring_teeth must exceed sun_teeth (the ring encloses the sun); "
            f"got ring {ring} vs sun {sun}"
        )
    speeds = {"sun_speed": sun_speed, "carrier_speed": carrier_speed, "ring_speed": ring_speed}
    unknowns = [name for name, value in speeds.items() if value is None]
    if len(unknowns) != 1:
        raise ValueError(
            f"exactly one of sun_speed, carrier_speed, ring_speed must be None (the "
            f"unknown to solve for); got {len(unknowns)} unknowns"
        )
    (unknown,) = unknowns
    if unknown == "carrier_speed":
        ws = _check_speed(sun_speed, "sun_speed")
        wr = _check_speed(ring_speed, "ring_speed")
        solved = (ring * wr + sun * ws) / (ring + sun)
    elif unknown == "sun_speed":
        wc = _check_speed(carrier_speed, "carrier_speed")
        wr = _check_speed(ring_speed, "ring_speed")
        solved = ((ring + sun) * wc - ring * wr) / sun
    else:
        wc = _check_speed(carrier_speed, "carrier_speed")
        ws = _check_speed(sun_speed, "sun_speed")
        solved = ((ring + sun) * wc - sun * ws) / ring
    return Quantity(magnitude=solved, unit="rpm")


class PlanetaryTorques(BaseModel):
    """The three reaction torques on an ideal (loss-free) planetary train.

    ``sun_torque``, ``ring_torque``, and ``carrier_torque`` are the external
    torques applied to each coaxial member, signed so their sum is zero (they
    balance the case). The carrier — the summing member — always carries the
    largest magnitude and the opposite sign to the sun and ring.
    """

    model_config = ConfigDict(frozen=True)

    sun_torque: Quantity
    ring_torque: Quantity
    carrier_torque: Quantity


def planetary_torques(
    *,
    sun_teeth: int,
    ring_teeth: int,
    input_member: str,
    input_torque: Quantity,
) -> PlanetaryTorques:
    """The ideal planetary torque split fixed by the tooth counts alone.

    In a loss-free epicyclic train the external torques share out purely by
    geometry, independent of which member is held or how fast anything turns:

        T_s : T_r : T_c = N_s : N_r : −(N_s + N_r)

    The sun and ring torques scale with their tooth counts and the carrier — the
    summing member — takes their sum with the opposite sign, so the three add to
    zero. Fixing the torque on any one member fixes the other two: name the
    driven member in ``input_member`` (``"sun"``, ``"ring"``, or ``"carrier"``)
    and pass its ``input_torque`` (a signed torque). This is the ideal split —
    a real train loses a few percent per mesh, and the carrier torque is the one
    a real efficiency discounts. ``sun_teeth`` and ``ring_teeth`` are positive
    whole tooth counts with N_r > N_s. Returns a :class:`PlanetaryTorques` with
    all three torques in N·m.
    """
    sun = _check_tooth_count(sun_teeth, "sun_teeth")
    ring = _check_tooth_count(ring_teeth, "ring_teeth")
    if ring <= sun:
        raise ValueError(
            f"ring_teeth must exceed sun_teeth (the ring encloses the sun); "
            f"got ring {ring} vs sun {sun}"
        )
    _require(input_torque, "[force] * [length]", "input_torque")
    ratios = {"sun": float(sun), "ring": float(ring), "carrier": -float(sun + ring)}
    if input_member not in ratios:
        raise ValueError(f"input_member must be one of {sorted(ratios)}; got {input_member!r}")
    scale = input_torque.to("N*m").magnitude / ratios[input_member]
    return PlanetaryTorques(
        sun_torque=Quantity(magnitude=scale * ratios["sun"], unit="N*m"),
        ring_torque=Quantity(magnitude=scale * ratios["ring"], unit="N*m"),
        carrier_torque=Quantity(magnitude=scale * ratios["carrier"], unit="N*m"),
    )
