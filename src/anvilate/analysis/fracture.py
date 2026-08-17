"""T1 analytical linear-elastic fracture mechanics (LEFM, closed-form).

Where the Inglis hole shows that a sharp flaw multiplies stress without limit, the
stress-intensity factor makes that danger quantitative. Around a crack tip the
elastic stress field has a fixed shape and a single amplitude — the mode-I
stress-intensity factor

    K_I = Y·σ·√(π·a),

for a remote stress σ, a crack of length a (half-length for a central crack), and a
dimensionless geometry factor Y that captures the crack's shape and location (Y = 1
for a central crack in a wide plate, ~1.12 for an edge crack — supplied like any
handbook coefficient). The crack runs when K_I reaches the material's fracture
toughness K_IC, which inverts to a critical crack length

    a_c = (1/π)·(K_IC / (Y·σ))²,

the flaw size a given stress can tolerate before fast fracture. Stresses and lengths
are dimension-checked :class:`~anvilate.units.Quantity` values; the fracture
toughness carries the LEFM unit MPa·√m.

Below that critical size a crack does not sit still under cyclic load: it grows a
little each cycle, at a rate the Paris-Erdogan law ties to the stress-intensity
range ΔK = Y·Δσ·√(π·a),

    da/dN = C·(ΔK)^m,

a straight line of slope m on a log-log plot between the threshold and fast
fracture. C and m are material constants from crack-growth testing (C quoted for
ΔK in MPa·√m and da in metres, so its units are m/cycle per (MPa·√m)^m). Because
ΔK itself rises with √a, the rate accelerates as the crack lengthens; integrating
da/dN from an initial flaw a_i to the final tolerable size a_f gives the
constant-amplitude propagation life

    N = [a_f^(1−m/2) − a_i^(1−m/2)] / [C·(Y·Δσ·√π)^m·(1 − m/2)]   (m ≠ 2),

the cycles a damage-tolerance inspection interval is built on.
"""

from __future__ import annotations

from math import cos, exp, pi, sin, sqrt

from pydantic import BaseModel, ConfigDict, model_validator

from ..scorecard import CheckStatus, ScorecardEntry
from ..units import Quantity

__all__ = [
    "crack_tip_opening_displacement",
    "stress_intensity_factor",
    "critical_crack_length",
    "critical_fracture_stress",
    "griffith_fracture_stress",
    "strain_energy_release_rate",
    "paris_law_crack_growth_rate",
    "paris_law_cycles_to_failure",
    "crack_tip_plastic_zone_size",
    "plane_strain_thickness_requirement",
    "SurfaceFlaw",
    "FADAssessment",
    "newman_raju_surface_flaw_sif",
    "surface_flaw_reference_stress",
    "fad_limit_load_ratio",
    "fad_option1_curve",
    "charpy_toughness_estimate",
    "fad_assessment",
    "fad_scorecard",
]


def _require(value: Quantity, expected: str, name: str) -> None:
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )


def stress_intensity_factor(
    *, remote_stress: Quantity, crack_length: Quantity, geometry_factor: float = 1.0
) -> Quantity:
    """The mode-I stress-intensity factor K_I = Y·σ·√(π·a).

    The amplitude of the crack-tip stress field, and the quantity to compare against
    the material's fracture toughness K_IC: the crack is stable while K_I < K_IC and
    runs when it reaches it. ``remote_stress`` σ is the applied (far-field) stress,
    ``crack_length`` a the crack length (the half-length for a central through-crack),
    and ``geometry_factor`` Y the dimensionless shape/location factor (1.0 for a
    central crack in a wide plate, ~1.12 for an edge crack). σ must be a stress, a a
    positive length, and Y positive. Returns K_I in MPa·√m.
    """
    _require(remote_stress, "[pressure]", "remote_stress")
    _require(crack_length, "[length]", "crack_length")
    if geometry_factor <= 0:
        raise ValueError(f"geometry_factor must be positive; got {geometry_factor}")
    sigma = remote_stress.to("MPa").magnitude
    a = crack_length.to("m").magnitude
    if a <= 0:
        raise ValueError(f"crack_length must be positive; got {crack_length}")
    return Quantity(magnitude=geometry_factor * sigma * sqrt(pi * a), unit="MPa*m**0.5")


def critical_crack_length(
    *, fracture_toughness: Quantity, remote_stress: Quantity, geometry_factor: float = 1.0
) -> Quantity:
    """The critical crack length a_c = (1/π)·(K_IC/(Y·σ))² for fast fracture.

    The inverse of :func:`stress_intensity_factor`: the largest crack a given stress
    can carry before K_I reaches the fracture toughness and the crack runs. Below
    a_c the flaw is stable; at it, fracture. ``fracture_toughness`` K_IC is the
    material's toughness (a MPa·√m quantity), ``remote_stress`` σ the applied stress,
    and ``geometry_factor`` Y the crack shape/location factor as in
    :func:`stress_intensity_factor`. A tougher material or a lower stress tolerates a
    larger flaw — the basis of a damage-tolerance inspection interval. Returns the
    critical crack length in millimetres.
    """
    _require(fracture_toughness, "[pressure] * [length]**0.5", "fracture_toughness")
    _require(remote_stress, "[pressure]", "remote_stress")
    if geometry_factor <= 0:
        raise ValueError(f"geometry_factor must be positive; got {geometry_factor}")
    kic = fracture_toughness.to("MPa*m**0.5").magnitude
    sigma = remote_stress.to("MPa").magnitude
    if sigma <= 0:
        raise ValueError(f"remote_stress must be positive; got {remote_stress}")
    a_c = (kic / (geometry_factor * sigma)) ** 2 / pi  # metres
    return Quantity(magnitude=a_c * 1000.0, unit="mm")


