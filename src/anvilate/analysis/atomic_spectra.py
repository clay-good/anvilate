"""T1 analytical hydrogen-like atomic-spectra (Bohr model) checks (closed-form).

The Bohr model pictures an electron in fixed circular orbits around a nucleus, each with a definite
radius and energy set by an integer quantum number. Jumps between these levels emit or absorb light
at sharp wavelengths — the line spectra that identify elements in a flame, a star, or a discharge
lamp. It captures hydrogen and other one-electron ions well enough for T1 screening, complementing
the light-quantum view of :mod:`anvilate.analysis.photon` (which gives a photon's energy from its
wavelength, without saying which transitions are allowed).

For a nucleus of charge Z with one electron, the orbit energy is E_n = −13.606·Z²/n² eV, negative
(bound) and rising toward zero as the level n increases; the ground state of hydrogen sits at
−13.6 eV. The orbit radius grows as r_n = n²·a₀/Z, from the Bohr radius a₀ ≈ 52.9 pm. A transition
between levels n₁ < n₂ emits a photon whose wavelength follows the Rydberg formula
1/λ = R·Z²·(1/n₁² − 1/n₂²) — the 656 nm red line of hydrogen's Balmer series comes from 3 → 2.
Inputs and outputs are dimension-checked :class:`~anvilate.units.Quantity` values.

Sources: Griffiths, *Introduction to Quantum Mechanics* (the hydrogen atom) — the Bohr energy
levels and orbit radii, the Rydberg formula for a transition wavelength, and Moseley's law for a
K-alpha line.
"""

from __future__ import annotations

from ..units import Quantity

_RYDBERG_ENERGY_EV = 13.605693  # eV, hydrogen ground-state binding energy
_RYDBERG_CONSTANT = 1.0973731568e7  # 1/m
_BOHR_RADIUS = 5.29177210903e-11  # m

__all__ = [
    "bohr_energy_level",
    "bohr_orbit_radius",
    "moseley_k_alpha_wavelength",
    "rydberg_transition_wavelength",
]


def bohr_energy_level(*, principal_quantum_number: int, atomic_number: int = 1) -> Quantity:
    """The Bohr energy level, E_n = −13.606·Z²/n² eV.

    The energy of the electron in level ``principal_quantum_number`` n of a hydrogen-like ion of
    ``atomic_number`` Z (1 for hydrogen): E_n = −13.606·Z²/n² eV. It is negative (the electron is
    bound) and climbs toward zero as n grows; n = 1 is the ground state. Returns the energy in eV.
    """
    if principal_quantum_number < 1:
        raise ValueError("principal_quantum_number must be a positive integer")
    if atomic_number < 1:
        raise ValueError("atomic_number must be a positive integer")
    e = -_RYDBERG_ENERGY_EV * atomic_number**2 / principal_quantum_number**2
    return Quantity(magnitude=e, unit="eV")


def bohr_orbit_radius(*, principal_quantum_number: int, atomic_number: int = 1) -> Quantity:
    """The Bohr orbit radius, r_n = n²·a₀/Z.

    The radius of the electron's orbit in level ``principal_quantum_number`` n of a hydrogen-like
    ion of ``atomic_number`` Z: r_n = n²·a₀/Z, with the Bohr radius a₀ ≈ 52.9 pm. The orbits grow
    as n² and shrink with the nuclear charge Z. Returns the radius in m.
    """
    if principal_quantum_number < 1:
        raise ValueError("principal_quantum_number must be a positive integer")
    if atomic_number < 1:
        raise ValueError("atomic_number must be a positive integer")
    r = principal_quantum_number**2 * _BOHR_RADIUS / atomic_number
    return Quantity(magnitude=r, unit="m")


def rydberg_transition_wavelength(
    *, lower_level: int, upper_level: int, atomic_number: int = 1
) -> Quantity:
    """The Rydberg transition wavelength, 1/λ = R·Z²·(1/n₁² − 1/n₂²).

    The wavelength of light emitted (or absorbed) when the electron of a hydrogen-like ion of
    ``atomic_number`` Z moves between the ``lower_level`` n₁ and the ``upper_level`` n₂ (n₁ < n₂):
    1/λ = R·Z²·(1/n₁² − 1/n₂²), with the Rydberg constant R. Hydrogen's Balmer 3 → 2 line lands at
    656 nm. Returns the wavelength in m.
    """
    if lower_level < 1:
        raise ValueError("lower_level must be a positive integer")
    if upper_level <= lower_level:
        raise ValueError("upper_level must exceed lower_level")
    if atomic_number < 1:
        raise ValueError("atomic_number must be a positive integer")
    inv_lambda = (
        _RYDBERG_CONSTANT * atomic_number**2 * (1.0 / lower_level**2 - 1.0 / upper_level**2)
    )
    return Quantity(magnitude=1.0 / inv_lambda, unit="m")


def moseley_k_alpha_wavelength(*, atomic_number: int) -> Quantity:
    """The characteristic K_α X-ray wavelength by Moseley's law, 1/λ = (3/4)·R·(Z − 1)².

    When an inner (K-shell) electron is knocked out and an L-shell electron drops to fill it, the
    atom emits a characteristic K_α X-ray. Moseley found its frequency rises with the square of the
    atomic number, screened by one unit of nuclear charge: 1/λ = (3/4)·R·(``atomic_number`` Z − 1)²,
    the Rydberg n = 2 → 1 transition seen by an effective charge (Z − 1). It is how Moseley ordered
    the periodic table by Z rather than atomic weight, and it underlies X-ray fluorescence element
    identification — copper's K_α is 1.54 Å. ``atomic_number`` must be at least 2. Returns the K_α
    wavelength in metres.
    """
    if atomic_number < 2:
        raise ValueError("atomic_number must be at least 2 (a K_alpha line needs an L shell)")
    inv_lambda = 0.75 * _RYDBERG_CONSTANT * (atomic_number - 1) ** 2
    return Quantity(magnitude=1.0 / inv_lambda, unit="m")
