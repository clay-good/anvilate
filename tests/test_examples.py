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
    # A well-sized mezzanine: the beam (bending + deflection + shear) and both
    # posts pass.
    assert card.status is CheckStatus.PASS
    assert len(card.entries) == 5
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


def test_machine_on_floor_beam_example_recovers_margin_from_the_real_position():
    namespace = runpy.run_path(str(_EXAMPLES / "machine_on_floor_beam.py"))
    card = namespace["screen_floor_beam"]()
    # The assume-mid-span screen fails (M = P*L/4 -> SF 1.19 < 1.5), but the real
    # quarter-point moment is 3/4 of that, so the actual-position screen passes
    # (SF 1.58). Same beam, same load -- only the declared position differs.
    assert card.status is CheckStatus.FAIL
    by_name = {e.name: e for e in card.entries}
    assert not by_name["assumed mid-span bending"].passed
    assert by_name["actual position bending"].passed


def test_jib_boom_example_recovers_margin_from_the_end_stop():
    namespace = runpy.run_path(str(_EXAMPLES / "jib_boom_trolley.py"))
    card = namespace["screen_jib_boom"]()
    # The assume-at-tip screen fails (M = P*L -> SF 1.33 < 1.5), but the trolley's
    # 750 mm end stop caps the moment at 3/4 of that, so the actual-position
    # screen passes (SF 1.78). Same boom, same hoist -- only the position differs.
    assert card.status is CheckStatus.FAIL
    by_name = {e.name: e for e in card.entries}
    assert not by_name["assumed at tip bending"].passed
    assert by_name["at end stop bending"].passed


def test_press_on_clamped_beam_example_shows_mid_span_is_unconservative():
    namespace = runpy.run_path(str(_EXAMPLES / "press_on_clamped_beam.py"))
    card = namespace["screen_clamped_beam"]()
    # The opposite lesson of the floor-beam example: on a fixed-fixed beam the
    # wall moment peaks at the third point (4*P*L/27 > P*L/8), so the assumed
    # mid-span screen passes (SF 1.62) while the real position fails (SF 1.36).
    assert card.status is CheckStatus.FAIL
    by_name = {e.name: e for e in card.entries}
    assert by_name["assumed mid-span bending"].passed
    assert not by_name["at third point bending"].passed


def test_walkway_beam_example_recovers_deflection_margin_from_end_fixity():
    namespace = runpy.run_path(str(_EXAMPLES / "walkway_beam_end_fixity.py"))
    card = namespace["screen_walkway_beam"]()
    # Bending passes identically both ways (M = w*L^2/8 either way, SF 3.0); only
    # deflection separates them: pin-pin 11.57 mm fails L/360 = 11.11 mm, the
    # propped cantilever's 4.81 mm passes.
    assert card.status is CheckStatus.FAIL
    by_name = {e.name: e for e in card.entries}
    assert by_name["assumed pin-pin bending"].passed
    assert not by_name["assumed pin-pin deflection"].passed
    assert by_name["wall end fixed bending"].passed
    assert by_name["wall end fixed deflection"].passed


def test_i_beam_same_steel_example_shows_shape_beats_area():
    namespace = runpy.run_path(str(_EXAMPLES / "i_beam_same_steel.py"))
    card = namespace["screen_same_steel"]()
    # Equal steel area, opposite verdicts: the square bar fails at SF 0.95 while
    # the I-shape's 7.4x section modulus passes at 6.99.
    assert card.status is CheckStatus.FAIL
    by_name = {e.name: e for e in card.entries}
    assert not by_name["square bar bending"].passed
    assert by_name["I-beam bending"].passed


def test_monorail_trolley_example_fails_only_at_the_true_worst_spot():
    namespace = runpy.run_path(str(_EXAMPLES / "monorail_trolley_sweep.py"))
    card = namespace["screen_runway_beam"]()
    # On a propped cantilever the wall moment peaks at L/sqrt(3) from the prop,
    # 2.6% above mid-span — so mid-span passes at SF 2.03 while the true worst
    # spot fails at 1.98. A mid-span-only screen would have missed it.
    assert card.status is CheckStatus.FAIL
    by_name = {e.name: e for e in card.entries}
    assert by_name["trolley at quarter point bending"].passed
    assert by_name["trolley at mid-span bending"].passed
    assert not by_name["trolley at worst spot bending"].passed


def test_clip_angle_example_fails_only_the_relocated_tearout():
    namespace = runpy.run_path(str(_EXAMPLES / "clip_angle_edge_tearout.py"))
    card = namespace["screen_clip_bolt"]()
    # Shear (SF 1.57) and bearing (1.67) are identical at both positions, but the
    # relocated bolt's clear distance drops to 4 mm and tear-out fails at SF 1.28.
    assert card.status is CheckStatus.FAIL
    by_name = {e.name: e for e in card.entries}
    assert by_name["as detailed edge tear-out"].passed
    assert by_name["relocated bolt shear"].passed
    assert by_name["relocated plate bearing"].passed
    assert not by_name["relocated edge tear-out"].passed


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


def test_flat_bar_strut_example_buckles_about_the_weak_axis():
    namespace = runpy.run_path(str(_EXAMPLES / "flat_bar_strut_weak_axis.py"))
    card = namespace["screen_flat_bar_strut"]()
    # The builder section carries both second moments, so the as-drawn
    # declaration screens about the weak axis automatically and fails
    # honestly; only a hand-built raw section (no transverse I) can still
    # produce the false strong-axis green.
    by_name = {e.name: e for e in card.entries}
    assert by_name["as-drawn (guarded) buckling (Euler)"].status is CheckStatus.FAIL
    assert by_name["raw strong-axis section buckling (Johnson)"].passed
    assert card.status is CheckStatus.FAIL


def test_flood_barrier_example_recovers_margin_from_the_true_load_shape():
    namespace = runpy.run_path(str(_EXAMPLES / "flood_barrier_stiffener.py"))
    card = namespace["screen_flood_barrier_stiffener"]()
    by_name = {e.name: e for e in card.entries}
    # Smearing the peak hydrostatic pressure over the span as a UDL fails both
    # checks; the actual triangular load passes both with room to spare.
    assert by_name["peak smeared as UDL bending"].status is CheckStatus.FAIL
    assert by_name["peak smeared as UDL deflection"].status is CheckStatus.FAIL
    assert by_name["actual hydrostatic triangle bending"].passed
    assert by_name["actual hydrostatic triangle deflection"].passed


def test_pallet_bay_example_brackets_the_patch_between_the_shortcuts():
    namespace = runpy.run_path(str(_EXAMPLES / "pallet_bay_floor_beam.py"))
    card = namespace["screen_pallet_bay"]()
    by_name = {e.name: e for e in card.entries}
    # The declared half-span patch passes at its true SF 2.32...
    assert by_name["declared half-span patch bending"].passed
    assert "safety factor 2.32" in by_name["declared half-span patch bending"].detail
    # ...while smearing the intensity over the span fails (over-conservative) and
    # spreading the total over the span reports margin that isn't there (2.61).
    assert by_name["intensity smeared over the span bending"].status is CheckStatus.FAIL
    assert by_name["total spread over the span bending"].passed
    assert "safety factor 2.61" in by_name["total spread over the span bending"].detail


def test_tank_baffle_example_shows_partial_fixity_raising_the_stress():
    namespace = runpy.run_path(str(_EXAMPLES / "tank_baffle_end_fixity.py"))
    card = namespace["screen_tank_baffle"]()
    by_name = {e.name: e for e in card.entries}
    assert card.status is CheckStatus.PASS
    # Welding only the floor seam in CUTS deflection but RAISES the peak stress
    # above the pinned idealization (w0*L^2/15 vs w0*L^2/(9*sqrt(3))); welding
    # both ends recovers strength too.
    assert "safety factor 2.66" in by_name["pinned both ends bending"].detail
    assert "safety factor 2.55" in by_name["welded floor seam only bending"].detail
    assert "safety factor 3.41" in by_name["welded both ends bending"].detail
    assert "deflection 4.986" in by_name["pinned both ends deflection"].detail
    assert "deflection 1.823" in by_name["welded floor seam only deflection"].detail
    assert "deflection 1.000" in by_name["welded both ends deflection"].detail


def test_machine_skid_example_shows_the_stress_neutral_fixity_win():
    namespace = runpy.run_path(str(_EXAMPLES / "machine_skid_end_fixity.py"))
    card = namespace["screen_machine_skid"]()
    by_name = {e.name: e for e in card.entries}
    assert card.status is CheckStatus.PASS
    # Welding the end the skid parks against cuts deflection three-fold at ZERO
    # stress cost — for a half-span end patch the wall moment w*a^2*(2L-a)^2/(8L^2)
    # coincides exactly with the pinned case's sagging peak 9*w*L^2/128 — unlike
    # the tank-baffle triangular case, where the same weld raised the stress.
    assert "safety factor 5.56" in by_name["pinned both ends bending"].detail
    assert "safety factor 5.56" in by_name["welded at the skid end bending"].detail
    assert "safety factor 6.83" in by_name["welded both ends bending"].detail
    assert "deflection 1.398" in by_name["pinned both ends deflection"].detail
    assert "deflection 0.451" in by_name["welded at the skid end deflection"].detail
    assert "deflection 0.285" in by_name["welded both ends deflection"].detail


def test_skid_position_example_fails_the_mid_platform_placement():
    namespace = runpy.run_path(str(_EXAMPLES / "skid_position_on_platform.py"))
    card = namespace["screen_skid_positions"]()
    by_name = {e.name: e for e in card.entries}
    # Rolling the skid from the wall to mid-platform doubles the wall moment
    # (w*a^2/2 -> w*a*L/2), halving the stress SF and tripling the tip
    # deflection past L/180 — the placement alone flips the screen.
    assert "safety factor 3.13" in by_name["parked at the wall bending"].detail
    assert "safety factor 1.56" in by_name["parked mid-platform bending"].detail
    assert by_name["parked at the wall deflection"].passed
    assert "deflection 3.883" in by_name["parked at the wall deflection"].detail
    assert by_name["parked mid-platform deflection"].status is CheckStatus.FAIL
    assert "deflection 11.649" in by_name["parked mid-platform deflection"].detail
    assert card.status is CheckStatus.FAIL


def test_stiffener_weld_end_example_fails_opposite_criteria():
    namespace = runpy.run_path(str(_EXAMPLES / "stiffener_weld_end.py"))
    card = namespace["screen_weld_ends"]()
    by_name = {e.name: e for e in card.entries}
    # Welding the sill puts the hydrostatic peak at the wall: stiff but
    # overstressed. Mirroring the fixity trims the wall moment (w0*L^2/15 ->
    # 7*w0*L^2/120) but bears on the softer mid-span — the two orientations
    # fail OPPOSITE criteria.
    assert by_name["welded at the sill (peak at the wall) bending"].status is CheckStatus.FAIL
    assert "safety factor 1.36" in by_name["welded at the sill (peak at the wall) bending"].detail
    assert by_name["welded at the sill (peak at the wall) deflection"].passed
    assert "deflection 2.469" in by_name["welded at the sill (peak at the wall) deflection"].detail
    assert by_name["welded at the waler (peak at the prop) bending"].passed
    assert "safety factor 1.55" in by_name["welded at the waler (peak at the prop) bending"].detail
    assert by_name["welded at the waler (peak at the prop) deflection"].status is CheckStatus.FAIL
    assert "deflection 3.155" in by_name["welded at the waler (peak at the prop) deflection"].detail
    assert card.status is CheckStatus.FAIL


