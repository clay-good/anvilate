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
