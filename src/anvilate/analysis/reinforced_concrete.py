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

from ..units import Quantity, require_finite

__all__ = [
    "rc_stress_block_depth",
    "rc_beam_nominal_moment",
    "rc_doubly_reinforced_moment",
    "rc_t_beam_moment",
    "rc_tension_steel_for_moment",
    "rc_concrete_shear_strength",
    "rc_shear_reinforcement_strength",
    "rc_stirrup_spacing_for_shear",
    "rc_column_axial_strength",
    "rc_column_balanced_point",
    "rc_beta1",
    "rc_net_tensile_strain",
    "rc_strength_reduction_factor",
    "rc_development_length",
    "rc_max_bar_spacing_crack_control",
    "rc_minimum_flexural_steel",
    "rc_maximum_tension_controlled_steel",
    "rc_two_way_shear_strength",
    "rc_cracking_moment",
    "rc_effective_moment_of_inertia",
]

# ACI 318-19 §24.2.3.5 uses the reduced effective cracking moment (2/3)·M_cr.
_ACI_EFFECTIVE_CRACKING_FRACTION = 2.0 / 3.0
_ACI_MODULUS_OF_RUPTURE_FACTOR = 0.62  # f_r = 0.62·√f'c (MPa)

# The tension-controlled neutral-axis ratio c/d at ε_t = 0.005 (with ε_cu = 0.003):
# c/d = 0.003 / (0.003 + 0.005) = 0.375.
_TENSION_CONTROLLED_C_OVER_D = 0.375

# ACI 318 ultimate concrete compressive strain (the strain-diagram anchor).
_ACI_CONCRETE_ULTIMATE_STRAIN = 0.003
# Elastic modulus of reinforcing steel, ACI 318 §20.2.2.2 (E_s = 200 GPa).
_ACI_STEEL_MODULUS_MPA = 200000.0

_ACI_STRESS_BLOCK_FACTOR = 0.85  # the 0.85·f'c Whitney stress-block intensity


def _require(value: Quantity, expected: str, name: str) -> None:
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )
    # Dimension is the easy half. A NaN magnitude passes every `<= 0` guard downstream
    # (all comparisons with NaN are False) and is then DROPPED by the max()/min() that
    # picks the governing case, so the answer comes back smaller, complete-looking, and
    # green. See units.require_finite.
    require_finite(value, name=name)


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


def _reject_beyond_the_steel(
    *, block_depth: float, effective_depth: float, beta1: float, label: str
) -> None:
    """Refuse a section whose neutral axis has reached or passed the tension steel.

    ``a = beta1*c``, so ``a >= beta1*d`` is ``c >= d``: the neutral axis has arrived at the
    bars, the steel is no longer in tension, and ``M_n = A_s*f_y*(d - a/2)`` — which
    *assumes* the steel has yielded in tension — has stopped meaning anything.

    The guard used to sit at ``a >= 2*d``, which is not a physical or code boundary at all:
    it is exactly where the lever arm ``(d - a/2)`` changes sign, so it caught the
    arithmetic blow-up and waved through the whole band between. A 200x300 mm section with
    4,047 mm2 of steel returns a confident 170.0 kN*m at ``c/d = 1.57`` — the neutral axis
    57% below the bars — while :func:`rc_net_tensile_strain` refuses the identical section
    for exactly this reason. Same module, same physics, two different answers.
    """
    if block_depth >= beta1 * effective_depth:
        raise ValueError(
            f"{label}: the stress block reaches the tension steel (a = {block_depth:.4g} mm "
            f"against beta1*d = {beta1 * effective_depth:.4g} mm, so c >= d), and the "
            f"steel is no longer in tension — the nominal-moment expression assumes it has "
            f"yielded in tension. This is an over-reinforced or mis-entered section; "
            f"screen it as such rather than reading a moment off it"
        )


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
    _reject_beyond_the_steel(
        block_depth=a,
        effective_depth=d,
        beta1=rc_beta1(concrete_strength=concrete_strength),
        label="rc_beam_nominal_moment",
    )
    as_mm2 = steel_area.to("mm**2").magnitude
    fy = steel_yield.to("MPa").magnitude
    moment_n_mm = as_mm2 * fy * (d - a / 2.0)
    return Quantity(magnitude=moment_n_mm / 1.0e6, unit="kN*m")