def test_genset_example_recovers_margin_from_the_declared_rails():
    namespace = runpy.run_path(str(_EXAMPLES / "genset_on_two_rails.py"))
    card = namespace["screen_genset_beam"]()
    by_name = {e.name: e for e in card.entries}
    # The lumped 10 kN mid-span resultant fails both screens; the declared
    # third-point rails carry a constant M = F*a, 2/3 of the lumped moment,
    # and pass both.
    assert by_name["lumped mid-span resultant bending"].status is CheckStatus.FAIL
    assert "safety factor 1.25" in by_name["lumped mid-span resultant bending"].detail
    assert by_name["lumped mid-span resultant deflection"].status is CheckStatus.FAIL
    assert "deflection 13.677" in by_name["lumped mid-span resultant deflection"].detail
    assert by_name["declared skid rails bending"].passed
    assert "safety factor 1.87" in by_name["declared skid rails bending"].detail
    assert by_name["declared skid rails deflection"].passed
    assert "deflection 11.650" in by_name["declared skid rails deflection"].detail
    assert card.status is CheckStatus.FAIL


def test_canopy_snow_drift_example_flips_on_the_drift_orientation():
    namespace = runpy.run_path(str(_EXAMPLES / "canopy_snow_drift.py"))
    card = namespace["screen_canopy_drift"]()
    by_name = {e.name: e for e in card.entries}
    # Drift assumed against the building face screens green; mirrored to the
    # edge fascia the resultant moves to 2L/3, doubling the wall moment and
    # nearly tripling the tip deflection (1/30 -> 11/120 of w0*L^4/EI).
    assert by_name["drift against the building face bending"].passed
    assert "safety factor 2.29" in by_name["drift against the building face bending"].detail
    assert by_name["drift against the building face deflection"].passed
    assert "deflection 8.855" in by_name["drift against the building face deflection"].detail
    assert by_name["drift against the edge fascia bending"].status is CheckStatus.FAIL
    assert "safety factor 1.14" in by_name["drift against the edge fascia bending"].detail
    assert by_name["drift against the edge fascia deflection"].status is CheckStatus.FAIL
    assert "deflection 24.350" in by_name["drift against the edge fascia deflection"].detail
    assert card.status is CheckStatus.FAIL


def test_davit_example_flips_on_the_sheave_overhang_couple():
    namespace = runpy.run_path(str(_EXAMPLES / "davit_sheave_overhang.py"))
    card = namespace["screen_davit_boom"]()
    by_name = {e.name: e for e in card.entries}
    # The hoist load idealized at the tip clears the rigging factor and L/180;
    # the sheave bracket's true couple F*e grows the wall moment by e/L = 25%
    # and adds M*L^2/2EI of tip deflection — both screens flip to FAIL.
    assert by_name["boom (load at tip) bending"].passed
    assert "safety factor 2.04" in by_name["boom (load at tip) bending"].detail
    assert by_name["boom (load at tip) deflection"].passed
    assert "deflection 5.870" in by_name["boom (load at tip) deflection"].detail
    assert by_name["boom (sheave overhang) bending"].status is CheckStatus.FAIL
    assert "safety factor 1.64" in by_name["boom (sheave overhang) bending"].detail
    assert by_name["boom (sheave overhang) deflection"].status is CheckStatus.FAIL
    assert "deflection 8.071" in by_name["boom (sheave overhang) deflection"].detail
    assert card.status is CheckStatus.FAIL


def test_test_blind_example_sizes_the_plate_through_the_pack():
    namespace = runpy.run_path(str(_EXAMPLES / "test_blind_sizing.py"))
    card = namespace["screen_test_blind"]()
    by_name = {e.name: e for e in card.entries}
    # The gasketed (simply-supported) blind at 12 mm fails both screens;
    # 16 mm passes both, each entry citing the plate theory it ran.
    assert by_name["12 mm blind plate bending"].status is CheckStatus.FAIL
    assert "safety factor 1.21" in by_name["12 mm blind plate bending"].detail
    assert by_name["12 mm blind flatness"].status is CheckStatus.FAIL
    assert "deflection 1.932" in by_name["12 mm blind flatness"].detail
    assert by_name["16 mm blind plate bending"].passed
    assert "safety factor 2.15" in by_name["16 mm blind plate bending"].detail
    assert by_name["16 mm blind flatness"].passed
    assert by_name["16 mm blind flatness"].reference == "Timoshenko plate theory"
    assert card.status is CheckStatus.FAIL


def test_dock_edge_example_is_governed_by_back_span_uplift():
    namespace = runpy.run_path(str(_EXAMPLES / "dock_edge_overhang.py"))
    card = namespace["screen_dock_edge"]()
    by_name = {e.name: e for e in card.entries}
    # Bending clears comfortably; the governing movement is the back span
    # bowing UP (4.20 mm, beating the 3.77 mm tip drop at this short
    # overhang) past the 3 mm deck flatness limit.
    assert by_name["dock edge bending"].passed
    assert "safety factor 2.86" in by_name["dock edge bending"].detail
    assert by_name["dock edge deflection"].status is CheckStatus.FAIL
    assert "deflection 4.203" in by_name["dock edge deflection"].detail
    assert card.status is CheckStatus.FAIL


def test_machine_foot_example_catches_the_smeared_footprint():
    namespace = runpy.run_path(str(_EXAMPLES / "machine_foot_on_panel.py"))
    card = namespace["screen_machine_foot"]()
    by_name = {e.name: e for e in card.entries}
    # The same 5 kN: smeared it screens comfortably green; on its true
    # 100 mm pad it concentrates 4.4x the bending and flips both checks.
    assert by_name["smeared over the panel bending"].passed
    assert "safety factor 6.26" in by_name["smeared over the panel bending"].detail
    assert by_name["smeared over the panel deflection"].passed
    assert by_name["declared 100 mm pad bending"].status is CheckStatus.FAIL
    assert "safety factor 1.41" in by_name["declared 100 mm pad bending"].detail
    assert by_name["declared 100 mm pad deflection"].status is CheckStatus.FAIL
    assert "deflection 3.433" in by_name["declared 100 mm pad deflection"].detail
    assert card.status is CheckStatus.FAIL


def test_manway_lid_example_flips_on_the_edge_fixity_assumption():
    namespace = runpy.run_path(str(_EXAMPLES / "manway_lid_fixity.py"))
    card = namespace["screen_manway_lid"]()
    by_name = {e.name: e for e in card.entries}
    # Clamped the lid screens comfortably; modeled honestly as gasketed
    # (simply supported) it deflects (5+nu)/(1+nu) = 4.08x more and busts the
    # gasket flatness limit, while strength still passes.
    assert by_name["welded rim (clamped) bending"].passed
    assert "safety factor 3.84" in by_name["welded rim (clamped) bending"].detail
    assert by_name["welded rim (clamped) flatness"].passed
    assert "deflection 0.771" in by_name["welded rim (clamped) flatness"].detail
    assert by_name["gasketed rim (simply supported) bending"].passed
    assert "safety factor 2.33" in by_name["gasketed rim (simply supported) bending"].detail
    assert by_name["gasketed rim (simply supported) flatness"].status is CheckStatus.FAIL
    assert "deflection 3.145" in by_name["gasketed rim (simply supported) flatness"].detail
    assert card.status is CheckStatus.FAIL


def test_access_cover_example_is_governed_by_stiffness_not_strength():
    namespace = runpy.run_path(str(_EXAMPLES / "access_cover_sizing.py"))
    card = namespace["screen_access_cover"]()
    by_name = {e.name: e for e in card.entries}
    # 6 mm clears the strength screen (SF 2.31) but bows past b/250; 8 mm
    # fixes it — stress falls with t^2 but deflection with t^3.
    assert by_name["6 mm cover bending"].passed
    assert "safety factor 2.31" in by_name["6 mm cover bending"].detail
    assert by_name["6 mm cover flatness"].status is CheckStatus.FAIL
    assert "deflection 2.499" in by_name["6 mm cover flatness"].detail
    assert by_name["8 mm cover bending"].passed
    assert by_name["8 mm cover flatness"].passed
    assert "deflection 1.054" in by_name["8 mm cover flatness"].detail
    assert card.status is CheckStatus.FAIL


def test_flywheel_example_moves_the_twist_mode_with_shaft_diameter():
    namespace = runpy.run_path(str(_EXAMPLES / "flywheel_torsional_mode.py"))
    card = namespace["screen_flywheel_drive"]()
    by_name = {e.name: e for e in card.entries}
    # The as-drawn stub's twist mode sits dead on the 3000 rpm torque ripple;
    # a 25% shaft upsize (J ~ d^4, f ~ d^2) moves it 56% and clears the floor.
    assert by_name["Ø20 shaft as drawn"].status is CheckStatus.FAIL
    assert "fundamental 50.5 Hz" in by_name["Ø20 shaft as drawn"].detail
    assert by_name["Ø25 shaft upsized"].passed
    assert "fundamental 78.8 Hz" in by_name["Ø25 shaft upsized"].detail
    assert card.status is CheckStatus.FAIL


def test_pump_beam_example_fails_only_the_modal_dimension():
    namespace = runpy.run_path(str(_EXAMPLES / "pump_mezzanine_beam.py"))
    card = namespace["screen_pump_beam"]()
    by_name = {e.name: e for e in card.entries}
    # One declaration yields all three dimensions: statically bulletproof
    # (SF 9.27, 2.1 mm inside L/360), yet the fundamental idles at ~80% of
    # the 1450 rpm forcing frequency and the card fails on resonance alone.
    assert by_name["pump beam bending"].passed
    assert "safety factor 9.27" in by_name["pump beam bending"].detail
    assert by_name["pump beam deflection"].passed
    assert "deflection 2.106" in by_name["pump beam deflection"].detail
    assert by_name["pump beam resonance"].status is CheckStatus.FAIL
    assert "fundamental 23.9 Hz" in by_name["pump beam resonance"].detail
    assert card.status is CheckStatus.FAIL


