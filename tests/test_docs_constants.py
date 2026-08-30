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


def test_the_uncertainty_page_rebuilds_from_its_own_inputs():
    """The page shows a runnable block and its outputs in comments beside it.

    Both halves are read off the page — the distributions in, the figures out — and the
    sampler is run between them. That is the right shape here *because the page states
    inputs and results*: reading only the results back and rebuilding from them would make
    the page its own fixture, which agrees with itself however far it drifts.
    """
    from anvilate.uncertainty import Normal, sample_margin

    page = _page("uncertainty-margins.md")
    inputs = dict(re.findall(r'"(\w+)": Normal\(mean=([\d.]+), std=', page))
    assert set(inputs) == {"load", "yield_strength", "area"}, inputs
    covs = dict(re.findall(r'"(\w+)": Normal\(mean=[\d.]+, std=([\d.]+) \* ', page))
    required = float(re.search(r"required=([\d.]+),", page).group(1))
    seed = int(re.search(r"seed=(\d+),", page).group(1))

    def response(values):
        return (values["yield_strength"] * values["area"] / 1000.0) / values["load"]

    result = sample_margin(
        response,
        {
            name: Normal(mean=float(mean), std=float(covs.get(name, 0.0)) * float(mean))
            for name, mean in inputs.items()
        },
        required=required,
        seed=seed,
    )

    printed = re.search(
        r"# (margin [\d.]+ ± [\d.]+, P\(below [\d.]+\) = [\d.]+% over \d+ samples)", page
    )
    assert printed is not None, "the printed line on uncertainty-margins.md has moved"
    assert str(result) == printed.group(1)

    stated_probability = float(
        re.search(r"# ([\d.]+) — the chance of falling short", page).group(1)
    )
    assert result.shortfall_probability == pytest.approx(stated_probability, abs=5e-4)
    dominant = re.search(r'# "(\w+)" — the input driving the scatter', page)
    assert dominant is not None and result.dominant().name == dominant.group(1)
    # The page says `is_fragile(threshold=0.05)` is True, which is the whole argument: a
    # nominal pass with a material chance of falling short.
    threshold = float(re.search(r"is_fragile\(threshold=([\d.]+)\)", page).group(1))
    assert result.is_fragile(threshold=threshold) is True
    assert result.shortfall_probability > threshold


def test_the_pressure_equipment_page_quotes_the_verdicts_the_example_computes():
    """A 3x2 table of safety factors, and the two ratios the prose draws from it.

    The ratios are the argument — the shell got 1.75x thinner and the opening 3.4x worse —
    so they are recomputed from the table rather than trusted, and the table from the run.
    """
    page = _page("pressure-equipment.md")
    rows = re.findall(
        r"\| ([^|]*?\([A-Z]+-\d+\)) "
        r"\| \*{0,2}\w+, SF ([\d.]+)\*{0,2} "
        r"\| \*{0,2}\w+, SF ([\d.]+)\*{0,2} \|",
        page,
    )
    assert len(rows) == 3, f"the two-thickness table on pressure-equipment.md has moved: {rows}"

    # The table's own values against the run, not merely against the prose beside them.
    # A coordinated edit — a cell and the ratio moved together — leaves the page internally
    # consistent and wrong, which is the whole failure mode a self-referential gate has.
    import runpy

    example = _DOCS.parent / "examples" / "pressure_vessel_nozzle_and_flange.py"
    namespace = runpy.run_path(str(example))
    screened = {
        column: {
            entry.name: entry.safety_factor
            for entry in namespace["screen_vessel"](
                namespace["Quantity"].parse(f"{millimetres} mm")
            ).entries
        }
        for column, millimetres in ((1, 14), (2, 8))
    }
    for name, thick_cell, thin_cell in rows:
        # The page writes "Shell wall (UG-27)" and "6 in nozzle opening (UG-37)"; the
        # entries are "shell wall (UG-27)" and "6 in nozzle opening" — different case, and
        # one carries the clause and one does not. Matched on the base name, and required
        # to be unambiguous rather than taken as the first hit.
        matches = [k for k in screened[1] if name.lower().startswith(k.split(" (")[0].lower())]
        assert len(matches) == 1, f"{name!r} matches {matches} in the run"
        key = matches[0]
        for column, cell in ((1, thick_cell), (2, thin_cell)):
            assert screened[column][key] == pytest.approx(float(cell), abs=5e-3), (
                f"the page says {name} is SF {cell} in column {column}; the run gives "
                f"{screened[column][key]:.3f}"
            )

    thick, thin = (float(v) for v in rows[2][1:])
    thick_shell, thin_shell = (float(v) for v in rows[0][1:])
    # The prose's two ratios, recomputed from the table above them.
    stated = re.search(
        r"got ([\d.]+)× thinner \((\d+) mm to (\d+) mm\) and the opening got ([\d.]+)× worse", page
    )
    assert stated is not None, "the ratio sentence on pressure-equipment.md has moved"
    assert float(stated.group(2)) / float(stated.group(3)) == pytest.approx(
        float(stated.group(1)), abs=5e-3
    )
    assert thick / thin == pytest.approx(float(stated.group(4)), abs=5e-2)
    # And the argument itself: the opening degrades faster than the wall it sits in.
    assert thick / thin > thick_shell / thin_shell


def test_the_agent_skill_page_quotes_a_governing_rule_the_scorecard_really_has():
    """ "A check that could not run governs over one at 99.99%" is a claim about
    `Scorecard.governing()`, not a figure of speech.

    The page's "what is not claimed" section exists because the skill originally said
    `governing()` names the check running closest to its limit and it does not — blocking
    status outranks utilization. The correction was prose, and prose is what goes quietly
    wrong.

    **The percentage itself is rhetoric and is not pinned, deliberately.** Blocking outranks
    utilization at *every* utilization, so an entry built at whatever figure the page names
    tests the same thing — editing 99.99 to 97.99 changes nothing, and asserting otherwise
    would claim a coverage this cannot have. What is pinned is the ordering, and the two
    properties that make the sentence apt at all: the figure has to be a utilization that
    still *passes*, and it has to be tight enough that "closest to its limit" would have
    picked it.
    """
    from anvilate.scorecard import CheckStatus, Scorecard, ScorecardEntry

    page = _page("agent-skill.md")
    claim = re.search(r"governs over one at ([\d.]+)%", page)
    assert claim is not None, "the governing-order sentence on agent-skill.md has moved"
    utilization = float(claim.group(1)) / 100.0

    required = 1.5
    tight = ScorecardEntry.from_safety_factor(
        "tight", computed=required / utilization, required=required
    )
    assert tight.utilization == pytest.approx(utilization, abs=5e-6)
    assert tight.status is CheckStatus.PASS, "the page's example is a *passing* check"
    assert 0.9 < utilization < 1.0, (
        f"the page names {claim.group(1)}% — the sentence only lands on a check that is "
        "passing and running very close to its limit"
    )

    blocked = ScorecardEntry(
        name="unrunnable", status=CheckStatus.NOT_EVALUATED, detail="no element type"
    )
    for entries in ((tight, blocked), (blocked, tight)):
        governing = Scorecard(entries=entries).governing()
        assert governing is not None and governing.name == "unrunnable", (
            "a check that could not run must outrank one at "
            f"{claim.group(1)}% utilization, in either order"
        )

    # The page's second correction, in the same paragraph: `governing()` is None when
    # nothing blocks and no check carries a safety factor, which is what makes the
    # copyable `card.governing().name` an AttributeError.
    assert "returns `None`" in page
    passing = Scorecard(
        entries=(ScorecardEntry(name="deflection", status=CheckStatus.PASS, detail="ok"),)
    )
    assert passing.governing() is None
    with pytest.raises(AttributeError):
        _ = passing.governing().name