def rc_t_beam_moment(
    *,
    tension_steel_area: Quantity,
    steel_yield: Quantity,
    concrete_strength: Quantity,
    flange_width: Quantity,
    web_width: Quantity,
    flange_thickness: Quantity,
    effective_depth: Quantity,
) -> Quantity:
    """The ACI 318 nominal moment of a flanged (T-) reinforced-concrete beam.

    A beam cast monolithically with its slab acts as a T: the slab is the wide compression
    flange. If the Whitney stress block stays within the flange (a ≤ h_f) the beam is simply
    a wide rectangular beam of the ``flange_width``. If the compression spills into the web
    (a > h_f) the strength splits into two couples — the flange overhangs
    (A_sf·f_y = 0.85·f'c·(b_f − b_w)·h_f acting at d − h_f/2) plus the web
    (the remaining steel over the web width b_w, at d − a_w/2). ``tension_steel_area`` A_s,
    ``steel_yield`` f_y, ``concrete_strength`` f'c, ``flange_width`` b_f, ``web_width`` b_w,
    ``flange_thickness`` h_f, and ``effective_depth`` d. The wide flange makes a T-beam far
    stronger and stiffer in positive bending than its web alone. Returns M_n in kN·m.
    """
    _require(tension_steel_area, "[area]", "tension_steel_area")
    _require(steel_yield, "[pressure]", "steel_yield")
    _require(concrete_strength, "[pressure]", "concrete_strength")
    _require(flange_width, "[length]", "flange_width")
    _require(web_width, "[length]", "web_width")
    _require(flange_thickness, "[length]", "flange_thickness")
    _require(effective_depth, "[length]", "effective_depth")
    a_s = tension_steel_area.to("mm**2").magnitude
    fy = steel_yield.to("MPa").magnitude
    fc = concrete_strength.to("MPa").magnitude
    bf = flange_width.to("mm").magnitude
    bw = web_width.to("mm").magnitude
    hf = flange_thickness.to("mm").magnitude
    d = effective_depth.to("mm").magnitude
    if min(a_s, fy, fc, bf, bw, hf, d) <= 0:
        raise ValueError("all areas, strengths, and dimensions must be positive")
    if bw > bf:
        raise ValueError("web_width cannot exceed flange_width")
    a_rectangular = a_s * fy / (_ACI_STRESS_BLOCK_FACTOR * fc * bf)
    if a_rectangular <= hf:
        # The stress block stays in the flange: a wide rectangular beam.
        moment_n_mm = a_s * fy * (d - a_rectangular / 2.0)
        return Quantity(magnitude=moment_n_mm / 1.0e6, unit="kN*m")
    # Compression spills into the web: flange-overhang couple + web couple.
    a_sf = _ACI_STRESS_BLOCK_FACTOR * fc * (bf - bw) * hf / fy
    moment_flange = a_sf * fy * (d - hf / 2.0)
    a_sw = a_s - a_sf
    if a_sw <= 0:
        raise ValueError("the flange overhang alone balances the steel; check the geometry")
    a_w = a_sw * fy / (_ACI_STRESS_BLOCK_FACTOR * fc * bw)
    _reject_beyond_the_steel(
        block_depth=a_w,
        effective_depth=d,
        beta1=rc_beta1(concrete_strength=concrete_strength),
        label="rc_t_beam_moment",
    )
    moment_web = a_sw * fy * (d - a_w / 2.0)
    return Quantity(magnitude=(moment_flange + moment_web) / 1.0e6, unit="kN*m")


