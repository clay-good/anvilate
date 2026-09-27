"""T1 analytical mass-energy-equivalence checks (closed-form).

Mass and energy are interchangeable through E = m*c^2, and the tiny mass lost when nucleons bind
into a nucleus is released as the enormous energy of nuclear fission and fusion. This is the
accounting behind a reactor's output, a bomb's yield, and the Sun's power, and it underlies the
decay energetics of :mod:`anvilate.analysis.radioactivity`. It is distinct from the relativistic
kinetic energy of :mod:`anvilate.analysis.relativity` (motion): here the energy comes from mass.

The mass-energy equivalence is E = m*c^2, from the speed of light c — so a single gram of mass is
worth about 90 terajoules, and the mass defect when a nucleus forms carries off that binding energy.
Inverting it, m = E/c^2 gives the mass equivalent of an energy (the tiny mass an energetic photon or
reaction carries). Dividing a nucleus's total binding energy by its nucleon count gives the binding
energy per nucleon, which peaks near iron at about 8.8 MeV: light nuclei release energy by fusing
toward the peak, heavy ones by fissioning toward it.

Sources: Krane, *Introductory Nuclear Physics* — the rest energy E = m·c², the mass an energy
corresponds to, and the binding energy per nucleon a mass defect gives.
"""

from __future__ import annotations

from ..refusal import RefusalError, Remedy
from ..units import Quantity, require_finite

_SPEED_OF_LIGHT = 299792458.0  # m/s
_MASS_ENERGY_MASS_SOURCE = "the mass inventory or calibrated mass measurement"
_MASS_ENERGY_ENERGY_SOURCE = "the governing reaction energy balance or calibrated energy record"
_NUCLIDE_SOURCE = "the identified nuclide and its verified nucleon count"


class _MassEnergyInputError(RefusalError, ValueError):
    """A mass-energy input that cannot be used without correction."""


def _mass_energy_refusal(message: str, *, subject: str, source: str) -> _MassEnergyInputError:
    return _MassEnergyInputError(
        message,
        remedies=(Remedy(action="replace", subject=subject, source=source),),
    )


def _mass_energy_input_source(name: str) -> str:
    if name == "mass":
        return _MASS_ENERGY_MASS_SOURCE
    return _MASS_ENERGY_ENERGY_SOURCE


__all__ = [
    "binding_energy_per_nucleon",
    "rest_energy",
    "mass_from_energy",
]


def rest_energy(*, mass: Quantity) -> Quantity:
    """The rest energy of a mass, E = m*c^2.

    The energy equivalent of a ``mass`` m: E = m*c^2. For a whole object this is its rest energy;
    for the mass defect of a nuclear reaction it is the energy released — about 90 TJ per gram,
    which is why nuclear processes dwarf chemical ones. Returns the energy in J.
    """
    _check(mass, "[mass]", "mass")
    m = mass.to("kg").magnitude
    if m < 0:
        raise _mass_energy_refusal(
            "mass must be non-negative", subject="mass", source=_MASS_ENERGY_MASS_SOURCE
        )
    return Quantity(magnitude=m * _SPEED_OF_LIGHT * _SPEED_OF_LIGHT, unit="J")


def mass_from_energy(*, energy: Quantity) -> Quantity:
    """The mass equivalent of an energy, m = E/c^2.

    The inverse of :func:`rest_energy`: the mass an ``energy`` E is equivalent to, m = E/c^2. It is
    the (tiny) mass an energetic photon or reaction carries, and the mass a system loses when it
    radiates energy away. Returns the mass in kg.
    """
    _check(energy, "[energy]", "energy")
    e = energy.to("J").magnitude
    if e < 0:
        raise _mass_energy_refusal(
            "energy must be non-negative", subject="energy", source=_MASS_ENERGY_ENERGY_SOURCE
        )
    return Quantity(magnitude=e / (_SPEED_OF_LIGHT * _SPEED_OF_LIGHT), unit="kg")


def binding_energy_per_nucleon(*, binding_energy: Quantity, nucleon_count: int) -> Quantity:
    """The binding energy per nucleon, B/A.

    The nuclear ``binding_energy`` B divided by the ``nucleon_count`` A: B/A. It measures how tight
    a nucleus is bound and peaks near iron (about 8.8 MeV/nucleon), so fusing light nuclei or
    fissioning heavy ones toward the peak both release energy. Returns the binding energy per
    nucleon as an energy (report in MeV).
    """
    _check(binding_energy, "[energy]", "binding_energy")
    b = binding_energy.to("J").magnitude
    if b < 0:
        raise _mass_energy_refusal(
            "binding_energy must be non-negative",
            subject="binding_energy",
            source=_MASS_ENERGY_ENERGY_SOURCE,
        )
    if nucleon_count < 1:
        raise _mass_energy_refusal(
            "nucleon_count must be a positive integer",
            subject="nucleon_count",
            source=_NUCLIDE_SOURCE,
        )
    return Quantity(magnitude=b / nucleon_count, unit="J")


def _check(value: Quantity, expected: str, name: str) -> None:
    if not isinstance(value, Quantity):
        raise _mass_energy_refusal(
            f"{name} must be a {expected} quantity; got {value!r}",
            subject=name,
            source=_mass_energy_input_source(name),
        )
    if not value.has_dimension(expected):
        raise _mass_energy_refusal(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})",
            subject=name,
            source=_mass_energy_input_source(name),
        )
    # The dimension is the easy half. Every comparison with NaN is False, so a NaN walks
    # past whatever `<= 0` guard follows; an infinity passes it too and then divides to
    # zero or overflows an `int()`. The `_require` helper in forty-eight sibling modules
    # has called this since it was written and this one, in a hundred and sixty-four, did
    # not — the same helper in two generations.
    require_finite(value, name=name)