def critical_fracture_stress(
    *, fracture_toughness: Quantity, crack_length: Quantity, geometry_factor: float = 1.0
) -> Quantity:
    """The critical fracture stress σ_c = K_IC/(Y·√(π·a)) for a known flaw.

    The third member of the K_I = Y·σ·√(π·a) triple, and the stress companion of
    :func:`critical_crack_length`: the remote stress at which a crack of a *known* length reaches
    the fracture toughness and runs. ``fracture_toughness`` K_IC is the material's toughness (a
    MPa·√m quantity), ``crack_length`` a the flaw length (half-length for a central through-crack),
    and ``geometry_factor`` Y the shape/location factor as in :func:`stress_intensity_factor`. It
    answers the acceptance question — with the largest flaw my inspection can miss, what stress dare
    I apply? — so a longer undetected crack or a lower toughness cuts the allowable stress. Returns
    the critical stress in MPa.
    """
    _require(fracture_toughness, "[pressure] * [length]**0.5", "fracture_toughness")
    _require(crack_length, "[length]", "crack_length")
    if geometry_factor <= 0:
        raise ValueError(f"geometry_factor must be positive; got {geometry_factor}")
    kic = fracture_toughness.to("MPa*m**0.5").magnitude
    a = crack_length.to("m").magnitude
    if a <= 0:
        raise ValueError(f"crack_length must be positive; got {crack_length}")
    return Quantity(magnitude=kic / (geometry_factor * sqrt(pi * a)), unit="MPa")


def griffith_fracture_stress(
    *, youngs_modulus: Quantity, surface_energy: Quantity, crack_length: Quantity
) -> Quantity:
    """The Griffith fracture stress σ_f = √(2·E·γ_s/(π·a)) of an ideally brittle solid.

    The energy-based fracture criterion that predates the stress-intensity view: a crack grows only
    when the elastic energy it releases exceeds the surface energy of the new faces it creates. For
    a central crack of length a that gives σ_f = √(2·E·γ_s/(π·a)) from the ``youngs_modulus`` E and
    the ``surface_energy`` γ_s (energy per unit created area, e.g. J/m²). It governs truly brittle
    solids — glasses, ceramics — where no plastic zone blunts the tip; in a ductile metal the
    effective γ must include the far larger plastic work, and the K_IC forms
    (:func:`critical_fracture_stress`) are the practical route. ``crack_length`` a is the flaw
    length. Returns the fracture stress in MPa.
    """
    _require(youngs_modulus, "[pressure]", "youngs_modulus")
    _require(surface_energy, "[force]/[length]", "surface_energy")
    _require(crack_length, "[length]", "crack_length")
    e = youngs_modulus.to("Pa").magnitude
    gamma = surface_energy.to("J/m**2").magnitude
    a = crack_length.to("m").magnitude
    if e <= 0:
        raise ValueError(f"youngs_modulus must be positive; got {youngs_modulus}")
    if gamma <= 0:
        raise ValueError(f"surface_energy must be positive; got {surface_energy}")
    if a <= 0:
        raise ValueError(f"crack_length must be positive; got {crack_length}")
    sigma = sqrt(2.0 * e * gamma / (pi * a))  # Pa
    return Quantity(magnitude=sigma / 1.0e6, unit="MPa")


def strain_energy_release_rate(
    *,
    stress_intensity: Quantity,
    youngs_modulus: Quantity,
    poisson_ratio: float = 0.0,
    plane_strain: bool = False,
) -> Quantity:
    """The strain-energy release rate (Irwin relation), G = K²/E'.

    The elastic energy freed per unit of new crack area, tying the stress-intensity view of fracture
    to Griffith's energy view: from the mode-I ``stress_intensity`` K (from
    :func:`stress_intensity_factor`) and the ``youngs_modulus`` E, G = K²/E'. The effective modulus
    E' is E in plane stress (thin sheets) and E/(1 − ν²) in ``plane_strain`` (thick sections, using
    the ``poisson_ratio`` ν), so a constrained thick body releases slightly less energy for the same
    K. Fracture runs when G reaches the material's toughness G_c = K_IC²/E'. Returns G in J/m².
    """
    _require(stress_intensity, "[pressure]*[length]**0.5", "stress_intensity")
    _require(youngs_modulus, "[pressure]", "youngs_modulus")
    k = stress_intensity.to("Pa*m**0.5").magnitude
    e = youngs_modulus.to("Pa").magnitude
    if e <= 0:
        raise ValueError(f"youngs_modulus must be positive; got {youngs_modulus}")
    if plane_strain and not -1.0 < poisson_ratio < 0.5:
        raise ValueError("poisson_ratio must be in (-1, 0.5) for plane strain")
    e_effective = e / (1.0 - poisson_ratio**2) if plane_strain else e
    return Quantity(magnitude=k * k / e_effective, unit="J/m**2")


def paris_law_crack_growth_rate(
    *,
    stress_range: Quantity,
    crack_length: Quantity,
    paris_coefficient: float,
    paris_exponent: float,
    geometry_factor: float = 1.0,
) -> Quantity:
    """The Paris-Erdogan fatigue crack-growth rate da/dN = C·(ΔK)^m.

    How fast a crack advances *per cycle* under a cyclic load. ``stress_range`` Δσ is
    the far-field stress range (σ_max − σ_min of the cycle), ``crack_length`` a the
    current crack length, and ``geometry_factor`` Y the shape/location factor as in
    :func:`stress_intensity_factor`; together they set the stress-intensity range
    ΔK = Y·Δσ·√(π·a). ``paris_coefficient`` C and ``paris_exponent`` m are the
    material's crack-growth constants (m typically 2.5–4 for steels), with C quoted
    for ΔK in MPa·√m and da in metres. Because ΔK grows with √a, the rate accelerates
    as the crack lengthens. Δσ must be a stress, a a positive length, Y positive, and
    C and m positive. Returns da/dN in metres per cycle.
    """
    _require(stress_range, "[pressure]", "stress_range")
    _require(crack_length, "[length]", "crack_length")
    if geometry_factor <= 0:
        raise ValueError(f"geometry_factor must be positive; got {geometry_factor}")
    if paris_coefficient <= 0:
        raise ValueError(f"paris_coefficient must be positive; got {paris_coefficient}")
    if paris_exponent <= 0:
        raise ValueError(f"paris_exponent must be positive; got {paris_exponent}")
    delta_sigma = stress_range.to("MPa").magnitude
    a = crack_length.to("m").magnitude
    if delta_sigma <= 0:
        raise ValueError(f"stress_range must be positive; got {stress_range}")
    if a <= 0:
        raise ValueError(f"crack_length must be positive; got {crack_length}")
    delta_k = geometry_factor * delta_sigma * sqrt(pi * a)
    return Quantity(magnitude=paris_coefficient * delta_k**paris_exponent, unit="m")


