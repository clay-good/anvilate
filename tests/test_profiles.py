"""EN 10365 rolled profiles by name (expand-open-design-data 2.5, 4.2)."""

from __future__ import annotations

import hashlib
import io
import os
from zipfile import ZIP_DEFLATED, ZipFile

import pytest

from anvilate.analysis.section import CrossSection
from anvilate.fetch import DatasetRecipe
from anvilate.standards import (
    UnknownProfileError,
    cached_aisc_profile_table,
    canonical_aisc_designation,
    canonical_channel_designation,
    canonical_designation,
    default_profile_table,
    fetch_aisc_profile_table,
)
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


def test_a_negative_root_radius_is_refused_rather_than_adding_material():
    """Every fillet term is an even power of r, so r = -5 mm made the section STRONGER than
    the plate-built shape it should have matched."""

    def build(radius: str) -> CrossSection:
        return CrossSection.rolled_i_section(
            depth=Quantity.parse("200 mm"),
            flange_width=Quantity.parse("100 mm"),
            flange_thickness=Quantity.parse("8.5 mm"),
            web_thickness=Quantity.parse("5.6 mm"),
            root_radius=Quantity.parse(radius),
        )

    with pytest.raises(ValueError, match="zero or positive"):
        build("-5 mm")
    # Zero is the plate-built section, and is allowed.
    assert _mm2(build("0 mm").area) == pytest.approx(2724.8)


def test_a_root_radius_that_cannot_fit_is_refused():
    with pytest.raises(ValueError, match="does not fit"):
        CrossSection.rolled_i_section(
            depth=Quantity.parse("200 mm"),
            flange_width=Quantity.parse("100 mm"),
            flange_thickness=Quantity.parse("8.5 mm"),
            web_thickness=Quantity.parse("5.6 mm"),
            root_radius=Quantity.parse("60 mm"),
        )


@pytest.mark.parametrize(
    ("written", "profile"),
    [
        ("IPE 200", "IPE 200"),
        ("IPE200", "IPE 200"),
        ("ipe 200", "IPE 200"),
        ("  Ipe  200 ", "IPE 200"),
        ("IPE-200", "IPE 200"),
        ("IPE_200", "IPE 200"),
        ("HEA 300", "HEA 300"),
        # EN 10365's own spelling of the H series, which the table refused before.
        ("HE 300 A", "HEA 300"),
        ("HE300A", "HEA 300"),
        ("he 300a", "HEA 300"),
    ],
)
def test_a_designation_resolves_however_it_is_written(written, profile):
    assert canonical_designation(written) == profile
    assert default_profile_table().get(written).designation == profile


@pytest.mark.parametrize("written", ["HE 300 B", "HE 300 M", "HEB 300", "IPE 2OO", "HE A 300"])
def test_a_near_spelling_of_a_profile_the_table_does_not_hold_is_not_read_as_one_it_does(written):
    """HE 300 B is a heavier section than HE 300 A; resolving it as the A would under-state it."""
    with pytest.raises(UnknownProfileError):
        default_profile_table().get(written)


def test_a_name_the_table_does_not_hold_is_refused_with_what_it_nearly_named():
    with pytest.raises(UnknownProfileError) as refused:
        default_profile_table().get("IPE 210")
    # The sizes either side, not the most similar strings (IPE 270 and IPE 240 came first).
    assert refused.value.suggestions == ["IPE 200", "IPE 220"]
    assert "declared by its properties" in str(refused.value)
    with pytest.raises(UnknownProfileError):
        default_profile_table().get("W12x26")


