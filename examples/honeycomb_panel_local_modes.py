"""Worked example: a honeycomb panel that dimples before it wrinkles.

An aluminium-faced honeycomb panel, 0.25 mm facings on a 12.7 mm core with 9.5 mm cells,
carries 60 MPa in its facings. NASA CR-1457 gives the intracell dimpling stress as
106.5 MPa and, with the core's waviness unknown, a lower-bound wrinkling stress of
212.2 MPa. Dimpling governs, at 0.56 of its allowable. CR-1457 is plain
that its dimpling coefficient is a fit and not a lower bound, and that dimpling is not
failure, so the screen carries both remarks.

A finer 4.8 mm cell raises dimpling to 417.3 MPa and hands the panel to
wrinkling, which no cell size touches. Shear crimping, at 3,961 MPa, is far away on
either core.

The properties are illustrative (E_f 70 GPa, core 300 MPa normal and 150 MPa shear
moduli), not a material record's.

Run it directly (``python examples/honeycomb_panel_local_modes.py``);
:func:`honeycomb_panel_local_modes` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import CoreKind, SandwichPanel, sandwich_local_modes
from anvilate.units import Quantity


def _q(v: float, unit: str) -> Quantity:
    return Quantity(magnitude=v, unit=unit)


def _screen(cell_mm: float):
    panel = SandwichPanel(
        facing_modulus=_q(70_000, "MPa"), facing_poisson=0.3, facing_thickness=_q(0.25, "mm"),
        core_thickness=_q(12.7, "mm"), core_kind=CoreKind.HONEYCOMB,
        core_normal_modulus=_q(300, "MPa"), core_shear_modulus=_q(150, "MPa"),
        cell_size=_q(cell_mm, "mm"),
    )  # fmt: skip
    return sandwich_local_modes(panel, facing_stress=_q(60, "MPa"))


def _allowable(screen, name: str) -> float:
    return next(m.allowable for m in screen.modes if m.mode == name)


def honeycomb_panel_local_modes() -> dict[str, float | str]:
    """Return each mode's allowable on the coarse and fine cores, and what governs."""
    coarse, fine = _screen(9.5), _screen(4.8)
    dimpling = _allowable(coarse, "intracell dimpling")
    return {
        "dimpling_mpa": dimpling,
        "wrinkling_mpa": _allowable(coarse, "face wrinkling"),
        "dimpling_ratio": 60.0 / dimpling,
        "governing_coarse": coarse.governing or "",
        "dimpling_fine_mpa": _allowable(fine, "intracell dimpling"),
        "governing_fine": fine.governing or "",
        "crimping_mpa": _allowable(coarse, "shear crimping"),
    }


def main() -> None:
    d = honeycomb_panel_local_modes()
    print(f"9.5 mm cells: dimpling {d['dimpling_mpa']:.1f} MPa")
    print(f"wrinkling: {d['wrinkling_mpa']:.1f} MPa")
    print(f"governs: {d['governing_coarse']} at {d['dimpling_ratio']:.2f} of its allowable")
    print(f"4.8 mm cells: dimpling {d['dimpling_fine_mpa']:.1f} MPa")
    print(f"governs: {d['governing_fine']}")
    print(f"shear crimping: {d['crimping_mpa']:,.0f} MPa")


if __name__ == "__main__":
    main()
