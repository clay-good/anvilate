"""Worked example: a glass-filled clip loses a third of its grip in a hot summer.

A PA66-GF30 snap-fit clip holds a panel with 40 N at assembly, its modulus then 6,000 MPa.
Parked in the sun it spends 1,000 hours at 85 °C over its life, and the held deflection
relaxes: the supplier's creep data put the apparent modulus at 4,000 MPa there, so the clip
holds 26.67 N, 0.67 of what it started with.

After 300 hours the record's points at 100 and 1,000 hours bracket the time, and the modulus
interpolated in log time gives 28.41 N. Ask for 20,000 hours and the record, which
stops at 10,000, cannot answer: the screen says so rather than extrapolate a creep curve.

The creep data here are illustrative, not a supplier's.

Run it directly (``python examples/clip_retention.py``);
:func:`clip_retention` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import CreepModulusPoint, CreepModulusRecord, retention_after_creep
from anvilate.units import Quantity

RECORD = CreepModulusRecord(
    temperature=Quantity(magnitude=85.0, unit="degC"),
    points=tuple(
        CreepModulusPoint(hours=h, modulus=Quantity(magnitude=e, unit="MPa"))
        for h, e in ((1, 5_500), (10, 5_000), (100, 4_500), (1_000, 4_000), (10_000, 3_600))
    ),
    source="supplier creep data, PA66-GF30 conditioned, 85 °C (illustrative)",
)


def _retain(hours: float):
    return retention_after_creep(
        initial_force=Quantity(magnitude=40.0, unit="N"),
        short_term_modulus=Quantity(magnitude=6_000.0, unit="MPa"),
        temperature=Quantity(magnitude=85.0, unit="degC"),
        hours=hours,
        records=[RECORD],
    )


def clip_retention() -> dict[str, float | str]:
    """Return the retained force at 1,000 h and 300 h, and the 20,000 h verdict."""
    summer, early, beyond = _retain(1_000), _retain(300), _retain(20_000)
    return {
        "force_n": summer.force or 0.0,
        "fraction": summer.fraction or 0.0,
        "force_300_n": early.force or 0.0,
        "beyond": beyond.reason or "",
    }


def main() -> None:
    d = clip_retention()
    print(f"after 1,000 h at 85 °C: {d['force_n']:.2f} N ({d['fraction']:.2f} of 40 N)")
    print(f"after 300 h: {d['force_300_n']:.2f} N")
    print(f"after 20,000 h: {d['beyond']}")


if __name__ == "__main__":
    main()