def rc_doubly_reinforced_moment(
    *,
    tension_steel_area: Quantity,
    compression_steel_area: Quantity,
    steel_yield: Quantity,
    concrete_strength: Quantity,
    beam_width: Quantity,
    effective_depth: Quantity,
    compression_steel_depth: Quantity,
    steel_modulus: Quantity | None = None,
) -> Quantity:
    """The ACI 318 nominal moment of a doubly-reinforced beam (with compression steel).

    When a section is too shallow to carry its moment on tension steel alone, compression
    steel A_s' is added near the top, and the nominal moment is the concrete-compression
    couple plus the compression-steel couple. This resolves the subtlety that the
    compression steel may or may not have yielded: it first assumes it yields
    (a = (A_s − A_s')·f_y/(0.85·f'c·b)) and checks the strain ε_s' = 0.003·(c − d')/c; if
    the steel is still elastic it solves the equilibrium quadratic for the neutral axis with
    f_s' = ε_s'·E_s instead. ``tension_steel_area`` A_s, ``compression_steel_area`` A_s',
    ``steel_yield`` f_y, ``concrete_strength`` f'c, ``beam_width`` b, ``effective_depth`` d,
    ``compression_steel_depth`` d' (from the compression face), and ``steel_modulus`` E_s
    (default 200 GPa). Returns M_n in kN·m — larger than the singly-reinforced strength for
    the same tension steel, and with a more ductile neutral axis.
    """
    _require(tension_steel_area, "[area]", "tension_steel_area")
    _require(compression_steel_area, "[area]", "compression_steel_area")
    _require(steel_yield, "[pressure]", "steel_yield")
    _require(concrete_strength, "[pressure]", "concrete_strength")
    _require(beam_width, "[length]", "beam_width")
    _require(effective_depth, "[length]", "effective_depth")
    _require(compression_steel_depth, "[length]", "compression_steel_depth")
    if steel_modulus is None:
        steel_modulus = Quantity(magnitude=_ACI_STEEL_MODULUS_MPA, unit="MPa")
    _require(steel_modulus, "[pressure]", "steel_modulus")
    a_s = tension_steel_area.to("mm**2").magnitude
    a_sp = compression_steel_area.to("mm**2").magnitude
    fy = steel_yield.to("MPa").magnitude
    fc = concrete_strength.to("MPa").magnitude
    b = beam_width.to("mm").magnitude
    d = effective_depth.to("mm").magnitude
    dp = compression_steel_depth.to("mm").magnitude
    es = steel_modulus.to("MPa").magnitude
    if min(a_s, a_sp, fy, fc, b, d, dp, es) <= 0:
        raise ValueError("all areas, strengths, and dimensions must be positive")
    if not dp < d:
        raise ValueError("compression_steel_depth must be less than effective_depth")
    beta1 = rc_beta1(concrete_strength=concrete_strength)
    ecu = _ACI_CONCRETE_ULTIMATE_STRAIN
    strain_yield = fy / es
    # First assume the compression steel yields.
    a_yield = (a_s - a_sp) * fy / (_ACI_STRESS_BLOCK_FACTOR * fc * b)
    c_yield = a_yield / beta1
    if a_yield > 0 and ecu * (c_yield - dp) / c_yield >= strain_yield:
        a = a_yield
        force_comp = a_sp * fy
    else:
        # Compression steel is elastic: solve the equilibrium quadratic for c.
        # 0.85*f'c*beta1*b*c^2 + (A_s'*ecu*Es - A_s*f_y)*c - A_s'*ecu*Es*d' = 0.
        qa = _ACI_STRESS_BLOCK_FACTOR * fc * beta1 * b
        qb = a_sp * ecu * es - a_s * fy
        qc = -a_sp * ecu * es * dp
        c = (-qb + sqrt(qb * qb - 4.0 * qa * qc)) / (2.0 * qa)
        a = beta1 * c
        stress_comp = min(ecu * (c - dp) / c * es, fy)
        force_comp = a_sp * stress_comp
    _reject_beyond_the_steel(
        block_depth=a,
        effective_depth=d,
        beta1=beta1,
        label="rc_doubly_reinforced_moment",
    )
    concrete_force = _ACI_STRESS_BLOCK_FACTOR * fc * a * b
    moment_n_mm = concrete_force * (d - a / 2.0) + force_comp * (d - dp)
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
    develop even at balanced conditions (a deeper or wider beam is needed) — checked against the
    balanced neutral axis c_b, not merely against where the quadratic runs out of discriminant,
    which sits about a third higher and would quietly hand back a brittle compression-controlled
    section. Returns the required steel area in mm².
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
    # The discriminant only runs out at the parabola's vertex (a = d), which is about a third
    # above the balanced point -- so between the two the quadratic happily returned a
    # COMPRESSION-CONTROLLED answer: more steel than the concrete can balance ductilely, failing
    # by concrete crushing with no warning and at phi = 0.65 rather than 0.90. The docstring
    # promised a raise at balanced conditions, so check there.
    beta1 = rc_beta1(concrete_strength=concrete_strength)
    a_depth = tension_force / (_ACI_STRESS_BLOCK_FACTOR * fc * b)
    neutral_axis = a_depth / beta1
    balanced_c = (
        _ACI_CONCRETE_ULTIMATE_STRAIN
        * d
        / (_ACI_CONCRETE_ULTIMATE_STRAIN + fy / _ACI_STEEL_MODULUS_MPA)
    )
    if neutral_axis > balanced_c:
        raise ValueError(
            f"the required moment needs more steel than the section can balance ductilely: the "
            f"neutral axis lands at c = {neutral_axis:.1f} mm against a balanced c_b = "
            f"{balanced_c:.1f} mm, so the beam would fail by concrete crushing before the steel "
            f"yields. Deepen or widen it, or add compression steel."
        )
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