# Three rows of the AISC Shapes Database v16.0, as its US customary columns give them. A
# cell the workbook leaves without a number holds an en dash.
_AISC_FIXTURE_ROWS = (
    {"A": "W", "C": "W12X26", "G": 12.2, "L": 6.49, "Q": 0.23, "T": 0.38, "Y": 0.68},
    {"A": "HSS", "C": "HSS6X4X1/4", "I": 6, "K": "–", "N": 4, "X": 0.233},
    {"A": "HSS", "C": "HSS6.000X0.250", "I": "–", "K": 6, "N": "–", "X": 0.233},
    {"A": "C", "C": "C10X30", "G": 10.0, "L": 3.03, "Q": 0.673, "T": 0.436},
)
_AISC_FIXTURE_HEAD = {
    "A": "Type", "C": "AISC_Manual_Label", "G": "d", "I": "Ht", "K": "OD", "L": "bf",
    "N": "B", "Q": "tw", "T": "tf", "X": "tdes", "Y": "kdes",
}  # fmt: skip


def _test_aisc_workbook(rows: tuple[dict, ...] = _AISC_FIXTURE_ROWS) -> bytes:
    strings: list[str] = []

    def cell(column: str, number: int, value: object) -> str:
        if isinstance(value, str):
            if value not in strings:
                strings.append(value)
            return f'<c r="{column}{number}" t="s"><v>{strings.index(value)}</v></c>'
        return f'<c r="{column}{number}"><v>{value}</v></c>'

    sheet = "".join(
        f'<row r="{number}">'
        + "".join(cell(column, number, value) for column, value in row.items())
        + "</row>"
        for number, row in enumerate((_AISC_FIXTURE_HEAD, *rows), start=1)
    )
    shared = "".join(f"<si><t>{value}</t></si>" for value in strings)
    namespace = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
    output = io.BytesIO()
    with ZipFile(output, "w", ZIP_DEFLATED) as archive:
        archive.writestr(
            "xl/sharedStrings.xml",
            f'<sst xmlns="{namespace}" count="{len(strings)}" uniqueCount="{len(strings)}">'
            f"{shared}</sst>",
        )
        archive.writestr(
            "xl/worksheets/sheet2.xml",
            f'<worksheet xmlns="{namespace}"><sheetData>{sheet}</sheetData></worksheet>',
        )
    return output.getvalue()


def _test_aisc_recipe(payload: bytes) -> DatasetRecipe:
    return DatasetRecipe(
        name="aisc-shapes-database-v16.0.xlsx",
        url="https://example.invalid/aisc-shapes-database-v16.0.xlsx",
        sha256=hashlib.sha256(payload).hexdigest(),
        license="LicenseRef-AISC-Terms",
        source="AISC Shapes Database v16.0, test fixture",
        redistributable=False,
    )


def test_aisc_designations_have_one_stable_spelling():
    for written in ("W12X26", "W12x26", "w 12 x 26", " W12×26 "):
        assert canonical_aisc_designation(written) == "W12X26"
    assert canonical_aisc_designation("IPE 200") is None


def test_an_aisc_fetch_verifies_caches_and_computes_the_section_from_geometry(
    tmp_path, monkeypatch
):
    from anvilate.standards import profiles

    payload = _test_aisc_workbook()
    monkeypatch.setattr(profiles, "AISC_SHAPES_V16", _test_aisc_recipe(payload))
    table = fetch_aisc_profile_table(
        retrieved="2026-09-27",
        consent=True,
        cache_dir=tmp_path,
        opener=lambda _url: payload,
    )
    assert len(table) == 1
    profile = table.get("w12x26")
    section = profile.section()
    assert section.area.to("in**2").magnitude == pytest.approx(7.65, rel=2e-3)
    assert section.second_moment.to("in**4").magnitude == pytest.approx(204, rel=3e-3)
    assert table.provenance.redistributable is False
    assert profile.depth.citation.license == "LicenseRef-AISC-Terms"

    def no_network(_url: str) -> bytes:
        raise AssertionError("a cached AISC profile lookup touched the network")

    again = fetch_aisc_profile_table(retrieved="2026-09-28", cache_dir=tmp_path, opener=no_network)
    assert again.get("W12X26").section() == section


