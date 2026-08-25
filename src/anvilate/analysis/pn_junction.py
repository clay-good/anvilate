"""T1 analytical pn-junction (semiconductor device) checks (closed-form, abrupt junction).

Where p-type and n-type semiconductor meet, diffusing carriers leave behind a charged depletion
region with a built-in electric field. The potential across it, the width it occupies, and the
capacitance it presents are the foundations of every diode, transistor, and solar cell. These
underlie the Shockley current of :mod:`anvilate.analysis.diode` and the carrier transport of
:mod:`anvilate.analysis.hall_effect`, describing the electrostatics of the junction itself.

The built-in potential is V_bi = (k*T/q)*ln(N_A*N_D/n_i^2), from the acceptor and donor doping
densities N_A and N_D, the intrinsic carrier density n_i, and the absolute temperature T — about
0.7 V for a silicon junction. For an abrupt junction the depletion region spreads to a width
W = sqrt(2*eps*V_bi/q*(1/N_A + 1/N_D)), set by the permittivity eps and the doping (a lightly-doped
side depletes more). The junction stores charge like a parallel-plate capacitor of that gap,
C/A = eps/W per unit area — the voltage-dependent capacitance that tunes a varactor.

Sources: Sedra & Smith, *Microelectronic Circuits* (the pn junction) — the built-in potential
from the doping levels, the depletion width under bias, the junction capacitance per unit area,
and the peak field in the depletion region.
"""

from __future__ import annotations

from math import log, sqrt

from ..units import Quantity

_BOLTZMANN = 1.380649e-23  # J/K
_ELEMENTARY_CHARGE = 1.602176634e-19  # C

__all__ = [
    "junction_peak_electric_field",
    "built_in_potential",
    "depletion_width",
    "junction_capacitance_per_area",
]


def built_in_potential(
    *,
    acceptor_density: Quantity,
    donor_density: Quantity,
    intrinsic_density: Quantity,
    temperature: Quantity,
) -> Quantity:
    """The junction built-in potential, V_bi = (k*T/q)*ln(N_A*N_D/n_i^2).

    The equilibrium potential across a pn junction, from the ``acceptor_density`` N_A,
    ``donor_density`` N_D, ``intrinsic_density`` n_i, and absolute ``temperature`` T:
    V_bi = (k*T/q)*ln(N_A*N_D/n_i^2). Heavier doping raises it; about 0.7 V for silicon at room
    temperature. Returns the built-in potential in V.
    """
    _check(acceptor_density, "1/[length]**3", "acceptor_density")
    _check(donor_density, "1/[length]**3", "donor_density")
    _check(intrinsic_density, "1/[length]**3", "intrinsic_density")
    _check(temperature, "[temperature]", "temperature")
    n_a = acceptor_density.to("1/m**3").magnitude
    n_d = donor_density.to("1/m**3").magnitude
    n_i = intrinsic_density.to("1/m**3").magnitude
    t = temperature.to("K").magnitude
    if n_a <= 0 or n_d <= 0:
        raise ValueError("acceptor_density and donor_density must be positive")
    if n_i <= 0:
        raise ValueError("intrinsic_density must be positive")
    if t <= 0:
        raise ValueError("temperature must be positive (absolute temperature)")
    v_bi = (_BOLTZMANN * t / _ELEMENTARY_CHARGE) * log(n_a * n_d / (n_i * n_i))
    return Quantity(magnitude=v_bi, unit="V")


