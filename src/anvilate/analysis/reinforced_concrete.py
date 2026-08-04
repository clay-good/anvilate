"""ACI 318 reinforced-concrete flexure: the moment a singly-reinforced beam carries.

At a reinforced-concrete beam's ultimate strength the concrete crushes in a
rectangular stress block of intensity 0.85·f'c and depth a, and the tension steel
yields at f_y. Force balance sets the block depth a = A_s·f_y/(0.85·f'c·b), and the
nominal moment is the steel force times the internal lever arm, M_n = A_s·f_y·(d −
a/2). This is the foundation of every reinforced-concrete beam design (ACI 318 §22.3).

Anvilate evaluates the closed form; the material strengths f'c and f_y are the
caller's inputs. This screens the flexural strength of an *under-reinforced*
(tension-controlled) section — the ductile design the code steers toward; verifying
the tension-controlled strain limit and applying the strength-reduction factor φ
(0.90 for tension-controlled flexure) are the caller's to add.
"""

from __future__ import annotations

from math import sqrt

from ..units import Quantity

__all__ = [
    "rc_stress_block_depth",
    "rc_beam_nominal_moment",
    "rc_tension_steel_for_moment",
    "rc_concrete_shear_strength",
]

_ACI_STRESS_BLOCK_FACTOR = 0.85  # the 0.85·f'c Whitney stress-block intensity


def _require(value: Quantity, expected: str, name: str) -> None:
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )


def rc_stress_block_depth(
    *,
    steel_area: Quantity,
    steel_yield: Quantity,
    concrete_strength: Quantity,
    beam_width: Quantity,
) -> Quantity:
    """The ACI Whitney stress-block depth a = A_s·f_y/(0.85·f'c·b).

    Force balance at ultimate: the tension steel force A_s·f_y equals the concrete
    compression 0.85·f'c·b·a, so a = A_s·f_y/(0.85·f'c·b). ``steel_area`` A_s is the
    tension reinforcement area, ``steel_yield`` f_y its yield, ``concrete_strength``
    f'c the concrete's cylinder strength, and ``beam_width`` b the section width.
    Returns the block depth in mm.
    """
    _require(steel_area, "[area]", "steel_area")
    _require(steel_yield, "[pressure]", "steel_yield")
    _require(concrete_strength, "[pressure]", "concrete_strength")
    _require(beam_width, "[length]", "beam_width")
    as_mm2 = steel_area.to("mm**2").magnitude
    fy = steel_yield.to("MPa").magnitude
    fc = concrete_strength.to("MPa").magnitude
    b = beam_width.to("mm").magnitude
    if as_mm2 <= 0 or fy <= 0 or fc <= 0 or b <= 0:
        raise ValueError(
            "steel_area, steel_yield, concrete_strength, and beam_width must be positive"
        )
    return Quantity(magnitude=as_mm2 * fy / (_ACI_STRESS_BLOCK_FACTOR * fc * b), unit="mm")


def rc_beam_nominal_moment(
    *,
    steel_area: Quantity,
    steel_yield: Quantity,
    concrete_strength: Quantity,
    beam_width: Quantity,
    effective_depth: Quantity,
) -> Quantity:
    """The ACI 318 nominal flexural strength M_n = A_s·f_y·(d − a/2) of a singly-
    reinforced beam.

    The steel tension force acting through the internal lever arm d − a/2, where a is
    :func:`rc_stress_block_depth` and ``effective_depth`` d is the distance from the
    compression face to the steel centroid. The other arguments are as in
    :func:`rc_stress_block_depth`. The design strength is φ·M_n (φ = 0.90 for a
    tension-controlled section). Returns M_n in kN·m.
    """
    a = (
        rc_stress_block_depth(
            steel_area=steel_area,
            steel_yield=steel_yield,
            concrete_strength=concrete_strength,
            beam_width=beam_width,
        )
        .to("mm")
        .magnitude
    )
    _require(effective_depth, "[length]", "effective_depth")
    d = effective_depth.to("mm").magnitude
    if d <= 0:
        raise ValueError(f"effective_depth must be positive; got {effective_depth}")
    if a >= 2.0 * d:
        raise ValueError("the stress block exceeds the section; check the inputs")
    as_mm2 = steel_area.to("mm**2").magnitude
    fy = steel_yield.to("MPa").magnitude
    moment_n_mm = as_mm2 * fy * (d - a / 2.0)
    return Quantity(magnitude=moment_n_mm / 1.0e6, unit="kN*m")