def test_fan_deck_example_rescues_resonance_with_end_fixity():
    namespace = runpy.run_path(str(_EXAMPLES / "fan_deck_resonance.py"))
    card = namespace["screen_fan_deck"]()
    by_name = {e.name: e for e in card.entries}
    # Simply supported the deck's first mode sits below the 1450 rpm fan;
    # welding the ends swaps the eigenvalue pi^2 -> 22.37 and clears the
    # 29 Hz floor with the same steel.
    assert by_name["on clip angles (simply supported)"].status is CheckStatus.FAIL
    assert "fundamental 17.0 Hz" in by_name["on clip angles (simply supported)"].detail
    assert by_name["ends welded to headers (fixed-fixed)"].passed
    assert "fundamental 38.6 Hz" in by_name["ends welded to headers (fixed-fixed)"].detail
    assert card.status is CheckStatus.FAIL


def test_retaining_wall_example_catches_the_unconservative_shortcut():
    namespace = runpy.run_path(str(_EXAMPLES / "retaining_wall_post.py"))
    card = namespace["screen_retaining_post"]()
    by_name = {e.name: e for e in card.entries}
    # The resultant-at-centroid shortcut reproduces the fixed-end moment exactly,
    # so both bending screens agree and pass...
    assert by_name["soldier post bending"].passed
    assert by_name["resultant-at-centroid bending"].passed
    # ...but it under-predicts the tip deflection by 26% (w0*L^4/40.5EI vs /30EI):
    # the shortcut reports a false green while the declared triangle fails L/180.
    assert by_name["resultant-at-centroid deflection"].passed
    assert by_name["soldier post deflection"].status is CheckStatus.FAIL
    assert card.status is CheckStatus.FAIL


def test_plenum_panel_example_hears_the_blower_only_through_the_modal_screen():
    namespace = runpy.run_path(str(_EXAMPLES / "plenum_access_panel.py"))
    card = namespace["screen_plenum_panel"]()
    by_name = {e.name: e for e in card.entries}
    # Statically the clipped panel is nowhere near working hard...
    assert by_name["clipped rim (simply supported) plate bending"].passed
    assert by_name["clipped rim (simply supported) flatness"].passed
    # ...but its first mode sits inside the blade-pass band, and only the
    # min_frequency floor sees it; welding the rim lifts the fundamental 1.9x.
    resonance = by_name["clipped rim (simply supported) resonance"]
    assert resonance.status is CheckStatus.FAIL
    assert "fundamental 108.3 Hz vs required minimum 120.0 Hz" in resonance.detail
    welded = by_name["welded rim (clamped) resonance"]
    assert welded.passed
    assert "fundamental 205.5 Hz" in welded.detail
    assert card.status is CheckStatus.FAIL


def test_sight_port_blind_example_fails_the_passing_blind_on_the_declared_hole():
    namespace = runpy.run_path(str(_EXAMPLES / "sight_port_blind.py"))
    card = namespace["screen_sight_port_blind"]()
    by_name = {e.name: e for e in card.entries}
    # The solid 16 mm blind passes the hydro screen...
    assert by_name["16 mm solid blind plate bending"].passed
    assert "safety factor 2.15" in by_name["16 mm solid blind plate bending"].detail
    # ...but the declared O80 sight port concentrates hoop bending at its free
    # edge (1.77x) and the same blind fails strength.
    ported = by_name["16 mm blind with port plate bending"]
    assert ported.status is CheckStatus.FAIL
    assert "safety factor 1.22" in ported.detail
    assert by_name["16 mm blind with port flatness"].passed
    # One size up clears both screens again.
    assert by_name["20 mm blind with port plate bending"].passed
    assert "safety factor 1.90" in by_name["20 mm blind with port plate bending"].detail
    assert by_name["20 mm blind with port flatness"].passed
    assert card.status is CheckStatus.FAIL


def test_cam_spring_example_fails_the_speed_up_on_surge_alone():
    namespace = runpy.run_path(str(_EXAMPLES / "cam_return_spring.py"))
    card = namespace["screen_cam_return_spring"]()
    by_name = {e.name: e for e in card.entries}
    # The wire stress never changes with machine speed...
    assert by_name["return spring wire shear"].passed
    assert "safety factor 2.00" in by_name["return spring wire shear"].detail
    # ...but the coil's own 139.7 Hz surge mode is 28 cam orders up at
    # 300 rpm and only 7 at 1200 — the speed-up fails on surge alone.
    assert by_name["coil surge at 300 rpm"].passed
    assert by_name["coil surge at 1200 rpm"].status is CheckStatus.FAIL
    assert "fundamental 139.7 Hz" in by_name["coil surge at 1200 rpm"].detail
    assert card.status is CheckStatus.FAIL


def test_hub_heating_example_sizes_the_oven_not_just_the_fit():
    namespace = runpy.run_path(str(_EXAMPLES / "hub_heating_for_assembly.py"))
    card = namespace["screen_hub_heating"]()
    by_name = {e.name: e for e in card.entries}
    # The 150 degC bench oven opens the O40 bore 61 um — past the 59 um
    # interference by 2 um, which is how hubs seize half-way on; the fit
    # plus the 25 um slip allowance needs 84 um (a ~199 degC setpoint).
    bench = by_name["bench oven at 150 degC bore opening"]
    assert bench.status is CheckStatus.FAIL
    assert "opens 61 um vs required 84 um" in bench.detail
    furnace = by_name["furnace at 250 degC bore opening"]
    assert furnace.passed
    assert "opens 108 um" in furnace.detail
    assert "setpoint needed 199 degC" in furnace.detail
    assert card.status is CheckStatus.FAIL


def test_hydraulic_cylinder_example_catches_the_misused_thin_wall_form():
    namespace = runpy.run_path(str(_EXAMPLES / "hydraulic_cylinder_wall.py"))
    card = namespace["screen_cylinder_barrel"]()
    by_name = {e.name: e for e in card.entries}
    # The membrane shortcut at r/t = 2.5 reads 150 MPa and passes...
    thin = by_name["thin-wall membrane (r/t 2.5)"]
    assert thin.passed
    assert "safety factor 2.78" in thin.detail
    # ...but the exact Lame bore Tresca intensity (185 hoop on -60 radial)
    # works the bore at 245 MPa and fails the same screen.
    lame = by_name["Lame bore intensity"]
    assert lame.status is CheckStatus.FAIL
    assert "safety factor 1.70" in lame.detail
    assert card.status is CheckStatus.FAIL


def test_off_center_post_example_catches_the_p_delta_feedback():
    namespace = runpy.run_path(str(_EXAMPLES / "off_center_post_load.py"))
    card = namespace["screen_off_center_post"]()
    by_name = {e.name: e for e in card.entries}
    # Plain superposition squeaks past the screen...
    naive = by_name["superposition (no P-delta)"]
    assert naive.passed
    assert "safety factor 2.03" in naive.detail
    # ...but at 60% of Euler the P-delta feedback amplifies the bending 2.88x
    # and the exact secant stress nearly reaches yield.
    secant = by_name["secant formula (exact)"]
    assert secant.status is CheckStatus.FAIL
    assert "safety factor 1.04" in secant.detail
    assert card.status is CheckStatus.FAIL


def test_guide_spring_buckling_example_folds_past_the_working_stroke():
    namespace = runpy.run_path(str(_EXAMPLES / "guide_spring_buckling.py"))
    card = namespace["screen_guide_spring_buckling"]()
    by_name = {e.name: e for e in card.entries}
    # The wire-stress screen is comfortable at the working load...
    shear = by_name["guide spring wire shear"]
    assert shear.passed
    assert "safety factor 2.00" in shear.detail
    # ...but the 60 mm stroke drives the slender coil past its 45 mm critical
    # buckling deflection, so it folds sideways and the screen FAILs.
    buckling = by_name["guide spring buckling"]
    assert buckling.status is CheckStatus.FAIL
    assert "60.000 mm vs limit 45.418 mm" in buckling.detail
    assert card.status is CheckStatus.FAIL


def test_frame_member_torsion_example_collapses_when_the_seam_is_left_open():
    namespace = runpy.run_path(str(_EXAMPLES / "frame_member_torsion.py"))
    card = namespace["screen_frame_member_torsion"]()
    by_name = {e.name: e for e in card.entries}
    # Closed into a box tube the wall shear is a comfortable SF 4.35...
    closed = by_name["closed box wall shear"]
    assert closed.passed
    assert "safety factor 4.35" in closed.detail
    # ...but the same wall left open (unwelded seam) carries ~20x the shear and
    # blows past the allowable -> the assembly FAILs.
    opened = by_name["open seam wall shear"]
    assert opened.status is CheckStatus.FAIL
    assert "safety factor 0.21" in opened.detail
    assert card.status is CheckStatus.FAIL


def test_bolt_tension_thread_area_example_fails_on_the_real_area():
    namespace = runpy.run_path(str(_EXAMPLES / "bolt_tension_thread_area.py"))
    card = namespace["screen_bolt_tension"]()
    by_name = {e.name: e for e in card.entries}
    # Spread over the nominal shank area the tension looks fine (SF 1.73)...
    shank = by_name["shank-area tension (nominal)"]
    assert shank.passed
    assert "safety factor 1.73" in shank.detail
    # ...but on the ISO 898 tensile stress area through the threads -- where the
    # bolt actually fails -- the same load is under the 1.5 requirement (SF 1.29).
    thread = by_name["tensile-area tension (threads)"]
    assert thread.status is CheckStatus.FAIL
    assert "safety factor 1.29" in thread.detail
    assert card.status is CheckStatus.FAIL


def test_conveyor_bearing_life_example_needs_the_heavy_bearing():
    namespace = runpy.run_path(str(_EXAMPLES / "conveyor_bearing_life.py"))
    card = namespace["screen_pulley_bearing"]()
    by_name = {e.name: e for e in card.entries}
    # The bearing that fits the shaft lasts only a quarter of the 30,000 h target.
    light = by_name["6208 (light)"]
    assert light.status is CheckStatus.FAIL
    assert "safety factor 0.25" in light.detail
    # Even a medium upsize falls short (SF 0.73)...
    medium = by_name["6308 (medium)"]
    assert medium.status is CheckStatus.FAIL
    assert "safety factor 0.73" in medium.detail
    assert card.status is CheckStatus.FAIL
    # ...only the heavy bearing clears it, with a comfortable life margin.
    heavy = by_name["6310 (heavy)"]
    assert heavy.passed
    assert "safety factor 2.28" in heavy.detail


def test_geared_shaft_example_fails_on_combined_loading():
    namespace = runpy.run_path(str(_EXAMPLES / "geared_shaft_sizing.py"))
    card = namespace["screen_geared_shaft"]()
    by_name = {e.name: e for e in card.entries}
    # Sized on torque alone the 30 mm shaft looks fine (SF 2.14)...
    torsion = by_name["torsion-only screen @ 30 mm"]
    assert torsion.passed
    assert "safety factor 2.14" in torsion.detail
    # ...but bending and torsion together bust the 2.0 requirement (SF 1.76).
    combined = by_name["combined bending+torsion @ 30 mm"]
    assert combined.status is CheckStatus.FAIL
    assert "safety factor 1.76" in combined.detail
    assert card.status is CheckStatus.FAIL
    # The 35 mm upsize clears the combined check (SF 2.80).
    upsized = by_name["combined bending+torsion @ 35 mm"]
    assert upsized.passed
    assert "safety factor 2.80" in upsized.detail
    # The combined sizing inverse names the ~31.3 mm floor between them.
    floor = namespace["combined_diameter_floor"]()
    assert floor.to("mm").magnitude == pytest.approx(31.30, rel=1e-3)


