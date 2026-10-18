"""Worked example: a handheld dropped onto a hard floor, and what its circuit board feels.

A 0.4 kg handheld falls 1.2 m and lands with 4.71 J. On a contact stiffness of
500 kN/m (the housing's corner on a hard floor, the caller's estimate) the impact is a
half-sine pulse of 2.81 ms peaking at 553.1 g.

The circuit board, 50 g on standoffs with a 300 Hz first mode, does not feel that peak.
Its mode and the pulse are close to the worst ratio, so the half-sine shock spectrum
amplifies the pulse by 1.77, and the board sees 977.4 g, a 479.2 N
load on its standoffs. Stiffened to 1,200 Hz, the board rides the pulse much more nearly
rigidly, at 1.17 times the peak.

The contact stiffness is the weakest number here, and every result is labelled an
estimate. A drop test measures what this predicts.

Run it directly (``python examples/handheld_drop.py``);
:func:`handheld_drop` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import MountedItem, drop_screen
from anvilate.units import Quantity


def _drop(board_hz: float):
    board = MountedItem(
        name="board", mass=Quantity(magnitude=0.05, unit="kg"),
        natural_frequency=Quantity(magnitude=board_hz, unit="Hz"),
    )  # fmt: skip
    return drop_screen(
        mass=Quantity(magnitude=0.4, unit="kg"), height=Quantity(magnitude=1.2, unit="m"),
        contact_stiffness=Quantity(magnitude=500_000.0, unit="N/m"), items=[board],
    )  # fmt: skip


def handheld_drop() -> dict[str, float]:
    """Return the drop's energy, pulse, peak, and the board's load at 300 and 1,200 Hz."""
    soft, stiff = _drop(300.0), _drop(1_200.0)
    (board,) = soft.items
    (stiff_board,) = stiff.items
    return {
        "energy_j": soft.energy,
        "pulse_ms": soft.pulse_duration * 1000,
        "peak_g": soft.peak_deceleration_g,
        "amplification": board.amplification,
        "board_g": board.peak_acceleration_g,
        "board_load_n": board.load,
        "stiff_amplification": stiff_board.amplification,
    }


def main() -> None:
    d = handheld_drop()
    print(f"energy {d['energy_j']:.2f} J; pulse {d['pulse_ms']:.2f} ms at {d['peak_g']:.1f} g")
    print(f"board at 300 Hz: x{d['amplification']:.2f}, {d['board_g']:.1f} g")
    print(f"board load: {d['board_load_n']:.1f} N")
    print(f"board at 1,200 Hz: x{d['stiff_amplification']:.2f}")


if __name__ == "__main__":
    main()