def test_the_callouts_page_prints_the_entry_the_library_actually_renders():
    """docs/typed-callouts.md leads with a printed scorecard entry.

    Three separate claims live in that block and none of them was joined to anything: the
    characteristic identifier, the surface factor, and the strength it was evaluated at.
    The identifier is the one that had gone stale — it is a digest of *what the
    characteristic is*, so the page was naming a callout this library cannot mint, which
    is exactly the field a reader would key a drawing revision on.
    """
    from anvilate.callouts import (
        CalloutSet,
        ProductionMethod,
        SurfaceFinish,
        callout_scorecard,
    )
    from anvilate.units import Quantity

    page = _page("typed-callouts.md")
    printed = re.search(
        r"# \[PASS\] surface finish at shaft_journal: \[([0-9a-f]{16})\] as forged, "
        r"Ra ([\d.]+) µm\n#\s+→ Marin surface factor k_a = ([\d.]+) at S_u = (\d+) MPa",
        page,
    )
    assert printed is not None, "the printed entry on typed-callouts.md has moved"
    identifier, roughness, factor, strength = printed.groups()

    finish = SurfaceFinish(
        scope="shaft_journal",
        roughness=Quantity.parse(f"{roughness} um"),
        method=ProductionMethod.AS_FORGED,
    )
    card = callout_scorecard(
        CalloutSet(callouts=(finish,)),
        ultimate_strength=Quantity.parse(f"{strength} MPa"),
    )
    rendered = str(card.entries[0])
    assert f"[{identifier}]" in rendered, (
        f"the page names characteristic {identifier}; the library mints {finish.characteristic_id}"
    )
    assert f"k_a = {factor} at S_u = {strength} MPa" in rendered


def test_the_callouts_page_kpsi_table_is_the_one_its_own_constants_give():
    """The anchoring table on typed-callouts.md derives a_kpsi from a_MPa.

    The derived column is a five-decimal figure the page states and nothing recomputed;
    the published column is the transcription the identity exists to check. Both are held
    here against `MARIN_SURFACE_CONSTANTS_MPA`, so a constant edited on either side of the
    page fails.
    """
    from anvilate.callouts import MARIN_SURFACE_CONSTANTS_MPA

    page = _page("typed-callouts.md")
    rows = re.findall(r"\| (ground|machined|hot-rolled|as-forged) \| ([\d.]+) \| ([\d.]+) \|", page)
    assert len(rows) == len(MARIN_SURFACE_CONSTANTS_MPA), (
        "the anchoring table on typed-callouts.md no longer has one row per constant"
    )
    mpa_per_kpsi = 6.894757
    for method, derived, published in rows:
        a_mpa, b = MARIN_SURFACE_CONSTANTS_MPA[method.replace("-", "_")]
        assert float(derived) == pytest.approx(a_mpa * mpa_per_kpsi**b, abs=5e-6), method
        assert float(derived) == pytest.approx(float(published), rel=3e-3), method

    # The same paragraph argues from the exponent that makes as-forged the loose row.
    exponent = re.search(r"b = (−[\d.]+) is quoted to three decimals", page)
    assert exponent is not None, "the as-forged sentence on typed-callouts.md has moved"
    assert float(exponent.group(1).replace("−", "-")) == MARIN_SURFACE_CONSTANTS_MPA["as_forged"][1]


def test_the_weld_fatigue_page_quotes_the_damage_the_example_accumulates():
    """ "identical loading gives Miner damage 2.54 (FAIL, SF 0.39) ... and 0.33 (PASS, SF 3.02)".

    Four figures carrying the page's argument that the detail category, not the load,
    decides the verdict. The example's own test pinned two of them as literals of its own,
    so the sentence a reader takes away was joined to nothing — and damage is the
    reciprocal of the factor, which is the relation that makes the sentence coherent.
    """
    import runpy

    page = _page("weld-fatigue-screening.md")
    claim = re.search(
        r"Miner damage ([\d.]+) \(FAIL, SF ([\d.]+)\)\s*\n?\s*on a category-(\d+) detail and "
        r"([\d.]+) \(PASS, SF ([\d.]+)\) on a category-(\d+) one",
        page,
    )
    assert claim is not None, "the two-detail sentence on weld-fatigue-screening.md has moved"
    harsh_damage, harsh_factor, harsh_category = claim.group(1), claim.group(2), claim.group(3)
    good_damage, good_factor, good_category = claim.group(4), claim.group(5), claim.group(6)
    assert int(harsh_category) < int(good_category), "the harsh detail is the lower category"

    namespace = runpy.run_path(
        str(Path(__file__).resolve().parent.parent / "examples" / "welded_bracket_fatigue.py")
    )
    for entry, damage, factor in (
        (namespace["screen_harsh_detail"]().entries[0], harsh_damage, harsh_factor),
        (namespace["screen_good_detail"]().entries[0], good_damage, good_factor),
    ):
        assert entry.safety_factor == pytest.approx(float(factor), abs=5e-3)
        assert 1.0 / entry.safety_factor == pytest.approx(float(damage), abs=5e-3)


def test_the_weld_fatigue_page_prints_the_mean_stress_numbers_the_module_returns():
    """The stress-relief block: 200 MPa as-welded, 160 relieved, and a 0.80 factor.

    The whole point of the paragraph is that claiming the bonus is a deliberate statement
    about fabrication, so the size of the bonus is the number that matters — and it was
    only ever a comment beside a call.
    """
    from anvilate.analysis import weld_effective_stress_range, weld_mean_stress_factor
    from anvilate.units import Quantity

    page = _page("weld-fatigue-screening.md")
    block = re.search(
        r'cycle = \{"max_stress": Quantity\.parse\("([^"]+)"\), '
        r'"min_stress": Quantity\.parse\("([^"]+)"\)\}\n'
        r"weld_effective_stress_range\(\*\*cycle\)\s+# ([\d.]+) MPa[^\n]*\n"
        r"weld_effective_stress_range\(\*\*cycle, stress_relieved=True\)\s+# ([\d.]+) MPa\n"
        r"weld_mean_stress_factor\(\*\*cycle, stress_relieved=True\)\s+# ([\d.]+)",
        page,
    )
    assert block is not None, "the stress-relief block on weld-fatigue-screening.md has moved"
    cycle = {
        "max_stress": Quantity.parse(block.group(1)),
        "min_stress": Quantity.parse(block.group(2)),
    }
    as_welded, relieved, factor = (float(value) for value in block.groups()[2:])
    assert weld_effective_stress_range(**cycle).to("MPa").magnitude == pytest.approx(as_welded)
    assert weld_effective_stress_range(**cycle, stress_relieved=True).to(
        "MPa"
    ).magnitude == pytest.approx(relieved)
    assert weld_mean_stress_factor(**cycle, stress_relieved=True) == pytest.approx(factor)
    # The sentence under the block: the factor is what relief buys, so it is below one.
    assert factor < 1.0 and relieved < as_welded