def paris_law_cycles_to_failure(
    *,
    stress_range: Quantity,
    initial_crack_length: Quantity,
    final_crack_length: Quantity,
    paris_coefficient: float,
    paris_exponent: float,
    geometry_factor: float = 1.0,
) -> float:
    """The constant-amplitude crack-propagation life, the integral of the Paris law.

    Integrating da/dN = C·(Y·Δσ·√(π·a))^m from an initial flaw ``initial_crack_length``
    a_i to the final tolerable size ``final_crack_length`` a_f (typically the
    :func:`critical_crack_length`) gives the cycles to grow the crack across that span,

        N = [a_f^(1−m/2) − a_i^(1−m/2)] / [C·(Y·Δσ·√π)^m·(1 − m/2)],

    valid while Δσ, Y and m are constant (constant-amplitude loading with a
    slowly-varying geometry factor). ``stress_range`` Δσ, ``geometry_factor`` Y,
    ``paris_coefficient`` C and ``paris_exponent`` m are as in
    :func:`paris_law_crack_growth_rate`. Both crack lengths must be positive with
    a_f > a_i, and m must differ from 2 (the m = 2 case integrates to a logarithm and
    is not covered). Returns the dimensionless number of cycles.
    """
    _require(stress_range, "[pressure]", "stress_range")
    _require(initial_crack_length, "[length]", "initial_crack_length")
    _require(final_crack_length, "[length]", "final_crack_length")
    if geometry_factor <= 0:
        raise ValueError(f"geometry_factor must be positive; got {geometry_factor}")
    if paris_coefficient <= 0:
        raise ValueError(f"paris_coefficient must be positive; got {paris_coefficient}")
    if paris_exponent <= 0:
        raise ValueError(f"paris_exponent must be positive; got {paris_exponent}")
    if paris_exponent == 2:
        raise ValueError("paris_exponent must differ from 2 (the m = 2 case is not covered)")
    delta_sigma = stress_range.to("MPa").magnitude
    # The sibling `paris_law_crack_growth_rate` rejects a non-positive stress range; this
    # one validated five other arguments and not the one sitting in the denominator under
    # a fractional power. Δσ = 0 was a bare ZeroDivisionError, Δσ = −100 MPa with an even m
    # erased the sign and returned the tensile answer, an odd m returned a NEGATIVE life,
    # and m = 2.5 — inside this docstring's own "typically 2.5–4 for steels" — returned a
    # complex number from a function annotated `-> float`.
    if delta_sigma <= 0:
        raise ValueError(
            f"stress_range must be positive; got {stress_range}. A crack grows under a "
            f"tensile stress range, and a non-positive one raised to the Paris exponent "
            f"is not a life."
        )
    a_i = initial_crack_length.to("m").magnitude
    a_f = final_crack_length.to("m").magnitude
    if a_i <= 0 or a_f <= 0:
        raise ValueError("crack lengths must be positive")
    if a_f <= a_i:
        raise ValueError("final_crack_length must exceed initial_crack_length")
    exponent = 1.0 - paris_exponent / 2.0
    numerator = a_f**exponent - a_i**exponent
    denominator = (
        paris_coefficient * (geometry_factor * delta_sigma * sqrt(pi)) ** paris_exponent * exponent
    )
    return numerator / denominator


def crack_tip_plastic_zone_size(
    *,
    stress_intensity: Quantity,
    yield_strength: Quantity,
    plane_strain: bool = False,
) -> Quantity:
    """The Irwin crack-tip plastic-zone size r_p at a loaded crack.

    Linear-elastic fracture mechanics assumes the crack tip yields over only a small
    region; r_p sizes that region and so tells you whether LEFM even applies. Irwin's
    estimate is r_p = (1/(2π))·(K/σ_y)² in plane stress (thin sections) and, because
    triaxial constraint suppresses yielding, a third of that, (1/(6π))·(K/σ_y)², in
    plane strain (thick sections). ``stress_intensity`` K is the applied stress-intensity
    factor (a MPa·√m quantity, from :func:`stress_intensity_factor`), ``yield_strength``
    σ_y the material's yield, and ``plane_strain`` selects the constraint. If r_p is not
    small compared with the crack length and the remaining ligament, LEFM is invalid and
    an elastic-plastic (J-integral / CTOD) treatment is needed. Returns r_p in mm.
    """
    _require(stress_intensity, "[pressure] * [length]**0.5", "stress_intensity")
    _require(yield_strength, "[pressure]", "yield_strength")
    k = stress_intensity.to("MPa*m**0.5").magnitude
    sy = yield_strength.to("MPa").magnitude
    if k < 0:
        raise ValueError(f"stress_intensity must be non-negative; got {stress_intensity}")
    if sy <= 0:
        raise ValueError(f"yield_strength must be positive; got {yield_strength}")
    coefficient = 1.0 / (6.0 * pi) if plane_strain else 1.0 / (2.0 * pi)
    r_p_m = coefficient * (k / sy) ** 2  # metres
    return Quantity(magnitude=r_p_m * 1000.0, unit="mm")