def test_a_rolled_hss_resolves_from_the_workbook_and_reproduces_its_tabulated_properties(
    tmp_path, monkeypatch
):
    """`HSS6X4X1/4` is 6 deep, 4 wide and a 0.233 in design wall, and the database tabulates
    A = 4.30 in², Ix = 20.9 in⁴, Iy = 11.1 in⁴ and Zx = 8.53 in³ for it; the round
    `HSS6.000X0.250`, A = 4.22, I = 17.6 and Z = 7.75. Each is computed here from the
    dimensions alone: a corner of twice the wall for the box, and none for the tube."""
    from anvilate.standards import profiles
    from anvilate.standards.profiles import canonical_hss_designation, resolve_profile

    for written in ("HSS6X4X1/4", "hss6x4x1/4", " HSS 6 x 4 x 1/4 ", "HSS6×4×1/4"):
        assert canonical_hss_designation(written) == "HSS6X4X1/4"
    for written in ("HSS6.000X0.250", "hss6x0.25", "HSS 6.0 x 0.250"):
        assert canonical_hss_designation(written) == "HSS6.000X0.250"
    for other in ("W12X26", "IPE 200", "HSS", "HSS6", "HSSAXB", "TUBE 60x4", "HSS6X4X1/4X2"):
        assert canonical_hss_designation(other) is None

    payload = _test_aisc_workbook()
    monkeypatch.setattr(profiles, "AISC_SHAPES_V16", _test_aisc_recipe(payload))
    table = fetch_aisc_profile_table(
        retrieved="2026-10-11", consent=True, cache_dir=tmp_path, opener=lambda _url: payload
    )
    assert len(table) == 1 and table.hollow_designations() == ["HSS6.000X0.250", "HSS6X4X1/4"]

    box = resolve_profile("hss6x4x1/4", cache_dir=tmp_path)
    assert str(box) == "HSS6X4X1/4 (h 152.4, b 101.6, t 5.9182 mm)"
    assert box.wall_thickness.citation.license == "LicenseRef-AISC-Terms"
    section = box.section()
    assert section.area.to("in**2").magnitude == pytest.approx(4.30, rel=2e-3)
    assert section.second_moment.to("in**4").magnitude == pytest.approx(20.9, rel=3e-3)
    assert section.second_moment_transverse.to("in**4").magnitude == pytest.approx(11.1, rel=3e-3)
    assert section.plastic_modulus.to("in**3").magnitude == pytest.approx(8.53, rel=2e-3)
    assert section.corner_radius.to("in").magnitude == pytest.approx(2 * 0.233)
    # The corners are what a box welded from plates would add: 3% of the area here.
    sharp = CrossSection.hollow_rectangular(
        width=Quantity.parse("4 in"),
        height=Quantity.parse("6 in"),
        wall_thickness=Quantity.parse("0.233 in"),
    )
    assert sharp.area.to("in**2").magnitude == pytest.approx(4 * 6 - 3.534 * 5.534)
    assert sharp.area.to("in**2").magnitude / section.area.to("in**2").magnitude == pytest.approx(
        1.0325, abs=5e-4
    )

    tube = resolve_profile("HSS6x0.25", cache_dir=tmp_path).section()
    assert tube.area.to("in**2").magnitude == pytest.approx(4.22, rel=2e-3)
    assert tube.second_moment.to("in**4").magnitude == pytest.approx(17.6, rel=3e-3)
    assert tube.plastic_modulus.to("in**3").magnitude == pytest.approx(7.75, rel=2e-3)
    assert tube.corner_radius is None and len(tube.outside) == 1

    with pytest.raises(UnknownProfileError, match="no AISC HSS record") as unknown:
        resolve_profile("HSS6X4X1/2", cache_dir=tmp_path)
    assert "did you mean HSS6X4X1/4?" in str(unknown.value)
    with pytest.raises(profiles.AiscProfileDataRequired, match="fetch aisc-shapes --consent"):
        resolve_profile("HSS6X4X1/4", cache_dir=tmp_path / "empty")