def test_the_aluminum_page_states_the_b4_formulas_the_module_evaluates():
    """The §B.4 block on aluminum-screening.md is the page's central claim.

    "No copy of the standard's tables is bundled" only means something if the formulas
    printed underneath are the ones that run, and every coefficient in them — the 2250 and
    1500 denominators, the /10, and the 0.41 intersection fraction — was transcribed prose.
    Evaluated here from the page's own text and held against the constants the module
    returns, so a coefficient edited on either side fails.
    """
    from anvilate.analysis.aluminum import aluminum_buckling_constants
    from anvilate.units import Quantity

    page = _page("aluminum-screening.md")
    stated = re.findall(
        r"B_([cp]) = F_cy\[1 \+ \(F_cy/(\d+)\)\^\(1/([23])\)\]\s+"
        r"D_[cp] = \(B_[cp]/(\d+)\)\(B_[cp]/E\)\^\(1/2\)\s+"
        r"C_[cp] = ([\d.]+)·B_[cp]/D_[cp]",
        page,
    )
    assert len(stated) == 2, "the §B.4 formula block on aluminum-screening.md has moved"

    yield_ksi, modulus_ksi = 35.0, 10100.0
    constants = aluminum_buckling_constants(
        compressive_yield=Quantity.parse(f"{yield_ksi} ksi"),
        elastic_modulus=Quantity.parse(f"{modulus_ksi} ksi"),
    )
    computed = {
        "c": (constants.intercept_member, constants.slope_member, constants.intersection_member),
        "p": (constants.intercept_plate, constants.slope_plate, constants.intersection_plate),
    }
    for family, denominator, root, divisor, fraction in stated:
        b = yield_ksi * (1.0 + (yield_ksi / float(denominator)) ** (1.0 / float(root)))
        d = (b / float(divisor)) * (b / modulus_ksi) ** 0.5
        c = float(fraction) * b / d
        intercept, slope, intersection = computed[family]
        # B and D are stresses; the ADM writes them in ksi and so does the page.
        assert b == pytest.approx(intercept.to("ksi").magnitude, rel=1e-9), family
        assert d == pytest.approx(slope.to("ksi").magnitude, rel=1e-9), family
        assert c == pytest.approx(intersection, rel=1e-9), family


def test_the_aluminum_page_is_right_that_the_beam_curve_carries_no_knockdown():
    """ "the beam LTB moment, with **no** 0.85 knockdown".

    A negative claim, and the only one on the page that names a constant it says is *not*
    applied — so it goes stale in two ways: the module could start applying it, or the
    module's factor could move and leave the sentence naming a number that no longer
    exists. Both are checked, in the elastic branch where the knockdown is the whole
    difference between the two curves.
    """
    from math import pi

    from anvilate.analysis.aluminum import (
        _OUT_OF_STRAIGHTNESS,
        aluminum_buckling_constants,
        aluminum_lateral_torsional_moment,
        aluminum_member_buckling_stress,
    )
    from anvilate.units import Quantity

    page = _page("aluminum-screening.md")
    named = re.search(r"with \*\*no\*\* ([\d.]+) knockdown", page)
    assert named is not None, "the LTB row on aluminum-screening.md has moved"
    assert float(named.group(1)) == _OUT_OF_STRAIGHTNESS, (
        "the page names a knockdown factor the module no longer holds"
    )

    modulus = Quantity.parse("10100 ksi")
    constants = aluminum_buckling_constants(
        compressive_yield=Quantity.parse("35 ksi"), elastic_modulus=modulus
    )
    slenderness = 2.0 * constants.intersection_member  # well into the elastic branch of both
    column = aluminum_member_buckling_stress(
        slenderness=slenderness,
        compressive_yield=Quantity.parse("35 ksi"),
        elastic_modulus=modulus,
        constants=constants,
    ).to("MPa")
    euler = pi**2 * modulus.to("MPa").magnitude / slenderness**2
    assert column.magnitude == pytest.approx(_OUT_OF_STRAIGHTNESS * euler, rel=1e-9)

    section_modulus = Quantity.parse("1.0e-4 m**3")
    beam = aluminum_lateral_torsional_moment(
        plastic_moment=Quantity.parse("50 kN*m"),
        section_modulus=section_modulus,
        slenderness=slenderness,
        elastic_modulus=modulus,
        constants=constants,
    ).to("kN*m")
    elastic = (
        pi**2 * modulus.to("kPa").magnitude * section_modulus.to("m**3").magnitude / slenderness**2
    )
    assert beam.magnitude == pytest.approx(elastic, rel=1e-9), (
        "the beam curve has acquired a knockdown the page says it does not carry"
    )


def test_the_lifting_devices_allowables_table_is_the_one_the_module_computes():
    """The five BTH-1 allowables, evaluated from the formulas the page prints.

    Three coefficients live only in those formulas — the 1.20 on net-section rupture, the
    0.60 on shear, the 1.25 on pin bearing — and the page's own paragraph explains that
    the 1.20 is what makes a rupture check stricter than a yield check. Evaluated here
    with the module's symbols bound to real strengths, so a coefficient that moves on
    either side fails, and a coefficient copied into the wrong row fails too.
    """
    from anvilate.analysis.lifting_device import (
        DesignCategory,
        bth1_allowable_stresses,
    )
    from anvilate.units import Quantity

    page = _page("lifting-devices.md")
    rows = {
        limit_state.strip(): formula
        for limit_state, formula in re.findall(
            r"\| ([^|]+?) \| §[\d.\-]+ \| `F_[tvbp] = ([^`]+)` \|", page
        )
    }
    assert len(rows) == 5, "the allowables table on lifting-devices.md has moved"

    yield_strength, ultimate = 250.0, 400.0
    for category in DesignCategory:
        allowables = bth1_allowable_stresses(
            yield_strength=Quantity.parse(f"{yield_strength} MPa"),
            ultimate_strength=Quantity.parse(f"{ultimate} MPa"),
            category=category,
        )
        environment = {
            "S_y": yield_strength,
            "S_u": ultimate,
            "N_d": category.design_factor,
            "__builtins__": {},
        }
        for limit_state, field in (
            ("Tension, gross section", allowables.tension_gross),
            ("Tension, net section", allowables.tension_net),
            ("Shear", allowables.shear),
            ("Bending, compact and braced", allowables.bending),
            ("Pin bearing, clearance fit", allowables.pin_bearing),
        ):
            stated = eval(rows[limit_state].replace("·", "*"), environment)  # noqa: S307
            assert stated == pytest.approx(field.to("MPa").magnitude, rel=1e-12), limit_state

    # The routing argument later on the page: a shear stress checked against the tension
    # allowable would pass at 1/0.60 — the shear coefficient's own reciprocal.
    routed = re.search(r"would pass at 1/([\d.]+) = \*\*([\d.]+)x the margin", page)
    assert routed is not None, "the limit-state routing sentence on lifting-devices.md has moved"
    assert eval(  # noqa: S307
        rows["Shear"].replace("·", "*"), {"S_y": 1.0, "N_d": 1.0, "__builtins__": {}}
    ) == pytest.approx(float(routed.group(1)), rel=1e-12)
    assert 1.0 / float(routed.group(1)) == pytest.approx(float(routed.group(2)), abs=5e-3)

    # The paragraph under the table: 1.20·N_d is what the Code tabulates as 2.40 and 3.60.
    tabulated = re.search(
        r"take\s*\n?(\d+\.\d+)·N_d\*\*, which the Code tabulates directly as "
        r"(\d+\.\d+) and (\d+\.\d+)",
        page,
    )
    assert tabulated is not None, "the 1.20·N_d paragraph on lifting-devices.md has moved"
    extra = float(tabulated.group(1))
    for stated, category in zip(tabulated.groups()[1:], DesignCategory, strict=True):
        assert float(stated) == pytest.approx(extra * category.design_factor, rel=1e-12)