def plane_strain_thickness_requirement(
    *,
    fracture_toughness: Quantity,
    yield_strength: Quantity,
) -> Quantity:
    """The ASTM E399 minimum thickness B ≥ 2.5·(K_IC/σ_y)² for a valid plane-strain K_IC.

    A fracture-toughness value is only a true, geometry-independent plane-strain K_IC if
    the specimen (or the component) is thick enough to hold the crack tip in plane strain;
    ASTM E399 requires B ≥ 2.5·(K_IC/σ_y)². Below that thickness the material behaves
    tougher (plane-stress, more plastic zone), so using a handbook K_IC would be
    conservative for the part but the test itself would be invalid. ``fracture_toughness``
    K_IC (a MPa·√m quantity) and ``yield_strength`` σ_y set the requirement — the same
    2.5·(K_IC/σ_y)² also bounds the crack length and ligament for a valid test. A tough,
    low-yield material needs a very thick section to be plane-strain. Returns B in mm.
    """
    _require(fracture_toughness, "[pressure] * [length]**0.5", "fracture_toughness")
    _require(yield_strength, "[pressure]", "yield_strength")
    kic = fracture_toughness.to("MPa*m**0.5").magnitude
    sy = yield_strength.to("MPa").magnitude
    if kic <= 0:
        raise ValueError(f"fracture_toughness must be positive; got {fracture_toughness}")
    if sy <= 0:
        raise ValueError(f"yield_strength must be positive; got {yield_strength}")
    b_m = 2.5 * (kic / sy) ** 2  # metres
    return Quantity(magnitude=b_m * 1000.0, unit="mm")


def crack_tip_opening_displacement(
    *,
    stress_intensity: Quantity,
    yield_strength: Quantity,
    youngs_modulus: Quantity,
    poisson_ratio: float = 0.0,
    plane_strain: bool = False,
) -> Quantity:
    """The crack-tip opening displacement, δ_t = K²/(σ_y·E′).

    How far the two crack faces separate at the tip — the elastic-plastic fracture parameter that
    stays meaningful after linear-elastic fracture mechanics stops being valid.
    :func:`crack_tip_plastic_zone_size`'s docstring ends by saying that when the plastic zone is no
    longer small "an elastic-plastic (J-integral / CTOD) treatment is needed", and the module then
    offered neither, leaving a user who discovers LEFM is invalid with no next step. CTOD is also
    the parameter BS 7910 and API 579 fitness-for-service assessments are written in.

    From the ``stress_intensity`` K, the ``yield_strength`` σ_y, and the effective modulus E′ — the
    ``youngs_modulus`` E in plane stress, or E/(1 − ν²) in plane strain, matching the convention of
    :func:`strain_energy_release_rate`. Equivalently δ_t = G/σ_y for a constraint factor of one,
    which is the identity worth remembering: it ties CTOD directly to the energy release rate the
    module already computes.

    A 50 MPa·√m field in a 400 MPa steel of E = 200 GPa opens the tip 31 µm — small, but a
    measurable and physically real crack mouth rather than the mathematical singularity LEFM
    predicts. Plane strain constrains the tip and gives a smaller opening for the same K, so it is
    the conservative choice. Returns the opening displacement in m.
    """
    _require(stress_intensity, "[pressure]*[length]**0.5", "stress_intensity")
    _require(yield_strength, "[pressure]", "yield_strength")
    _require(youngs_modulus, "[pressure]", "youngs_modulus")
    sigma_y = yield_strength.to("Pa").magnitude
    if sigma_y <= 0:
        raise ValueError("yield_strength must be positive")
    release_rate = strain_energy_release_rate(
        stress_intensity=stress_intensity,
        youngs_modulus=youngs_modulus,
        poisson_ratio=poisson_ratio,
        plane_strain=plane_strain,
    )
    return Quantity(magnitude=release_rate.to("J/m**2").magnitude / sigma_y, unit="m")


# --- Fitness-for-service screening: SIF, reference stress, FAD ---------------
#
# The functions above give K, a critical size, and a growth rate. Assessing a real
# flaw needs three more things: a handbook K solution for the flaw's actual shape,
# a plastic-collapse measure of how close the remaining ligament is to yielding,
# and a way to combine the two — because a flawed component fails by brittle
# fracture at one extreme, by plastic collapse at the other, and by a mixture in
# between, which neither limit alone predicts.
#
# The failure assessment diagram is that combination. Plot K_I/K_mat up the axis
# and sigma_ref/sigma_y along it, and a single curve separates acceptable from
# unacceptable. A point low and right fails by collapse, high and left by
# fracture, and the interaction near the knee is what a K-only check misses.
#
# Sources: Newman & Raju, "Stress-Intensity Factor Equations for Cracks in
# Three-Dimensional Finite Bodies Subjected to Tension and Bending Loads" (NASA TM
# 85793, 1984 — a public-domain US government report) for the surface-flaw K
# solution; BS 7910 / R6 for the Option 1 failure assessment curve, the surface-flaw
# reference stress, and the Lr cutoff; Rolfe & Novak / Barsom for the upper-shelf
# Charpy correlation.
#
# FRAMING, and it is not decoration: what these functions produce is a SCREENING
# MARGIN, not a fitness-for-service disposition. Deciding that a flawed component
# may stay in service is the job of a qualified assessor working to the full
# assessment code, with the residual stresses, the weld metal properties, and the
# inspection uncertainty this screen does not have. Nothing here says "fit for
# continued service" and nothing here should be quoted as though it did.