def test_every_rolled_hss_in_a_fetched_workbook_reproduces_its_tabulated_properties(monkeypatch):
    """The whole table, where the workbook has been fetched. It is not redistributable, so
    this is the check a machine with it runs; the fixture above is what runs everywhere.

    The corner of twice the wall and the flat of the outside less three walls were solved
    out of these columns, so this holds them to every row: area, both second moments and
    the plastic modulus to the three figures the database prints, and b/t and h/t."""
    from anvilate.fetch import cached_dataset
    from anvilate.packs.structural import _box_flats
    from anvilate.standards import profiles

    # The suite keeps every test out of the user's own cache, so the fetched workbook is
    # named: ANVILATE_FETCHED_DATA=~/.cache/anvilate/datasets pytest tests/test_profiles.py
    where = os.environ.get("ANVILATE_FETCHED_DATA")
    found = cached_dataset(profiles.AISC_SHAPES_V16, cache_dir=where) if where else None
    if found is None:
        pytest.skip(
            "fetch the workbook (`anvilate fetch aisc-shapes --consent`) and set "
            "ANVILATE_FETCHED_DATA to its folder to check every HSS row"
        )
    table = cached_aisc_profile_table(cache_dir=where)
    extra = {"F": "A", "AI": "b/tdes", "AK": "h/tdes", "AM": "Ix", "AN": "Zx", "AQ": "Iy"}
    for column, heading in extra.items():
        monkeypatch.setitem(profiles._AISC_COLUMNS, column, heading)
    rows = [row for row in profiles._aisc_rows(found[0]) if row["A"] == "HSS"]
    assert len(rows) == 714 == len(table.hollow_designations())
    boxes = 0
    for row in rows:
        section = table.get(row["C"]).section()
        box = section.corner_radius is not None
        boxes += box
        # A small section's three printed figures round further than a large one's.
        loose = 1.5 if float(row["F"]) < 1.5 else 1.0
        for have, column, unit, tight, round_tube in (
            (section.area, "F", "in**2", 5e-3, 8e-3),
            (section.second_moment, "AM", "in**4", 1e-2, 2e-2),
            (section.second_moment_transverse, "AQ", "in**4", 1e-2, 2e-2),
            (section.plastic_modulus, "AN", "in**3", 6e-3, 1.4e-2),
        ):
            allowed = (tight if box else round_tube) * loose
            assert have.to(unit).magnitude == pytest.approx(float(row[column]), rel=allowed), (
                row["C"],
                column,
            )
        if box:
            wall = section.wall_thickness.to("in").magnitude
            flats = [flat / 25.4 / wall for flat in _box_flats(section)]
            assert flats == pytest.approx(
                [float(row["AI"]), float(row["AK"])], rel=8e-3, abs=0.07
            ), row["C"]
    assert boxes == 525


@pytest.mark.parametrize(
    ("written", "designation"),
    [
        ("C10X30", "C10X30"),
        ("c10x30", "C10X30"),
        ("C 10 X 30", "C10X30"),
        ("C10×30", "C10X30"),
        ("MC18X51.9", "MC18X51.9"),
        ("mc18x51.9", "MC18X51.9"),
        ("C15X33.9", "C15X33.9"),
    ],
)
def test_a_channel_designation_resolves_however_it_is_written(written, designation):
    assert canonical_channel_designation(written) == designation


@pytest.mark.parametrize("written", ["W12X26", "HSS6X4X1/4", "IPE 200", "L4X4X1/2", "C10", "MC"])
def test_only_a_channel_designation_is_read_as_one(written):
    assert canonical_channel_designation(written) is None