def rc_shear_reinforcement_strength(
    *,
    stirrup_area: Quantity,
    stirrup_yield: Quantity,
    effective_depth: Quantity,
    stirrup_spacing: Quantity,
) -> Quantity:
    """The ACI 318 shear strength V_s = A_v·f_yt·d/s carried by vertical stirrups.

    Beyond the concrete's own shear (:func:`rc_concrete_shear_strength`), stirrups crossing
    the diagonal crack carry the rest: each set at spacing s develops V_s = A_v·f_yt·d/s,
    where A_v is the total stirrup area cutting the crack (both legs of a closed tie), and
    the total factored shear must reach V_u/φ ≤ V_c + V_s (ACI 318-19 §22.5.1.1).
    ``stirrup_area`` A_v, ``stirrup_yield`` f_yt, ``effective_depth`` d, and
    ``stirrup_spacing`` s. Closer spacing or a larger bar raises V_s, but §22.5.1.2 caps it
    at 0.66·√f'c·b_w·d — past that the concrete diagonal crushes and a bigger section is
    needed rather than more stirrups. Returns V_s in kN.
    """
    _require(stirrup_area, "[area]", "stirrup_area")
    _require(stirrup_yield, "[pressure]", "stirrup_yield")
    _require(effective_depth, "[length]", "effective_depth")
    _require(stirrup_spacing, "[length]", "stirrup_spacing")
    av = stirrup_area.to("mm**2").magnitude
    fyt = stirrup_yield.to("MPa").magnitude
    d = effective_depth.to("mm").magnitude
    s = stirrup_spacing.to("mm").magnitude
    if av <= 0 or fyt <= 0 or d <= 0 or s <= 0:
        raise ValueError("all inputs must be positive")
    vs_n = av * fyt * d / s
    return Quantity(magnitude=vs_n / 1000.0, unit="kN")


# ACI 318 §9.7.6.2.2: stirrup spacing may not exceed d/2 nor 600 mm.
_ACI_MAX_STIRRUP_SPACING_MM = 600.0


def rc_stirrup_spacing_for_shear(
    *,
    required_shear_strength: Quantity,
    stirrup_area: Quantity,
    stirrup_yield: Quantity,
    effective_depth: Quantity,
) -> Quantity:
    """The stirrup spacing s = A_v·f_yt·d/V_s a required shear-reinforcement strength needs.

    The design inverse of :func:`rc_shear_reinforcement_strength`: once the concrete's V_c
    falls short of the factored shear, the stirrups must supply the balance
    V_s = V_u/φ − V_c, and rearranging V_s = A_v·f_yt·d/s gives the spacing
    s = A_v·f_yt·d/V_s for a chosen bar. ``required_shear_strength`` V_s is the shear the
    stirrups must carry, ``stirrup_area`` A_v the total leg area, ``stirrup_yield`` f_yt, and
    ``effective_depth`` d. The result is the maximum spacing that satisfies **both** strength
    and ACI's detailing cap of d/2 ≤ 600 mm, which is applied here rather than delegated —
    at a light demand the strength spacing alone runs several times past it, and a spacing
    that wide puts no stirrup across a diagonal crack. The further *halving* where V_s
    exceeds 0.33·√f'c·b_w·d needs f'c and b_w, which this function does not take, so that
    one remains the caller's. A higher demand or a smaller bar forces tighter stirrups.
    Returns the required spacing in mm.
    """
    _require(required_shear_strength, "[force]", "required_shear_strength")
    _require(stirrup_area, "[area]", "stirrup_area")
    _require(stirrup_yield, "[pressure]", "stirrup_yield")
    _require(effective_depth, "[length]", "effective_depth")
    vs = required_shear_strength.to("N").magnitude
    av = stirrup_area.to("mm**2").magnitude
    fyt = stirrup_yield.to("MPa").magnitude
    d = effective_depth.to("mm").magnitude
    if vs <= 0 or av <= 0 or fyt <= 0 or d <= 0:
        raise ValueError("all inputs must be positive")
    # The strength spacing alone is unbounded as V_s falls, and at a wide spacing no stirrup
    # crosses a 45° diagonal crack at all — which makes the V_s the companion function
    # reports fictitious. ACI's d/2 ≤ 600 mm cap was documented here as the caller's job and
    # no caller applied it, so a light demand returned 1491 mm where ACI permits 250 mm.
    # Applying it is the code requirement and it is conservative; the *halving* clause
    # genuinely needs f'c and b_w, which this function does not take, so it stays the
    # caller's and is named in the docstring.
    strength_spacing = av * fyt * d / vs
    capped = min(strength_spacing, d / 2.0, _ACI_MAX_STIRRUP_SPACING_MM)
    return Quantity(magnitude=capped, unit="mm")


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