def test_the_lifting_devices_service_class_table_is_the_enumerations_own():
    """Every cycle boundary on the page, against `ServiceClass.cycle_range`.

    The page says Class 0's upper bound is the only number in the table that changes
    whether an analysis is required at all, and that boundary is quoted twice — once in
    the table and once in the sentence — with nothing joining either to the enumeration.
    """
    from anvilate.analysis.lifting_device import ServiceClass

    page = _page("lifting-devices.md")
    rows = re.findall(
        r"\| (\d) \| (?:(\S+) – (\S+)|over (\S+)) \| (\*\*Not required\*\*|Required) \|", page
    )
    assert len(rows) == len(ServiceClass), "the Service Class table on lifting-devices.md has moved"
    for (name, low, high, unbounded, requirement), service_class in zip(
        rows, ServiceClass, strict=True
    ):
        assert name == service_class.value
        lower, upper = service_class.cycle_range
        if unbounded:
            assert upper is None
            # "over 2,000,000" is the class below's ceiling, and the class starts one past it.
            assert int(unbounded.replace(",", "")) == lower - 1
        else:
            assert int(low.replace(",", "")) == lower
            assert upper is not None and int(high.replace(",", "")) == upper
        assert (requirement == "Required") is service_class.fatigue_required

    exempt = re.search(r"the ([\d,]+)-cycle boundary is the only one in the", page)
    assert exempt is not None, "the exempt-boundary sentence on lifting-devices.md has moved"
    assert int(exempt.group(1).replace(",", "")) == ServiceClass.CLASS_0.cycle_range[1]
    assert not ServiceClass.CLASS_0.fatigue_required
    assert all(
        other.fatigue_required for other in ServiceClass if other is not ServiceClass.CLASS_0
    )


def test_the_masonry_page_states_the_formulas_the_module_evaluates():
    """TMS 402's four coefficients, none of which appears anywhere but in a formula.

    0.25·f'm is the allowable the whole page is derating, 140 and 70 are the slenderness
    factor's own constants, 0.65 is what the steel adds, and 0.45·f'm is the flexural
    allowable. Each is evaluated from the page's text against the function it describes,
    on both sides of the h/r = 99 branch, so a coefficient that moves fails.
    """
    from anvilate.analysis.masonry import (
        masonry_allowable_axial_stress,
        masonry_allowable_flexural_stress,
        masonry_column_axial_capacity,
    )
    from anvilate.units import Quantity

    page = _page("masonry-screening.md")
    axial = re.search(
        r"`([\d.]+)·f'm·\[1 − \(h/(\d+)r\)²\]` up to h/r = (\d+) and "
        r"`([\d.]+)·f'm·\((\d+)r/h\)²` beyond",
        page,
    )
    assert axial is not None, "the axial-allowable sentence on masonry-screening.md has moved"
    stocky_coefficient, stocky_divisor, split, slender_coefficient, slender_numerator = (
        float(value) for value in axial.groups()
    )
    strength = 12.0
    for ratio in (split - 1.0, split + 1.0):
        if ratio <= split:
            stated = stocky_coefficient * strength * (1.0 - (ratio / stocky_divisor) ** 2)
        else:
            stated = slender_coefficient * strength * (slender_numerator / ratio) ** 2
        computed = masonry_allowable_axial_stress(
            masonry_strength=Quantity.parse(f"{strength} MPa"), slenderness_ratio=ratio
        )
        assert stated == pytest.approx(computed.to("MPa").magnitude, rel=1e-12), ratio

    column = re.search(r"`\(([\d.]+)·f'm·A_n \+ ([\d.]+)·A_st·F_s\)` times the slenderness", page)
    assert column is not None, "the column-capacity sentence on masonry-screening.md has moved"
    masonry_share, steel_share = (float(value) for value in column.groups())
    net_area, steel_area, steel_allowable, ratio = 50_000.0, 800.0, 165.0, 20.0
    factor = 1.0 - (ratio / stocky_divisor) ** 2
    stated = (masonry_share * strength * net_area + steel_share * steel_area * steel_allowable) * (
        factor
    )
    computed = masonry_column_axial_capacity(
        masonry_strength=Quantity.parse(f"{strength} MPa"),
        net_area=Quantity.parse(f"{net_area} mm**2"),
        slenderness_ratio=ratio,
        steel_area=Quantity.parse(f"{steel_area} mm**2"),
        steel_allowable_stress=Quantity.parse(f"{steel_allowable} MPa"),
    )
    assert stated == pytest.approx(computed.to("N").magnitude, rel=1e-9)

    flexural = re.search(r"the flexural compressive allowable `([\d.]+)·f'm`", page)
    assert flexural is not None, "the flexural-allowable line on masonry-screening.md has moved"
    assert float(flexural.group(1)) * strength == pytest.approx(
        masonry_allowable_flexural_stress(masonry_strength=Quantity.parse(f"{strength} MPa"))
        .to("MPa")
        .magnitude,
        rel=1e-12,
    )


def test_the_cold_formed_page_states_winters_limit_and_reduction():
    """ "b = w if λ ≤ 0.673, else ρ·w, ρ = (1 − 0.22/λ)/λ".

    The whole effective-width rule, written on the page as a comment beside the call. The
    1.052 in the slenderness was already held against its constant; the limit that decides
    which branch runs, and the reduction applied above it, were not.
    """
    from anvilate.analysis.cold_formed_steel import aisi_effective_width, aisi_plate_slenderness
    from anvilate.units import Quantity

    page = _page("cold-formed-steel.md")
    rule = re.search(r"# b = w if λ ≤ ([\d.]+), else ρ·w, ρ = \(1 − ([\d.]+)/λ\)/λ", page)
    assert rule is not None, "the effective-width comment on cold-formed-steel.md has moved"
    limit, reduction = (float(value) for value in rule.groups())
    assert float(re.search(r"fully effective \(λ ≤ ([\d.]+)\)", page).group(1)) == limit, (
        "the page states its own limit twice and the two disagree"
    )

    stress, modulus = Quantity.parse("345 MPa"), Quantity.parse("203000 MPa")
    thickness = Quantity.parse("1.5 mm")
    for width in ("40 mm", "150 mm"):
        arguments = {
            "flat_width": Quantity.parse(width),
            "thickness": thickness,
            "stress": stress,
            "elastic_modulus": modulus,
        }
        slenderness = aisi_plate_slenderness(**arguments)
        effective = aisi_effective_width(**arguments).to("mm").magnitude
        full = Quantity.parse(width).to("mm").magnitude
        if slenderness <= limit:
            assert effective == pytest.approx(full, rel=1e-12), width
        else:
            rho = (1.0 - reduction / slenderness) / slenderness
            assert effective == pytest.approx(rho * full, rel=1e-12), width
    # Both branches were exercised: a 40 mm flat at 1.5 mm is fully effective, a 150 mm is not.
    assert (
        aisi_plate_slenderness(
            flat_width=Quantity.parse("40 mm"),
            thickness=thickness,
            stress=stress,
            elastic_modulus=modulus,
        )
        <= limit
    )
    assert (
        aisi_plate_slenderness(
            flat_width=Quantity.parse("150 mm"),
            thickness=thickness,
            stress=stress,
            elastic_modulus=modulus,
        )
        > limit
    )


def test_the_concrete_page_quotes_the_tension_controlled_phi_the_module_returns():
    """ "φ = 0.90 for a tension-controlled section", stated beside the nominal moment.

    φ is what turns the module's nominal strength into a design strength, so the page
    naming the wrong one would mis-scale every result a reader computes by hand.
    """
    from anvilate.analysis.reinforced_concrete import rc_strength_reduction_factor
    from anvilate.units import Quantity

    page = _page("reinforced-concrete.md")
    claim = re.search(r"design strength is φ·M_n \(φ = ([\d.]+) for\s*\n?\s*a tension-", page)
    assert claim is not None, "the φ sentence on reinforced-concrete.md has moved"
    yield_strength = Quantity.parse("420 MPa")
    assert rc_strength_reduction_factor(
        net_tensile_strain=0.01, steel_yield=yield_strength
    ) == pytest.approx(float(claim.group(1)), rel=1e-12)