def depletion_width(
    *,
    built_in_potential: Quantity,
    permittivity: Quantity,
    acceptor_density: Quantity,
    donor_density: Quantity,
) -> Quantity:
    """The depletion width, W = sqrt(2*eps*V_bi/q*(1/N_A + 1/N_D)).

    The width of the charge-depleted region of an abrupt junction at equilibrium, from the
    ``built_in_potential`` V_bi, the semiconductor ``permittivity`` eps, and the doping densities
    ``acceptor_density`` N_A and ``donor_density`` N_D: W = sqrt(2*eps*V_bi/q*(1/N_A + 1/N_D)). The
    lightly-doped side depletes more, so the region sits mostly there. Returns the width in m.
    """
    _check(built_in_potential, "[electric_potential]", "built_in_potential")
    _check(permittivity, "[capacitance]/[length]", "permittivity")
    _check(acceptor_density, "1/[length]**3", "acceptor_density")
    _check(donor_density, "1/[length]**3", "donor_density")
    v_bi = built_in_potential.to("V").magnitude
    eps = permittivity.to("F/m").magnitude
    n_a = acceptor_density.to("1/m**3").magnitude
    n_d = donor_density.to("1/m**3").magnitude
    if v_bi <= 0:
        raise ValueError("built_in_potential must be positive")
    if eps <= 0:
        raise ValueError("permittivity must be positive")
    if n_a <= 0 or n_d <= 0:
        raise ValueError("acceptor_density and donor_density must be positive")
    w = sqrt(2.0 * eps * v_bi / _ELEMENTARY_CHARGE * (1.0 / n_a + 1.0 / n_d))
    return Quantity(magnitude=w, unit="m")


def junction_capacitance_per_area(*, permittivity: Quantity, depletion_width: Quantity) -> Quantity:
    """The junction capacitance per unit area, C/A = eps/W.

    The depletion region stores charge like a parallel-plate capacitor of gap equal to the
    ``depletion_width`` W, giving C/A = ``permittivity``/W per unit area. Because W grows under
    reverse bias, this capacitance falls with voltage — the tunable capacitance of a varactor diode.
    Returns the capacitance per area in F/m**2.
    """
    _check(permittivity, "[capacitance]/[length]", "permittivity")
    _check(depletion_width, "[length]", "depletion_width")
    eps = permittivity.to("F/m").magnitude
    w = depletion_width.to("m").magnitude
    if eps <= 0:
        raise ValueError("permittivity must be positive")
    if w <= 0:
        raise ValueError("depletion_width must be positive")
    return Quantity(magnitude=eps / w, unit="F/m**2")


def _check(value: Quantity, expected: str, name: str) -> None:
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )


def junction_peak_electric_field(
    *, built_in_potential: Quantity, depletion_width: Quantity
) -> Quantity:
    """The peak junction field, E_max = 2·V_bi/W.

    The maximum electric field in an abrupt p-n junction, reached at the metallurgical junction
    itself. The space charge is uniform on each side, so by Poisson's equation the field rises
    linearly through each depletion region to a peak at the junction, and the area under that
    triangle is the potential it supports — hence E_max = 2·V_bi/W from the
    ``built_in_potential`` V_bi and the ``depletion_width`` W that :func:`depletion_width` gives.

    This is the number that says whether a junction survives. Silicon avalanches near 30 MV/m,
    and a diode sized only by :func:`depletion_width` and :func:`junction_capacitance_per_area`
    can pass both and still break down, because neither looks at the field. At equilibrium the
    margin is usually large — a 10²³/10²¹ m⁻³ silicon junction peaks at 1.5 MV/m — but reverse
    bias adds to the potential while the width grows only as its square root, so the field climbs
    and the margin tightens fast on a varactor swept over its range.

    Pass the *total* junction potential: at equilibrium that is V_bi, and under a reverse bias V_R
    it is V_bi + V_R, with W evaluated at the same bias. The abrupt-junction assumption makes this
    an upper bound for a graded junction, which spreads the same potential over a gentler profile.
    Returns the peak field in V/m.
    """
    _check(built_in_potential, "[electric_potential]", "built_in_potential")
    _check(depletion_width, "[length]", "depletion_width")
    v = built_in_potential.to("V").magnitude
    w = depletion_width.to("m").magnitude
    if v <= 0:
        raise ValueError("built_in_potential must be positive")
    if w <= 0:
        raise ValueError("depletion_width must be positive")
    return Quantity(magnitude=2.0 * v / w, unit="V/m")