def rc_column_balanced_point(
    *,
    width: Quantity,
    total_depth: Quantity,
    tension_steel_depth: Quantity,
    compression_steel_depth: Quantity,
    tension_steel_area: Quantity,
    compression_steel_area: Quantity,
    concrete_strength: Quantity,
    steel_yield: Quantity,
    steel_modulus: Quantity | None = None,
) -> tuple[Quantity, Quantity]:
    """The balanced-failure point (P_b, M_b) of a rectangular reinforced-concrete column.

    An RC column is governed by its P-M interaction diagram, and the balanced point is its
    hinge — the axial-load/moment pair at which the concrete crushes (ε = 0.003) exactly as
    the tension steel yields. Below P_b the column fails in tension (ductile); above it, in
    compression (brittle). The balanced neutral axis is c_b = 0.003·d/(0.003 + f_y/E_s); the
    stress block a_b = β₁·c_b carries C_c = 0.85·f'c·a_b·b, the compression steel adds
    A_s'·f_s' (yielded or not per its strain), and the tension steel pulls A_s·f_y, giving
    P_b = C_c + C_s − T and M_b taken about the section mid-depth. ``width`` b,
    ``total_depth`` h, ``tension_steel_depth`` d and ``compression_steel_depth`` d' (from the
    compression face), the two steel areas, ``concrete_strength`` f'c, ``steel_yield`` f_y,
    and ``steel_modulus`` E_s (default 200 GPa). Displaced concrete under the compression
    steel is neglected (a small, standard screening simplification). Returns ``(P_b, M_b)``
    with P_b in kN (compression positive) and M_b in kN·m.
    """
    _require(width, "[length]", "width")
    _require(total_depth, "[length]", "total_depth")
    _require(tension_steel_depth, "[length]", "tension_steel_depth")
    _require(compression_steel_depth, "[length]", "compression_steel_depth")
    _require(tension_steel_area, "[area]", "tension_steel_area")
    _require(compression_steel_area, "[area]", "compression_steel_area")
    _require(concrete_strength, "[pressure]", "concrete_strength")
    _require(steel_yield, "[pressure]", "steel_yield")
    if steel_modulus is None:
        steel_modulus = Quantity(magnitude=_ACI_STEEL_MODULUS_MPA, unit="MPa")
    _require(steel_modulus, "[pressure]", "steel_modulus")
    b = width.to("mm").magnitude
    h = total_depth.to("mm").magnitude
    d = tension_steel_depth.to("mm").magnitude
    dp = compression_steel_depth.to("mm").magnitude
    a_s = tension_steel_area.to("mm**2").magnitude
    a_sp = compression_steel_area.to("mm**2").magnitude
    fc = concrete_strength.to("MPa").magnitude
    fy = steel_yield.to("MPa").magnitude
    es = steel_modulus.to("MPa").magnitude
    if min(b, h, d, dp, a_s, a_sp, fc, fy, es) <= 0:
        raise ValueError("all dimensions, areas, and material properties must be positive")
    if not dp < d < h:
        raise ValueError("require compression_steel_depth < tension_steel_depth < total_depth")
    strain_yield = fy / es
    c_b = _ACI_CONCRETE_ULTIMATE_STRAIN / (_ACI_CONCRETE_ULTIMATE_STRAIN + strain_yield) * d
    beta1 = rc_beta1(concrete_strength=concrete_strength)
    a_b = beta1 * c_b
    c_c = _ACI_STRESS_BLOCK_FACTOR * fc * a_b * b  # N
    strain_comp = _ACI_CONCRETE_ULTIMATE_STRAIN * (c_b - dp) / c_b
    stress_comp = min(abs(strain_comp) * es, fy)
    if strain_comp < 0:  # compression steel actually in tension (shallow c_b)
        stress_comp = -stress_comp
    c_s = a_sp * stress_comp  # N
    tension = a_s * fy  # N
    p_b = c_c + c_s - tension  # N
    m_b = c_c * (h / 2.0 - a_b / 2.0) + c_s * (h / 2.0 - dp) + tension * (d - h / 2.0)  # N*mm
    return (
        Quantity(magnitude=p_b / 1000.0, unit="kN"),
        Quantity(magnitude=m_b / 1.0e6, unit="kN*m"),
    )


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


