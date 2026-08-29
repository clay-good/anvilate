"""Tests for the industrial pack: CoverPlate declaration and auto-dispatch."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from anvilate.packs.industrial import CoverPlate, PlateEdge, screen_cover_plate
from anvilate.scorecard import CheckStatus
from anvilate.units import Quantity


def _q(text: str) -> Quantity:
    return Quantity.parse(text)


def _rect(edge: PlateEdge = PlateEdge.SIMPLY_SUPPORTED, **overrides) -> CoverPlate:
    fields = {
        "name": "cover",
        "pressure": _q("50 kPa"),
        "thickness": _q("6 mm"),
        "material": "ASTM-A36",
        "edge": edge,
        "length": _q("500 mm"),
        "width": _q("500 mm"),
    }
    fields.update(overrides)
    return CoverPlate(**fields)


def _round(edge: PlateEdge = PlateEdge.SIMPLY_SUPPORTED, **overrides) -> CoverPlate:
    fields = {
        "name": "blank",
        "pressure": _q("50 kPa"),
        "thickness": _q("6 mm"),
        "material": "ASTM-A36",
        "edge": edge,
        "diameter": _q("500 mm"),
    }
    fields.update(overrides)
    return CoverPlate(**fields)


def test_rectangular_covers_dispatch_by_edge_condition():
    # 500x500x6 A36 under 50 kPa: simply supported the Navier centre stress is
    # 99.8 MPa (SF 2.51); clamped the Roark edge stress is 106.9 MPa (SF 2.34)
    # — the clamped square's peak stress is HIGHER even as it deflects 3.2x
    # less, and each entry cites the theory it ran.
    ss = screen_cover_plate(_rect(), required_safety_factor=2.0)
    assert ss.entries[0].passed
    assert "safety factor 2.51" in ss.entries[0].detail
    assert ss.entries[0].reference == "Kirchhoff plate theory (Navier series)"
    clamped = screen_cover_plate(_rect(PlateEdge.CLAMPED), required_safety_factor=2.0)
    assert clamped.entries[0].passed
    assert "safety factor 2.34" in clamped.entries[0].detail
    assert clamped.entries[0].reference == "Roark's Formulas, Table 11.4"


def test_circular_covers_dispatch_by_edge_condition():
    # The O500 blank: simply supported 107.4 MPa (SF 2.33), clamped 65.1 MPa
    # (SF 3.84) at the rim.
    ss = screen_cover_plate(_round(), required_safety_factor=2.0)
    assert "safety factor 2.33" in ss.entries[0].detail
    clamped = screen_cover_plate(_round(PlateEdge.CLAMPED), required_safety_factor=2.0)
    assert "safety factor 3.84" in clamped.entries[0].detail
    assert clamped.entries[0].reference == "Timoshenko plate theory"


def test_deflection_limit_adds_the_flatness_screen():
    # Without a limit there is one entry; with a 2 mm limit the SS cover's
    # 3.21 mm centre deflection fails the flatness screen.
    bare = screen_cover_plate(_rect(), required_safety_factor=2.0)
    assert len(bare.entries) == 1
    limited = screen_cover_plate(_rect(deflection_limit=_q("2 mm")), required_safety_factor=2.0)
    flatness = next(e for e in limited.entries if "flatness" in e.name)
    assert flatness.status is CheckStatus.FAIL
    assert "deflection 3.209" in flatness.detail


def test_patch_footprint_dispatches_the_patch_check():
    # The 5 kN machine foot from the analysis worked example (0.5 MPa on a
    # centred 100x100 pad of a 500x500x6 panel): sigma 177.0 MPa -> the
    # bending screen FAILs at 2.0 where the same load smeared passed 6.26.
    card = screen_cover_plate(
        _rect(
            pressure=_q("0.5 MPa"),
            patch_length=_q("100 mm"),
            patch_width=_q("100 mm"),
        ),
        required_safety_factor=2.0,
    )
    assert card.entries[0].status is CheckStatus.FAIL
    assert "safety factor 1.41" in card.entries[0].detail


def test_patch_footprint_is_restricted_to_the_encoded_case():
    with pytest.raises(ValidationError, match="needs both patch_length and patch_width"):
        _rect(patch_length=_q("100 mm"))
    with pytest.raises(ValidationError, match="only encoded for a simply-supported"):
        _rect(
            edge=PlateEdge.CLAMPED,
            patch_length=_q("100 mm"),
            patch_width=_q("100 mm"),
        )
    with pytest.raises(ValidationError, match="only encoded for a simply-supported"):
        _round(patch_length=_q("100 mm"), patch_width=_q("100 mm"))


def test_cover_geometry_must_be_declared_exactly_one_way():
    with pytest.raises(ValidationError, match="length/width for a rectangle OR diameter"):
        _rect(diameter=_q("500 mm"))
    with pytest.raises(ValidationError, match="needs both length and width"):
        _rect(width=None)
    with pytest.raises(ValidationError, match="declare the plan geometry"):
        CoverPlate(
            name="cover",
            pressure=_q("50 kPa"),
            thickness=_q("6 mm"),
            material="ASTM-A36",
        )


def test_cover_rejects_a_force_pressure():
    with pytest.raises(ValidationError, match="pressure must be a"):
        _rect(pressure=_q("50 N"))


def test_min_frequency_adds_the_resonance_screen():
    # The bare 500x500x6 A36 cover (mu = rho*t = 47.1 kg/m^2) rings at 115.2 Hz
    # simply supported, so a 120 Hz floor fails it; clamping the same plate
    # raises the fundamental 1.82x (gamma 35.982 vs 2*pi^2) to 209.9 Hz and
    # passes — no new field beyond the floor, the mass comes from the material.
    assert len(screen_cover_plate(_rect(), required_safety_factor=2.0).entries) == 1
    ss = screen_cover_plate(_rect(min_frequency=_q("120 Hz")), required_safety_factor=2.0)
    resonance = next(e for e in ss.entries if "resonance" in e.name)
    assert resonance.status is CheckStatus.FAIL
    assert "fundamental 115.2 Hz vs required minimum 120.0 Hz" in resonance.detail
    assert resonance.reference == "Kirchhoff plate theory (Navier eigenvalue)"
    clamped = screen_cover_plate(
        _rect(PlateEdge.CLAMPED, min_frequency=_q("120 Hz")), required_safety_factor=2.0
    )
    resonance = next(e for e in clamped.entries if "resonance" in e.name)
    assert resonance.status is CheckStatus.PASS
    assert "fundamental 209.9 Hz" in resonance.detail
    assert resonance.reference == "Kirchhoff plate theory (FD-verified eigenvalue table)"


def test_circular_resonance_dispatches_by_edge():
    # The gasketed O500 blank also rings at 115.2 Hz; welding the rim jumps it
    # the exact 10.2158/4.9351 = 2.07x eigenvalue ratio to 238.4 Hz.
    ss = screen_cover_plate(_round(min_frequency=_q("200 Hz")), required_safety_factor=2.0)
    resonance = next(e for e in ss.entries if "resonance" in e.name)
    assert resonance.status is CheckStatus.FAIL
    assert "fundamental 115.2 Hz" in resonance.detail
    clamped = screen_cover_plate(
        _round(PlateEdge.CLAMPED, min_frequency=_q("200 Hz")), required_safety_factor=2.0
    )
    resonance = next(e for e in clamped.entries if "resonance" in e.name)
    assert resonance.status is CheckStatus.PASS
    assert "fundamental 238.4 Hz" in resonance.detail
    assert resonance.reference == "Kirchhoff plate theory (Bessel eigenvalue)"


def test_min_frequency_must_be_a_frequency():
    with pytest.raises(ValidationError, match="min_frequency must be a"):
        _rect(min_frequency=_q("120 mm"))


def test_hole_dispatches_the_annular_check():
    # The O400 gasketed blind that passes a 6 bar hydro test at 16 mm
    # (SF 2.15) grows a O80 sight port: the port sheds its share of the
    # pressure, but the hole-edge hoop concentration grows the governing
    # stress 1.77x — SF 1.22, FAIL — and the entry cites the annular form.
    solid = screen_cover_plate(
        _round(thickness=_q("16 mm"), pressure=_q("0.6 MPa"), diameter=_q("400 mm")),
        required_safety_factor=1.5,
    )
    assert solid.entries[0].passed
    assert "safety factor 2.15" in solid.entries[0].detail
    ported = screen_cover_plate(
        _round(
            thickness=_q("16 mm"),
            pressure=_q("0.6 MPa"),
            diameter=_q("400 mm"),
            hole_diameter=_q("80 mm"),
        ),
        required_safety_factor=1.5,
    )
    assert ported.entries[0].status is CheckStatus.FAIL
    assert "safety factor 1.22" in ported.entries[0].detail
    assert ported.entries[0].reference == "Kirchhoff plate theory (axisymmetric closed form)"


def test_hole_is_restricted_to_the_encoded_cases():
    with pytest.raises(ValidationError, match="only encoded for a circular cover"):
        _rect(hole_diameter=_q("80 mm"))
    with pytest.raises(ValidationError, match="hole_diameter must be a"):
        _round(hole_diameter=_q("80 kPa"))


def test_holed_cover_resonance_uses_the_annular_eigenvalue():
    # The O500 blank with a O150 port (b/a = 0.3, the bottom of the
    # eigenvalue dip): the solid blank rang at 115.2 Hz, the ported one at
    # 108.8 — the hole LOWERS a gasketed cover's fundamental. Welding the rim
    # jumps the annular eigenvalue to 11.424 (266.6 Hz).
    ss = screen_cover_plate(
        _round(hole_diameter=_q("150 mm"), min_frequency=_q("120 Hz")),
        required_safety_factor=2.0,
    )
    resonance = next(e for e in ss.entries if "resonance" in e.name)
    assert resonance.status is CheckStatus.FAIL
    assert "fundamental 108.8 Hz" in resonance.detail
    assert resonance.reference == "Kirchhoff plate theory (FD-verified eigenvalue table)"
    clamped = screen_cover_plate(
        _round(PlateEdge.CLAMPED, hole_diameter=_q("150 mm"), min_frequency=_q("120 Hz")),
        required_safety_factor=2.0,
    )
    resonance = next(e for e in clamped.entries if "resonance" in e.name)
    assert resonance.status is CheckStatus.PASS
    assert "fundamental 266.6 Hz" in resonance.detail


# --- the page that documents this pack ------------------------------------------------------


def _covers_page() -> str:
    from pathlib import Path

    return (Path(__file__).resolve().parent.parent / "docs" / "industrial-covers.md").read_text(
        encoding="utf-8"
    )


def _page_cover(edge: PlateEdge) -> CoverPlate:
    """The page's own declared cover, read out of its code block."""
    import re

    page = _covers_page()
    block = page[page.index("```python") : page.index("```", page.index("```python") + 9)]

    def quantity(field: str) -> Quantity:
        found = re.search(rf'{field}=Quantity\.parse\("([^"]+)"\)', block)
        assert found is not None, f"{field} has moved on the covers page"
        return Quantity.parse(found.group(1))

    return CoverPlate(
        name=re.search(r'name="([^"]+)"', block).group(1),
        pressure=quantity("pressure"),
        thickness=quantity("thickness"),
        material=re.search(r'material="([^"]+)"', block).group(1),
        edge=edge,
        length=quantity("length"),
        width=quantity("width"),
        deflection_limit=quantity("deflection_limit"),
    )