def test_every_page_naming_a_python_version_names_the_one_the_package_requires():
    """Four places state the interpreter, and `requires-python` is the one that decides.

    A page saying 3.11 beside a package requiring 3.12 sends a reader to an install that
    fails, and the composite action's default is what a caller who names no version gets.
    All of them are read here against `pyproject.toml`, which is the only one an installer
    consults.
    """
    import tomllib

    root = Path(__file__).resolve().parent.parent
    with (root / "pyproject.toml").open("rb") as handle:
        required = tomllib.load(handle)["project"]["requires-python"]
    assert required.startswith(">="), f"requires-python is no longer a floor: {required}"
    floor = required.removeprefix(">=").strip()

    stated = {
        "README.md": (root / "README.md").read_text(),
        "docs/quickstart.md": _page("quickstart.md"),
        "docs/headless-cli.md": _page("headless-cli.md"),
        ".github/actions/check/action.yml": (
            root / ".github" / "actions" / "check" / "action.yml"
        ).read_text(),
    }
    claims = {
        "README.md": r"Python ([\d.]+)\+",
        "docs/quickstart.md": r"Python ([\d.]+) or newer",
        "docs/headless-cli.md": r"\| `python-version` \| `([\d.]+)` \|",
        ".github/actions/check/action.yml": r'python-version:(?:.|\n)*?default: "([\d.]+)"',
    }
    for where, pattern in claims.items():
        found = re.search(pattern, stated[where])
        assert found is not None, f"the Python-version claim in {where} has moved"
        assert found.group(1) == floor, (
            f"{where} names Python {found.group(1)}; pyproject requires {required}"
        )


def test_the_pressure_equipment_page_states_the_seating_width_rule_the_module_applies():
    """ "`b = b₀` only up to b₀ = 6.35 mm (¼ in); above that `b = 2.52·√b₀`".

    The page calls this one of Appendix 2's two traps and says using b₀ above the limit
    overstates both bolt loads while staying plausible — so the limit and the coefficient
    are the numbers the warning rests on, and both were prose. Checked on both sides of
    the limit, including that the ¼ in the page glosses it with really is 6.35 mm.
    """
    from anvilate.analysis import asme_appendix_2_gasket_geometry
    from anvilate.units import Quantity

    page = _page("pressure-equipment.md")
    rule = re.search(
        r"`b = b₀` only up to b₀ = ([\d.]+) mm\n\(([\d/¼]+) in\); above that `b = ([\d.]+)·√b₀`",
        page,
    )
    assert rule is not None, "the seating-width rule on pressure-equipment.md has moved"
    limit, coefficient = float(rule.group(1)), float(rule.group(3))
    assert limit == pytest.approx(Quantity.parse("0.25 in").to("mm").magnitude, abs=5e-3), (
        "the page glosses the limit as a quarter inch"
    )

    outside = Quantity.parse("300 mm")
    for basic, wide in ((limit - 0.05, False), (limit + 0.05, True), (2.0 * limit, True)):
        geometry = asme_appendix_2_gasket_geometry(
            contact_width=Quantity.parse(f"{2.0 * basic} mm"), outside_diameter=outside
        )
        assert geometry.is_wide is wide, basic
        expected = coefficient * basic**0.5 if wide else basic
        assert geometry.effective_width.to("mm").magnitude == pytest.approx(expected, rel=1e-9)
        # "The diameter G moves with it": the mean diameter narrow, OD − 2b wide.
        diameter = geometry.diameter.to("mm").magnitude
        # b₀ is half the contact width N, so the gasket's mean diameter is OD − N.
        assert diameter == pytest.approx(300.0 - 2.0 * (expected if wide else basic), rel=1e-9)


def test_the_pressure_equipment_page_quotes_the_bolt_areas_appendix_2_requires():
    """ "the required areas are 2,326 mm² and 3,645 mm²: operating governs, by 57%".

    The section exists to say that comparing the two *loads* gets the answer backwards,
    and every number in the argument — both areas, the percentage, and the one-number
    form's answer — was prose. Recomputed from the loads and allowables the same
    paragraph states.
    """
    from anvilate.analysis import asme_appendix_2_required_bolt_area
    from anvilate.units import Quantity

    page = _page("pressure-equipment.md")
    stated = re.search(
        r"the seating load is ([\d.]+) kN and the operating load ([\d.]+) kN.*?"
        r"(\d+) MPa cold,\n(\d+) MPa at 400 °C — and the required areas are ([\d,]+) mm² and "
        r"\*\*([\d,]+) mm²\*\*: operating\ngoverns, by (\d+)%\..*?returns ([\d,]+) mm²,\n"
        r"\*\*(\d+)% short",
        page,
        re.S,
    )
    assert stated is not None, "the bolt-area paragraph on pressure-equipment.md has moved"
    seating_load, operating_load = (float(value) for value in stated.groups()[:2])
    cold, hot = (float(value) for value in stated.groups()[2:4])
    seating_area, operating_area = (float(v.replace(",", "")) for v in stated.groups()[4:6])
    margin, one_number, short = (
        float(stated.group(7)),
        float(stated.group(8).replace(",", "")),
        float(stated.group(9)),
    )

    for load, allowable, claimed in (
        (seating_load, cold, seating_area),
        (operating_load, hot, operating_area),
    ):
        assert load * 1000.0 / allowable == pytest.approx(claimed, abs=1.0)
    assert operating_area > seating_area, "the page's whole point is that operating governs"
    assert 100.0 * (operating_area / seating_area - 1.0) == pytest.approx(margin, abs=0.5)
    # The correct consumer returns the larger of the two; the one-number form returns the
    # area the *larger load* gives against the seating allowable, which is the smaller.
    required = (
        asme_appendix_2_required_bolt_area(
            operating_bolt_load=Quantity.parse(f"{operating_load} kN"),
            seating_bolt_load=Quantity.parse(f"{seating_load} kN"),
            operating_allowable=Quantity.parse(f"{hot} MPa"),
            seating_allowable=Quantity.parse(f"{cold} MPa"),
        )
        .to("mm**2")
        .magnitude
    )
    assert required == pytest.approx(operating_area, abs=1.0)
    assert one_number == pytest.approx(seating_area, abs=1.0)
    assert 100.0 * (1.0 - one_number / required) == pytest.approx(short, abs=0.5)