def rc_strength_reduction_factor(
    *,
    net_tensile_strain: float,
    steel_yield: Quantity,
    steel_modulus: Quantity | None = None,
    compression_controlled_factor: float = 0.65,
) -> float:
    """The ACI 318 strength-reduction factor φ from the net tensile strain.

    ACI rewards ductility with a higher φ: a section that fails with the steel well past
    yield (tension-controlled) is trusted at φ = 0.90, while a brittle compression-controlled
    section is held to φ = 0.65 (tied) or 0.75 (spiral), with a linear transition between
    (ACI 318-19 §21.2.2). The break points are the steel yield strain ε_ty = f_y/E_s and
    ε_ty + 0.003: φ = 0.90 at or above the upper, ``compression_controlled_factor`` at or
    below the lower, and φ = φ_cc + (0.90 − φ_cc)·(ε_t − ε_ty)/0.003 in between.
    ``net_tensile_strain`` ε_t (from :func:`rc_net_tensile_strain`), ``steel_yield`` f_y,
    ``steel_modulus`` E_s (default 200 GPa), and ``compression_controlled_factor`` (0.65 tied,
    0.75 spiral). Multiply φ by the nominal strength for the design strength. Returns the
    dimensionless φ in [φ_cc, 0.90].
    """
    _require(steel_yield, "[pressure]", "steel_yield")
    if steel_modulus is None:
        steel_modulus = Quantity(magnitude=_ACI_STEEL_MODULUS_MPA, unit="MPa")
    _require(steel_modulus, "[pressure]", "steel_modulus")
    fy = steel_yield.to("MPa").magnitude
    es = steel_modulus.to("MPa").magnitude
    if fy <= 0 or es <= 0:
        raise ValueError("steel_yield and steel_modulus must be positive")
    if net_tensile_strain < 0:
        raise ValueError(f"net_tensile_strain must be non-negative; got {net_tensile_strain}")
    if not 0 < compression_controlled_factor <= 0.90:
        raise ValueError("compression_controlled_factor must be in (0, 0.90]")
    strain_yield = fy / es
    tension_controlled = strain_yield + 0.003
    if net_tensile_strain <= strain_yield:
        return compression_controlled_factor
    if net_tensile_strain >= tension_controlled:
        return 0.90
    return (
        compression_controlled_factor
        + (0.90 - compression_controlled_factor) * (net_tensile_strain - strain_yield) / 0.003
    )


# ACI 318 §25.4.1.4 caps sqrt(f'c) at 100 psi for every development and splice length.
# 100 psi = 0.6895 MPa/psi -> 8.3 MPa to the two figures the code states it in.
_SQRT_FC_CAP_MPA = 8.3


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
    # ACI 318 §25.4.1.4: the value of sqrt(f'c) used in a development-length calculation
    # shall not exceed 8.3 MPa (100 psi). The clause has no exception, and it binds on
    # ordinary high-strength column concrete: without it, f'c = 100 MPa detailed the bar
    # 17% shorter than the code requires and f'c = 140 MPa 30% shorter, because l_d goes
    # as 1/sqrt(f'c) and nothing stopped the root running away. The sibling `rc_beta1`
    # already enforces its own f'c-keyed limit; this one delegated nothing and checked
    # nothing.
    root_fc = min(sqrt(fc), _SQRT_FC_CAP_MPA)
    ld = (fy * location_factor * coating_factor * db) / (
        size_spacing_constant * lightweight_factor * root_fc
    )
    return Quantity(magnitude=ld, unit="mm")


def rc_max_bar_spacing_crack_control(
    *,
    steel_service_stress: Quantity,
    clear_cover: Quantity,
) -> Quantity:
    """The ACI 318 maximum bar spacing for flexural crack control,
    s = min(380·(280/f_s) − 2.5·c_c, 300·(280/f_s)).

    Distributing the flexural reinforcement limits crack widths at service load
    (ACI 318-19 §24.3.2): the centre-to-centre spacing of the tension bars nearest the
    face must not exceed s = 380·(280/f_s) − 2.5·c_c, capped by 300·(280/f_s), where
    ``steel_service_stress`` f_s is the stress in the bars at service load (permitted
    as ⅔·f_y) and ``clear_cover`` c_c the least clear cover to those bars. Higher steel
    stress or more cover forces the bars closer together. Returns the maximum spacing
    in mm.
    """
    _require(steel_service_stress, "[pressure]", "steel_service_stress")
    _require(clear_cover, "[length]", "clear_cover")
    fs = steel_service_stress.to("MPa").magnitude
    cc = clear_cover.to("mm").magnitude
    if fs <= 0:
        raise ValueError(f"steel_service_stress must be positive; got {steel_service_stress}")
    if cc < 0:
        raise ValueError(f"clear_cover must be non-negative; got {clear_cover}")
    spacing = min(380.0 * (280.0 / fs) - 2.5 * cc, 300.0 * (280.0 / fs))
    if spacing <= 0:
        raise ValueError("the cover and steel stress leave no permissible spacing; check inputs")
    return Quantity(magnitude=spacing, unit="mm")


