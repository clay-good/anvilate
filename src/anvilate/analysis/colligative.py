"""T1 analytical colligative-property checks (closed-form).

Some solution properties depend only on how many solute particles are dissolved, not on what they
are — the colligative properties. Dissolving something raises a liquid's boiling point, lowers its
freezing point, and lets it draw pure solvent across a membrane by osmosis, each in proportion to
the particle concentration. These set the salt needed to de-ice a road, the antifreeze protection of
a coolant, and the pressure a reverse-osmosis plant must beat. They are distinct from the reaction
kinetics of :mod:`anvilate.analysis.arrhenius` and the cell voltage of
:mod:`anvilate.analysis.nernst`: no reaction is involved, only the count of dissolved particles.

The van 't Hoff factor i counts the particles each formula unit releases (1 for sugar, 2 for NaCl).
The osmotic pressure is pi = i * c * R * T, from the molar concentration c and absolute temperature
T — about 24.8 bar for a 1 mol/L ideal solute at 25 C, and the thermodynamic floor a reverse-osmosis
membrane must exceed. The freezing-point depression is Delta_Tf = i * Kf * b and the boiling-point
elevation Delta_Tb = i * Kb * b, both from the molality b and the solvent's cryoscopic (Kf) or
ebullioscopic (Kb) constant — 1.86 and 0.512 K*kg/mol for water.

Sources: Atkins & de Paula, *Physical Chemistry* (colligative properties) — the van 't Hoff
osmotic pressure, and the freezing-point depression and boiling-point elevation a molality
produces at the solvent's cryoscopic and ebullioscopic constants.
"""

from __future__ import annotations

from ..refusal import RefusalError, Remedy
from ..units import Quantity, require_finite

_SOLUTION_SOURCE = "the solution's prepared concentration or molality record"
_STATE_SOURCE = "the solution's measured absolute temperature"
_SOLVENT_SOURCE = "the solvent's cited cryoscopic or ebullioscopic constant"
_DISSOCIATION_SOURCE = "the solute's formula or measured osmotic activity"


class _ColligativeInputError(RefusalError, ValueError):
    """A colligative-property input that cannot be used without correction."""


def _colligative_refusal(message: str, *, subject: str, source: str) -> _ColligativeInputError:
    return _ColligativeInputError(
        message,
        remedies=(Remedy(action="replace", subject=subject, source=source),),
    )


def _colligative_input_source(name: str) -> str:
    if name == "temperature":
        return _STATE_SOURCE
    if name in {"cryoscopic_constant", "ebullioscopic_constant"}:
        return _SOLVENT_SOURCE
    if name == "vant_hoff_factor":
        return _DISSOCIATION_SOURCE
    return _SOLUTION_SOURCE


_GAS_CONSTANT = 8.314462618  # J/(mol*K)

__all__ = [
    "boiling_point_elevation",
    "freezing_point_depression",
    "osmotic_pressure",
]


def osmotic_pressure(
    *, concentration: Quantity, temperature: Quantity, vant_hoff_factor: float = 1.0
) -> Quantity:
    """The osmotic pressure, pi = i * c * R * T.

    The pressure that would just stop pure solvent from crossing a semipermeable membrane into a
    solution of molar ``concentration`` c at absolute ``temperature`` T, pi = i * c * R * T, with
    the ``vant_hoff_factor`` i (particles per formula unit: 1 for glucose, 2 for NaCl). It is the
    minimum pressure a reverse-osmosis process must exceed to push water the other way. Returns the
    osmotic pressure in Pa.
    """
    _check(concentration, "[substance]/[length]**3", "concentration")
    _check(temperature, "[temperature]", "temperature")
    c = concentration.to("mol/m**3").magnitude
    t = temperature.to("K").magnitude
    if c < 0:
        raise _colligative_refusal(
            "concentration must be non-negative", subject="concentration", source=_SOLUTION_SOURCE
        )
    if t <= 0:
        raise _colligative_refusal(
            "temperature must be positive (absolute temperature)",
            subject="temperature",
            source=_STATE_SOURCE,
        )
    if vant_hoff_factor <= 0:
        raise _colligative_refusal(
            "vant_hoff_factor must be positive",
            subject="vant_hoff_factor",
            source=_DISSOCIATION_SOURCE,
        )
    return Quantity(magnitude=vant_hoff_factor * c * _GAS_CONSTANT * t, unit="Pa")