def test_a_channel_is_computed_from_the_four_dimensions_the_workbook_gives_it(
    tmp_path, monkeypatch
):
    """`C10X30` resolves to the section its strong axis follows from, and nothing more.

    The fixture's channel row is a real one, so the properties can be read against the
    Manual's: A 8.81 in², I_x 103 in⁴, S_x 20.7 in³, and a shear centre 0.368 in off the
    back of the web. The weak axis is absent on purpose.
    """
    from anvilate.standards import profiles

    payload = _test_aisc_workbook()
    monkeypatch.setattr(profiles, "AISC_SHAPES_V16", _test_aisc_recipe(payload))
    table = fetch_aisc_profile_table(
        retrieved="2026-09-27", consent=True, cache_dir=tmp_path, opener=lambda _url: payload
    )
    assert table.channel_designations() == ["C10X30"]
    channel = table.get("c10 x 30")
    assert channel.designation == "C10X30"
    assert channel.depth.quantity.to("in").magnitude == pytest.approx(10.0)
    assert "C10X30 flange width" in channel.citations()["flange_width"].condition
    assert str(channel).startswith("C10X30 (d 254, b_f 76.96")

    section = channel.section()
    assert section.area.to("in**2").magnitude == pytest.approx(8.81, rel=3e-3)
    assert section.second_moment.to("in**4").magnitude == pytest.approx(103.0, rel=3e-3)
    assert section.section_modulus.to("in**3").magnitude == pytest.approx(20.7, rel=4e-3)
    assert section.shear_centre_offset.to("in").magnitude == pytest.approx(0.368, rel=3e-3)
    # The weak axis is withheld, so nothing downstream can read a strong axis as one.
    assert section.second_moment_transverse is None
    assert section.radius_of_gyration_transverse is None

    with pytest.raises(UnknownProfileError) as refused:
        table.get("C10X31")
    assert refused.value.suggestions == ["C10X30"]
    assert "series, depth, weight per foot" in str(refused.value)


def test_every_rolled_channel_in_a_fetched_workbook_reproduces_its_tabulated_properties(
    monkeypatch,
):
    """All 72 C and MC rows, where the workbook has been fetched.

    The sharp-cornered model is held to the strong-axis properties it claims, and to the
    direction it claims them in. A, I_x and S_x come out under the tabulated value on 69 or
    more of the 72 rows, because the root fillets add metal the sharp corner does not; the
    few that sit above it do so by no more than 0.2%, which is the three figures the
    database prints, not the model drifting. Both ends are pinned, because a model that
    drifted *above* the tabulation would be unconservative and the bound alone would not
    catch it.

    The weak axis is checked the other way: it is NOT derived, and this measures how far
    out it would be if it were, which is what the withholding rests on.
    """
    from anvilate.fetch import cached_dataset
    from anvilate.standards import profiles

    where = os.environ.get("ANVILATE_FETCHED_DATA")
    found = cached_dataset(profiles.AISC_SHAPES_V16, cache_dir=where) if where else None
    if found is None:
        pytest.skip(
            "fetch the workbook (`anvilate fetch aisc-shapes --consent`) and set "
            "ANVILATE_FETCHED_DATA to its folder to check every channel row"
        )
    table = cached_aisc_profile_table(cache_dir=where)
    extra = {"F": "A", "AD": "eo", "AM": "Ix", "AN": "Zx", "AO": "Sx", "AQ": "Iy", "AB": "x"}
    for column, heading in extra.items():
        monkeypatch.setitem(profiles._AISC_COLUMNS, column, heading)
    rows = profiles._aisc_rows(found[0], kinds=("C", "MC"))
    assert len(rows) == 72 == len(table.channel_designations())
    weak_errors: list[float] = []
    low = dict.fromkeys(("F", "AM", "AO"), 0)
    for row in rows:
        profile = table.get(row["C"])
        section = profile.section()
        depth = profile.depth.quantity
        for have, column, unit in (
            (section.area, "F", "in**2"),
            (section.second_moment, "AM", "in**4"),
            (section.section_modulus, "AO", "in**3"),
        ):
            ratio = have.to(unit).magnitude / float(row[column])
            assert 1 - 1.8e-2 <= ratio <= 1 + 2e-3, (row["C"], column, ratio)
            low[column] += ratio <= 1.0
        # The shear centre is computed, not read, and it is held tightly.
        assert section.shear_centre_offset.to("in").magnitude == pytest.approx(
            float(row["AD"]), rel=7e-3
        ), row["C"]
        # What the weak axis would be, modelled as sharp rectangles: up to 30% HIGH.
        flange = profile.flange_width.quantity.to("mm").magnitude
        web = profile.web_thickness.quantity.to("mm").magnitude
        thick = profile.flange_thickness.quantity.to("mm").magnitude
        tall = depth.to("mm").magnitude
        outstand = flange - web
        areas = ((tall * web, web / 2), (outstand * thick, web + outstand / 2))
        total = areas[0][0] + 2 * areas[1][0]
        centroid = (areas[0][0] * areas[0][1] + 2 * areas[1][0] * areas[1][1]) / total
        weak = tall * web**3 / 12 + areas[0][0] * (areas[0][1] - centroid) ** 2
        weak += 2 * (thick * outstand**3 / 12 + areas[1][0] * (areas[1][1] - centroid) ** 2)
        tabulated = float(row["AQ"]) * 25.4**4
        weak_errors.append(weak / tabulated - 1)
    # Low on nearly every row, which is the direction the sharp corner should err in.
    assert min(low.values()) >= 64, low
    assert max(weak_errors) == pytest.approx(0.30, abs=0.01)
    assert min(weak_errors) > 0.05  # every row high, so no row is safe to derive
    # The uniform-thickness shear-centre formula is not the one used, and this is why.
    from anvilate.analysis.section import channel_shear_center
    from anvilate.units import Quantity

    uniform = []
    for row in rows[:12]:
        profile = table.get(row["C"])
        web = profile.web_thickness.quantity.to("mm").magnitude
        naive = channel_shear_center(
            flange_width=Quantity(
                magnitude=profile.flange_width.quantity.to("mm").magnitude - web / 2, unit="mm"
            ),
            web_height=Quantity(
                magnitude=profile.depth.quantity.to("mm").magnitude
                - profile.flange_thickness.quantity.to("mm").magnitude,
                unit="mm",
            ),
        )
        uniform.append(abs(naive.to("in").magnitude / float(row["AD"]) - 1))
    assert max(uniform) > 0.5