def rc_minimum_flexural_steel(
    *,
    concrete_strength: Quantity,
    steel_yield: Quantity,
    beam_width: Quantity,
    effective_depth: Quantity,
) -> Quantity:
    """The ACI 318 minimum flexural steel A_s,min = max(0.25·√f'c/f_y, 1.4/f_y)·b_w·d.

    A beam needs enough tension steel that it does not fail more abruptly cracked than
    uncracked (ACI 318-19 §9.6.1.2): A_s,min is the larger of 0.25·√f'c/f_y and 1.4/f_y
    times b_w·d. ``concrete_strength`` f'c, ``steel_yield`` f_y, ``beam_width`` b_w, and
    ``effective_depth`` d describe the section. Returns A_s,min in mm².
    """
    _require(concrete_strength, "[pressure]", "concrete_strength")
    _require(steel_yield, "[pressure]", "steel_yield")
    _require(beam_width, "[length]", "beam_width")
    _require(effective_depth, "[length]", "effective_depth")
    fc = concrete_strength.to("MPa").magnitude
    fy = steel_yield.to("MPa").magnitude
    b = beam_width.to("mm").magnitude
    d = effective_depth.to("mm").magnitude
    if fc <= 0 or fy <= 0 or b <= 0 or d <= 0:
        raise ValueError("all inputs must be positive")
    ratio = max(0.25 * sqrt(fc) / fy, 1.4 / fy)
    return Quantity(magnitude=ratio * b * d, unit="mm**2")


def rc_maximum_tension_controlled_steel(
    *,
    concrete_strength: Quantity,
    steel_yield: Quantity,
    beam_width: Quantity,
    effective_depth: Quantity,
) -> Quantity:
    """The tension steel that keeps a beam tension-controlled (ductile), A_s,max.

    The most reinforcement a singly-reinforced section can carry while its extreme
    steel strain stays at the tension-controlled limit ε_t = 0.005 (so φ = 0.90). At
    that limit the neutral axis sits at c = 0.375·d, the stress block at a = β₁·c, and
    force balance gives A_s,max = 0.85·β₁·(f'c/f_y)·0.375·b·d. ``concrete_strength`` f'c
    sets β₁; the other arguments are as in :func:`rc_minimum_flexural_steel`. Steel
    above this pushes the section into the transition/compression-controlled range
    (falling φ, less warning) and calls for compression steel. Returns A_s,max in mm².
    """
    _require(concrete_strength, "[pressure]", "concrete_strength")
    _require(steel_yield, "[pressure]", "steel_yield")
    _require(beam_width, "[length]", "beam_width")
    _require(effective_depth, "[length]", "effective_depth")
    fc = concrete_strength.to("MPa").magnitude
    fy = steel_yield.to("MPa").magnitude
    b = beam_width.to("mm").magnitude
    d = effective_depth.to("mm").magnitude
    if fc <= 0 or fy <= 0 or b <= 0 or d <= 0:
        raise ValueError("all inputs must be positive")
    beta1 = rc_beta1(concrete_strength=concrete_strength)
    ratio = _ACI_STRESS_BLOCK_FACTOR * beta1 * (fc / fy) * _TENSION_CONTROLLED_C_OVER_D
    return Quantity(magnitude=ratio * b * d, unit="mm**2")


def rc_two_way_shear_strength(
    *,
    concrete_strength: Quantity,
    critical_perimeter: Quantity,
    effective_depth: Quantity,
    column_aspect_ratio: float = 1.0,
    column_position_factor: float = 40.0,
    lightweight_factor: float = 1.0,
) -> Quantity:
    """The ACI 318 two-way (punching) shear strength V_c at a slab-column connection.

    The governing check for a flat plate: the slab tends to punch through around the
    column on a critical perimeter b_o at d/2 from the column face. ACI 318-19
    §22.6.5.2 takes the least of three limits,

        V_c = min[ 0.33·λ·√f'c,
                   0.17·(1 + 2/β)·λ·√f'c,
                   0.083·(2 + α_s·d/b_o)·λ·√f'c ] · b_o · d,

    where ``critical_perimeter`` b_o is the perimeter of the critical section,
    ``effective_depth`` d the slab depth to steel, ``column_aspect_ratio`` β the ratio
    of the column's long to short side (a very oblong column concentrates the shear),
    ``column_position_factor`` α_s (40 interior, 30 edge, 20 corner), and
    ``lightweight_factor`` λ. Returns V_c in kN.
    """
    _require(concrete_strength, "[pressure]", "concrete_strength")
    _require(critical_perimeter, "[length]", "critical_perimeter")
    _require(effective_depth, "[length]", "effective_depth")
    fc = concrete_strength.to("MPa").magnitude
    bo = critical_perimeter.to("mm").magnitude
    d = effective_depth.to("mm").magnitude
    if fc <= 0 or bo <= 0 or d <= 0:
        raise ValueError(
            "concrete_strength, critical_perimeter, and effective_depth must be positive"
        )
    if column_aspect_ratio < 1.0:
        raise ValueError(f"column_aspect_ratio must be at least 1; got {column_aspect_ratio}")
    if column_position_factor <= 0 or lightweight_factor <= 0:
        raise ValueError("column_position_factor and lightweight_factor must be positive")
    lam_root = lightweight_factor * sqrt(fc)
    stress = min(
        0.33 * lam_root,
        0.17 * (1.0 + 2.0 / column_aspect_ratio) * lam_root,
        0.083 * (2.0 + column_position_factor * d / bo) * lam_root,
    )
    return Quantity(magnitude=stress * bo * d / 1000.0, unit="kN")