def test_tapped_hole_engagement_example_strips_the_soft_threads():
    namespace = runpy.run_path(str(_EXAMPLES / "tapped_hole_engagement.py"))
    card = namespace["screen_tapped_hole"]()
    by_name = {e.name: e for e in card.entries}
    # The steel bolt's own threads clear one diameter of engagement (SF 2.16)...
    steel = by_name["steel bolt threads @ 1*d"]
    assert steel.passed
    assert "safety factor 2.16" in steel.detail
    # ...but the soft aluminium tapped hole strips first -- one diameter busts the
    # 2.0 requirement (SF 1.29) -> the joint FAILs.
    alum_short = by_name["aluminium hole threads @ 1*d"]
    assert alum_short.status is CheckStatus.FAIL
    assert "safety factor 1.29" in alum_short.detail
    assert card.status is CheckStatus.FAIL
    # Two diameters of engagement halves the stripping stress and recovers it.
    alum_deep = by_name["aluminium hole threads @ 2*d"]
    assert alum_deep.passed
    assert "safety factor 2.58" in alum_deep.detail


def test_coupling_key_example_passes_shear_but_fails_bearing():
    namespace = runpy.run_path(str(_EXAMPLES / "coupling_key_sizing.py"))
    card = namespace["screen_coupling_key"]()
    by_name = {e.name: e for e in card.entries}
    # Sized on shear, the 10 mm key clears the shear screen (SF 1.52)...
    shear = by_name["key shear at 10 mm"]
    assert shear.passed
    assert "safety factor 1.52" in shear.detail
    # ...but a parallel key fails in bearing first -> the side stress busts the
    # 1.5 requirement (SF 0.84) and the assembly FAILs.
    bearing = by_name["key bearing at 10 mm"]
    assert bearing.status is CheckStatus.FAIL
    assert "safety factor 0.84" in bearing.detail
    assert card.status is CheckStatus.FAIL
    # The sizing inverse confirms bearing governs and needs ~18 mm.
    req = namespace["required_key_length"]()
    assert req.governing_mode == "bearing"
    assert req.required_length.to("mm").magnitude == pytest.approx(17.778, rel=1e-3)


def test_beam_section_sizing_example_picks_the_section_above_the_floor():
    namespace = runpy.run_path(str(_EXAMPLES / "beam_section_sizing.py"))
    # The required section modulus is the floor a section must clear.
    floor = namespace["floor_section_modulus"]()
    assert floor.to("mm**3").magnitude == pytest.approx(72727.3, rel=1e-4)
    card = namespace["screen_beam_sections"]()
    by_name = {e.name: e for e in card.entries}
    # The 80x120x5 box (Z ~ 62,600 < floor) misses the 1.5 margin...
    small = by_name["80x120x5 box bending"]
    assert small.status is CheckStatus.FAIL
    assert "safety factor 1.29" in small.detail
    # ...the 100x140x6 box (Z ~ 107,000 > floor) clears it comfortably.
    large = by_name["100x140x6 box bending"]
    assert large.passed
    assert "safety factor 2.21" in large.detail
    assert card.status is CheckStatus.FAIL


def test_drive_shaft_sizing_example_fails_when_sized_on_the_mean_torque():
    namespace = runpy.run_path(str(_EXAMPLES / "drive_shaft_sizing.py"))
    on_mean, on_design = namespace["sizing_floors"]()
    # Sizing on the mean torque understates the shaft the peak needs.
    assert on_mean.to("mm").magnitude == pytest.approx(30.21, rel=1e-3)
    assert on_design.to("mm").magnitude == pytest.approx(38.06, rel=1e-3)
    card = namespace["screen_drive_shaft"]()
    by_name = {e.name: e for e in card.entries}
    # Under the service-factored peak the mean-sized 31 mm shaft misses 2.0...
    mean = by_name["mean-sized 31 mm shaft shear"]
    assert mean.status is CheckStatus.FAIL
    assert "safety factor 1.08" in mean.detail
    # ...the design-sized 40 mm shaft clears it.
    design = by_name["design-sized 40 mm shaft shear"]
    assert design.passed
    assert "safety factor 2.32" in design.detail
    assert card.status is CheckStatus.FAIL


def test_lineshaft_critical_speed_example_resonates_only_when_combined():
    namespace = runpy.run_path(str(_EXAMPLES / "lineshaft_critical_speed.py"))
    card = namespace["screen_lineshaft"]()
    by_name = {e.name: e for e in card.entries}
    # Each pulley checked alone clears the 31.2 Hz resonance floor...
    assert by_name["pulley A alone"].passed
    assert by_name["pulley B alone"].passed
    # ...but the Dunkerley-combined critical speed drops below it -> FAIL.
    combined = by_name["both (Dunkerley)"]
    assert combined.status is CheckStatus.FAIL
    assert "28.8 Hz" in combined.detail
    assert card.status is CheckStatus.FAIL


def test_floor_beam_serviceability_example_is_governed_by_deflection():
    namespace = runpy.run_path(str(_EXAMPLES / "floor_beam_serviceability.py"))
    card = namespace["screen_floor_beam"]()
    by_name = {e.name: e for e in card.entries}
    # The beam is comfortably strong (SF 1.71 in bending)...
    bending = by_name["mid-span bending"]
    assert bending.passed
    assert "safety factor 1.71" in bending.detail
    # ...but too flexible: it sags past the L/360 = 16.67 mm limit -> FAIL.
    deflection = by_name["mid-span deflection (L/360)"]
    assert deflection.status is CheckStatus.FAIL
    assert "18.095 mm vs limit 16.667 mm" in deflection.detail
    assert card.status is CheckStatus.FAIL


def test_bracket_weld_sizing_example_fails_the_default_fillet():
    namespace = runpy.run_path(str(_EXAMPLES / "bracket_weld_sizing.py"))
    # The load and length need about an 8 mm leg at the 2.0 margin.
    assert namespace["required_leg"]().to("mm").magnitude == pytest.approx(8.129, rel=1e-3)
    card = namespace["screen_bracket_weld"]()
    by_name = {e.name: e for e in card.entries}
    # The shop-default 5 mm fillet misses the 2.0 requirement (SF 1.23)...
    drawn = by_name["5 mm fillet (as drawn) throat shear"]
    assert drawn.status is CheckStatus.FAIL
    assert "safety factor 1.23" in drawn.detail
    # ...the revised 10 mm fillet clears it.
    revised = by_name["10 mm fillet (revised) throat shear"]
    assert revised.passed
    assert "safety factor 2.46" in revised.detail
    assert card.status is CheckStatus.FAIL


def test_drivetrain_shaft_twist_example_is_governed_by_stiffness():
    namespace = runpy.run_path(str(_EXAMPLES / "drivetrain_shaft_twist.py"))
    card = namespace["screen_drivetrain_shaft"]()
    by_name = {e.name: e for e in card.entries}
    # The shaft is comfortably strong in torsion (SF 2.88)...
    shear = by_name["torsional shear"]
    assert shear.passed
    assert "safety factor 2.88" in shear.detail
    # ...but it winds up past the 0.25 deg/ft positioning limit -> FAIL.
    twist = by_name["shaft twist (0.25 deg/ft)"]
    assert twist.status is CheckStatus.FAIL
    assert "safety factor 0.73" in twist.detail
    assert card.status is CheckStatus.FAIL


def test_winch_band_brake_example_is_sized_by_lining_pressure():
    namespace = runpy.run_path(str(_EXAMPLES / "winch_band_brake.py"))
    card = namespace["screen_winch_brake"]()
    by_name = {e.name: e for e in card.entries}
    # The wrap holds the torque with margin at the rated band tension...
    torque = by_name["hold torque"]
    assert torque.passed
    assert "safety factor 1.66" in torque.detail
    # ...but the working tension crushes the lining on the 40 mm strap -> FAIL.
    narrow = by_name["lining pressure (40 mm band)"]
    assert narrow.status is CheckStatus.FAIL
    assert "safety factor 0.75" in narrow.detail
    assert card.status is CheckStatus.FAIL
    # A 60 mm band spreads the same tension under the allowable.
    wide = by_name["lining pressure (60 mm band)"]
    assert wide.passed
    assert "safety factor 1.12" in wide.detail


def test_high_speed_belt_drive_example_hits_the_power_ceiling():
    namespace = runpy.run_path(str(_EXAMPLES / "high_speed_belt_drive.py"))
    card = namespace["screen_belt_drive"]()
    by_name = {e.name: e for e in card.entries}
    # Short at 3,000 rpm...
    slow = by_name["5.5 kW at 3000 rpm"]
    assert slow.status is CheckStatus.FAIL
    assert "safety factor 0.73" in slow.detail
    # ...and doubling the speed barely helps: past v* the belt carries itself.
    fast = by_name["5.5 kW at 6000 rpm"]
    assert fast.status is CheckStatus.FAIL
    assert "safety factor 0.85" in fast.detail
    # No speed works -- the belt's power ceiling sits below the demand.
    ceiling = by_name["power ceiling at v*"]
    assert ceiling.status is CheckStatus.FAIL
    assert "safety factor 0.92" in ceiling.detail
    assert card.status is CheckStatus.FAIL
    # The fix is tension rating (belt width), not rpm.
    wider = by_name["wider (700 N) belt at its v*"]
    assert wider.passed
    assert "safety factor 1.52" in wider.detail


def test_cart_drum_brake_example_has_a_rotation_direction():
    namespace = runpy.run_path(str(_EXAMPLES / "cart_drum_brake.py"))
    card = namespace["screen_cart_brake"]()
    by_name = {e.name: e for e in card.entries}
    # With the drum dragging the shoe in, the lever holds with margin...
    forward = by_name["hold, drum forward (self-energizing)"]
    assert forward.passed
    assert "safety factor 1.17" in forward.detail
    # ...but the same brake creeps when the rotation de-energizes the shoe.
    reverse = by_name["hold, drum reverse (de-energizing)"]
    assert reverse.status is CheckStatus.FAIL
    assert "safety factor 0.87" in reverse.detail
    assert card.status is CheckStatus.FAIL
    # Leverage, not self-energizing geometry, is the honest fix.
    longer = by_name["800 mm lever, drum reverse"]
    assert longer.passed
    assert "safety factor 1.16" in longer.detail