def test_the_covers_page_quotes_the_packs_own_verdicts():
    """`industrial` shipped with no page, and was excused from the pack-documentation gate
    with a reason that was not true. Every figure on its page is now recomputed."""
    import re

    page = _covers_page()
    required = float(re.search(r"required_safety_factor=([\d.]+)", page).group(1))

    supported = screen_cover_plate(
        _page_cover(PlateEdge.SIMPLY_SUPPORTED), required_safety_factor=required
    )
    clamped = screen_cover_plate(_page_cover(PlateEdge.CLAMPED), required_safety_factor=required)

    quoted = re.findall(r"safety factor ([\d.]+) vs required minimum ([\d.]+)", page)
    assert len(quoted) == 2, quoted
    for card, (factor, minimum) in zip((supported, clamped), quoted, strict=True):
        bending = next(e for e in card.entries if "bending" in e.name)
        assert bending.safety_factor == pytest.approx(float(factor), abs=5e-3)
        assert float(minimum) == pytest.approx(required)

    deflections = re.findall(r"deflection ([\d.]+) mm vs limit ([\d.]+) mm", page)
    assert len(deflections) == 2, deflections
    for card, (shown, limit) in zip((supported, clamped), deflections, strict=True):
        flatness = next(e for e in card.entries if "flatness" in e.name)
        assert shown in flatness.detail and limit in flatness.detail, flatness.detail

    # The page's argument, not just its numbers: the cover passes on stress and fails on
    # stiffness, and clamping the rim fixes it.
    assert supported.status is CheckStatus.FAIL
    assert clamped.status is CheckStatus.PASS
    assert next(e for e in supported.entries if "bending" in e.name).status is CheckStatus.PASS