def rc_cracking_moment(
    *,
    concrete_strength: Quantity,
    gross_inertia: Quantity,
    extreme_tension_distance: Quantity,
    lightweight_factor: float = 1.0,
) -> Quantity:
    """The ACI 318 cracking moment M_cr = f_r·I_g/y_t of a concrete section.

    The moment at which the concrete's tension face first cracks — below it the beam
    acts uncracked, above it a crack propagates and the stiffness drops. The modulus
    of rupture is f_r = 0.62·λ·√f'c (ACI 318-19 §19.2.3.1); ``gross_inertia`` I_g is the
    uncracked (gross) second moment of area and ``extreme_tension_distance`` y_t the
    distance from the centroid to the extreme tension fibre. ``concrete_strength`` f'c
    and ``lightweight_factor`` λ are the caller's. Returns M_cr in kN·m.
    """
    _require(concrete_strength, "[pressure]", "concrete_strength")
    _require(gross_inertia, "[length]**4", "gross_inertia")
    _require(extreme_tension_distance, "[length]", "extreme_tension_distance")
    fc = concrete_strength.to("MPa").magnitude
    ig = gross_inertia.to("mm**4").magnitude
    yt = extreme_tension_distance.to("mm").magnitude
    if fc <= 0 or ig <= 0 or yt <= 0:
        raise ValueError(
            "concrete_strength, gross_inertia, and extreme_tension_distance must be positive"
        )
    if lightweight_factor <= 0:
        raise ValueError(f"lightweight_factor must be positive; got {lightweight_factor}")
    fr = _ACI_MODULUS_OF_RUPTURE_FACTOR * lightweight_factor * sqrt(fc)
    return Quantity(magnitude=fr * ig / yt / 1.0e6, unit="kN*m")


def rc_effective_moment_of_inertia(
    *,
    cracked_inertia: Quantity,
    gross_inertia: Quantity,
    cracking_moment: Quantity,
    applied_moment: Quantity,
) -> Quantity:
    """The ACI 318-19 effective moment of inertia I_e for deflection (Bischoff).

    A cracked beam is stiffer than its fully-cracked section (uncracked lengths
    between cracks help), so deflection uses an I between I_cr and I_g that tightens
    toward I_cr as the load grows (ACI 318-19 §24.2.3.5):

        I_e = I_g                                                   for M_a ≤ ⅔·M_cr,
        I_e = I_cr / [1 − (⅔·M_cr/M_a)²·(1 − I_cr/I_g)]             for M_a > ⅔·M_cr,

    where ``cracked_inertia`` I_cr, ``gross_inertia`` I_g, ``cracking_moment`` M_cr
    (from :func:`rc_cracking_moment`), and ``applied_moment`` M_a is the service moment.
    Returns I_e in mm⁴.
    """
    _require(cracked_inertia, "[length]**4", "cracked_inertia")
    _require(gross_inertia, "[length]**4", "gross_inertia")
    _require(cracking_moment, "[force] * [length]", "cracking_moment")
    _require(applied_moment, "[force] * [length]", "applied_moment")
    icr = cracked_inertia.to("mm**4").magnitude
    ig = gross_inertia.to("mm**4").magnitude
    mcr = cracking_moment.to("N*mm").magnitude
    ma = applied_moment.to("N*mm").magnitude
    if icr <= 0 or ig <= 0 or mcr <= 0 or ma <= 0:
        raise ValueError("all inertias and moments must be positive")
    if icr > ig:
        raise ValueError("cracked_inertia cannot exceed gross_inertia")
    if ma <= _ACI_EFFECTIVE_CRACKING_FRACTION * mcr:
        return Quantity(magnitude=ig, unit="mm**4")
    ratio = _ACI_EFFECTIVE_CRACKING_FRACTION * mcr / ma
    ie = icr / (1.0 - ratio**2 * (1.0 - icr / ig))
    return Quantity(magnitude=ie, unit="mm**4")