_CLAUSE_NEWMAN_RAJU = "Newman & Raju, NASA TM 85793 (1984), surface crack in a plate"
_CLAUSE_FAD = "BS 7910 / R6 Option 1 failure assessment diagram"
_CLAUSE_REFERENCE_STRESS = "BS 7910 Annex P, local collapse of a surface-flawed plate"
_CLAUSE_CHARPY = "Rolfe-Novak-Barsom upper-shelf Charpy correlation (an ESTIMATE)"

# BS 7910 Option 1: the exponent coefficient is capped, so a very stiff or very
# low-yield material cannot push the curve's tail out indefinitely.
_FAD_MU_CAP = 0.6
_FAD_MU_COEFFICIENT = 0.001


class SurfaceFlaw(BaseModel):
    """A semi-elliptical surface flaw in a plate, and the geometry K depends on.

    ``depth`` a is the flaw's depth into the wall, ``half_length`` c half its length
    along the surface, ``thickness`` t the wall, and ``half_width`` b half the plate's
    width (the plate is treated as wide when it is omitted).

    :meth:`outside_validity` returns the Newman & Raju validity limits this geometry
    breaks. The limits matter: the equations are a fit to finite-element results over a
    stated range, and outside it they do not degrade gracefully — the a/c > 1 branch is
    a *different* set of coefficients, not an extrapolation of this one.
    """

    model_config = ConfigDict(frozen=True)

    depth: Quantity
    half_length: Quantity
    thickness: Quantity
    half_width: Quantity | None = None

    @model_validator(mode="after")
    def _well_formed(self) -> SurfaceFlaw:
        for value, name in (
            (self.depth, "depth"),
            (self.half_length, "half_length"),
            (self.thickness, "thickness"),
            (self.half_width, "half_width"),
        ):
            if value is None:
                continue
            if not value.has_dimension("[length]"):
                raise ValueError(f"{name} must be a [length] quantity; got {value}")
            if value.magnitude <= 0:
                raise ValueError(f"{name} must be positive; got {value}")
        return self

    @property
    def aspect_ratio(self) -> float:
        """a/c — 1.0 for a semi-circular flaw, small for a long shallow one."""
        return self.depth.to("mm").magnitude / self.half_length.to("mm").magnitude

    @property
    def depth_ratio(self) -> float:
        """a/t — how far through the wall the flaw has eaten."""
        return self.depth.to("mm").magnitude / self.thickness.to("mm").magnitude

    def outside_validity(self) -> tuple[str, ...]:
        """The Newman-Raju validity limits this geometry falls outside. Empty = inside."""
        outside: list[str] = []
        if not 0.0 < self.aspect_ratio <= 1.0:
            outside.append(
                f"a/c = {self.aspect_ratio:.4g} outside (0, 1]; a flaw longer than it is "
                f"deep takes the a/c > 1 coefficient set, which is a different fit"
            )
        if self.depth_ratio >= 1.0:
            outside.append(
                f"a/t = {self.depth_ratio:.4g} — the flaw has reached the far wall and "
                f"is no longer a surface flaw"
            )
        if self.half_width is not None:
            c_over_b = self.half_length.to("mm").magnitude / self.half_width.to("mm").magnitude
            if c_over_b >= 0.5:
                outside.append(f"c/b = {c_over_b:.4g} exceeds the 0.5 finite-width limit")
        return tuple(outside)


def newman_raju_surface_flaw_sif(
    *,
    flaw: SurfaceFlaw,
    membrane_stress: Quantity,
    bending_stress: Quantity | None = None,
    parametric_angle: float = pi / 2,
) -> Quantity:
    """The Newman & Raju stress-intensity factor for a surface flaw in a plate, in MPa·√m.

    K_I = (σ_m + H·σ_b)·√(π·a/Q)·F, where Q = 1 + 1.464(a/c)^1.65 is the flaw shape
    factor, F the boundary-correction polynomial in a/t and a/c, and H the bending
    multiplier. ``parametric_angle`` φ selects the point on the flaw front: π/2 (the
    default) is the deepest point, 0 is where the flaw breaks the surface. Both matter
    and neither always governs — a shallow flaw grows fastest at the surface, a deep one
    at the depth, which is what makes a semi-elliptical flaw change shape as it grows.

    A sanity anchor worth keeping in mind: for a semi-circular flaw (a/c = 1) in a wide,
    thick plate the equation returns 0.663·σ√(πa) at the deepest point, which is exactly
    1.04 times the (2/π)·σ√(πa) of an embedded penny-shaped crack — the 1.04 being the
    free-surface magnification. At the surface point it gives 0.728·σ√(πa).

    Raises when the geometry is outside the equations' validity (see
    :meth:`SurfaceFlaw.outside_validity`). The fit does not extrapolate: past a/c = 1 the
    published solution uses different coefficients entirely, so a number produced here
    would be wrong rather than approximate.
    """
    outside = flaw.outside_validity()
    if outside:
        raise ValueError(
            "the flaw geometry is outside the Newman-Raju validity range, where these "
            "equations do not extrapolate: " + "; ".join(outside)
        )
    _require(membrane_stress, "[pressure]", "membrane_stress")
    if bending_stress is not None:
        _require(bending_stress, "[pressure]", "bending_stress")
    if not 0.0 <= parametric_angle <= pi:
        raise ValueError(
            f"parametric_angle must be between 0 (the surface point) and pi; got {parametric_angle}"
        )
    sigma_m = membrane_stress.to("MPa").magnitude
    sigma_b = 0.0 if bending_stress is None else bending_stress.to("MPa").magnitude
    a = flaw.depth.to("m").magnitude
    ac = flaw.aspect_ratio
    at = flaw.depth_ratio
    phi = parametric_angle

    q = 1.0 + 1.464 * ac**1.65
    m1 = 1.13 - 0.09 * ac
    m2 = -0.54 + 0.89 / (0.2 + ac)
    m3 = 0.5 - 1.0 / (0.65 + ac) + 14.0 * (1.0 - ac) ** 24
    g = 1.0 + (0.1 + 0.35 * at**2) * (1.0 - sin(phi)) ** 2
    f_phi = (ac**2 * cos(phi) ** 2 + sin(phi) ** 2) ** 0.25
    if flaw.half_width is None:
        f_w = 1.0
    else:
        c = flaw.half_length.to("m").magnitude
        b = flaw.half_width.to("m").magnitude
        f_w = sqrt(1.0 / cos(pi * c * sqrt(at) / (2.0 * b)))
    f = (m1 + m2 * at**2 + m3 * at**4) * g * f_phi * f_w

    # The bending multiplier H, which runs from H1 at the surface to H2 at the depth.
    g1 = -1.22 - 0.12 * ac
    g2 = 0.55 - 1.05 * ac**0.75 + 0.47 * ac**1.5
    h1 = 1.0 - 0.34 * at - 0.11 * ac * at
    h2 = 1.0 + g1 * at + g2 * at**2
    p = 0.2 + ac + 0.6 * at
    h = h1 + (h2 - h1) * sin(phi) ** p

    k = (sigma_m + h * sigma_b) * sqrt(pi * a / q) * f
    return Quantity(magnitude=k, unit="MPa*m**0.5")


