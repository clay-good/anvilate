"""Rainflow counting against NASA CR-181942's worked example, and the invariants it obeys.

CR-181942 (Khosrovaneh and Dowling, 1989; NTRS 19900006166, public use permitted) counts
the ASTM E1049 history −2, 1, −3, 5, −1, 3, −4, 4, −2 as a repeating block in its
Table 1 and program output: ranges 4, 3, 7, 9 with means 1, −0.5, 0.5, 0.5, one cycle
each. The open form has no public primary example; it is held to the result the two
MIT-licensed reference implementations (iamlikeme/rainflow, pawelkn/rainflow) test for
the same history, and to invariants every count must keep.
"""

from __future__ import annotations

import random

import pytest

from anvilate.analysis.rainflow import rainflow_count
from anvilate.refusal import RefusalError
from anvilate.units import Quantity

_E1049 = (-2, 1, -3, 5, -1, 3, -4, 4, -2)


def _mpa(values) -> list[Quantity]:
    return [Quantity(magnitude=float(v), unit="MPa") for v in values]


def test_cr181942_table_1_repeating_block():
    count = rainflow_count(_mpa(_E1049), repeating=True)
    got = [(c.range, c.mean, c.count) for c in count.cycles]
    assert got == [(4, 1.0, 1.0), (3, -0.5, 1.0), (7, 0.5, 1.0), (9, 0.5, 1.0)]
    assert count.residual == (5.0,) and count.total_cycles == 4


def test_the_open_form_matches_the_reference_implementations():
    count = rainflow_count(_mpa(_E1049), repeating=False)
    got = [(c.range, c.mean, c.count) for c in count.cycles]
    assert got == [(3, -0.5, 0.5), (4, -1.0, 0.5), (4, 1.0, 1.0), (8, 1.0, 0.5),
                   (9, 0.5, 0.5), (8, 0.0, 0.5), (6, 1.0, 0.5)]  # fmt: skip
    assert count.histogram() == ((9, 0.5), (8, 1.0), (6, 0.5), (4, 1.5), (3, 0.5))
    assert count.residual == (5.0, -4.0, 4.0, -2.0)
    assert "residual" in str(count) and "ASTM E1049" in str(count)


def test_a_repeating_count_starting_at_its_extreme_is_the_same_wherever_the_block_starts():
    rotated = (5, -1, 3, -4, 4, -2, 1, -3, 5)
    a = rainflow_count(_mpa(_E1049), repeating=True)
    b = rainflow_count(_mpa(rotated), repeating=True)
    assert sorted((c.range, c.mean) for c in a.cycles) == sorted(
        (c.range, c.mean) for c in b.cycles
    )


@pytest.mark.parametrize("seed", range(20))
def test_invariants_on_random_histories(seed):
    rng = random.Random(seed)
    history = [rng.uniform(-100, 100) for _ in range(rng.randint(3, 60))]
    open_count = rainflow_count(_mpa(history), repeating=False)
    # every range lies within the history's span
    span = max(history) - min(history)
    assert all(0 < c.range <= span + 1e-9 for c in open_count.cycles)
    # each range between consecutive reversals is used once — a full cycle takes two, a
    # half cycle one — so an open count of n reversals is (n − 1)/2 cycles
    turns = [history[0]]
    for x in history[1:]:
        if len(turns) >= 2 and (turns[-1] - turns[-2]) * (x - turns[-1]) > 0:
            turns[-1] = x
        elif x != turns[-1]:
            turns.append(x)
    assert open_count.total_cycles == pytest.approx((len(turns) - 1) / 2)
    # the history's whole span is counted, as a half or a full cycle
    assert max(c.range for c in open_count.cycles) == pytest.approx(span)
    repeating = rainflow_count(_mpa(history), repeating=True)
    assert all(c.count == 1.0 for c in repeating.cycles)
    assert max(c.range for c in repeating.cycles) == pytest.approx(span)


def test_non_reversals_and_repeats_are_dropped_first():
    noisy = (0, 1, 2, 2, 5, 4, 3, -1, -1, 2)
    clean = (0, 5, -1, 2)
    a = rainflow_count(_mpa(noisy), repeating=False)
    b = rainflow_count(_mpa(clean), repeating=False)
    assert a.cycles == b.cycles


def test_mixed_units_are_read_in_the_first_ones():
    history = [Quantity(magnitude=1.0, unit="MPa"), Quantity(magnitude=-2000.0, unit="kPa"),
               Quantity(magnitude=3.0, unit="MPa")]  # fmt: skip
    count = rainflow_count(history, repeating=False)
    assert count.unit == "MPa" and count.histogram()[0] == (5.0, 0.5)


def test_refusals():
    with pytest.raises(RefusalError, match="fewer than two reversals"):
        rainflow_count(_mpa([1, 1, 1]), repeating=False)
    with pytest.raises(ValueError, match="history"):
        rainflow_count([Quantity(magnitude=1, unit="MPa"), Quantity(magnitude=1, unit="m")],
                       repeating=True)  # fmt: skip
    with pytest.raises(ValueError, match=r"history\[1\]"):
        rainflow_count(_mpa([1, float("nan"), 2]), repeating=False)
    with pytest.raises(RefusalError, match="repeating"):
        rainflow_count(_mpa(_E1049), repeating="yes")  # type: ignore[arg-type]


def test_the_durability_page_quotes_what_the_code_counts():
    from pathlib import Path

    page = (Path(__file__).parents[1] / "docs" / "durability-screening.md").read_text()
    assert "counts ranges 4, 3, 7 and 9, one cycle each" in page
    assert "(n − 1)/2" in page and "about 1.77 times the peak" in page