def test_the_timber_page_states_the_nds_coefficients_the_module_holds():
    """Four NDS constants the page prints and nothing read.

    The two Euler coefficients are the pair the page warns about — 1.20 for the beam and
    0.822 for the column "in the identical shape", where swapping them understates the
    beam's buckling stress by a third — so the swap is checked as well as the values. The
    beam-stability formula's 1.9 and 0.95, and the §3.10.4 bearing bonus, are the other
    fixed numbers on the page.
    """
    from anvilate.analysis import (
        nds_beam_stability_factor,
        nds_bearing_area_factor,
        nds_bending_buckling_stress,
        nds_euler_buckling_stress,
    )
    from anvilate.units import Quantity

    page = _page("timber-screening.md")
    modulus, ratio = Quantity.parse("620000 psi"), 20.0

    beam_coefficient = re.search(r"F_bE = \*\*([\d.]+)\*\*·E'_min/R_B²", page)
    column_coefficient = re.search(r"F_cE = ([\d.]+)·E'_min/\(l_e/d\)²", page)
    assert beam_coefficient is not None and column_coefficient is not None, (
        "the two Euler-coefficient sentences on timber-screening.md have moved"
    )
    beam = nds_bending_buckling_stress(min_modulus=modulus, slenderness_ratio=ratio)
    column = nds_euler_buckling_stress(min_modulus=modulus, slenderness_ratio=ratio)
    for coefficient, stress in (
        (beam_coefficient.group(1), beam),
        (column_coefficient.group(1), column),
    ):
        assert stress.to("psi").magnitude == pytest.approx(
            float(coefficient) * modulus.to("psi").magnitude / ratio**2, rel=1e-12
        )
    # "swapping them understates the beam's buckling stress by a third" — the page's own
    # reason for warning about the pair, and it is the ratio of the two coefficients.
    understated = re.search(r"understates the beam's\s+buckling stress by a (\w+)", page)
    assert understated is not None and understated.group(1) == "third"
    assert 1.0 - column.to("psi").magnitude / beam.to("psi").magnitude == pytest.approx(
        1.0 / 3.0, abs=0.02
    )

    stability = re.search(
        r"C_L = \(1\+x\)/([\d.]+) − √\(\[\(1\+x\)/([\d.]+)\]² − x/([\d.]+)\)", page
    )
    assert stability is not None, "the C_L formula on timber-screening.md has moved"
    first, second, divisor = (float(value) for value in stability.groups())
    assert first == second, "the page writes the same constant twice and they disagree"
    reference = Quantity.parse("1000 psi")
    for buckling in ("500 psi", "1500 psi"):
        x = Quantity.parse(buckling).to("psi").magnitude / reference.to("psi").magnitude
        stated = (1.0 + x) / first - (((1.0 + x) / first) ** 2 - x / divisor) ** 0.5
        assert nds_beam_stability_factor(
            buckling_stress=Quantity.parse(buckling), reference_bending_value=reference
        ) == pytest.approx(stated, rel=1e-12), buckling

    bearing = re.search(r"C_b = \(l_b \+ ([\d.]+) in\)/l_b", page)
    assert bearing is not None, "the bearing-area factor on timber-screening.md has moved"
    for length in ("1.5 in", "3.5 in"):
        inches = Quantity.parse(length).to("in").magnitude
        assert nds_bearing_area_factor(bearing_length=Quantity.parse(length)) == pytest.approx(
            (inches + float(bearing.group(1))) / inches, rel=1e-12
        )


def test_the_timber_page_lists_the_load_duration_factors_the_table_holds():
    """C_D, the one factor the page says is universally republished — all six of them.

    The page names each factor beside the duration it belongs to, which is the part that
    can go wrong silently: a value transposed between two rows leaves the same six numbers
    on the page and screens every snow case as construction.
    """
    from anvilate.analysis import nds_load_duration_factor
    from anvilate.analysis.nds_timber import LoadDuration

    page = _page("timber-screening.md")
    listed = re.search(r"values \(([^)]+)\)\. Every", page)
    assert listed is not None, "the C_D list on timber-screening.md has moved"
    named = re.findall(r"([\d.]+)\s+([a-z/\-]+)", listed.group(1))
    assert len(named) == len(LoadDuration), "the page no longer lists every duration"
    spelling = {
        "permanent": LoadDuration.PERMANENT,
        "ten-year": LoadDuration.TEN_YEAR,
        "snow": LoadDuration.TWO_MONTH,
        "construction": LoadDuration.SEVEN_DAY,
        "wind/earthquake": LoadDuration.TEN_MINUTE,
        "impact": LoadDuration.IMPACT,
    }
    for factor, duration in named:
        assert duration in spelling, f"the page names a duration this test cannot place: {duration}"
        assert float(factor) == pytest.approx(
            nds_load_duration_factor(spelling[duration]), rel=1e-12
        ), duration
    assert {spelling[duration] for _, duration in named} == set(LoadDuration)


def test_the_thermal_page_states_the_correlation_it_says_anvilate_evaluates():
    """ "Nu = 0.664·Re^(1/2)·Pr^(1/3)", on a page whose framing is that no fluid-property
    database is carried and the correlation is the whole contribution.

    Evaluated from the page's own text, at a Reynolds number under the laminar limit the
    same sentence names, and the limit itself is checked by asking for a `None` above it.
    """
    from anvilate.analysis import flat_plate_forced_convection_coefficient
    from anvilate.units import Quantity

    page = _page("thermal-screening.md")
    stated = re.search(
        r"Nu = ([\d.]+)·Re\^\(1/2\)·Pr\^\(1/3\)\. Above the laminar limit "
        r"\(Re ≈ ([\d.]+)×10⁵\)",
        page,
    )
    assert stated is not None, "the convection correlation on thermal-screening.md has moved"
    coefficient, limit = float(stated.group(1)), float(stated.group(2)) * 1e5

    conductivity, prandtl = Quantity.parse("0.026 W/m/K"), 0.71
    viscosity, length = Quantity.parse("1.5e-5 m**2/s"), Quantity.parse("0.5 m")
    # Bracketing the limit, not straddling it widely: a page naming the wrong Reynolds
    # number still separates a low case from a high one, and only a tight bracket says
    # the number on the page is where the refusal actually happens.
    for reynolds in (0.99 * limit, 1.01 * limit):
        velocity = reynolds * viscosity.to("m**2/s").magnitude / length.to("m").magnitude
        computed = flat_plate_forced_convection_coefficient(
            fluid_velocity=Quantity(magnitude=velocity, unit="m/s"),
            plate_length=length,
            thermal_conductivity=conductivity,
            kinematic_viscosity=viscosity,
            prandtl_number=prandtl,
        )
        if reynolds > limit:
            assert computed is None, "the page says the correlation refuses past the limit"
            continue
        nusselt = coefficient * reynolds**0.5 * prandtl ** (1.0 / 3.0)
        assert computed is not None
        assert computed.to("W/m**2/K").magnitude == pytest.approx(
            nusselt * conductivity.to("W/m/K").magnitude / length.to("m").magnitude, rel=1e-9
        )


def test_the_thermal_page_prints_the_isolator_entry_it_actually_renders():
    """The AMPLIFIES entry, and the two transmissibilities the paragraph contrasts.

    The page's argument is that a mount too stiff to isolate passes *more* than a rigid
    bolt-down, so reporting its TR beside a real one would invite the wrong reading. Both
    numbers in that sentence — the 5.69 and the 0.02 it must not be compared to — were
    prose, as was every figure in the block above it.
    """
    from anvilate.analysis import isolator_selection_scorecard
    from anvilate.units import Quantity

    page = _page("thermal-screening.md")
    call = re.search(
        r'isolator_selection_scorecard\(\s*"([^"]+)", '
        r'forcing_frequency=Quantity\.parse\("([^"]+)"\),\s*'
        r"target_transmissibility=([\d.]+), "
        r'selected_static_deflection=Quantity\.parse\("([^"]+)"\),',
        page,
    )
    assert call is not None, "the isolator example on thermal-screening.md has moved"
    printed = re.search(
        r"# \[FAIL\] selected ([\d.]+) mm against ([\d.]+) mm required \(f_n ([\d.]+) Hz\), "
        r"the mount AMPLIFIES\n#\s+\(f/f_n = ([\d.]+) < √2, TR = ([\d.]+)\)",
        page,
    )
    assert printed is not None, "the printed isolator entry has moved"

    entry = isolator_selection_scorecard(
        call.group(1),
        forcing_frequency=Quantity.parse(call.group(2)),
        target_transmissibility=float(call.group(3)),
        selected_static_deflection=Quantity.parse(call.group(4)),
    )
    for figure in printed.groups():
        assert figure in entry.detail, f"the page prints {figure}; the entry says {entry.detail}"
    assert "AMPLIFIES" in entry.detail

    # And the scale the paragraph says the amplified figure does not belong on: the
    # transmissibility a mount meeting the target would show.
    contrast = re.search(
        r"transmissibility of ([\d.]+) as\s+though it belonged on the same scale as (\d+\.\d+)",
        page,
    )
    assert contrast is not None, "the amplification sentence on thermal-screening.md has moved"
    assert contrast.group(1) == printed.group(5), (
        "the sentence quotes a transmissibility the block above it does not print"
    )
    assert float(contrast.group(2)) < float(call.group(3)), (
        "the contrast only lands if the other figure is an isolating one"
    )