def test_crane_hook_example_fails_the_straight_beam_screen_honestly():
    namespace = runpy.run_path(str(_EXAMPLES / "crane_hook_shank.py"))
    card = namespace["screen_crane_hook"]()
    by_name = {e.name: e for e in card.entries}
    # The straight-beam formula happily passes the 50 mm shank...
    straight = by_name["bore, straight-beam screen (h=50)"]
    assert straight.passed
    assert "safety factor 2.20" in straight.detail
    # ...but curvature crowds 31% more stress onto the bore -> FAIL.
    winkler = by_name["bore, Winkler curved-beam (h=50)"]
    assert winkler.status is CheckStatus.FAIL
    assert "safety factor 1.68" in winkler.detail
    assert card.status is CheckStatus.FAIL
    # Deepening the shank passes with the honest theory.
    deeper = by_name["bore, Winkler curved-beam (h=60)"]
    assert deeper.passed
    assert "safety factor 2.14" in deeper.detail


def test_fixture_clamp_example_rides_the_belleville_plateau():
    namespace = runpy.run_path(str(_EXAMPLES / "fixture_clamp_washers.py"))
    card = namespace["screen_clamp_washers"]()
    by_name = {e.name: e for e in card.entries}
    # The shallow disc sheds half the clamp force as the joint settles -> FAIL.
    shallow = by_name["shallow disc (h/t = 0.5)"]
    assert shallow.status is CheckStatus.FAIL
    assert "safety factor 0.19" in shallow.detail
    assert card.status is CheckStatus.FAIL
    # The h/t = sqrt(2) disc rides its force plateau: 2.3% loss, 4.3x margin.
    plateau = by_name["plateau disc (h/t = sqrt(2))"]
    assert plateau.passed
    assert "safety factor 4.34" in plateau.detail


def test_winch_planetary_example_checks_teeth_before_torque():
    namespace = runpy.run_path(str(_EXAMPLES / "winch_planetary_reducer.py"))
    card = namespace["screen_winch_reducer"]()
    by_name = {e.name: e for e in card.entries}
    # The motor alone musters a quarter of the drum demand.
    direct = by_name["direct drive, drum torque"]
    assert direct.status is CheckStatus.FAIL
    assert "safety factor 0.28" in direct.detail
    # The tidy 4.5:1 needs a 37.5-tooth planet -- that set cannot be cut...
    half_tooth = by_name["4.5:1 (sun 30, ring 105), buildable"]
    assert half_tooth.status is CheckStatus.FAIL
    assert "no whole-tooth planet fits" in half_tooth.detail
    # ...and 4.7:1 cuts fine but three equally spaced planets never phase in.
    spacing = by_name["4.7:1 (sun 30, ring 110), buildable"]
    assert spacing.status is CheckStatus.FAIL
    assert "cannot assemble" in spacing.detail
    assert card.status is CheckStatus.FAIL
    # The buildable 4.6:1 assembles and clears the torque demand with margin.
    buildable = by_name["4.6:1 (sun 30, ring 108), buildable"]
    assert buildable.passed
    assert "39-tooth planets" in buildable.detail
    torque = by_name["4.6:1 (sun 30, ring 108), drum torque"]
    assert torque.passed
    assert "safety factor 1.26" in torque.detail
    # Unbuildable candidates never get a torque row -- teeth vote first.
    assert "4.5:1 (sun 30, ring 105), drum torque" not in by_name


def test_worm_hoist_example_must_self_lock_before_it_is_efficient():
    namespace = runpy.run_path(str(_EXAMPLES / "worm_hoist_selflock.py"))
    card = namespace["screen_worm_hoist"]()
    by_name = {e.name: e for e in card.entries}
    # Only the single-start worm self-locks -- and it pays in efficiency.
    single = by_name["single-start worm"]
    assert single.passed
    assert "safety factor 1.30" in single.detail
    assert "efficiency 43%" in single.detail
    # The faster multi-start worms back-drive: the load would drop on power loss.
    double = by_name["double-start worm"]
    assert double.status is CheckStatus.FAIL
    assert "efficiency 60%" in double.detail
    triple = by_name["triple-start worm"]
    assert triple.status is CheckStatus.FAIL
    assert "efficiency 69%" in triple.detail
    # A hoist that only self-locks one way overall fails the safe-hold screen.
    assert card.status is CheckStatus.FAIL


def test_conveyor_chain_example_rejects_the_rough_small_sprocket():
    namespace = runpy.run_path(str(_EXAMPLES / "conveyor_chain_drive.py"))
    card = namespace["screen_conveyor_chain"]()
    by_name = {e.name: e for e in card.entries}
    # The cheap 11-tooth driver ripples 4% -- over twice the 2% spec.
    small = by_name["11-tooth driver"]
    assert small.status is CheckStatus.FAIL
    assert "safety factor 0.49" in small.detail
    # 13 teeth still fail; only 17 teeth clear the smoothness spec.
    assert by_name["13-tooth driver"].status is CheckStatus.FAIL
    good = by_name["17-tooth driver"]
    assert good.passed
    assert "safety factor 1.17" in good.detail
    # A drive that offers a failing sprocket overall fails.
    assert card.status is CheckStatus.FAIL


def test_highspeed_cam_example_is_a_speed_squared_problem():
    namespace = runpy.run_path(str(_EXAMPLES / "highspeed_cam_follower.py"))
    card = namespace["screen_cam_follower"]()
    by_name = {e.name: e for e in card.entries}
    # Comfortable at 600 rpm...
    slow = by_name["SHM at 600 rpm"]
    assert slow.passed
    assert "safety factor 3.34" in slow.detail
    # ...but doubling the speed quadruples the acceleration and floats the
    # follower (the omega^2 law).
    fast = by_name["SHM at 1200 rpm"]
    assert fast.status is CheckStatus.FAIL
    assert "safety factor 0.83" in fast.detail
    # Cycloidal's smoother ends cost a higher mid-rise peak: it fails harder.
    cyc = by_name["cycloidal at 1200 rpm"]
    assert cyc.status is CheckStatus.FAIL
    assert "safety factor 0.65" in cyc.detail
    assert card.status is CheckStatus.FAIL


def test_engine_shaking_force_example_turns_on_the_rod_ratio():
    namespace = runpy.run_path(str(_EXAMPLES / "engine_shaking_force.py"))
    card = namespace["screen_shaking_force"]()
    by_name = {e.name: e for e in card.entries}
    # The stubby rod's secondary shake overloads the mounts.
    short = by_name["short rod (L/r = 3.5)"]
    assert short.status is CheckStatus.FAIL
    assert "safety factor 0.95" in short.detail
    # A longer rod lowers the peak and clears the mount rating.
    assert by_name["medium rod (L/r = 5.0)"].passed
    assert "safety factor 1.01" in by_name["medium rod (L/r = 5.0)"].detail
    long = by_name["long rod (L/r = 6.67)"]
    assert long.passed
    assert "safety factor 1.06" in long.detail
    # One failing option makes the overall screen fail.
    assert card.status is CheckStatus.FAIL


def test_fourbar_linkage_example_needs_a_healthy_transmission_angle():
    namespace = runpy.run_path(str(_EXAMPLES / "fourbar_linkage_design.py"))
    card = namespace["screen_fourbar_linkage"]()
    by_name = {e.name: e for e in card.entries}
    # The long-coupler linkage turns but binds -- its worst transmission angle
    # falls to 21 deg, below the 45 deg floor.
    poor = by_name["long-coupler crank-rocker"]
    assert poor.status is CheckStatus.FAIL
    assert "safety factor 0.46" in poor.detail
    # Rebalanced lengths keep the transmission angle healthy through the turn.
    good = by_name["balanced crank-rocker"]
    assert good.passed
    assert "safety factor 1.07" in good.detail
    assert card.status is CheckStatus.FAIL


def test_multistage_reducer_example_sizes_on_delivered_torque():
    namespace = runpy.run_path(str(_EXAMPLES / "multistage_reducer_efficiency.py"))
    card = namespace["screen_reducer"]()
    by_name = {e.name: e for e in card.entries}
    # On ideal (lossless) torque the reducer clears the demand...
    ideal = by_name["ideal (lossless) output torque"]
    assert ideal.passed
    assert "safety factor 1.06" in ideal.detail
    # ...but the compounded three-stage losses drop it below the demand.
    real = by_name["real output torque (three-stage losses)"]
    assert real.status is CheckStatus.FAIL
    assert "safety factor 0.97" in real.detail
    assert card.status is CheckStatus.FAIL


def test_spanning_cable_example_has_no_tension_that_passes_both():
    namespace = runpy.run_path(str(_EXAMPLES / "spanning_cable_tension.py"))
    card = namespace["screen_cable_span"]()
    by_name = {e.name: e for e in card.entries}
    # Slack: protects the cable but sags too far.
    assert by_name["slack (6 kN): sag clearance"].status is CheckStatus.FAIL
    assert by_name["slack (6 kN): cable strength"].passed
    # Balanced: meets clearance exactly but is over the tension allowable.
    assert by_name["balanced (8 kN): sag clearance"].passed
    assert by_name["balanced (8 kN): cable strength"].status is CheckStatus.FAIL
    assert "safety factor 0.98" in by_name["balanced (8 kN): cable strength"].detail
    # Taut: clears the sag with margin but badly overloads the cable.
    assert by_name["taut (12 kN): sag clearance"].passed
    assert by_name["taut (12 kN): cable strength"].status is CheckStatus.FAIL
    # No tension clears both demands -> the window is empty, overall fail.
    assert card.status is CheckStatus.FAIL


def test_shrink_fit_at_speed_example_loses_grip_at_high_speed():
    namespace = runpy.run_path(str(_EXAMPLES / "shrink_fit_at_speed.py"))
    card = namespace["screen_shrink_fit"]()
    by_name = {e.name: e for e in card.entries}
    # Grips cold with margin...
    at_rest = by_name["at rest"]
    assert at_rest.passed
    assert "safety factor 1.67" in at_rest.detail
    # ...still holds at moderate speed, just...
    assert by_name["at 6000 rpm"].passed
    assert "safety factor 1.15" in by_name["at 6000 rpm"].detail
    # ...but the rim growth exceeds the interference at high speed: fit lost.
    fast = by_name["at 12000 rpm"]
    assert fast.status is CheckStatus.FAIL
    assert "safety factor -0.40" in fast.detail
    assert card.status is CheckStatus.FAIL


def test_fracture_toughness_example_favors_toughness_over_strength():
    namespace = runpy.run_path(str(_EXAMPLES / "fracture_toughness_screen.py"))
    card = namespace["screen_fracture_toughness"]()
    by_name = {e.name: e for e in card.entries}
    # The high-strength (brittle) steel's critical crack barely exceeds the
    # detectable flaw size -> fails the inspection margin.
    brittle = by_name["high-strength steel (K_IC 50)"]
    assert brittle.status is CheckStatus.FAIL
    assert "safety factor 0.50" in brittle.detail
    # The tougher steel tolerates a comfortably inspectable crack.
    tough = by_name["tough steel (K_IC 100)"]
    assert tough.passed
    assert "safety factor 1.99" in tough.detail
    assert card.status is CheckStatus.FAIL


