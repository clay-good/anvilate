"""Execute the bundled examples so they stay green in CI (a runnable quickstart)."""

from __future__ import annotations

import runpy
from pathlib import Path

import pytest

from anvilate.scorecard import CheckStatus

_EXAMPLES = Path(__file__).resolve().parent.parent / "examples"


def test_cantilever_bracket_example_screens_to_a_failing_scorecard():
    # run_path executes the module without triggering its __main__ block.
    namespace = runpy.run_path(str(_EXAMPLES / "cantilever_bracket_check.py"))
    card = namespace["screen_cantilever_bracket"]()
    # The aluminum bracket passes yield but fails deflection -> overall FAIL.
    assert card.status is CheckStatus.FAIL
    by_name = {e.name: e for e in card.entries}
    assert by_name["bending yield"].status is CheckStatus.PASS
    assert by_name["tip deflection"].status is CheckStatus.FAIL


def test_bolted_joint_example_screens_to_a_passing_scorecard():
    namespace = runpy.run_path(str(_EXAMPLES / "bolted_joint_check.py"))
    card = namespace["screen_bolted_joint"]()
    # The joint is sized so both bearing and shear pass -> overall PASS.
    assert card.status is CheckStatus.PASS
    assert {e.name for e in card.entries} == {"plate bearing", "bolt shear"}
    assert all(e.passed for e in card.entries)


def test_motor_mount_example_flags_a_resonance():
    namespace = runpy.run_path(str(_EXAMPLES / "motor_mount_resonance.py"))
    card = namespace["screen_motor_mount"]()
    # The flexible bracket resonates below the running speed -> FAIL.
    assert card.status is CheckStatus.FAIL
    assert [e.name for e in card.entries] == ["mount resonance"]


def test_mezzanine_structure_example_passes():
    namespace = runpy.run_path(str(_EXAMPLES / "mezzanine_structure.py"))
    card = namespace["screen_mezzanine"]()
    # A well-sized mezzanine: the beam (bending + deflection) and both posts pass.
    assert card.status is CheckStatus.PASS
    assert len(card.entries) == 4
    assert all(e.passed for e in card.entries)


def test_lifting_padeye_example_flags_pin_bearing():
    namespace = runpy.run_path(str(_EXAMPLES / "lifting_padeye.py"))
    card = namespace["screen_padeye"]()
    # Net tension and weld pass, but the pin bearing is short of the 2.0 rigging
    # safety factor -> the assembly FAILs, catching an under-sized pin/hole.
    assert card.status is CheckStatus.FAIL
    by_name = {e.name: e for e in card.entries}
    assert by_name["padeye net tension"].passed
    assert by_name["padeye_weld weld shear"].passed
    assert not by_name["padeye pin bearing"].passed


def test_brace_tie_example_is_governed_by_net_rupture():
    namespace = runpy.run_path(str(_EXAMPLES / "brace_tie_check.py"))
    card = namespace["screen_brace_tie"]()
    # Both §D2 limit states pass, but shear lag makes net rupture the tighter one:
    # a gross-area-only check would report the looser gross-yield safety factor.
    assert card.status is CheckStatus.PASS
    by_name = {e.name: e for e in card.entries}
    gross = by_name["brace gross yielding"]
    net = by_name["brace net rupture"]
    assert gross.passed and net.passed

    def _sf(entry) -> float:
        # detail reads "safety factor 2.42 vs required minimum 1.67"
        return float(entry.detail.split("safety factor ")[1].split(" ")[0])

    assert _sf(net) < _sf(gross)


def test_load_and_validate_spec_example_round_trips():
    namespace = runpy.run_path(str(_EXAMPLES / "load_and_validate_spec.py"))
    spec = namespace["load_and_validate"]()
    # The golden NEMA 23 bracket spec loads, validates, and round-trips.
    assert spec.name == "nema23_bracket"
    assert spec.material.ref == "AA-6061-T6"


def test_evidence_bundle_example_collects_a_cited_trail():
    namespace = runpy.run_path(str(_EXAMPLES / "evidence_bundle.py"))
    records = namespace["build_evidence"]()
    # Material, two standard components, the ISO 2768 general class, the ISO 286
    # fit on the bore, and ISO 1101 for the geometric call-out -- each cited.
    kinds = [r.kind for r in records]
    assert kinds == ["material", "component", "component", "tolerance", "tolerance", "tolerance"]
    assert {r.ref for r in records} >= {"AA-6061-T6", "NEMA23", "6204", "pilot_bore"}
    assert all(r.sources and all(r.sources) for r in records)


def test_dfm_process_example_flags_and_suggests():
    namespace = runpy.run_path(str(_EXAMPLES / "dfm_process_check.py"))
    result = namespace["screen_manufacturability"]()
    # FDM (0.20 mm floor) cannot hold a 0.02 mm band -> flagged, with tighter
    # processes suggested finest-first.
    assert result["check"].achievable is False
    assert result["alternatives"]  # non-empty
    assert "grinding" in result["alternatives"]