def test_the_workbooks_pipe_areas_do_not_follow_from_its_own_pipe_dimensions(monkeypatch):
    """Why a pipe member is read from ASME B36.10M and not from this workbook's Pipe rows.

    A member's section is computed from dimensions, so a table it is held to has to agree
    with its own. The W and HSS rows do, to their rounding, which is what lets those shapes
    be computed. The Pipe rows do not: a third of them put the tabulated area more than half
    a percent from the area their own outside diameter and design wall make, which is why
    `_pipe_section` goes to the bundled standard instead. Reading the claim is the test; if
    a later edition fixes these rows, this fails and the sourcing can be revisited.
    """
    import math

    from anvilate.fetch import cached_dataset
    from anvilate.standards import profiles

    where = os.environ.get("ANVILATE_FETCHED_DATA")
    found = cached_dataset(profiles.AISC_SHAPES_V16, cache_dir=where) if where else None
    if found is None:
        pytest.skip(
            "fetch the workbook (`anvilate fetch aisc-shapes --consent`) and set "
            "ANVILATE_FETCHED_DATA to its folder to check the Pipe rows"
        )
    monkeypatch.setitem(profiles._AISC_COLUMNS, "F", "A")
    rows = profiles._aisc_rows(found[0], kinds=("PIPE",))
    assert len(rows) == 51
    gaps = {}
    for row in rows:
        outer, wall, tabulated = (float(row[column]) for column in ("K", "X", "F"))
        computed = math.pi * (outer**2 - (outer - 2 * wall) ** 2) / 4
        gaps[row["C"]] = (computed - tabulated) / tabulated
    assert sum(1 for gap in gaps.values() if abs(gap) > 0.005) == 18
    # The two worst rows, in both directions, named rather than counted.
    assert gaps["Pipe20XS"] == pytest.approx(0.034, abs=5e-4)
    assert gaps["Pipe10STD"] == pytest.approx(-0.033, abs=5e-4)
    assert max(abs(gap) for gap in gaps.values()) == pytest.approx(0.034, abs=5e-4)
    # The same arithmetic on the bundled standard's own dimensions is exact, which is the
    # difference that decides where pipe is read from.
    from anvilate.packs.structural import _pipe_section
    from anvilate.standards import default_pipe_schedule_table

    table = default_pipe_schedule_table()
    for designation in table.designations():
        record = table.get(*designation.removeprefix("NPS ").split(" SCH "))
        diameter = record.outside_diameter.quantity.to("mm").magnitude
        thickness = record.wall_thickness.quantity.to("mm").magnitude
        section = _pipe_section(designation)
        assert section is not None
        assert section.area.to("mm**2").magnitude == pytest.approx(
            math.pi * (diameter**2 - (diameter - 2 * thickness) ** 2) / 4, rel=1e-12
        ), designation