def test_the_citations_page_prints_what_the_basis_gate_returns():
    """Two blocks, one member, and the difference between them is the basis.

    The page's argument is that a check citing a clause has to refuse a mean strength and
    say so — and then that an opt-in must not put the silence back. Both blocks are its
    evidence and both were prose: the refusal's wording, the factor the opt-in prints, and
    the declaration that has to land on a *passing* entry. The member is now stated on the
    page, so the numbers under it are reproducible rather than asserted.
    """
    from anvilate.packs.structural import TensionMember, screen_tension_member
    from anvilate.standards import AllowableBasis
    from anvilate.units import Quantity

    page = _page("citations.md")
    declared = re.search(
        r'member = TensionMember\(\s*name="([^"]+)", material="([^"]+)", '
        r'load=Quantity\.parse\("([^"]+)"\),\s*'
        r'gross_area=Quantity\.parse\("([^"]+)"\), net_area=Quantity\.parse\("([^"]+)"\),',
        page,
    )
    assert declared is not None, "the tension member on citations.md has moved"
    member = TensionMember(
        name=declared.group(1),
        material=declared.group(2),
        load=Quantity.parse(declared.group(3)),
        gross_area=Quantity.parse(declared.group(4)),
        net_area=Quantity.parse(declared.group(5)),
    )

    refused = re.search(
        r"screen_tension_member\(member, required_safety_factor=([\d.]+)\)\n"
        r"# \[NOT_EVALUATED\] ([^:]+): (not evaluated — [^\n]+)\n#\s+(\([^\n]+)",
        page,
    )
    assert refused is not None, "the refusal block on citations.md has moved"
    entry = screen_tension_member(member, required_safety_factor=float(refused.group(1))).entries[0]
    assert entry.name == refused.group(2)
    assert entry.status.name == "NOT_EVALUATED"
    for fragment in (refused.group(3), refused.group(4)):
        assert fragment.rstrip() in entry.detail, (fragment, entry.detail)

    accepted = re.search(
        r"screen_tension_member\(member, required_safety_factor=([\d.]+), "
        r"required_basis=AllowableBasis\.([A-Z_]+)\)\n"
        r"# \[PASS\] ([^:]+): (safety factor [\d.]+ vs required minimum [\d.]+)\n"
        r"#\s+(\[screened against[^\n]+)",
        page,
    )
    assert accepted is not None, "the opt-in block on citations.md has moved"
    card = screen_tension_member(
        member,
        required_safety_factor=float(accepted.group(1)),
        required_basis=AllowableBasis[accepted.group(2)],
    )
    assert card.entries[0].name == accepted.group(3)
    assert card.entries[0].status.name == "PASS"
    assert accepted.group(4) in card.entries[0].detail
    assert accepted.group(5) in card.entries[0].detail
    # "The declaration lands on every entry the screen produced, including the ones that
    # passed" — the sentence under the block, and the reason the opt-in is not a silence.
    declaration = accepted.group(5).rstrip("]").lstrip("[")
    assert all(declaration in other.detail for other in card.entries)
    assert len(card.entries) > 1, "one entry cannot show that the note lands on every one"


def test_the_citations_page_is_right_about_where_the_en1993_curve_stops():
    """ "returns nothing below 10,000 cycles ... while the bare formula will happily
    evaluate there".

    The paragraph's point is that a power law run past the end of its method returns a
    number that looks exactly like data, so the boundary is the claim. Checked on both
    sides of the figure the page names, and against the bare power law it contrasts with.
    """
    from anvilate.standards.fatigue import en1993_detail_category_curve
    from anvilate.units import Quantity

    page = _page("citations.md")
    claim = re.search(
        r"curve expressed in this schema returns nothing below ([\d,]+)\ncycles", page
    )
    assert claim is not None, "the cycle-range sentence on citations.md has moved"
    floor = float(claim.group(1).replace(",", ""))

    curve = en1993_detail_category_curve(detail_category=Quantity.parse("90 MPa"))
    assert curve.stress_range_at(0.99 * floor) is None, (
        f"the page says the curve declines below {floor:,.0f} cycles"
    )
    just_inside = curve.stress_range_at(1.01 * floor)
    assert just_inside is not None
    # "the bare formula will happily evaluate there": the same segment extrapolated by
    # hand returns a plausible, larger number at the life the curve refuses.
    at_two_million = curve.stress_range_at(2.0e6)
    assert at_two_million is not None
    extrapolated = at_two_million.to("MPa").magnitude * (2.0e6 / (0.99 * floor)) ** (1.0 / 3.0)
    assert extrapolated > just_inside.to("MPa").magnitude


def test_the_process_piping_page_prints_the_temperature_refusal_it_describes():
    """The block whose whole subject is that an allowable is only meaningful at a
    temperature — and both temperatures in it were prose.

    The two Kelvin figures are the claim: an allowable read at one temperature against a
    line designed for another. The refusal names both, so a page that changed either would
    be describing a mismatch the library does not report.
    """
    from anvilate.analysis import AllowableStress, asme_b313_pressure_scorecard
    from anvilate.standards import default_pipe_schedule_table
    from anvilate.units import Quantity

    page = _page("process-piping.md")
    block = re.search(
        r'value=Quantity\.parse\("([^"]+)"\), temperature=Quantity\.parse\("([^"]+)"\),\s*\n'
        r'\s*material="([^"]+)", source="([^"]+)",(?:.|\n)*?'
        r'design_pressure=Quantity\.parse\("([^"]+)"\),\s*\n'
        r'\s*design_temperature=Quantity\.parse\("([^"]+)"\),(?:.|\n)*?'
        r'corrosion_allowance=Quantity\.parse\("([^"]+)"\),\s*\n\)\n'
        r"# \[NOT EVALUATED\] ([^\n]+)",
        page,
    )
    assert block is not None, "the temperature-mismatch block on process-piping.md has moved"
    allowable = AllowableStress(
        value=Quantity.parse(block.group(1)),
        temperature=Quantity.parse(block.group(2)),
        material=block.group(3),
        source=block.group(4),
    )
    pipe = default_pipe_schedule_table().get("4", "40")
    entry = asme_b313_pressure_scorecard(
        "process line",
        design_pressure=Quantity.parse(block.group(5)),
        design_temperature=Quantity.parse(block.group(6)),
        outside_diameter=pipe.outside_diameter.quantity,
        nominal_wall=pipe.wall_thickness.quantity,
        allowable=allowable,
        corrosion_allowance=Quantity.parse(block.group(7)),
    )
    assert entry.status.name == "NOT_EVALUATED"
    assert block.group(8).strip() in entry.detail, (block.group(8), entry.detail)
    # And the sentence above it: the same allowable at its own temperature does evaluate,
    # which is what makes the refusal a temperature check rather than a broken input.
    assert allowable.is_valid_at(allowable.temperature)
    assert not allowable.is_valid_at(Quantity.parse(block.group(6)))

    # The prose names the two rows in Celsius and the block states them in Kelvin. A
    # reader checking the example against the table it cites reads the two as the same
    # pair, so they have to be — and only the conversion says whether they are.
    rows = re.search(r"# (\d+) °C, not the (\d+) °C row", page)
    assert rows is not None, "the row comment on process-piping.md has moved"
    for kelvin, celsius in ((block.group(6), rows.group(1)), (block.group(2), rows.group(2))):
        assert Quantity.parse(kelvin).to("degC").magnitude == pytest.approx(
            float(celsius), abs=0.01
        )


