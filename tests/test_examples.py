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
