"""EN 10365 rolled profiles by name (expand-open-design-data 2.5, 4.2)."""

from __future__ import annotations

import pytest

from anvilate.analysis.section import CrossSection
from anvilate.standards import UnknownProfileError, canonical_designation, default_profile_table
from anvilate.units import Quantity

# The anchor: area and second moments as the two public tabulations the bundled dimensions
# were read from publish them — IPE in mm² and 10⁶ mm⁴, HEA in cm² and cm⁴. These are the
# tabulations' own derived values, not the dimensions under test, so a mistyped dimension in
# the bundle moves the computed section away from them.
_IPE_PUBLISHED = {  # A mm², I_y 10⁶ mm⁴, I_z 10⁶ mm⁴
    "IPE 80": (764, 0.8014, 0.08489),
    "IPE 100": (1032, 1.710, 0.1592),
    "IPE 120": (1321, 3.178, 0.2767),
    "IPE 140": (1643, 5.412, 0.4492),
    "IPE 160": (2009, 8.693, 0.6831),
    "IPE 180": (2395, 13.17, 1.009),
    "IPE 200": (2848, 19.43, 1.424),
    "IPE 220": (3337, 27.72, 2.049),
    "IPE 240": (3912, 38.92, 2.836),
    "IPE 270": (4595, 57.90, 4.199),
    "IPE 300": (5381, 83.56, 6.038),
    "IPE 330": (6261, 117.7, 7.881),
    "IPE 360": (7273, 162.7, 10.43),
    "IPE 400": (8446, 231.3, 13.18),
    "IPE 450": (9882, 337.4, 16.76),
    "IPE 500": (11552, 482.0, 21.42),
    "IPE 550": (13442, 671.2, 26.68),
    "IPE 600": (15598, 920.8, 33.87),
}
_HEA_PUBLISHED = {  # A cm², I_y cm⁴
    "HEA 100": (21.2, 349),
    "HEA 120": (25.3, 606),
    "HEA 140": (31.4, 1030),
    "HEA 160": (38.8, 1670),
    "HEA 180": (45.3, 2510),
    "HEA 200": (53.8, 3690),
    "HEA 220": (64.3, 5410),
    "HEA 240": (76.8, 7760),
    "HEA 260": (86.8, 10450),
    "HEA 280": (97.3, 13670),
    "HEA 300": (113, 18260),
    "HEA 320": (124, 22930),
    "HEA 340": (133, 27690),
    "HEA 360": (143, 33090),
    "HEA 400": (159, 45070),
    "HEA 450": (178, 63720),
    "HEA 500": (198, 86970),
    "HEA 550": (211.8, 111932),
    "HEA 600": (226.6, 141208),
    "HEA 650": (241.6, 175178),
    "HEA 700": (260.5, 215301),
    "HEA 800": (285.8, 303442),
    "HEA 900": (320.5, 422075),
    "HEA 1000": (346.8, 553846),
}


def _mm2(value: Quantity) -> float:
    return value.to("mm**2").magnitude


def _mm4(value: Quantity | None) -> float:
    assert value is not None
    return value.to("mm**4").magnitude


def test_every_bundled_profile_reproduces_its_published_properties():
    table = default_profile_table()
    assert set(table.designations()) == set(_IPE_PUBLISHED) | set(_HEA_PUBLISHED)
    for designation, (area, strong, weak) in _IPE_PUBLISHED.items():
        section = table.get(designation).section()
        assert _mm2(section.area) == pytest.approx(area, rel=5e-4), designation
        assert _mm4(section.second_moment) / 1e6 == pytest.approx(strong, rel=1e-3), designation
        assert _mm4(section.second_moment_transverse) / 1e6 == pytest.approx(weak, rel=1e-3)
    # The HEA tabulation rounds its area to three figures, which is the looser tolerance.
    for designation, (area, strong) in _HEA_PUBLISHED.items():
        section = table.get(designation).section()
        assert _mm2(section.area) / 100 == pytest.approx(area, rel=5e-3), designation
        assert _mm4(section.second_moment) / 1e4 == pytest.approx(strong, rel=5e-3), designation


def test_the_fillets_are_what_the_plate_built_section_leaves_out():
    """Four root fillets are 4% of an IPE 200; the plate-built shape is not the profile."""
    profile = default_profile_table().get("IPE 200")
    plated = CrossSection.i_section(
        depth=profile.depth.quantity,
        flange_width=profile.flange_width.quantity,
        flange_thickness=profile.flange_thickness.quantity,
        web_thickness=profile.web_thickness.quantity,
    )
    assert _mm2(plated.area) == pytest.approx(2724.8)
    assert _mm2(profile.section().area) == pytest.approx(2848.4, abs=0.1)


