"""Docs pages that argue from a constant, held against the constant the library holds.

The docs-page ratchet in `test_contract.py` asks whether a page's *filename* appears in a
test. That is a substring gate: a page can be named in a test that never reads a number off
it. The behavioural sweep in `docs/contributing-analysis.md` — change a number on the page,
see whether anything fails — found these arguing from figures nothing checked.

Each page here quotes a **constant the library also holds**, so the gate is a comparison
rather than a fixture: the page is read, the library is asked, and the two must agree. A
constant re-transcribed on either side fails.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

_DOCS = Path(__file__).resolve().parent.parent / "docs"


def _page(name: str) -> str:
    return (_DOCS / name).read_text(encoding="utf-8")


def test_the_aluminum_page_quotes_the_out_of_straightness_knockdown_the_module_uses():
    """ADM §E.3's 0.85 on the elastic column curve. The page states the formula with the
    coefficient in it; the module keeps it as a named constant and nothing joined them."""
    from anvilate.analysis.aluminum import _OUT_OF_STRAIGHTNESS

    claim = re.search(r"`([\d.]+)·π²E/λ²`", _page("aluminum-screening.md"))
    assert claim is not None, "the column-curve formula on aluminum-screening.md has moved"
    assert float(claim.group(1)) == _OUT_OF_STRAIGHTNESS


def test_the_cold_formed_page_quotes_the_winter_coefficient_the_module_uses():
    """AISI S100's 1.052 in the plate slenderness. The page writes the whole expression."""
    from anvilate.analysis.cold_formed_steel import _AISI_WINTER_COEFFICIENT

    claim = re.search(r"λ = \(([\d.]+)/√k\)", _page("cold-formed-steel.md"))
    assert claim is not None, "the slenderness expression on cold-formed-steel.md has moved"
    assert float(claim.group(1)) == _AISI_WINTER_COEFFICIENT


def test_the_weld_fatigue_page_quotes_ratios_the_curve_actually_produces():
    """Δσ_D ≈ 0.737·Δσ_C at 5M and Δσ_L ≈ 0.405·Δσ_C at 100M.

    Both are consequences of the standard's own anchor points rather than tabulated
    numbers — (2/5)^(1/3) and (2/5)^(1/3)·(5/100)^(1/5) — so they are recomputed from the
    library's curve rather than looked up, and the *cycle counts* the sentence names are
    read out of it too. A page quoting the right ratio at the wrong life is still wrong.
    """
    from anvilate.analysis.fatigue import weld_detail_allowable_stress_range
    from anvilate.units import Quantity

    page = _page("weld-fatigue-screening.md")
    claim = re.search(
        r"Δσ_D ≈ ([\d.]+)·Δσ_C at (\d+)M cycles,\s*the cutoff Δσ_L ≈ ([\d.]+)·Δσ_C at (\d+)M",
        page,
    )
    assert claim is not None, "the curve-anchor sentence on weld-fatigue-screening.md has moved"
    category = 90.0
    for stated_ratio, stated_millions in (
        (claim.group(1), claim.group(2)),
        (claim.group(3), claim.group(4)),
    ):
        cycles = float(stated_millions) * 1e6
        computed = (
            weld_detail_allowable_stress_range(
                life_cycles=cycles, detail_category=Quantity.parse(f"{category} MPa")
            )
            .to("MPa")
            .magnitude
        )
        assert computed / category == pytest.approx(float(stated_ratio), abs=5e-4), (
            f"the page says {stated_ratio} at {stated_millions}M; the curve gives "
            f"{computed / category:.4f}"
        )


def test_the_lifting_devices_page_quotes_the_design_factors_the_module_documents():
    """BTH-1's N_d table. Two numbers whose whole point is that they differ by 50%, so the
    gate checks the ratio as well as the values — a page listing 2.00 twice would otherwise
    satisfy every equality."""
    from anvilate.analysis import lifting_device

    page = _page("lifting-devices.md")
    rows = re.findall(r"\*\*Design Category ([AB])\*\* \| ([\d.]+) \|", page)
    assert len(rows) == 2, "the design-factor table on lifting-devices.md has moved"
    factors = {category: float(value) for category, value in rows}
    module = lifting_device.__doc__ or ""
    for category, value in factors.items():
        assert f"Design Category {category}**, N_d = {value:.2f}" in module, (
            f"the page says Category {category} is {value:.2f}; the module says otherwise"
        )
    assert factors["B"] == pytest.approx(1.5 * factors["A"])


def test_the_gdt_page_quotes_the_half_band_the_converter_produces():
    """Ø0.2 contributes ±0.1 mm, and ±0.15 mm with 0.1 mm of bonus at MMC.

    Both are the converter's own output, so both are recomputed. The bonus half is the one
    that matters: adding a bonus to an RFS callout is refused, so a page quoting the MMC
    figure against an RFS frame would be describing a call the library will not make.
    """
    from anvilate.gdt import (
        Characteristic,
        DatumReference,
        FeatureControlFrame,
        FeatureType,
        MaterialCondition,
        position_stack_contribution,
    )
    from anvilate.units import Quantity

    page = _page("semantic-gdt.md")
    claim = re.search(
        r"Ø([\d.]+) contributes\s*±([\d.]+) mm, and at MMC with ([\d.]+) mm of bonus "
        r"earned, ±([\d.]+) mm",
        page,
    )
    assert claim is not None, "the half-band sentence on semantic-gdt.md has moved"
    zone, rfs_band, bonus, mmc_band = (float(value) for value in claim.groups())

    def _frame(condition: MaterialCondition) -> FeatureControlFrame:
        return FeatureControlFrame(
            characteristic=Characteristic.POSITION,
            tolerance=Quantity.parse(f"{zone} mm"),
            feature_type=FeatureType.FEATURE_OF_SIZE,
            material_condition=condition,
            # Position is a relationship to a datum reference frame; the frame refuses to
            # exist without one, so the page's example has one too.
            datums=(DatumReference(letter="A"),),
        )

    plain = position_stack_contribution(_frame(MaterialCondition.RFS))
    assert plain.to("mm").magnitude == pytest.approx(rfs_band)
    at_mmc = position_stack_contribution(
        _frame(MaterialCondition.MMC), bonus=Quantity.parse(f"{bonus} mm")
    )
    assert at_mmc.to("mm").magnitude == pytest.approx(mmc_band)