def test_vacuum_vessel_example_buckles_before_it_bursts():
    namespace = runpy.run_path(str(_EXAMPLES / "vacuum_vessel_buckling.py"))
    card = namespace["screen_vacuum_vessel"]()
    by_name = {e.name: e for e in card.entries}
    # The thin wall is fine for internal pressure but implodes under vacuum.
    thin = by_name["3 mm wall"]
    assert thin.status is CheckStatus.FAIL
    assert "safety factor 0.04" in thin.detail
    # 8 mm is closer but still short of the buckling margin.
    assert by_name["8 mm wall"].status is CheckStatus.FAIL
    # Only the 12 mm wall (t^3 law) clears the external-pressure buckling margin.
    thick = by_name["12 mm wall"]
    assert thick.passed
    assert "safety factor 2.53" in thick.detail
    assert card.status is CheckStatus.FAIL


def test_helical_thrust_example_lands_on_the_bearing():
    namespace = runpy.run_path(str(_EXAMPLES / "helical_gear_thrust_bearing.py"))
    card = namespace["screen_helical_thrust"]()
    by_name = {e.name: e for e in card.entries}
    # A shallow helix keeps the thrust within the bearing margin...
    shallow = by_name["15 deg helix"]
    assert shallow.passed
    assert "safety factor 2.24" in shallow.detail
    # ...but a smoother, steeper helix overruns it.
    assert by_name["30 deg helix"].status is CheckStatus.FAIL
    steep = by_name["45 deg helix"]
    assert steep.status is CheckStatus.FAIL
    assert "safety factor 0.60" in steep.detail
    assert card.status is CheckStatus.FAIL


def test_cable_resonance_example_tunes_off_the_forcing():
    namespace = runpy.run_path(str(_EXAMPLES / "cable_resonance_tuning.py"))
    card = namespace["screen_cable_resonance"]()
    by_name = {e.name: e for e in card.entries}
    # The low tension tunes the fundamental right onto the forcing -> resonance.
    low = by_name["40 kN"]
    assert low.status is CheckStatus.FAIL
    assert "safety factor 0.68" in low.detail
    # Tightening lifts the fundamental clear of the keep-out band.
    assert by_name["90 kN"].passed
    high = by_name["150 kN"]
    assert high.passed
    assert "safety factor 1.32" in high.detail
    # With a resonant option present, the overall screen fails.
    assert card.status is CheckStatus.FAIL


def test_imperfect_column_example_fails_where_euler_passes():
    namespace = runpy.run_path(str(_EXAMPLES / "imperfect_column_capacity.py"))
    card = namespace["screen_column_capacity"]()
    by_name = {e.name: e for e in card.entries}
    # The perfect-column (Euler/yield) screen waves the column through...
    perfect = by_name["Euler / perfect-column screen"]
    assert perfect.passed
    assert "safety factor 1.22" in perfect.detail
    # ...but the real imperfect column is overloaded.
    real = by_name["Perry-Robertson (real imperfection)"]
    assert real.status is CheckStatus.FAIL
    assert "safety factor 0.87" in real.detail
    assert card.status is CheckStatus.FAIL


def test_glass_thermal_shock_example_favors_low_expansion():
    namespace = runpy.run_path(str(_EXAMPLES / "glass_thermal_shock.py"))
    card = namespace["screen_thermal_shock"]()
    by_name = {e.name: e for e in card.entries}
    # The high-expansion soda-lime glass shatters under the quench...
    soda = by_name["soda-lime tumbler"]
    assert soda.status is CheckStatus.FAIL
    assert "safety factor 0.41" in soda.detail
    # ...but the low-expansion borosilicate survives it.
    boro = by_name["borosilicate beaker"]
    assert boro.passed
    assert "safety factor 1.26" in boro.detail
    assert card.status is CheckStatus.FAIL


def test_machine_isolation_example_needs_a_soft_mount():
    namespace = runpy.run_path(str(_EXAMPLES / "machine_vibration_isolation.py"))
    card = namespace["screen_isolation"]()
    by_name = {e.name: e for e in card.entries}
    # The stiff mount amplifies -- worse than no mount at all.
    stiff = by_name["stiff mount (20 Hz)"]
    assert stiff.status is CheckStatus.FAIL
    assert "safety factor 0.11" in stiff.detail
    # The medium mount isolates a little but falls short of the target.
    assert by_name["medium mount (12 Hz)"].status is CheckStatus.FAIL
    # Only the soft mount clears the isolation target with margin.
    soft = by_name["soft mount (6 Hz)"]
    assert soft.passed
    assert "safety factor 3.02" in soft.detail
    assert card.status is CheckStatus.FAIL


def test_gearbox_output_shaft_example_passes_all_three_modes():
    namespace = runpy.run_path(str(_EXAMPLES / "gearbox_output_shaft.py"))
    card = namespace["screen_output_shaft"]()
    by_name = {e.name: e for e in card.entries}
    # A coherent design clears all three independent failure modes...
    shaft = by_name["shaft, combined bending + torsion"]
    assert shaft.passed
    assert "safety factor 2.98" in shaft.detail
    assert by_name["key, shear"].passed
    # ...and the bearing fatigue life is the governing (tightest) check.
    bearing = by_name["bearings, L10 fatigue life"]
    assert bearing.passed
    assert "safety factor 1.13" in bearing.detail
    assert card.status is CheckStatus.PASS


def test_spring_buckling_example_folds_the_tall_spring():
    namespace = runpy.run_path(str(_EXAMPLES / "spring_buckling_freelength.py"))
    card = namespace["screen_spring_buckling"]()
    by_name = {e.name: e for e in card.entries}
    # The squat spring is absolutely stable...
    short = by_name["short (120 mm)"]
    assert short.passed
    assert "absolutely stable" in short.detail
    # ...the medium one is a column but safe at the operating deflection...
    medium = by_name["medium (150 mm)"]
    assert medium.passed
    assert "safety factor 1.26" in medium.detail
    # ...and the tall one buckles in service though its wire is fine.
    tall = by_name["tall (180 mm)"]
    assert tall.status is CheckStatus.FAIL
    assert "safety factor 0.92" in tall.detail
    assert card.status is CheckStatus.FAIL


def test_bevel_gear_thrust_example_loads_the_gear_shaft_harder():
    namespace = runpy.run_path(str(_EXAMPLES / "bevel_gear_thrust.py"))
    card = namespace["screen_bevel_thrust"]()
    by_name = {e.name: e for e in card.entries}
    # The fast pinion's thrust is comfortably held...
    pinion = by_name["pinion (18 teeth)"]
    assert pinion.passed
    assert "safety factor 1.84" in pinion.detail
    # ...but the larger gear throws twice the thrust (the gear ratio) and overruns
    # the same bearing.
    gear = by_name["gear (36 teeth)"]
    assert gear.status is CheckStatus.FAIL
    assert "safety factor 0.92" in gear.detail
    assert card.status is CheckStatus.FAIL


def test_indexing_table_example_runs_out_of_dwell():
    namespace = runpy.run_path(str(_EXAMPLES / "indexing_table_stations.py"))
    card = namespace["screen_indexing_table"]()
    by_name = {e.name: e for e in card.entries}
    # 6 stations leave just enough dwell for the operation...
    six = by_name["6 stations"]
    assert six.passed
    assert "safety factor 1.05" in six.detail
    # ...but adding stations steals dwell until the operation no longer fits.
    assert by_name["8 stations"].status is CheckStatus.FAIL
    twelve = by_name["12 stations"]
    assert twelve.status is CheckStatus.FAIL
    assert "safety factor 0.92" in twelve.detail
    assert card.status is CheckStatus.FAIL


def test_jacketed_reactor_example_is_governed_by_vacuum():
    namespace = runpy.run_path(str(_EXAMPLES / "jacketed_reactor_vacuum.py"))
    card = namespace["screen_reactor_shell"]()
    by_name = {e.name: e for e in card.entries}
    # Every wall clears the internal pressure with margin...
    assert by_name["3 mm wall: internal pressure (hoop)"].passed
    assert "safety factor 2.07" in by_name["3 mm wall: internal pressure (hoop)"].detail
    assert by_name["12 mm wall: internal pressure (hoop)"].passed
    # ...but the vacuum buckling governs: thin walls fail it.
    assert by_name["3 mm wall: external vacuum (buckling)"].status is CheckStatus.FAIL
    assert by_name["6 mm wall: external vacuum (buckling)"].status is CheckStatus.FAIL
    thick_vac = by_name["12 mm wall: external vacuum (buckling)"]
    assert thick_vac.passed
    assert "safety factor 2.53" in thick_vac.detail
    # The 3 mm wall passes pressure but fails vacuum -> overall FAIL.
    assert card.status is CheckStatus.FAIL


def test_bolted_cover_flange_example_counts_bolts_for_the_end_force():
    namespace = runpy.run_path(str(_EXAMPLES / "bolted_cover_flange.py"))
    card = namespace["screen_cover_bolts"]()
    by_name = {e.name: e for e in card.entries}
    # Four bolts overstress the threads under the pressure end-force...
    four = by_name["4 bolts"]
    assert four.status is CheckStatus.FAIL
    assert "safety factor 1.73" in four.detail
    # ...six clear the proof-strength margin, eight give room.
    six = by_name["6 bolts"]
    assert six.passed
    assert "safety factor 2.59" in six.detail
    assert by_name["8 bolts"].passed
    assert card.status is CheckStatus.FAIL


def test_flywheel_speed_limits_example_whirls_though_it_holds():
    namespace = runpy.run_path(str(_EXAMPLES / "flywheel_speed_limits.py"))
    card = namespace["screen_flywheel"]()
    by_name = {e.name: e for e in card.entries}
    # The flywheel stores enough energy and is nowhere near bursting...
    energy = by_name["stored energy"]
    assert energy.passed
    assert "safety factor 1.22" in energy.detail
    assert by_name["rim burst stress"].passed
    assert "safety factor 4.84" in by_name["rim burst stress"].detail
    # ...but the slender shaft whirls near the running speed -> the assembly fails.
    whirl = by_name["shaft whirl critical speed"]
    assert whirl.status is CheckStatus.FAIL
    assert "safety factor 0.86" in whirl.detail
    assert card.status is CheckStatus.FAIL


def test_fatigue_link_example_passes_static_but_fails_fatigue():
    namespace = runpy.run_path(str(_EXAMPLES / "fatigue_link_stress_riser.py"))
    card = namespace["screen_fatigue_link"]()
    by_name = {e.name: e for e in card.entries}
    # The link is comfortably safe on its peak static load...
    static = by_name["static yield on peak load"]
    assert static.passed
    assert "safety factor 2.40" in static.detail
    # ...but the stress riser drives the modified-Goodman fatigue check below one.
    fatigue = by_name["modified-Goodman fatigue at the hole"]
    assert fatigue.status is CheckStatus.FAIL
    assert "safety factor 0.84" in fatigue.detail
    assert card.status is CheckStatus.FAIL