def test_a_root_radius_that_cannot_fit_is_refused():
    with pytest.raises(ValueError, match="does not fit"):
        CrossSection.rolled_i_section(
            depth=Quantity.parse("200 mm"),
            flange_width=Quantity.parse("100 mm"),
            flange_thickness=Quantity.parse("8.5 mm"),
            web_thickness=Quantity.parse("5.6 mm"),
            root_radius=Quantity.parse("60 mm"),
        )


@pytest.mark.parametrize("written", ["IPE 200", "IPE200", "ipe 200", "  Ipe  200 "])
def test_a_designation_resolves_however_it_is_spaced_or_cased(written):
    assert canonical_designation(written) == "IPE 200"
    assert default_profile_table().get(written).designation == "IPE 200"


def test_a_name_the_table_does_not_hold_is_refused_with_what_it_nearly_named():
    with pytest.raises(UnknownProfileError) as refused:
        default_profile_table().get("IPE 210")
    assert "IPE 220" in refused.value.suggestions
    assert "declared by its properties" in str(refused.value)
    with pytest.raises(UnknownProfileError):
        default_profile_table().get("W12x26")


def test_every_dimension_carries_its_citation():
    profile = default_profile_table().get("HEA 300")
    citations = profile.citations()
    assert set(citations) == {
        "depth",
        "flange_width",
        "web_thickness",
        "flange_thickness",
        "root_radius",
    }
    assert all("EN 10365" in str(c.source) for c in citations.values())
    assert str(profile) == "HEA 300 (h 290, b 300, t_w 8.5, t_f 14, r 27 mm)"


_BEAM_SPEC = """
anvilate_spec: "1.3.0"
name: floor beam
description: A simply supported floor beam declared by its profile name.
units: {{value: SI, origin: user_stated}}
material: {{ref: ASTM-A36}}
manufacturing: {{process: sheet_metal}}
acceptance: {{tiers: [T1_analytical]}}
constraints: {{min_safety_factor: {{value: 1.5, origin: user_stated}}}}
element_type: beam_member
element_params:
  name: floor_beam
  section: {section}
  length: {{magnitude: 4.0, unit: m}}
  support: simply_supported
  load: {{magnitude: 20.0, unit: kN}}
  load_type: point
  material: ASTM-A36
"""


def _card(section: str):  # type: ignore[no-untyped-def]
    from anvilate.screening import screen_spec
    from anvilate.spec import load_spec_yaml

    return screen_spec(load_spec_yaml(_BEAM_SPEC.format(section=section)))


def test_a_spec_that_names_a_profile_screens_as_if_it_had_declared_the_section():
    """The front door: `section: IPE 200` reaches the beam screen as the profile's section."""
    import json

    profile = default_profile_table().get("IPE 200").section()
    explicit = json.dumps(profile.model_dump(mode="json"))
    named, declared = _card("IPE 200"), _card(explicit)
    by_name = {entry.name: entry for entry in named.entries}
    by_properties = {entry.name: entry for entry in declared.entries}
    bending = by_name["floor_beam bending"]
    assert bending.safety_factor is not None
    assert bending.safety_factor == by_properties["floor_beam bending"].safety_factor
    assert [entry.status for entry in named.entries] == [entry.status for entry in declared.entries]


def test_a_spec_that_names_an_unknown_profile_is_refused_naming_the_near_misses():
    card = _card("IPE 205")
    unevaluated = [entry for entry in card.entries if "IPE 205" in (entry.detail or "")]
    assert unevaluated, [entry.detail for entry in card.entries]
    assert "did you mean" in unevaluated[0].detail


def test_the_evidence_trail_records_where_a_named_section_came_from():
    from anvilate.evidence import provenance_for
    from anvilate.spec import load_spec_yaml

    records = provenance_for(load_spec_yaml(_BEAM_SPEC.format(section="IPE 200")))
    (section,) = [record for record in records if record.kind == "section"]
    assert section.ref == "IPE 200" and section.name == "IPE 200"
    assert any("EN 10365" in source for source in section.sources)
    properties = (
        "{area: {magnitude: 2848, unit: mm**2}, second_moment: {magnitude: 1.943e7, "
        "unit: mm**4}, extreme_fibre: {magnitude: 100, unit: mm}}"
    )
    declared = provenance_for(load_spec_yaml(_BEAM_SPEC.format(section=properties)))
    # A section declared by its properties came from the document, not the table.
    assert not [record for record in declared if record.kind == "section"]