def test_the_uncertainty_page_quotes_the_annotation_a_report_really_prints():
    """ "the report says `P(below 2.00) = 3.1% over 4096 samples by monte_carlo`".

    The page's subject is that the label travels with the number — method, sample count
    and screening label together — and the example of that is a rendered line nothing
    rendered. Built here from the figures the sentence itself states, so the format is
    held as well as the fields: a probability printed to a different precision, or a
    method dropped, no longer matches the page.
    """
    from anvilate.report import CalculationReport, ReportSection
    from anvilate.scorecard import ScorecardEntry
    from anvilate.uncertainty import MarginUncertainty
    from anvilate.units import UnitSystem

    page = _page("uncertainty-margins.md")
    quoted = re.search(r"`P\(below ([\d.]+)\) = ([\d.]+)% over (\d+) samples by (\w+)`", page)
    assert quoted is not None, "the rendered annotation on uncertainty-margins.md has moved"
    required, percent, samples, method = quoted.groups()

    uncertainty = MarginUncertainty(
        method=method,
        samples=int(samples),
        seed=1,
        sensitivities=(),
        required=float(required),
        mean=2.4,
        std=0.3,
        shortfall_probability=float(percent) / 100.0,
        lower=1.9,
        upper=3.0,
        coverage=0.9,
        citation="Screening only — not a certified reliability analysis.",
    )
    report = CalculationReport(
        title="Uncertainty annotation",
        project="Docs",
        date="2026-07-27",
        unit_system=UnitSystem.SI,
        sections=(
            ReportSection(
                entry=ScorecardEntry.from_safety_factor(
                    "bending", computed=2.4, required=float(required)
                ).model_copy(update={"uncertainty": uncertainty}),
            ),
        ),
    )
    assert quoted.group(0).strip("`") in report.to_text()
    # And the label the same paragraph says is printed beneath it.
    assert uncertainty.citation in report.to_text()


def test_the_repair_feedback_page_prints_the_governing_shift_rendering():
    """ "governing check changed: 'bending' (util 0.94) → 'bolt bearing' (util 0.88)".

    The one line the page shows for `governing_shift`, and the direction in it is the
    point: the reference moved to a check with a *lower* utilization, which is what makes
    a shift worth reporting rather than a ranking. The block is an illustration — the page
    defines no cards above it — so the two utilizations feed both sides and are not
    pinned. What is held is the rendering itself, and the ordering claim: the new
    reference is the tighter check, not the larger number.
    """
    from anvilate.scorecard import Scorecard, ScorecardEntry

    page = _page("repair-feedback.md")
    printed = re.search(
        r"# governing check changed: '([^']+)' \(util ([\d.]+)\) → '([^']+)' \(util ([\d.]+)\)",
        page,
    )
    assert printed is not None, "the governing-shift line on repair-feedback.md has moved"
    was, was_utilization, now, now_utilization = printed.groups()

    def _card(governing: str, utilization: str, other: str) -> Scorecard:
        required = 1.5
        return Scorecard(
            entries=(
                ScorecardEntry.from_safety_factor(
                    governing, computed=required / float(utilization), required=required
                ),
                ScorecardEntry.from_safety_factor(
                    other, computed=required / 0.1, required=required
                ),
            )
        )

    before = _card(was, was_utilization, now)
    after = _card(now, now_utilization, was)
    assert before.governing() is not None and before.governing().name == was
    shift = after.governing_shift(before)
    assert shift is not None, "the page shows a shift; these two cards produce none"
    assert str(shift) == printed.group(0).removeprefix("# ")
    # The page's own point: the new reference is the tighter check on this card and not
    # the higher utilization of the two — so a rendering that sorted them would disagree.
    assert float(now_utilization) < float(was_utilization)
    assert after.governing_shift(after) is None


def test_the_timber_anchor_table_rows_are_recomputed_from_their_own_problems():
    """Two rows of the worked-example table, rebuilt from the problem stated beside them.

    The table is the pack's regression floor as a *reader* meets it — the anchors are
    pinned in `test_analysis.py` against hand-worked numbers, and the page restates them
    with nothing joining the two. The beam-stability row states every input it needs; the
    post row states the section, the length and the load, and its lesson ("skipping C_P
    reports 2.52 on the same post") is a number in its own right.
    """
    from anvilate.analysis import (
        nds_beam_slenderness_ratio,
        nds_bending_buckling_stress,
        nds_column_stability_factor,
        nds_euler_buckling_stress,
    )
    from anvilate.units import Quantity

    page = _page("timber-screening.md")
    beam = re.search(
        r"\| Beam stability \| l_e ([\d.]+) in, ([\d.]+) x ([\d.]+) in, "
        r"E'_min ([\d,]+) psi \| R_B ([\d.]+), F_bE ([\d,]+) psi, C_L ([\d.]+) \|",
        page,
    )
    assert beam is not None, "the beam-stability anchor row on timber-screening.md has moved"
    length, depth, breadth = (float(value) for value in beam.groups()[:3])
    modulus = float(beam.group(4).replace(",", ""))
    ratio = nds_beam_slenderness_ratio(
        effective_length=Quantity.parse(f"{length} in"),
        depth=Quantity.parse(f"{depth} in"),
        breadth=Quantity.parse(f"{breadth} in"),
    )
    assert ratio == pytest.approx(float(beam.group(5)), abs=5e-3)
    # F_bE at the *rounded* R_B the page prints, which is the chain the published example
    # runs and the anchor test reproduces. At the unrounded ratio it is 7,656 psi — the
    # same 0.04% gap the flange anchor on pressure-equipment.md is a parenthetical about,
    # and asserting against it here would be holding the page to a chain nobody worked.
    buckling = nds_bending_buckling_stress(
        min_modulus=Quantity.parse(f"{modulus} psi"), slenderness_ratio=float(beam.group(5))
    )
    assert buckling.to("psi").magnitude == pytest.approx(
        float(beam.group(6).replace(",", "")), abs=1.0
    )

    post = re.search(
        r"\| Post \| (\d)x\d, (\d+) ft, ([\d,]+) lb \| compression SF ([\d.]+), "
        r"bearing SF ([\d.]+) \|[^|]*?skipping it reports ([\d.]+) on the same post",
        page,
    )
    assert post is not None, "the post anchor row on timber-screening.md has moved"
    nominal, feet = int(post.group(1)), float(post.group(2))
    load = float(post.group(3).replace(",", ""))
    actual = nominal - 0.5  # a 6x6 is 5.5 in, the dressed size the anchor test works in
    stress = load / actual**2
    reference = Quantity.parse("1000 psi")
    euler = nds_euler_buckling_stress(
        min_modulus=Quantity.parse("580000 psi"), slenderness_ratio=feet * 12.0 / actual
    )
    stability = nds_column_stability_factor(
        euler_buckling_stress=euler, reference_compression=reference
    )
    allowed = stability * reference.to("psi").magnitude
    assert allowed / stress == pytest.approx(float(post.group(4)), abs=5e-3)
    # The lesson column: the same post with the buckling factor left out.
    assert reference.to("psi").magnitude / stress == pytest.approx(float(post.group(6)), abs=5e-3)
    assert float(post.group(6)) > float(post.group(4)), (
        "the page's point is that skipping C_P reads *higher* than the post has"
    )