def test_crack_growth_inspection_interval_example_fails_at_heavy_duty():
    namespace = runpy.run_path(str(_EXAMPLES / "crack_growth_inspection_interval.py"))
    card = namespace["screen_inspection_interval"]()
    by_name = {e.name: e for e in card.entries}
    # The moderate duty cycle grows the crack past twice the inspection interval.
    moderate = by_name["moderate duty (stress range 150 MPa)"]
    assert moderate.passed
    assert "safety factor 1.91" in moderate.detail
    # A 50% larger stress range cuts the propagation life below the doubled
    # interval (the Paris cube law) -> the schedule is unsafe.
    heavy = by_name["heavy duty (stress range 220 MPa)"]
    assert heavy.status is CheckStatus.FAIL
    assert "safety factor 0.60" in heavy.detail
    assert card.status is CheckStatus.FAIL


def test_crane_rail_on_foundation_example_the_soft_pad_fails():
    namespace = runpy.run_path(str(_EXAMPLES / "crane_rail_on_foundation.py"))
    card = namespace["screen_crane_rail"]()
    by_name = {e.name: e for e in card.entries}
    # A stiffer foundation concentrates the wheel load and lowers the rail moment.
    stiff = by_name["stiff grout bed (k 100)"]
    assert stiff.passed
    assert "safety factor 1.89" in stiff.detail
    # The softer pad lets the load spread, so the rail bends more and fails 1.5.
    soft = by_name["soft elastomeric pad (k 20)"]
    assert soft.status is CheckStatus.FAIL
    assert "safety factor 1.26" in soft.detail
    assert card.status is CheckStatus.FAIL


def test_section_shape_factor_example_ranks_reserve_by_shape():
    namespace = runpy.run_path(str(_EXAMPLES / "section_shape_factor.py"))
    card = namespace["screen_shape_factors"]()
    by_name = {e.name: e for e in card.entries}
    # A solid round bar keeps ~70% in reserve past first yield.
    assert by_name["solid round bar (d 80)"].passed
    assert "safety factor 1.70" in by_name["solid round bar (d 80)"].detail
    # A rectangle's shape factor is exactly 1.5 -- it just meets the requirement.
    assert by_name["solid rectangle (40x120)"].passed
    assert "safety factor 1.50" in by_name["solid rectangle (40x120)"].detail
    # An I-section has almost all its area at the extreme fibre -> little reserve.
    i_beam = by_name["I-section (100x200, 15/10)"]
    assert i_beam.status is CheckStatus.FAIL
    assert "safety factor 1.17" in i_beam.detail
    assert card.status is CheckStatus.FAIL


def test_plastic_collapse_reserve_example_elastic_fails_plastic_passes():
    namespace = runpy.run_path(str(_EXAMPLES / "plastic_collapse_reserve.py"))
    card = namespace["screen_collapse_reserve"]()
    by_name = {e.name: e for e in card.entries}
    # First-yield (elastic) design rejects the beam at SF 1.25...
    elastic = by_name["first-yield (elastic)"]
    assert elastic.status is CheckStatus.FAIL
    assert "safety factor 1.25" in elastic.detail
    # ...but the true plastic collapse load is 2x higher (shape factor 1.5 x
    # redistribution 16/12), passing with SF 2.50.
    plastic = by_name["plastic collapse"]
    assert plastic.passed
    assert "safety factor 2.50" in plastic.detail
    # The overall card is FAIL because the elastic entry fails (No silent green).
    assert card.status is CheckStatus.FAIL


def test_support_beam_resonance_example_beam_mass_moves_it_onto_the_peak():
    namespace = runpy.run_path(str(_EXAMPLES / "support_beam_resonance.py"))
    card = namespace["screen_support_resonance"]()
    by_name = {e.name: e for e in card.entries}
    # Ignoring the beam's own mass, the fundamental clears the running speed.
    ignored = by_name["resonance margin (beam mass ignored)"]
    assert ignored.passed
    assert "safety factor 1.12" in ignored.detail
    # Including 17/35 of the 30 kg beam drops the frequency below the running
    # speed -> the check fails once the support's own mass is counted.
    included = by_name["resonance margin (beam mass included)"]
    assert included.status is CheckStatus.FAIL
    assert "safety factor 0.99" in included.detail
    assert card.status is CheckStatus.FAIL


def test_fatigue_criteria_compared_example_three_verdicts():
    namespace = runpy.run_path(str(_EXAMPLES / "fatigue_criteria_compared.py"))
    card = namespace["screen_fatigue_criteria"]()
    by_name = {e.name: e for e in card.entries}
    # The conservative Soderberg (to yield) and Goodman (to ultimate) both fail 1.5...
    assert by_name["Soderberg (to yield)"].status is CheckStatus.FAIL
    assert "safety factor 1.11" in by_name["Soderberg (to yield)"].detail
    assert by_name["Goodman (to ultimate)"].status is CheckStatus.FAIL
    assert "safety factor 1.36" in by_name["Goodman (to ultimate)"].detail
    # ...but the Gerber parabola, hugging the data, passes the same cycle.
    assert by_name["Gerber (parabola)"].passed
    assert "safety factor 1.70" in by_name["Gerber (parabola)"].detail
    # No-silent-green: any failing entry makes the whole card FAIL.
    assert card.status is CheckStatus.FAIL


def test_flywheel_bore_stress_example_the_shaft_hole_doubles_the_stress():
    namespace = runpy.run_path(str(_EXAMPLES / "flywheel_bore_stress.py"))
    card = namespace["screen_flywheel_bore"]()
    by_name = {e.name: e for e in card.entries}
    # As a solid disc the peak (centre) stress passes the 2.0 factor.
    solid = by_name["solid disc (peak at centre)"]
    assert solid.passed
    assert "safety factor 2.24" in solid.detail
    # The shaft bore moves the peak to the bore and roughly doubles it -> fails.
    bored = by_name["disc with shaft bore (peak at bore)"]
    assert bored.status is CheckStatus.FAIL
    assert "safety factor 1.12" in bored.detail
    assert card.status is CheckStatus.FAIL


def test_bearing_reliability_life_example_higher_reliability_costs_life():
    namespace = runpy.run_path(str(_EXAMPLES / "bearing_reliability_life.py"))
    card = namespace["screen_bearing_reliability"]()
    by_name = {e.name: e for e in card.entries}
    # The catalogue L10 (90% reliability) clears the service life comfortably...
    assert by_name["life at 90% reliability"].passed
    assert "safety factor 1.85" in by_name["life at 90% reliability"].detail
    # ...95% still passes, but only just.
    assert by_name["life at 95% reliability"].passed
    assert "safety factor 1.14" in by_name["life at 95% reliability"].detail
    # ...and a 99% requirement (a1 = 0.21) collapses the usable life below target.
    assert by_name["life at 99% reliability"].status is CheckStatus.FAIL
    assert "safety factor 0.39" in by_name["life at 99% reliability"].detail
    assert card.status is CheckStatus.FAIL


def test_steam_pipe_thermal_gradient_example_thermal_governs_not_pressure():
    namespace = runpy.run_path(str(_EXAMPLES / "steam_pipe_thermal_gradient.py"))
    card = namespace["screen_steam_pipe"]()
    by_name = {e.name: e for e in card.entries}
    # The pressure hoop stress is a trivial fraction of yield.
    hoop = by_name["pressure hoop stress"]
    assert hoop.passed
    assert "safety factor 12.50" in hoop.detail
    # The through-wall thermal gradient stress -- which the pressure check never
    # sees -- pushes past yield and governs the pipe.
    thermal = by_name["through-wall thermal gradient"]
    assert thermal.status is CheckStatus.FAIL
    assert "safety factor 0.97" in thermal.detail
    assert card.status is CheckStatus.FAIL


def test_bimetal_thermostat_blade_example_length_is_the_lever():
    namespace = runpy.run_path(str(_EXAMPLES / "bimetal_thermostat_blade.py"))
    card = namespace["screen_thermostat_blades"]()
    by_name = {e.name: e for e in card.entries}
    # The short blade's tip does not reach the contact gap -> it fails to trip.
    assert by_name["40 mm blade"].status is CheckStatus.FAIL
    assert "safety factor 0.71" in by_name["40 mm blade"].detail
    # Lengthening the blade grows the stroke as L^2, so 50 and 60 mm both clear it.
    assert by_name["50 mm blade"].passed
    assert "safety factor 1.11" in by_name["50 mm blade"].detail
    assert by_name["60 mm blade"].passed
    assert "safety factor 1.59" in by_name["60 mm blade"].detail
    assert card.status is CheckStatus.FAIL


def test_transmission_line_clearance_example_parabola_hides_a_violation():
    namespace = runpy.run_path(str(_EXAMPLES / "transmission_line_clearance.py"))
    card = namespace["screen_line_clearance"]()
    by_name = {e.name: e for e in card.entries}
    # The parabolic approximation says the line clears the sag limit...
    assert by_name["parabolic-approximation sag"].passed
    assert "safety factor 1.02" in by_name["parabolic-approximation sag"].detail
    # ...but the exact catenary (which sags ~3% more on a deep span) does not.
    assert by_name["exact catenary sag"].status is CheckStatus.FAIL
    assert "safety factor 0.99" in by_name["exact catenary sag"].detail
    assert card.status is CheckStatus.FAIL


def test_cam_base_circle_pressure_angle_example_bigger_base_circle_fixes_jamming():
    namespace = runpy.run_path(str(_EXAMPLES / "cam_base_circle_pressure_angle.py"))
    card = namespace["screen_cam_pressure_angle"]()
    by_name = {e.name: e for e in card.entries}
    # The tight base circle pushes the pressure angle over the 30-degree limit.
    assert by_name["40 mm base circle"].status is CheckStatus.FAIL
    assert "safety factor 0.97" in by_name["40 mm base circle"].detail
    # Opening the base circle flattens the geometry and clears the limit.
    assert by_name["60 mm base circle"].passed
    assert "safety factor 1.29" in by_name["60 mm base circle"].detail
    assert card.status is CheckStatus.FAIL


def test_drivetrain_torsional_mode_example_stiffer_coupling_clears_the_firing_freq():
    namespace = runpy.run_path(str(_EXAMPLES / "drivetrain_torsional_mode.py"))
    card = namespace["screen_drivetrain_mode"]()
    by_name = {e.name: e for e in card.entries}
    # The soft coupling puts the two-rotor mode too near the firing frequency.
    assert by_name["soft coupling (20 kN*m/rad)"].status is CheckStatus.FAIL
    assert "safety factor 0.64" in by_name["soft coupling (20 kN*m/rad)"].detail
    # Stiffening it lifts the mode above the excitation with margin.
    assert by_name["stiff coupling (100 kN*m/rad)"].passed
    assert "safety factor 1.42" in by_name["stiff coupling (100 kN*m/rad)"].detail
    assert card.status is CheckStatus.FAIL