def test_clamping_cuts_the_deflection_by_the_factor_the_page_claims():
    """ "Clamping cuts the deflection by more than a factor of three" — the largest single
    lever on the page, so it is the one asserted rather than described."""
    import re

    page = _covers_page()
    claimed = re.search(r"by more than a factor of (\w+)", page).group(1)
    assert claimed == "three", claimed

    def deflection(edge: PlateEdge) -> float:
        card = screen_cover_plate(_page_cover(edge), required_safety_factor=2.0)
        entry = next(e for e in card.entries if "flatness" in e.name)
        return float(re.search(r"deflection ([\d.]+) mm", entry.detail).group(1))

    ratio = deflection(PlateEdge.SIMPLY_SUPPORTED) / deflection(PlateEdge.CLAMPED)
    assert ratio > 3.0, ratio


def test_the_citation_changes_with_the_edge_as_the_page_says():
    """Navier series for the simply supported case, Roark's table for the clamped one — and
    the page names both, so an entry citing something else fails here."""
    import re
    from collections import Counter

    page = _covers_page()
    # Per output block, not per page. The page shows the citation twice — once under each
    # edge condition — so "the reference appears somewhere" passes while one of the two is
    # wrong, which is exactly what the first version of this let through.
    blocks = re.findall(r"```text\n((?:.|\n)*?)```", page)
    assert len(blocks) == 2, f"the covers page has {len(blocks)} output blocks"

    cards = [
        screen_cover_plate(_page_cover(edge), required_safety_factor=2.0)
        for edge in (PlateEdge.SIMPLY_SUPPORTED, PlateEdge.CLAMPED)
    ]
    for card, block in zip(cards, blocks, strict=True):
        # Counted, not merely present: this block shows the same citation under both of its
        # entries, so "the reference appears in the block" passes while one of the two lines
        # is wrong — which is what the previous two versions of this let through.
        for entry in card.entries:
            assert entry.reference, f"{entry.name} names no source"
        wanted = Counter(entry.reference for entry in card.entries)
        for reference, count in wanted.items():
            assert block.count(reference) == count, (
                f"{reference!r} appears {block.count(reference)} times in its block; "
                f"{count} entries cite it"
            )
    assert cards[0].entries[0].reference != cards[1].entries[0].reference


def test_a_cover_with_no_deflection_limit_carries_no_flatness_entry():
    """ "a plate with no stated flatness requirement genuinely has none to screen against" —
    the card carries the bending check alone rather than an entry with a made-up threshold.
    """
    page = _covers_page()
    assert "made-up threshold" in page
    bare = _page_cover(PlateEdge.SIMPLY_SUPPORTED).model_copy(update={"deflection_limit": None})
    card = screen_cover_plate(bare, required_safety_factor=2.0)
    assert not any("flatness" in entry.name for entry in card.entries)
    assert any("bending" in entry.name for entry in card.entries)