def test_tolerance_stackup_example_worst_case_fails_but_yield_is_high():
    namespace = runpy.run_path(str(_EXAMPLES / "tolerance_stackup.py"))
    result = namespace["analyze_gap"]()
    # Nominal 0.3 mm gap; worst-case floor 0.20 mm breaks the 0.25 mm minimum, yet
    # the Monte Carlo yield shows almost every assembly clears it -- the classic
    # statistical-tolerancing result.
    assert result["worst_case"].nominal.to("mm").magnitude == pytest.approx(0.3)
    assert result["worst_case_ok"] is False
    assert 0.98 < result["predicted_yield"] < 1.0


def test_column_base_plate_example_governed_by_plate_bending():
    namespace = runpy.run_path(str(_EXAMPLES / "column_base_plate.py"))
    card = namespace["screen_base_plate_design"]()
    # Bearing passes comfortably (SF 4.25) but the 25 mm plate's bending stress
    # sits at yield -> plate bending governs and FAILs the 1.5 requirement.
    assert card.status is CheckStatus.FAIL
    by_name = {e.name: e for e in card.entries}
    assert by_name["col_base concrete bearing"].passed
    assert not by_name["col_base plate bending"].passed


def test_coped_beam_web_example_is_governed_by_shear_rupture():
    namespace = runpy.run_path(str(_EXAMPLES / "coped_beam_web_shear.py"))
    card = namespace["screen_coped_web"]()
    # Both §J4.2 limit states pass the Omega=2.00 requirement, but the three
    # bolt-hole deductions make shear rupture (SF ~2.32) the tighter limit state
    # over gross shear yielding (SF ~2.42).
    assert card.status is CheckStatus.PASS
    by_name = {e.name: e for e in card.entries}
    yielding = by_name["coped web shear yielding"]
    rupture = by_name["coped web shear rupture"]
    assert yielding.passed and rupture.passed

    def _sf(entry) -> float:
        # detail reads "safety factor 2.32 vs required minimum 2.0"
        return float(entry.detail.split("safety factor ")[1].split(" ")[0])

    assert _sf(rupture) < _sf(yielding)


def test_hanger_bracket_example_fails_only_the_combined_interaction():
    namespace = runpy.run_path(str(_EXAMPLES / "hanger_bracket_bolt.py"))
    card = namespace["screen_hanger_bolt"]()
    # Shear (SF 2.72), bearing (2.40), and tension (2.62) each clear 2.0, but the
    # §J3.7 combined tension+shear interaction fails at SF 1.89 -> overall FAIL.
    assert card.status is CheckStatus.FAIL
    by_name = {e.name: e for e in card.entries}
    assert by_name["bracket bolt shear"].passed
    assert by_name["bracket plate bearing"].passed
    assert by_name["bracket bolt tension"].passed
    assert not by_name["bracket combined tension+shear"].passed


def test_beam_column_example_passes_h1_interaction():
    namespace = runpy.run_path(str(_EXAMPLES / "beam_column_check.py"))
    card = namespace["screen_beam_column_post"]()
    # The pipe beam-column clears the AISC §H1.1 interaction (SF ~1.64 vs 1.5).
    assert card.status is CheckStatus.PASS
    assert card.entries[0].name == "frame_post interaction"
    assert card.entries[0].reference == "AISC 360-16 §H1.1"


def test_wheel_rail_contact_example_fails_on_soft_steel():
    namespace = runpy.run_path(str(_EXAMPLES / "wheel_rail_contact.py"))
    card = namespace["screen_wheel_contact"]()
    # The ~600 MPa surface contact pressure exceeds annealed 4140's 417 MPa yield
    # -> FAIL, the lesson that rolling-contact parts must be surface-hardened.
    assert card.status is CheckStatus.FAIL
    assert [e.name for e in card.entries] == ["wheel/rail surface contact"]


def test_shrink_fit_example_passes_hub_yield():
    namespace = runpy.run_path(str(_EXAMPLES / "shrink_fit_check.py"))
    card = namespace["screen_shrink_fit"]()
    # The Ø40 H7/s6 fit in a solid 80 mm steel hub develops a hub bore hoop stress
    # well within 1045 steel's yield -> PASS (SF ~2.87 vs the 2.0 requirement).
    assert card.status is CheckStatus.PASS
    assert [e.name for e in card.entries] == ["hub bore hoop"]


def test_lug_drawing_example_checks_and_draws(tmp_path):
    pytest.importorskip("ezdxf")
    namespace = runpy.run_path(str(_EXAMPLES / "lug_drawing.py"))
    card, path = namespace["check_and_draw_lug"](tmp_path / "padeye.dxf")
    # The full white-space vertical: the lug passes its ASME BTH-1 checks and its
    # DXF outline is written.
    assert card.status is CheckStatus.PASS
    assert path.exists()
