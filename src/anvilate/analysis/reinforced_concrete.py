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
    "rc_column_axial_strength",
    "rc_beta1",
    "rc_net_tensile_strain",
    "rc_development_length",
]

# ACI 318 ultimate concrete compressive strain (the strain-diagram anchor).
_ACI_CONCRETE_ULTIMATE_STRAIN = 0.003

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


def rc_column_axial_strength(
    *,
    gross_area: Quantity,
    steel_area: Quantity,
    concrete_strength: Quantity,
    steel_yield: Quantity,
) -> Quantity:
    """The ACI 318 nominal axial strength P_o = 0.85·f'c·(A_g − A_st) + f_y·A_st.

    The concentric (zero-eccentricity) squash load of a reinforced-concrete column
    (ACI 318-19 §22.4.2.2): the concrete on its net area A_g − A_st at 0.85·f'c plus
    the longitudinal steel A_st at yield. ``gross_area`` A_g is the column's gross
    cross-section, ``steel_area`` A_st the total longitudinal reinforcement,
    ``concrete_strength`` f'c, and ``steel_yield`` f_y. The design maximum caps this at
    φ·0.80·P_o for a tied column (φ·0.85·P_o spiral) to allow for accidental
    eccentricity — apply that on top. Requires A_st < A_g. Returns P_o in kN.
    """
    _require(gross_area, "[area]", "gross_area")
    _require(steel_area, "[area]", "steel_area")
    _require(concrete_strength, "[pressure]", "concrete_strength")
    _require(steel_yield, "[pressure]", "steel_yield")
    ag = gross_area.to("mm**2").magnitude
    ast = steel_area.to("mm**2").magnitude
    fc = concrete_strength.to("MPa").magnitude
    fy = steel_yield.to("MPa").magnitude
    if ag <= 0 or ast <= 0 or fc <= 0 or fy <= 0:
        raise ValueError(
            "gross_area, steel_area, concrete_strength, and steel_yield must be positive"
        )
    if ast >= ag:
        raise ValueError(f"steel_area ({steel_area}) must be below the gross area ({gross_area})")
    po_n = _ACI_STRESS_BLOCK_FACTOR * fc * (ag - ast) + fy * ast
    return Quantity(magnitude=po_n / 1000.0, unit="kN")


def rc_beta1(*, concrete_strength: Quantity) -> float:
    """The ACI 318 stress-block depth factor β₁ from the concrete strength.

    The ratio of the equivalent rectangular stress-block depth a to the neutral-axis
    depth c (ACI 318-19 Table 22.2.2.4.3): β₁ = 0.85 for f'c ≤ 28 MPa, decreasing by
    0.05 for each 7 MPa above 28, and floored at 0.65 for f'c ≥ 55 MPa — stronger,
    more brittle concrete keeps a shallower compression zone. ``concrete_strength`` is
    f'c. Returns the dimensionless β₁ in [0.65, 0.85].
    """
    _require(concrete_strength, "[pressure]", "concrete_strength")
    fc = concrete_strength.to("MPa").magnitude
    if fc <= 0:
        raise ValueError(f"concrete_strength must be positive; got {concrete_strength}")
    if fc <= 28.0:
        return 0.85
    if fc >= 55.0:
        return 0.65
    return 0.85 - 0.05 * (fc - 28.0) / 7.0


def rc_net_tensile_strain(
    *,
    stress_block_depth: Quantity,
    effective_depth: Quantity,
    concrete_strength: Quantity,
) -> float:
    """The ACI 318 net tensile strain ε_t at the extreme steel — the ductility measure.

    From the linear strain diagram (concrete at 0.003 on the compression face), the
    tension steel strain is ε_t = 0.003·(d − c)/c, where c = a/β₁ is the neutral-axis
    depth, ``stress_block_depth`` a is :func:`rc_stress_block_depth`, and
    ``effective_depth`` d the depth to the steel. ε_t ≥ 0.005 is *tension-controlled*
    (ductile, φ = 0.90); ε_t ≤ f_y/E_s is compression-controlled (brittle, φ = 0.65);
    between is the transition. ``concrete_strength`` sets β₁. Returns the dimensionless
    ε_t.
    """
    _require(stress_block_depth, "[length]", "stress_block_depth")
    _require(effective_depth, "[length]", "effective_depth")
    a = stress_block_depth.to("mm").magnitude
    d = effective_depth.to("mm").magnitude
    if a <= 0 or d <= 0:
        raise ValueError("stress_block_depth and effective_depth must be positive")
    c = a / rc_beta1(concrete_strength=concrete_strength)
    if c >= d:
        raise ValueError("the neutral axis reaches the steel; check the inputs")
    return _ACI_CONCRETE_ULTIMATE_STRAIN * (d - c) / c


def rc_development_length(
    *,
    bar_diameter: Quantity,
    steel_yield: Quantity,
    concrete_strength: Quantity,
    location_factor: float = 1.0,
    coating_factor: float = 1.0,
    lightweight_factor: float = 1.0,
    size_spacing_constant: float = 2.1,
) -> Quantity:
    """The ACI 318 tension development length l_d = (f_y·ψ_t·ψ_e·d_b)/(c·λ·√f'c).

    The straight-bar embedment a deformed bar needs to develop its yield in tension
    (ACI 318-19 §25.4.2, the simplified form). ``bar_diameter`` d_b, ``steel_yield``
    f_y, and ``concrete_strength`` f'c set the base length; ``location_factor`` ψ_t
    (1.3 for "top" bars with ≥ 300 mm of concrete cast below, else 1.0),
    ``coating_factor`` ψ_e (up to 1.5 for epoxy-coated bars), and
    ``lightweight_factor`` λ (0.75 lightweight) modify it. ``size_spacing_constant`` is
    the denominator constant from the simplified table — 2.1 for No. 19 and smaller
    with adequate cover and spacing, 1.7 for No. 22 and larger (or halve for confined
    cases) — exposed so the caller picks the row. Returns l_d in mm.
    """
    _require(bar_diameter, "[length]", "bar_diameter")
    _require(steel_yield, "[pressure]", "steel_yield")
    _require(concrete_strength, "[pressure]", "concrete_strength")
    db = bar_diameter.to("mm").magnitude
    fy = steel_yield.to("MPa").magnitude
    fc = concrete_strength.to("MPa").magnitude
    if db <= 0 or fy <= 0 or fc <= 0:
        raise ValueError("bar_diameter, steel_yield, and concrete_strength must be positive")
    for factor, label in (
        (location_factor, "location_factor"),
        (coating_factor, "coating_factor"),
        (lightweight_factor, "lightweight_factor"),
        (size_spacing_constant, "size_spacing_constant"),
    ):
        if factor <= 0:
            raise ValueError(f"{label} must be positive; got {factor}")
    ld = (fy * location_factor * coating_factor * db) / (
        size_spacing_constant * lightweight_factor * sqrt(fc)
    )
    return Quantity(magnitude=ld, unit="mm")