def test_an_absent_w_shape_suggests_the_weights_either_side_at_its_depth(tmp_path, monkeypatch):
    from anvilate.standards import profiles

    payload = _test_aisc_workbook()
    monkeypatch.setattr(profiles, "AISC_SHAPES_V16", _test_aisc_recipe(payload))
    fetched = fetch_aisc_profile_table(
        retrieved="2026-09-27", consent=True, cache_dir=tmp_path, opener=lambda _url: payload
    )
    shape = fetched.get("W12X26")
    names = ("W12X22", "W12X26", "W12X30", "W14X26", "W10X26")
    table = profiles.AiscProfileTable(dict.fromkeys(names, shape), fetched.provenance)
    with pytest.raises(UnknownProfileError) as refused:
        table.get("W12x27")
    assert refused.value.suggestions == ["W12X26", "W12X30"]
    assert "did you mean W12X26, W12X30?" in str(refused.value)


def test_a_w_shape_is_not_guessed_before_the_workbook_is_fetched(tmp_path, monkeypatch):
    monkeypatch.setenv("ANVILATE_DATA_HOME", str(tmp_path))
    assert cached_aisc_profile_table() is None
    card = _card("W12x26")
    refusal = next(entry for entry in card.entries if "W12x26" in entry.detail)
    assert refusal.status.value == "not_evaluated"
    assert "anvilate fetch aisc-shapes --consent" in refusal.detail
    assert not list(tmp_path.iterdir())


def test_a_fetched_w_shape_screens_offline_and_records_fetch_provenance(tmp_path, monkeypatch):
    import json

    from anvilate.evidence import provenance_for
    from anvilate.spec import load_spec_yaml
    from anvilate.standards import profiles

    payload = _test_aisc_workbook()
    monkeypatch.setattr(profiles, "AISC_SHAPES_V16", _test_aisc_recipe(payload))
    monkeypatch.setenv("ANVILATE_DATA_HOME", str(tmp_path))
    table = fetch_aisc_profile_table(
        retrieved="2026-09-27",
        consent=True,
        opener=lambda _url: payload,
    )
    explicit = json.dumps(table.get("W12X26").section().model_dump(mode="json"))
    named, declared = _card("W12x26"), _card(explicit)
    by_name = {entry.name: entry for entry in named.entries}
    by_properties = {entry.name: entry for entry in declared.entries}
    assert (
        by_name["floor_beam bending"].safety_factor
        == by_properties["floor_beam bending"].safety_factor
    )

    records = provenance_for(load_spec_yaml(_BEAM_SPEC.format(section="W12x26")))
    (section,) = [record for record in records if record.kind == "section"]
    assert section.ref == "W12x26"
    assert section.name == "W12X26"
    assert section.sources == ("AISC Shapes Database v16.0, test fixture",)