def surface_flaw_reference_stress(
    *,
    flaw: SurfaceFlaw,
    membrane_stress: Quantity,
    bending_stress: Quantity | None = None,
) -> Quantity:
    """The BS 7910 local-collapse reference stress of a surface-flawed plate, in MPa.

    σ_ref = [σ_b + √(σ_b² + 9σ_m²(1−α)²)] / (3(1−α)²), with α = (a/t)/(1 + t/c) the
    fraction of the ligament the flaw has taken. This is the plastic-collapse half of a
    failure assessment: it measures how close the *remaining ligament* is to yielding,
    which K says nothing about.

    Two checks the form has to pass, and does. With no bending it collapses to the plain
    net-section stress σ_m/(1−α). With no flaw and pure bending it gives (2/3)σ_b, which
    is the elastic bending stress divided by the 1.5 shape factor of a rectangular
    section — the ratio between first yield and a fully plastic hinge.

    Note α uses (a/t)/(1 + t/c), not a/t: a short flaw takes far less of the ligament
    than its depth suggests, because the material either side of it still carries load.
    """
    _require(membrane_stress, "[pressure]", "membrane_stress")
    if bending_stress is not None:
        _require(bending_stress, "[pressure]", "bending_stress")
    sigma_m = membrane_stress.to("MPa").magnitude
    sigma_b = 0.0 if bending_stress is None else bending_stress.to("MPa").magnitude
    if sigma_m < 0 or sigma_b < 0:
        raise ValueError(
            "membrane_stress and bending_stress must be non-negative; a compressive "
            "primary stress does not drive this collapse mode and cannot be netted off "
            "against a tensile one"
        )
    t = flaw.thickness.to("mm").magnitude
    c = flaw.half_length.to("mm").magnitude
    alpha = flaw.depth_ratio / (1.0 + t / c)
    if alpha >= 1.0:
        raise ValueError(
            f"the flaw has consumed the whole ligament (alpha = {alpha:.4g}); there is "
            f"no collapse load left to compare against"
        )
    ligament = (1.0 - alpha) ** 2
    numerator = sigma_b + sqrt(sigma_b**2 + 9.0 * sigma_m**2 * ligament)
    return Quantity(magnitude=numerator / (3.0 * ligament), unit="MPa")


def fad_limit_load_ratio(*, yield_strength: Quantity, ultimate_strength: Quantity) -> float:
    """The BS 7910 cutoff L_r,max = (σ_y + σ_u)/(2σ_y) — the flow stress over the yield.

    Where the assessment diagram stops. Past L_r,max the ligament is fully plastic and no
    amount of toughness helps, so the curve does not continue: the answer is collapse.
    A material with little strain hardening (σ_u close to σ_y) has a cutoff barely above
    1.0 and very little collapse reserve; a heavily hardening one runs out past 1.3.
    """
    _require(yield_strength, "[pressure]", "yield_strength")
    _require(ultimate_strength, "[pressure]", "ultimate_strength")
    sy = yield_strength.to("MPa").magnitude
    su = ultimate_strength.to("MPa").magnitude
    if sy <= 0 or su <= 0:
        raise ValueError("yield_strength and ultimate_strength must be positive")
    if su < sy:
        raise ValueError(
            f"ultimate_strength ({ultimate_strength}) is below yield_strength "
            f"({yield_strength}); check they are not swapped"
        )
    return (sy + su) / (2.0 * sy)


def fad_option1_curve(
    *, load_ratio: float, yield_strength: Quantity, elastic_modulus: Quantity
) -> float:
    """The BS 7910 / R6 Option 1 failure assessment curve f(L_r).

    f(L_r) = (1 + 0.5·L_r²)^(-1/2)·[0.3 + 0.7·exp(−μ·L_r⁶)], with μ = min(0.001·E/σ_y, 0.6).

    The generic curve, used when no material-specific stress-strain data is available.
    It starts at f = 1.0 (pure fracture: all the toughness is available) and falls away
    as the ligament yields, because plasticity at the crack tip drives K up faster than
    the elastic solution says. μ sets how sharply: a low-yield, stiff material yields
    earlier relative to its elastic range and its curve drops sooner, which is why μ is
    E/σ_y and not a constant. The 0.6 cap stops that from running away.

    ``load_ratio`` is L_r = σ_ref/σ_y. Returns the acceptable K_r at that L_r; an
    assessment point below the curve is acceptable, on or above it is not. The curve is
    only defined up to :func:`fad_limit_load_ratio`, which this function does not know —
    it is checked in :func:`fad_assessment`.
    """
    _require(yield_strength, "[pressure]", "yield_strength")
    _require(elastic_modulus, "[pressure]", "elastic_modulus")
    if load_ratio < 0:
        raise ValueError(f"load_ratio L_r must be non-negative; got {load_ratio}")
    sy = yield_strength.to("MPa").magnitude
    e = elastic_modulus.to("MPa").magnitude
    if sy <= 0 or e <= 0:
        raise ValueError("yield_strength and elastic_modulus must be positive")
    mu = min(_FAD_MU_COEFFICIENT * e / sy, _FAD_MU_CAP)
    return (1.0 + 0.5 * load_ratio**2) ** -0.5 * (0.3 + 0.7 * exp(-mu * load_ratio**6))