def freezing_point_depression(
    *, molality: Quantity, cryoscopic_constant: Quantity, vant_hoff_factor: float = 1.0
) -> Quantity:
    """The freezing-point depression, Delta_Tf = i * Kf * b.

    How far a solute lowers the solvent's freezing point: the ``vant_hoff_factor`` i times the
    ``cryoscopic_constant`` Kf and the ``molality`` b, Delta_Tf = i * Kf * b. For water Kf is
    1.86 K*kg/mol, so a 1 molal ideal solute drops the freezing point 1.86 K — the physics of road
    salt and antifreeze. Returns the depression as a temperature interval in K.
    """
    _check(molality, "[substance]/[mass]", "molality")
    _check(cryoscopic_constant, "[temperature]*[mass]/[substance]", "cryoscopic_constant")
    b = molality.to("mol/kg").magnitude
    kf = cryoscopic_constant.to("K*kg/mol").magnitude
    if b < 0:
        raise _colligative_refusal(
            "molality must be non-negative", subject="molality", source=_SOLUTION_SOURCE
        )
    if kf <= 0:
        raise _colligative_refusal(
            "cryoscopic_constant must be positive",
            subject="cryoscopic_constant",
            source=_SOLVENT_SOURCE,
        )
    if vant_hoff_factor <= 0:
        raise _colligative_refusal(
            "vant_hoff_factor must be positive",
            subject="vant_hoff_factor",
            source=_DISSOCIATION_SOURCE,
        )
    return Quantity(magnitude=vant_hoff_factor * kf * b, unit="K")


def boiling_point_elevation(
    *, molality: Quantity, ebullioscopic_constant: Quantity, vant_hoff_factor: float = 1.0
) -> Quantity:
    """The boiling-point elevation, Delta_Tb = i * Kb * b.

    How far a solute raises the solvent's boiling point: the ``vant_hoff_factor`` i times the
    ``ebullioscopic_constant`` Kb and the ``molality`` b, Delta_Tb = i * Kb * b. For water Kb is
    0.512 K*kg/mol, so a 1 molal ideal solute raises the boiling point only 0.512 K — much weaker
    than the freezing depression. Returns the elevation as a temperature interval in K.
    """
    _check(molality, "[substance]/[mass]", "molality")
    _check(ebullioscopic_constant, "[temperature]*[mass]/[substance]", "ebullioscopic_constant")
    b = molality.to("mol/kg").magnitude
    kb = ebullioscopic_constant.to("K*kg/mol").magnitude
    if b < 0:
        raise _colligative_refusal(
            "molality must be non-negative", subject="molality", source=_SOLUTION_SOURCE
        )
    if kb <= 0:
        raise _colligative_refusal(
            "ebullioscopic_constant must be positive",
            subject="ebullioscopic_constant",
            source=_SOLVENT_SOURCE,
        )
    if vant_hoff_factor <= 0:
        raise _colligative_refusal(
            "vant_hoff_factor must be positive",
            subject="vant_hoff_factor",
            source=_DISSOCIATION_SOURCE,
        )
    return Quantity(magnitude=vant_hoff_factor * kb * b, unit="K")


def _check(value: Quantity, expected: str, name: str) -> None:
    if not isinstance(value, Quantity):
        raise _colligative_refusal(
            f"{name} must be a {expected} quantity; got {value!r}",
            subject=name,
            source=_colligative_input_source(name),
        )
    if not value.has_dimension(expected):
        raise _colligative_refusal(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})",
            subject=name,
            source=_colligative_input_source(name),
        )
    # The dimension is the easy half. Every comparison with NaN is False, so a NaN walks
    # past whatever `<= 0` guard follows; an infinity passes it too and then divides to
    # zero or overflows an `int()`. The `_require` helper in forty-eight sibling modules
    # has called this since it was written and this one, in a hundred and sixty-four, did
    # not — the same helper in two generations.
    require_finite(value, name=name)