def rc_tension_steel_for_moment(
    *,
    required_moment: Quantity,
    steel_yield: Quantity,
    concrete_strength: Quantity,
    beam_width: Quantity,
    effective_depth: Quantity,
) -> Quantity:
    """The tension steel area A_s a required nominal moment needs (the design inverse).

    Inverting M_n = A_s·f_y·(d − a/2) with a = A_s·f_y/(0.85·f'c·b) is a quadratic in
    the steel force T = A_s·f_y; the under-reinforced (smaller) root gives the least
    reinforcement that reaches ``required_moment`` M_n. The arguments are as in
    :func:`rc_beam_nominal_moment`. Raises when the moment exceeds what the section can
    develop even at balanced conditions (a deeper or wider beam is needed). Returns the
    required steel area in mm².
    """
    _require(required_moment, "[force] * [length]", "required_moment")
    _require(steel_yield, "[pressure]", "steel_yield")
    _require(concrete_strength, "[pressure]", "concrete_strength")
    _require(beam_width, "[length]", "beam_width")
    _require(effective_depth, "[length]", "effective_depth")
    mn = required_moment.to("N*mm").magnitude
    fy = steel_yield.to("MPa").magnitude
    fc = concrete_strength.to("MPa").magnitude
    b = beam_width.to("mm").magnitude
    d = effective_depth.to("mm").magnitude
    if mn <= 0 or fy <= 0 or fc <= 0 or b <= 0 or d <= 0:
        raise ValueError("all inputs must be positive")
    # T² − (1.7·f'c·b·d)·T + 1.7·f'c·b·M_n = 0, from M_n = T·d − T²/(1.7·f'c·b).
    coeff = 1.7 * fc * b  # = 2·0.85·f'c·b
    discriminant = (coeff * d) ** 2 - 4.0 * coeff * mn
    if discriminant < 0:
        raise ValueError(
            "the required moment exceeds the section's flexural capacity; deepen or "
            "widen the beam (or use compression steel)"
        )
    tension_force = (coeff * d - sqrt(discriminant)) / 2.0
    return Quantity(magnitude=tension_force / fy, unit="mm**2")


def rc_concrete_shear_strength(
    *,
    concrete_strength: Quantity,
    beam_width: Quantity,
    effective_depth: Quantity,
    lightweight_factor: float = 1.0,
) -> Quantity:
    """The ACI 318 concrete shear strength V_c = 0.17·λ·√f'c·b_w·d of a beam.

    The shear a reinforced-concrete beam carries in the concrete alone, before any
    stirrups (ACI 318-19 §22.5.5.1, the simplified form for a member without axial
    load): V_c = 0.17·λ·√f'c·b_w·d, where ``concrete_strength`` f'c is the cylinder
    strength, ``beam_width`` b_w the web width, ``effective_depth`` d the depth to the
    tension steel, and ``lightweight_factor`` λ the concrete-weight factor (1.0
    normalweight, 0.75 all-lightweight). When the factored shear exceeds φ·V_c
    (φ = 0.75) the section needs stirrups; above φ·(V_c + V_s,max) a larger section is
    required. f'c and λ are the caller's inputs. Returns V_c in kN.
    """
    _require(concrete_strength, "[pressure]", "concrete_strength")
    _require(beam_width, "[length]", "beam_width")
    _require(effective_depth, "[length]", "effective_depth")
    fc = concrete_strength.to("MPa").magnitude
    b = beam_width.to("mm").magnitude
    d = effective_depth.to("mm").magnitude
    if fc <= 0 or b <= 0 or d <= 0:
        raise ValueError("concrete_strength, beam_width, and effective_depth must be positive")
    if lightweight_factor <= 0:
        raise ValueError(f"lightweight_factor must be positive; got {lightweight_factor}")
    vc_n = 0.17 * lightweight_factor * sqrt(fc) * b * d
    return Quantity(magnitude=vc_n / 1000.0, unit="kN")