def charpy_toughness_estimate(*, charpy_energy: Quantity, yield_strength: Quantity) -> Quantity:
    """An ESTIMATE of K_IC from upper-shelf Charpy energy (Rolfe-Novak-Barsom), in MPa·√m.

    (K_IC/σ_y)² = 5[(CVN/σ_y) − 0.05], in ksi·√in, ksi and ft·lbf. A correlation, not a
    measurement: it was fitted to upper-shelf data for structural and pressure-vessel
    steels and it scatters. Use it to decide whether a real toughness test is worth
    commissioning, and label every number that comes out of it as an estimate — which is
    why this function is named for what it is.

    It is only meaningful on the upper shelf. In the transition region the same Charpy
    energy can correspond to toughness values a factor of two apart, and the correlation
    has no way to know which side of the transition the test was on.
    """
    _require(charpy_energy, "[energy]", "charpy_energy")
    _require(yield_strength, "[pressure]", "yield_strength")
    cvn = charpy_energy.to("foot_pound").magnitude
    sy = yield_strength.to("ksi").magnitude
    if cvn <= 0 or sy <= 0:
        raise ValueError("charpy_energy and yield_strength must be positive")
    bracket = 5.0 * (cvn / sy - 0.05)
    if bracket <= 0:
        raise ValueError(
            f"the correlation gives a non-positive toughness for CVN = {charpy_energy} at "
            f"a yield of {yield_strength}: the energy is below the 0.05·σ_y floor the fit "
            f"is defined above, which means the steel is not on its upper shelf here"
        )
    kic_ksi_in = sy * sqrt(bracket)
    return Quantity(magnitude=kic_ksi_in, unit="ksi*inch**0.5").to("MPa*m**0.5")


class FADAssessment(BaseModel):
    """Where a flaw lands on the BS 7910 failure assessment diagram.

    ``fracture_ratio`` K_r = K_I/K_mat is how much of the toughness the flaw uses;
    ``load_ratio`` L_r = σ_ref/σ_y how much of the collapse load the ligament uses.
    ``acceptable_fracture_ratio`` is the curve's height at that L_r, and ``acceptable``
    says whether the point is under it and inside the L_r cutoff.

    ``load_line_margin`` is the useful number: the factor by which the primary load can
    be scaled before the point reaches the curve. It is ``None`` when there is no primary
    load to scale — a point at the origin has nothing to evaluate, and reporting an
    infinite margin there is the zero-demand silent green this library refuses everywhere
    else. Both ratios are linear in load, so the
    point travels out along a straight line from the origin and the margin is where that
    line crosses. It is the FAD's answer to "how much have I got left", and it is not
    1/K_r — the curve bends, so a point at K_r = 0.5 with L_r near the cutoff may have
    almost nothing in hand.

    This is a SCREENING margin. A disposition — deciding a flawed component may stay in
    service — is a qualified assessor's call under the full assessment code, with the
    residual stresses, weld properties and inspection uncertainty this screen lacks.
    """

    model_config = ConfigDict(frozen=True)

    fracture_ratio: float
    load_ratio: float
    acceptable_fracture_ratio: float
    limit_load_ratio: float
    acceptable: bool
    load_line_margin: float | None
    toughness_is_estimate: bool = False

    def __str__(self) -> str:
        verdict = "inside" if self.acceptable else "outside"
        margin = (
            "not evaluated" if self.load_line_margin is None else f"{self.load_line_margin:.3g}"
        )
        return (
            f"FAD point (L_r {self.load_ratio:.3g}, K_r {self.fracture_ratio:.3g}) "
            f"{verdict} the curve, load-line margin {margin}"
        )