def test_the_aisc_recipe_fetches_and_parses_the_publisher_workbook(tmp_path):
    if not os.environ.get("ANVILATE_ALLOW_NETWORK"):
        pytest.skip("set ANVILATE_ALLOW_NETWORK=1 to exercise the real AISC recipe")

    table = fetch_aisc_profile_table(retrieved="2026-09-27", consent=True, cache_dir=tmp_path)
    assert len(table) == 289
    section = table.get("W12x26").section()
    assert section.area.to("in**2").magnitude == pytest.approx(7.65, rel=2e-3)
    assert section.second_moment.to("in**4").magnitude == pytest.approx(204, rel=3e-3)


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


@pytest.mark.parametrize("section", ["FLAT 50x10", "TUBE 60x4", "BOX 100x50x4"])
def test_a_bar_named_by_its_dimensions_keeps_the_rest_of_the_evidence_trail(section):
    """`FLAT 50x10` is no table's record, and looking it up lost every other source.

    The trail is all or nothing, so an unknown profile empties it. A bar named by its own
    dimensions is not an unknown profile: its section came from the document, and the
    material's record and the tolerance class are still where the rest came from.
    """
    from anvilate.evidence import provenance_for
    from anvilate.spec import load_spec_yaml

    def kinds(named):
        records = provenance_for(load_spec_yaml(_BEAM_SPEC.format(section=named)))
        return [(record.kind, record.ref) for record in records]

    rolled = kinds("IPE 200")
    assert ("section", "IPE 200") in rolled and len(rolled) > 1
    assert kinds(section) == [record for record in rolled if record[0] != "section"]


_STRUCTURE_SPEC = """
anvilate_spec: "1.3.0"
name: platform
description: A platform whose members name their profiles.
units: {value: SI, origin: user_stated}
material: {ref: ASTM-A36}
manufacturing: {process: sheet_metal}
acceptance: {tiers: [T1_analytical]}
constraints: {min_safety_factor: {value: 1.5, origin: user_stated}}
element_type: structure
element_params:
  members:
    - element_type: beam_member
      element_params:
        name: girder
        section: HEA 200
        length: {magnitude: 5.0, unit: m}
        support: simply_supported
        load: {magnitude: 30.0, unit: kN}
        load_type: point
        material: ASTM-A36
    - element_type: beam_member
      element_params:
        name: joist
        section: IPE 160
        length: {magnitude: 3.0, unit: m}
        support: simply_supported
        load: {magnitude: 6.0, unit: kN}
        load_type: point
        material: ASTM-A36
"""


def test_a_structure_whose_members_name_profiles_screens_them_and_records_each_source():
    """The trail read only the top-level section; a structure's members named theirs one level
    down, screened fine, and left the bundle silent about where two sections came from."""
    from anvilate.evidence import provenance_for
    from anvilate.screening import screen_spec
    from anvilate.spec import load_spec_yaml

    spec = load_spec_yaml(_STRUCTURE_SPEC)
    names = {entry.name for entry in screen_spec(spec).entries}
    assert any(name.endswith("girder bending") for name in names), names
    assert any(name.endswith("joist bending") for name in names), names
    sections = {record.ref for record in provenance_for(spec) if record.kind == "section"}
    assert sections == {"HEA 200", "IPE 160"}


@pytest.mark.parametrize(
    ("label", "build"),
    [
        (
            "a rectangle the wrong way round",
            lambda: CrossSection.rectangular(
                width=Quantity.parse("-50 mm"), height=Quantity.parse("100 mm")
            ),
        ),
        (
            "a round bar of no diameter",
            lambda: CrossSection.solid_circular(diameter=Quantity.parse("0 mm")),
        ),
        (
            "a round bar of negative diameter",
            lambda: CrossSection.solid_circular(diameter=Quantity.parse("-40 mm")),
        ),
    ],
)
def test_a_section_dimension_that_is_not_a_size_is_refused(label, build):
    """A negative width returned a negative area AND a negative second moment, which divides
    into a deflection and clears every limit; a negative diameter returned the positive
    section of its magnitude, because both terms are even powers of d."""
    with pytest.raises(ValueError, match="must be positive"):
        build()