def test_cover_plate_edge_fixity_example_clamped_edge_passes():
    namespace = runpy.run_path(str(_EXAMPLES / "cover_plate_edge_fixity.py"))
    card = namespace["screen_cover_plate"]()
    by_name = {e.name: e for e in card.entries}
    # The simply-supported plate dishes past the 1 mm limit...
    assert by_name["simply-supported edge"].status is CheckStatus.FAIL
    assert "safety factor 0.58" in by_name["simply-supported edge"].detail
    # ...but clamping the edge makes the same plate 2.5x stiffer and it clears it.
    assert by_name["clamped edge"].passed
    assert "safety factor 1.47" in by_name["clamped edge"].detail
    assert card.status is CheckStatus.FAIL


def test_bracket_bolt_group_eccentric_example_direct_shear_underestimates():
    namespace = runpy.run_path(str(_EXAMPLES / "bracket_bolt_group_eccentric.py"))
    card = namespace["screen_bracket_bolts"]()
    by_name = {e.name: e for e in card.entries}
    # Sharing the load equally (P/n) looks safe...
    assert by_name["direct-shear estimate (P/n)"].passed
    assert "safety factor 2.50" in by_name["direct-shear estimate (P/n)"].detail
    # ...but the eccentric moment drives the corner bolt to ~2.8x that and it fails.
    assert by_name["true peak (eccentric)"].status is CheckStatus.FAIL
    assert "safety factor 0.90" in by_name["true peak (eccentric)"].detail
    assert card.status is CheckStatus.FAIL


def test_rotor_unbalance_response_example_resonance_amplifies_the_shake():
    namespace = runpy.run_path(str(_EXAMPLES / "rotor_unbalance_response.py"))
    card = namespace["screen_rotor_vibration"]()
    by_name = {e.name: e for e in card.entries}
    # Well below and well above the critical speed the unbalance is comfortable.
    assert by_name["well below critical (r = 0.5)"].passed
    assert "safety factor 3.76" in by_name["well below critical (r = 0.5)"].detail
    assert by_name["super-critical (r = 2.0)"].passed
    assert "safety factor 15.03" in by_name["super-critical (r = 2.0)"].detail
    # Just under the critical speed the dynamic magnification spikes and it fails.
    assert by_name["just under critical (r = 0.95)"].status is CheckStatus.FAIL
    assert "safety factor 0.68" in by_name["just under critical (r = 0.95)"].detail
    assert card.status is CheckStatus.FAIL


def test_flat_bar_torsion_penalty_example_thin_section_twists_far_more():
    namespace = runpy.run_path(str(_EXAMPLES / "flat_bar_torsion_penalty.py"))
    card = namespace["screen_torsion_sections"]()
    by_name = {e.name: e for e in card.entries}
    # The compact square (same area, same steel) stays inside the twist limit...
    assert by_name["compact square (31.6 x 31.6 mm)"].passed
    assert "safety factor 1.97" in by_name["compact square (31.6 x 31.6 mm)"].detail
    # ...but the equal-area flat bar twists ~4.5x more and fails.
    assert by_name["flat bar (100 x 10 mm)"].status is CheckStatus.FAIL
    assert "safety factor 0.44" in by_name["flat bar (100 x 10 mm)"].detail
    assert card.status is CheckStatus.FAIL


def test_thin_tube_shell_buckling_example_shell_governs_not_column():
    namespace = runpy.run_path(str(_EXAMPLES / "thin_tube_shell_buckling.py"))
    card = namespace["screen_tube_strut"]()
    by_name = {e.name: e for e in card.entries}
    # As a column the thin tube looks bombproof -- 12x clear of Euler buckling...
    assert by_name["Euler column buckling"].passed
    assert "safety factor 12.28" in by_name["Euler column buckling"].detail
    # ...but its wall crinkles (local shell buckling) below the working stress.
    assert by_name["shell (local wall) buckling"].status is CheckStatus.FAIL
    assert "safety factor 0.91" in by_name["shell (local wall) buckling"].detail
    assert card.status is CheckStatus.FAIL


def test_gear_nonstandard_center_example_operating_angle_caps_the_stretch():
    namespace = runpy.run_path(str(_EXAMPLES / "gear_nonstandard_center.py"))
    card = namespace["screen_gear_centers"]()
    by_name = {e.name: e for e in card.entries}
    # A 62 mm centre keeps the operating pressure angle just inside the 25-deg cap.
    assert by_name["62 mm centre"].passed
    assert "safety factor 1.02" in by_name["62 mm centre"].detail
    # Stretching to 63 mm pushes the operating angle past the cap -> a redesign.
    assert by_name["63 mm centre"].status is CheckStatus.FAIL
    assert "safety factor 0.94" in by_name["63 mm centre"].detail
    assert card.status is CheckStatus.FAIL


def test_bracket_weld_group_eccentric_example_direct_shear_underestimates():
    namespace = runpy.run_path(str(_EXAMPLES / "bracket_weld_group_eccentric.py"))
    card = namespace["screen_bracket_welds"]()
    by_name = {e.name: e for e in card.entries}
    # Spreading the load over the whole weld throat looks very safe...
    assert by_name["direct-shear estimate"].passed
    assert "safety factor 3.39" in by_name["direct-shear estimate"].detail
    # ...but the eccentric moment drives the weld ends to ~4x that and fails.
    assert by_name["true peak (eccentric)"].status is CheckStatus.FAIL
    assert "safety factor 0.90" in by_name["true peak (eccentric)"].detail
    assert card.status is CheckStatus.FAIL


def test_shaft_bearing_misalignment_example_slope_governs():
    namespace = runpy.run_path(str(_EXAMPLES / "shaft_bearing_misalignment.py"))
    card = namespace["screen_shaft"]()
    by_name = {e.name: e for e in card.entries}
    # The shaft is plenty strong and plenty stiff...
    assert by_name["bending stress"].passed
    assert "safety factor 11.45" in by_name["bending stress"].detail
    assert by_name["midspan deflection"].passed
    assert "safety factor 1.18" in by_name["midspan deflection"].detail
    # ...but the slope at its bearings exceeds the tight roller tolerance.
    assert by_name["bearing misalignment slope"].status is CheckStatus.FAIL
    assert "safety factor 0.79" in by_name["bearing misalignment slope"].detail
    assert card.status is CheckStatus.FAIL


def test_sheet_metal_bend_radius_example_ductility_governs():
    namespace = runpy.run_path(str(_EXAMPLES / "sheet_metal_bend_radius.py"))
    card = namespace["screen_bend"]()
    by_name = {e.name: e for e in card.entries}
    # A 400 kN brake covers the ~104 kN air bend nearly four times over...
    assert by_name["press-brake tonnage"].passed
    assert "safety factor 3.86" in by_name["press-brake tonnage"].detail
    # ...but the 1t radius cracks the H32 temper: a ductility limit no press can move.
    assert by_name["bend radius vs ductility limit"].status is CheckStatus.FAIL
    assert "safety factor 0.67" in by_name["bend radius vs ductility limit"].detail
    assert card.status is CheckStatus.FAIL
    # The flat blank is the tangent flanges plus the bend allowance, not the flange sum.
    flat = namespace["flat_blank_length"]().to("mm").magnitude
    assert flat == pytest.approx(104.52, abs=0.01)
    assert flat > 100.0  # the naive 40+60 flange sum would misplace every downstream hole


def test_snap_fit_latch_example_strain_governs_not_force():
    namespace = runpy.run_path(str(_EXAMPLES / "snap_fit_latch_strain.py"))
    drawn = namespace["screen_latch"]()
    by_name = {e.name: e for e in drawn.entries}
    # The stubby finger assembles by hand (46 N < 65 N)...
    assert by_name["mating force vs hand limit"].passed
    assert "safety factor 1.40" in by_name["mating force vs hand limit"].detail
    # ...but over-strains its root at 4.7% vs the 2% allowable and cracks.
    assert by_name["root strain vs allowable"].status is CheckStatus.FAIL
    assert "safety factor 0.43" in by_name["root strain vs allowable"].detail
    assert drawn.status is CheckStatus.FAIL
    # The slender redesign clears the same undercut within the strain allowable.
    fixed = namespace["screen_redesigned_latch"]()
    fixed_by_name = {e.name: e for e in fixed.entries}
    assert fixed_by_name["root strain vs allowable"].passed
    assert "safety factor 1.50" in fixed_by_name["root strain vs allowable"].detail
    assert fixed.status is CheckStatus.PASS


def test_o_ring_gland_fill_example_width_and_depth_are_independent():
    namespace = runpy.run_path(str(_EXAMPLES / "o_ring_gland_fill.py"))
    narrow = namespace["screen_gland"]()
    by_name = {e.name: e for e in narrow.entries}
    # The depth gives a textbook squeeze...
    assert by_name["squeeze vs 15% floor"].passed
    assert "safety factor 1.40" in by_name["squeeze vs 15% floor"].detail
    # ...but the narrow groove overfills and the ring will extrude on swell.
    assert by_name["gland fill vs 90% ceiling"].status is CheckStatus.FAIL
    assert "safety factor 0.97" in by_name["gland fill vs 90% ceiling"].detail
    assert narrow.status is CheckStatus.FAIL
    # Widening the groove fixes fill without touching the (still-passing) squeeze.
    wide = namespace["screen_widened_gland"]()
    wide_by_name = {e.name: e for e in wide.entries}
    assert wide_by_name["gland fill vs 90% ceiling"].passed
    assert "safety factor 1.21" in wide_by_name["gland fill vs 90% ceiling"].detail
    assert wide_by_name["squeeze vs 15% floor"].detail == by_name["squeeze vs 15% floor"].detail
    assert wide.status is CheckStatus.PASS


def test_sling_angle_overload_example_capacity_is_an_angle_problem():
    namespace = runpy.run_path(str(_EXAMPLES / "sling_angle_overload.py"))
    shallow = namespace["screen_sling"]()
    entry = shallow.entries[0]
    # At 30 degrees each leg carries the whole load and blows past its rating.
    assert entry.status is CheckStatus.FAIL
    assert "safety factor 0.67" in entry.detail
    assert shallow.status is CheckStatus.FAIL
    # The same sling and load, rigged steeper, comes back inside the rating.
    steep = namespace["screen_steep_sling"]()
    assert steep.entries[0].passed
    assert "safety factor 1.15" in steep.entries[0].detail
    assert steep.status is CheckStatus.PASS


def test_gasket_flange_leak_example_tightness_governs():
    namespace = runpy.run_path(str(_EXAMPLES / "gasket_flange_leak.py"))
    card = namespace["screen_flange"]()
    by_name = {e.name: e for e in card.entries}
    # The preload seats the gasket and out-pulls the end force...
    assert by_name["seat the gasket at assembly"].passed
    assert "safety factor 2.17" in by_name["seat the gasket at assembly"].detail
    assert by_name["hold against the end force"].passed
    assert "safety factor 1.19" in by_name["hold against the end force"].detail
    # ...but cannot keep the gasket crushed under pressure, so the joint leaks.
    assert by_name["stay tight under pressure"].status is CheckStatus.FAIL
    assert "safety factor 0.85" in by_name["stay tight under pressure"].detail
    assert card.status is CheckStatus.FAIL