def fad_assessment(
    *,
    stress_intensity: Quantity,
    fracture_toughness: Quantity,
    reference_stress: Quantity,
    yield_strength: Quantity,
    ultimate_strength: Quantity,
    elastic_modulus: Quantity,
    toughness_is_estimate: bool = False,
) -> FADAssessment:
    """Place a flaw on the BS 7910 Option 1 assessment diagram and measure its margin.

    Combines the two halves: ``stress_intensity`` K_I (from
    :func:`newman_raju_surface_flaw_sif` or any handbook solution) over
    ``fracture_toughness`` K_mat gives K_r, and ``reference_stress`` (from
    :func:`surface_flaw_reference_stress`) over ``yield_strength`` gives L_r.

    The load-line margin is found by scaling both ratios together — which is what
    scaling the primary load does, since K and σ_ref are both linear in it — and finding
    where the ray from the origin crosses the curve or the L_r cutoff, whichever comes
    first. A margin below 1.0 means the point is already outside.

    ``toughness_is_estimate`` travels through to the result and into the scorecard
    detail, so a verdict resting on a Charpy correlation cannot be mistaken for one
    resting on a measured K_IC.
    """
    _require(stress_intensity, "[pressure] * [length]**0.5", "stress_intensity")
    _require(fracture_toughness, "[pressure] * [length]**0.5", "fracture_toughness")
    _require(reference_stress, "[pressure]", "reference_stress")
    k = stress_intensity.to("MPa*m**0.5").magnitude
    kmat = fracture_toughness.to("MPa*m**0.5").magnitude
    sigma_ref = reference_stress.to("MPa").magnitude
    sy = yield_strength.to("MPa").magnitude
    if kmat <= 0:
        raise ValueError(f"fracture_toughness must be positive; got {fracture_toughness}")
    if k < 0 or sigma_ref < 0:
        raise ValueError("stress_intensity and reference_stress must be non-negative")
    if sy <= 0:
        raise ValueError(f"yield_strength must be positive; got {yield_strength}")
    kr = k / kmat
    lr = sigma_ref / sy
    lr_max = fad_limit_load_ratio(
        yield_strength=yield_strength, ultimate_strength=ultimate_strength
    )

    def curve(x: float) -> float:
        return fad_option1_curve(
            load_ratio=x, yield_strength=yield_strength, elastic_modulus=elastic_modulus
        )

    acceptable_kr = curve(lr) if lr <= lr_max else 0.0
    acceptable = lr <= lr_max and kr < acceptable_kr

    # The load-line margin: the scale s at which (s·L_r, s·K_r) reaches the curve or the
    # cutoff. Both ratios are linear in the primary load, so the point rides a ray from
    # the origin. Bisect on g(s) = s·K_r − f(s·L_r), which is negative inside and
    # positive outside, and cap s at the cutoff.
    # No demand at all is nothing to evaluate, not a member with infinite reserve. It is
    # also the only way this function could emit a non-finite float, which no strict JSON
    # encoder will accept out the far side of a report.
    def _gap(s: float, s_cutoff: float) -> float:
        x = s * lr
        return s * kr - (curve(x) if x <= lr_max else 0.0)

    margin: float | None
    if lr == 0:
        # No primary load to scale. A point on the K_r axis does not ride out along a
        # load line at all, and an infinite margin here is the zero-demand silent green
        # this library refuses everywhere else — it is also the only way this function
        # could emit a non-finite float, which no strict JSON encoder accepts.
        margin = None
    else:
        s_cutoff = lr_max / lr
        if kr == 0:
            margin = s_cutoff
        else:
            low, high = 0.0, s_cutoff
            if _gap(high, s_cutoff) <= 0:
                margin = high
            else:
                for _ in range(200):
                    mid = 0.5 * (low + high)
                    if _gap(mid, s_cutoff) > 0:
                        high = mid
                    else:
                        low = mid
                margin = 0.5 * (low + high)
    return FADAssessment(
        fracture_ratio=kr,
        load_ratio=lr,
        acceptable_fracture_ratio=acceptable_kr,
        limit_load_ratio=lr_max,
        acceptable=acceptable,
        load_line_margin=margin,
        toughness_is_estimate=toughness_is_estimate,
    )


def fad_scorecard(
    name: str,
    *,
    assessment: FADAssessment | None,
    required: float = 1.0,
    missing: str = "",
) -> ScorecardEntry:
    """Screen a BS 7910 FAD assessment into a :class:`ScorecardEntry`.

    The safety factor is the load-line margin against ``required``. The detail carries
    both coordinates, which mode the point is closest to failing in, and — always — that
    this is a screening margin and not a fitness-for-service disposition.

    ``assessment`` of ``None`` is ``NOT_EVALUATED``: a flaw outside the SIF solution's
    validity range, or one with no toughness supplied, has not been assessed. ``missing``
    names what was absent.

    A verdict resting on a Charpy-correlated toughness is downgraded from ``PASS`` to
    ``NOT_EVALUATED``. The correlation scatters by enough that a pass built on it is not
    a pass — it is a reason to commission a toughness test.
    """
    if assessment is None:
        detail = "not evaluated"
        if missing.strip():
            detail = f"{detail} — {missing.strip()}"
        else:
            detail = f"{detail} — the flaw could not be placed on the assessment diagram"
        return ScorecardEntry(
            name=name,
            status=CheckStatus.NOT_EVALUATED,
            detail=detail,
            reference=_CLAUSE_FAD,
        )
    if assessment.load_line_margin is None:
        return ScorecardEntry(
            name=name,
            status=CheckStatus.NOT_EVALUATED,
            detail=(
                "not evaluated — the assessment point carries no primary load, so there "
                "is no load line to ride out and no margin to report. Nothing to "
                "evaluate is not an infinite reserve."
            ),
            reference=_CLAUSE_FAD,
        )
    mode = (
        "plastic collapse"
        if assessment.load_ratio / assessment.limit_load_ratio > assessment.fracture_ratio
        else "brittle fracture"
    )
    detail = (
        f"screening margin only, not a fitness-for-service disposition: the assessment "
        f"point sits at L_r {assessment.load_ratio:.3g} (cutoff "
        f"{assessment.limit_load_ratio:.3g}), K_r {assessment.fracture_ratio:.3g} "
        f"(curve {assessment.acceptable_fracture_ratio:.3g}), nearer {mode}; the primary "
        f"load can be scaled by {assessment.load_line_margin:.3g} before it reaches the "
        f"curve. Disposition is a qualified assessor's call under the full code."
    )
    entry = ScorecardEntry.from_safety_factor(
        name, computed=assessment.load_line_margin, required=required
    )
    if assessment.toughness_is_estimate:
        detail = (
            f"the toughness is a Charpy correlation, not a measurement, and the "
            f"correlation scatters — treat this as a reason to test, not a result. {detail}"
        )
        if entry.status is CheckStatus.PASS:
            return entry.model_copy(
                update={
                    "status": CheckStatus.NOT_EVALUATED,
                    "detail": detail,
                    "reference": _CLAUSE_CHARPY,
                    "safety_factor": None,
                }
            )
    return entry.model_copy(update={"detail": detail, "reference": _CLAUSE_FAD})
