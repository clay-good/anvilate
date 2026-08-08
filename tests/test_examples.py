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


def test_beam_bearing_web_checks_example_is_governed_by_crippling():
    namespace = runpy.run_path(str(_EXAMPLES / "beam_bearing_web_checks.py"))
    result = namespace["end_bearing_capacity"]()
    yielding = result["yielding"].to("kN").magnitude
    crippling = result["crippling"].to("kN").magnitude
    # At this short end bearing the thin web buckles (crippling) before it crushes
    # (yielding), so crippling is the smaller strength and governs the ~213 kN capacity.
    assert crippling < yielding
    assert result["governing"] is result["crippling"]
    assert crippling == pytest.approx(212.6, abs=0.5)


def test_rc_t_beam_floor_example_flange_adds_strength_and_ductility():
    namespace = runpy.run_path(str(_EXAMPLES / "rc_t_beam_floor.py"))
    r = namespace["floor_beam_capacity"]()
    # The flange adds strength ...
    assert r["t_beam_moment_kn_m"] > r["web_only_moment_kn_m"]
    assert r["t_beam_moment_kn_m"] == pytest.approx(649, abs=5)
    # ... and keeps the section far more ductile (net tensile strain well past 0.005).
    assert r["t_beam_strain"] > 0.02
    assert r["web_only_strain"] < r["t_beam_strain"]


def test_gear_shaft_assembly_example_sizes_three_subsystems():
    namespace = runpy.run_path(str(_EXAMPLES / "gear_shaft_assembly.py"))
    result = namespace["size_the_shaft_assembly"]()
    # The DE-Goodman fatigue diameter drives the design (~28.5 mm, rounded to 30).
    assert result["shaft_diameter_mm"] == pytest.approx(28.5, abs=0.5)
    # The key length and bearing life follow from that shaft, each a real number.
    assert 10 < result["key_length_mm"] < 30
    assert result["bearing_life_hours"] > 50000


def test_cfrp_ply_example_shows_the_anisotropy():
    namespace = runpy.run_path(str(_EXAMPLES / "cfrp_ply_anisotropy.py"))
    p = namespace["ply_properties"]()
    # A unidirectional ply is an order of magnitude stiffer along the fibers than across.
    assert p["longitudinal_modulus_mpa"] > 10 * p["transverse_modulus_mpa"]
    assert p["longitudinal_modulus_mpa"] == pytest.approx(139400, rel=0.01)
    assert p["longitudinal_strength_mpa"] == pytest.approx(2428, abs=5)


def test_aluminum_ladder_rail_example_is_buckling_governed():
    namespace = runpy.run_path(str(_EXAMPLES / "aluminum_ladder_rail.py"))
    r = namespace["rail_strengths"]()
    # Aluminum's low modulus makes the slender strut buckle far below the material
    # strength it reaches in tension.
    assert r["buckling_stress_mpa"] < r["tension_stress_mpa"]
    assert r["buckling_stress_mpa"] == pytest.approx(107, abs=3)
    assert r["tension_stress_mpa"] == pytest.approx(240, abs=1)


def test_masonry_wall_slenderness_example_combined_check_governs():
    namespace = runpy.run_path(str(_EXAMPLES / "masonry_wall_slenderness.py"))
    a = namespace["wall_check"]()
    # The allowable stress falls monotonically as the wall gets more slender.
    assert a["Fa_hr_30_mpa"] > a["Fa_hr_60_mpa"] > a["Fa_hr_90_mpa"]
    # A slender wall (h/r = 90) has shed nearly 40% of the stocky (h/r = 30) allowable.
    assert a["Fa_hr_90_mpa"] / a["Fa_hr_30_mpa"] < 0.65
    # Gravity alone passes comfortably, but adding the out-of-plane wind bending pushes
    # the TMS 402 unity ratio past 1.0 — the combined check, not either stress, governs.
    assert a["axial_utilization"] < 0.6
    assert a["combined_unity"] > 1.0
    assert a["combined_unity"] == pytest.approx(1.01, abs=0.02)


def test_clay_backfill_tension_crack_example():
    namespace = runpy.run_path(str(_EXAMPLES / "clay_backfill_tension_crack.py"))
    p = namespace["backfill_pressures"]()
    # A tension crack opens over a substantial fraction of the wall.
    assert p["tension_crack_m"] == pytest.approx(2.38, abs=0.05)
    # Surface pressure is tensile (negative), base pressure compressive.
    assert p["surface_pressure_kpa"] < 0
    assert p["base_pressure_kpa"] > 0


def test_masonry_wall_scorecard_example_combined_governs():
    namespace = runpy.run_path(str(_EXAMPLES / "masonry_wall_scorecard.py"))
    w = namespace["wall_scorecards"]()
    assert w["light_status"] == "pass"
    assert w["design_status"] == "fail"
    # The combined axial+flexure check is what fails under design wind (gravity axial passes).
    assert "combined axial + flexure" in w["design_failures"]


def test_pump_duty_scorecard_example_sound_passes_marginal_fails():
    namespace = runpy.run_path(str(_EXAMPLES / "pump_duty_scorecard.py"))
    d = namespace["duty_scorecards"]()
    assert d["sound_status"] == "pass"
    assert d["marginal_status"] == "fail"
    assert "motor rating" in d["marginal_failures"]
    assert "NPSH margin" in d["marginal_failures"]


def test_retaining_wall_scorecard_example_good_passes_weak_fails():
    namespace = runpy.run_path(str(_EXAMPLES / "retaining_wall_scorecard.py"))
    w = namespace["wall_scorecards"]()
    assert w["good_status"] == "pass"
    assert w["weak_status"] == "fail"
    # The under-built wall fails both external-stability checks.
    assert "overturning" in w["weak_failures"]
    assert "sliding" in w["weak_failures"]


def test_spread_footing_scorecard_example_passes_then_fails():
    namespace = runpy.run_path(str(_EXAMPLES / "spread_footing_scorecard.py"))
    s = namespace["footing_scorecards"]()
    # The service load passes the bearing check; the overload fails it — a cited pass/fail.
    assert s["service_status"] == "pass"
    assert s["overloaded_status"] == "fail"
    assert "3.33" in s["service_detail"]


def test_strip_footing_bearing_example_deeper_founding_lifts_capacity():
    namespace = runpy.run_path(str(_EXAMPLES / "strip_footing_bearing.py"))
    cap = namespace["footing_capacity"]()
    # Founding the same footing deeper adds surcharge (q = gamma*D_f) and raises capacity.
    assert cap["q_ult_D1.5_kpa"] > cap["q_ult_D0.5_kpa"]
    assert cap["q_allow_D1.5_kpa"] > cap["q_allow_D0.5_kpa"]
    # The allowable is the ultimate over the factor of safety of 3.
    assert cap["q_allow_D0.5_kpa"] == pytest.approx(cap["q_ult_D0.5_kpa"] / 3.0, rel=1e-9)
    assert cap["q_ult_D0.5_kpa"] == pytest.approx(1322, abs=5)


def test_clay_layer_settlement_example_fails_serviceability_over_years():
    namespace = runpy.run_path(str(_EXAMPLES / "clay_layer_settlement.py"))
    s = namespace["settlement_summary"]()
    # The soil is strong but the layer consolidates far past a 25 mm serviceability limit.
    assert s["ultimate_settlement_mm"] == pytest.approx(97, abs=2)
    assert s["ultimate_settlement_mm"] > 25.0
    # Reaching 90% consolidation takes years, not days — T_v(90%) = 0.848.
    assert s["time_factor"] == pytest.approx(0.848, abs=0.001)
    assert s["years_to_target"] > 5.0


def test_retaining_wall_stability_example_bearing_governs():
    namespace = runpy.run_path(str(_EXAMPLES / "retaining_wall_stability.py"))
    s = namespace["wall_stability"]()
    # Overturning and sliding both pass their usual minimums.
    assert s["fs_overturning"] >= 2.0
    assert s["fs_sliding"] >= 1.5
    # But the resultant is outside the middle third, so the heel lifts off and the toe
    # pressure spikes — the governing check is bearing, not stability.
    assert s["q_min_kpa"] == pytest.approx(0.0, abs=1e-9)
    assert s["q_max_kpa"] == pytest.approx(148, abs=2)


def test_pump_line_pressure_drop_example_fittings_are_not_minor():
    namespace = runpy.run_path(str(_EXAMPLES / "pump_line_pressure_drop.py"))
    r = namespace["line_losses"]()
    assert r["reynolds"] == pytest.approx(2e5, rel=1e-6)
    assert r["friction_factor"] == pytest.approx(0.0187, abs=0.0005)
    # The fitting head is a real fraction of the friction head, worth ~30 m of extra pipe.
    assert r["fitting_head_m"] > 0.2 * r["friction_head_m"]
    assert r["equivalent_fitting_length_m"] == pytest.approx(29, abs=3)
    # Total pressure the pump must supply.
    assert r["pressure_drop_kpa"] == pytest.approx(48, abs=2)


def test_drainage_channel_capacity_example_passes_and_is_subcritical():
    namespace = runpy.run_path(str(_EXAMPLES / "drainage_channel_capacity.py"))
    c = namespace["channel_check"]()
    # The channel carries more than the 4.5 m3/s design storm.
    assert c["discharge_m3s"] == pytest.approx(5.19, abs=0.05)
    assert c["discharge_m3s"] > 4.5
    # Subcritical flow: Fr < 1 and the flow depth exceeds the critical depth — same verdict.
    assert c["froude"] < 1.0
    assert c["flow_depth_m"] > c["critical_depth_m"]
    assert c["critical_depth_m"] == pytest.approx(0.67, abs=0.02)


def test_trapezoidal_canal_capacity_example_carries_and_is_subcritical():
    namespace = runpy.run_path(str(_EXAMPLES / "trapezoidal_canal_capacity.py"))
    c = namespace["canal_capacity"]()
    # The canal carries more than its 5 m3/s design flow, subcritically.
    assert c["discharge_m3s"] > 5.0
    assert c["discharge_m3s"] == pytest.approx(6.2, abs=0.2)
    assert c["froude"] < 1.0


def test_weir_flow_gauging_example_vnotch_reads_lower():
    namespace = runpy.run_path(str(_EXAMPLES / "weir_flow_gauging.py"))
    w = namespace["weir_discharges"]()
    # At the same head the V-notch passes far less than the 1 m rectangular crest.
    assert w["vnotch_lps"] < w["rectangular_lps"]
    assert w["rectangular_lps"] == pytest.approx(301, abs=5)
    assert w["vnotch_lps"] == pytest.approx(68, abs=3)


def test_spillway_stilling_basin_example_jump_dissipates_energy():
    namespace = runpy.run_path(str(_EXAMPLES / "spillway_stilling_basin.py"))
    d = namespace["jump_design"]()
    # The jump raises the water several-fold and burns real energy.
    assert d["sequent_depth_m"] == pytest.approx(1.34, abs=0.03)
    assert d["depth_ratio"] > 4.0
    assert d["energy_loss_m"] == pytest.approx(0.70, abs=0.03)


def test_pump_selection_from_line_example_chains_to_a_motor():
    namespace = runpy.run_path(str(_EXAMPLES / "pump_selection_from_line.py"))
    d = namespace["pump_duty"]()
    # Total head is the static lift (8 m) plus real friction and fitting losses.
    assert d["total_head_m"] > 8.0
    assert d["total_head_m"] == pytest.approx(19.2, abs=1.0)
    # Shaft power exceeds hydraulic power by the efficiency factor (1/0.7).
    assert d["shaft_power_kw"] == pytest.approx(d["hydraulic_power_kw"] / 0.70, rel=1e-6)
    # Low specific speed -> a centrifugal pump.
    assert d["specific_speed"] < 1.0


def test_submerged_gate_hinge_example_center_of_pressure_below_centroid():
    namespace = runpy.run_path(str(_EXAMPLES / "submerged_gate_hinge.py"))
    g = namespace["gate_loads"]()
    assert g["base_pressure_kpa"] == pytest.approx(29.4, abs=0.2)
    assert g["force_kn"] == pytest.approx(88.3, abs=0.5)
    # The resultant acts at two-thirds of the depth for a surface-piercing gate — below the
    # centroid, the whole point of the check.
    assert g["center_of_pressure_m"] == pytest.approx(2.0, abs=0.01)
    assert g["center_of_pressure_m"] > g["centroid_depth_m"]


def test_stack_effect_draft_example_worse_in_winter():
    namespace = runpy.run_path(str(_EXAMPLES / "stack_effect_draft.py"))
    d = namespace["building_draft"]()
    # The cold day drives a much larger stack pressure than the mild day.
    assert d["winter_pa"] > d["mild_pa"] > 0
    assert d["winter_over_mild"] > 3.0
    assert d["winter_pa"] == pytest.approx(68, abs=3)


def test_pontoon_stability_example_capsizes_with_a_high_load():
    namespace = runpy.run_path(str(_EXAMPLES / "pontoon_stability.py"))
    s = namespace["pontoon_stability"]()
    # Low load: positive metacentric height and a real righting moment.
    assert s["low_load_gm_m"] > 0
    assert s["low_load_righting_knm"] > 0
    # High load: the center of gravity climbs above the metacenter and GM goes negative.
    assert s["high_load_gm_m"] < 0


def test_slope_stability_rain_example_cohesion_holds_until_saturation():
    namespace = runpy.run_path(str(_EXAMPLES / "slope_stability_rain.py"))
    f = namespace["slope_factors"]()
    # Friction alone can't hold a slope steeper than the friction angle.
    assert f["friction_only"] < 1.0
    # Cohesion makes it comfortably stable when dry.
    assert f["dry"] > 1.4
    # Saturation (pore pressure) erodes the margin back toward 1.
    assert f["dry"] > f["saturated"] > 1.0
    assert f["saturated"] == pytest.approx(1.07, abs=0.05)


def test_friction_pile_capacity_example_shaft_carries_the_load():
    namespace = runpy.run_path(str(_EXAMPLES / "friction_pile_capacity.py"))
    p = namespace["pile_capacity"]()
    assert p["shaft_kn"] == pytest.approx(990, abs=5)
    assert p["tip_kn"] == pytest.approx(85, abs=3)
    # The shaft carries the large majority — the whole point of a friction pile.
    assert p["shaft_fraction"] > 0.9
    assert p["allowable_kn"] == pytest.approx(430, abs=5)


def test_cofferdam_seepage_piping_example_piping_governs():
    namespace = runpy.run_path(str(_EXAMPLES / "cofferdam_seepage_piping.py"))
    s = namespace["seepage_check"]()
    # The inflow is a small pump duty.
    assert s["inflow_lps"] == pytest.approx(1.5, abs=0.1)
    # The critical gradient is near 1, and the piping FS falls short of the 2.5 target.
    assert 0.9 < s["critical_gradient"] < 1.0
    assert s["piping_fs"] < 2.5
    assert s["piping_fs"] == pytest.approx(1.94, abs=0.05)


def test_square_footing_shape_depth_example_recovers_capacity():
    namespace = runpy.run_path(str(_EXAMPLES / "square_footing_shape_depth.py"))
    r = namespace["corrected_bearing"]()
    # The shape and depth corrections add substantial capacity over the strip estimate.
    assert r["corrected_kpa"] > r["strip_kpa"]
    assert r["ratio"] == pytest.approx(1.6, abs=0.05)
    assert r["strip_kpa"] == pytest.approx(1488, abs=5)


def test_inclined_load_footing_example_loses_capacity():
    namespace = runpy.run_path(str(_EXAMPLES / "inclined_load_footing.py"))
    r = namespace["inclined_capacity"]()
    # The horizontal thrust derates the bearing capacity below the vertical-only value.
    assert r["inclined_kpa"] < r["vertical_kpa"]
    assert r["ratio"] == pytest.approx(0.66, abs=0.03)
    assert r["vertical_kpa"] == pytest.approx(1488, abs=5)


def test_blower_mach_limit_example_fast_jet_is_compressible():
    namespace = runpy.run_path(str(_EXAMPLES / "blower_mach_limit.py"))
    d = namespace["duct_mach_check"]()
    assert d["speed_of_sound_ms"] == pytest.approx(340, abs=2)
    # The normal duct stays well within the incompressible regime; the fast jet crosses M~0.3.
    assert d["normal_mach"] < 0.3
    assert d["fast_mach"] > 0.3
    # The fast jet warms measurably at a stagnation point.
    assert d["fast_stagnation_rise_c"] > 5.0


def test_relief_valve_choked_flow_example_is_choked():
    namespace = runpy.run_path(str(_EXAMPLES / "relief_valve_choked_flow.py"))
    r = namespace["relief_capacity"]()
    # The vessel-to-atmosphere ratio is well below critical, so the valve is choked.
    assert r["actual_ratio"] < r["critical_ratio"]
    assert r["is_choked"] is True
    assert r["critical_ratio"] == pytest.approx(0.528, abs=0.002)
    # It relieves a substantial mass flow, capped by the upstream conditions.
    assert r["mass_flow_kgs"] == pytest.approx(0.595, abs=0.02)


def test_air_compressor_duty_example_brackets_power_and_heat():
    namespace = runpy.run_path(str(_EXAMPLES / "air_compressor_duty.py"))
    d = namespace["compressor_duty"]()
    # Adiabatic (uncooled) power exceeds the isothermal ideal by about a third.
    assert d["adiabatic_kw"] > d["isothermal_kw"]
    assert d["adiabatic_over_isothermal"] == pytest.approx(1.34, abs=0.03)
    # Air taken to 7:1 in one stage leaves near 230 deg C — the intercooling driver.
    assert d["discharge_degc"] == pytest.approx(229, abs=3)


def test_dew_point_condensation_example_cold_surface_sweats():
    namespace = runpy.run_path(str(_EXAMPLES / "dew_point_condensation.py"))
    m = namespace["room_moisture"]()
    # 25 C / 60% RH air carries ~12 g/kg and dews around 16-17 C.
    assert m["humidity_ratio_gkg"] == pytest.approx(11.9, abs=0.3)
    assert m["dew_point_degc"] == pytest.approx(16.7, abs=0.3)
    # The 15 C pipe is below the dew point, so it condenses.
    assert m["cold_surface_degc"] < m["dew_point_degc"]
    assert m["condenses"] is True


def test_cooling_coil_load_example_latent_is_a_big_share():
    namespace = runpy.run_path(str(_EXAMPLES / "cooling_coil_load.py"))
    c = namespace["coil_load"]()
    # The total load exceeds the sensible-only load — the difference is the latent (drying) load.
    assert c["total_kw"] > c["sensible_kw"]
    assert c["total_kw"] == pytest.approx(33.3, abs=1.0)
    # For warm humid air a large fraction of the load is latent, not temperature.
    assert c["latent_fraction"] > 0.4


def test_chiller_second_law_efficiency_example_ranking_flips():
    namespace = runpy.run_path(str(_EXAMPLES / "chiller_second_law_efficiency.py"))
    g = namespace["chiller_grades"]()
    # By COP the easy-duty chiller looks better; by second-law efficiency the hard-duty one wins.
    assert g["easy_cop"] > g["hard_cop"]
    assert g["hard_eta2"] > g["easy_eta2"]
    assert g["easy_eta2"] == pytest.approx(0.40, abs=0.01)
    assert g["hard_eta2"] == pytest.approx(0.55, abs=0.01)


def test_heat_pump_cold_day_example_cop_collapses():
    namespace = runpy.run_path(str(_EXAMPLES / "heat_pump_cold_day.py"))
    p = namespace["heat_pump_performance"]()
    # The Carnot ceiling falls sharply as the outdoor temperature drops.
    assert p["cold_carnot_cop"] < p["mild_carnot_cop"]
    # The same heat demand costs substantially more compressor power on the cold day.
    assert p["cold_power_kw"] > p["mild_power_kw"]
    assert p["cold_power_kw"] / p["mild_power_kw"] > 1.5


def test_machine_sound_power_survey_example_power_then_pressure():
    namespace = runpy.run_path(str(_EXAMPLES / "machine_sound_power_survey.py"))
    s = namespace["survey_and_predict"]()
    # 85 dB intensity over 10 m^2 -> 95 dB power level.
    assert s["sound_power_level_db"] == pytest.approx(95.0, abs=0.1)
    # The predicted operator level is below the source power level.
    assert s["operator_pressure_level_db"] < s["sound_power_level_db"]


def test_machine_noise_placement_example_corner_adds_9db():
    namespace = runpy.run_path(str(_EXAMPLES / "machine_noise_placement.py"))
    lv = namespace["operator_levels"]()
    # Free field < on floor < in corner; the corner is 9 dB over free field.
    assert lv["free_field_q1"] < lv["on_floor_q2"] < lv["in_corner_q8"]
    assert lv["in_corner_q8"] - lv["free_field_q1"] == pytest.approx(9.0, abs=0.1)


def test_plant_noise_exposure_example_loudest_dominates():
    namespace = runpy.run_path(str(_EXAMPLES / "plant_noise_exposure.py"))
    a = namespace["noise_assessment"]()
    # The combined level sits just above the loudest machine (energy summing).
    assert a["combined_db"] == pytest.approx(94.2, abs=0.3)
    assert a["margin_over_loudest"] < 3.0
    # The inverse-square safe distance drops the level to the action level.
    assert a["level_at_safe_distance"] == pytest.approx(85.0, abs=0.1)
    assert a["safe_distance_m"] > 1.0


def test_noncompact_flange_beam_strength_example_penalizes_below_mp():
    namespace = runpy.run_path(str(_EXAMPLES / "noncompact_flange_beam_strength.py"))
    r = namespace["flange_governed_strength"]()
    assert r["flange_class"] == "noncompact"
    # The noncompact flange knocks the plastic moment down (~16%).
    assert r["nominal_moment_kip_in"] < r["plastic_moment_kip_in"]
    assert r["reduction_percent"] == pytest.approx(16.0, abs=1.0)


def test_beam_flexural_compactness_example_slender_web_reclassifies():
    namespace = runpy.run_path(str(_EXAMPLES / "beam_flexural_compactness.py"))
    c = namespace["classify_sections"]()
    assert c["rolled_w18x50"] == "compact"
    # The plate girder's slender web makes the whole section slender.
    assert c["plate_girder"] == "slender"


def test_rectangular_torsion_bar_stress_example_flat_bar_loses():
    namespace = runpy.run_path(str(_EXAMPLES / "rectangular_torsion_bar_stress.py"))
    b = namespace["bar_stresses"]()
    # The flat bar carries higher stress and more twist than the equal-area square.
    assert b["flat_100x10mm"]["stress_mpa"] > b["square_31.6mm"]["stress_mpa"]
    assert b["flat_100x10mm"]["twist_deg"] > b["square_31.6mm"]["twist_deg"]
    assert b["flat_100x10mm"]["stress_mpa"] == pytest.approx(64.0, abs=1.0)


def test_clutch_thermal_capacity_example_slip_below_brake_limit():
    namespace = runpy.run_path(str(_EXAMPLES / "clutch_thermal_capacity.py"))
    e = namespace["engagement_heat"]()
    # The slip energy is below the brake-limit energy (driven side is finite, not infinite).
    assert e["slip_energy_kj"] < e["brake_limit_kj"]
    assert e["slip_energy_kj"] == pytest.approx(14.21, abs=0.05)
    assert e["brake_limit_kj"] == pytest.approx(18.0, abs=0.05)


def test_vertical_ball_screw_axis_example_needs_a_brake():
    namespace = runpy.run_path(str(_EXAMPLES / "vertical_ball_screw_axis.py"))
    t = namespace["axis_torques"]()
    assert t["drive_torque_nm"] == pytest.approx(7.07, abs=0.05)
    # The load back-drives with a real torque, so a holding brake is required.
    assert t["back_drive_torque_nm"] == pytest.approx(5.09, abs=0.05)
    assert t["back_drive_torque_nm"] > 0


def test_wide_flange_torsional_properties_example_matches_manual():
    namespace = runpy.run_path(str(_EXAMPLES / "wide_flange_torsional_properties.py"))
    t = namespace["w18x50_torsion"]()
    # Thin-wall J runs a little under the Manual's 1.24 in^4; C_w is essentially exact.
    assert t["j_in4"] == pytest.approx(1.18, abs=0.05)
    assert t["j_in4"] < 1.24
    assert t["cw_in6"] == pytest.approx(3040.0, rel=5e-3)


def test_stack_vortex_lock_in_example_flags_common_wind():
    namespace = runpy.run_path(str(_EXAMPLES / "stack_vortex_lock_in.py"))
    s = namespace["stack_viv_screen"]()
    # 0.9 Hz, 1 m, St 0.2 -> lock-in at 4.5 m/s, a common wind speed.
    assert s["lock_in_wind_m_s"] == pytest.approx(4.5, abs=0.05)
    # At lock-in the reduced velocity is 1/St = 5.
    assert s["reduced_velocity_at_lock_in"] == pytest.approx(5.0, rel=1e-6)


def test_engine_cycle_efficiency_example_higher_compression_wins():
    namespace = runpy.run_path(str(_EXAMPLES / "engine_cycle_efficiency.py"))
    c = namespace["cycle_efficiencies"]()
    # At equal compression the diesel cycle is a touch below the Otto.
    assert c["diesel_r10"] < c["otto_r10"]
    # But the diesel's much higher compression ratio overtakes the knock-limited gasoline engine.
    assert c["diesel_r18"] > c["otto_r10"]


def test_boiler_flue_gas_efficiency_example_tuning_matters():
    namespace = runpy.run_path(str(_EXAMPLES / "boiler_flue_gas_efficiency.py"))
    b = namespace["boiler_efficiency"]()
    # The well-tuned boiler loses less up the stack and is more efficient.
    assert b["tuned_loss"] == pytest.approx(5.87, abs=0.05)
    assert b["tuned_efficiency"] == pytest.approx(94.1, abs=0.1)
    assert b["drifted_loss"] > b["tuned_loss"]
    assert b["drifted_efficiency"] < b["tuned_efficiency"]


def test_boiler_combustion_air_example_flue_confirms_excess():
    namespace = runpy.run_path(str(_EXAMPLES / "boiler_combustion_air.py"))
    t = namespace["combustion_tune"]()
    assert t["stoichiometric_afr"] == pytest.approx(17.3, abs=0.2)
    assert t["excess_air_percent"] == pytest.approx(16.8, abs=0.5)
    # The actual ratio is the stoichiometric one scaled up by the excess air.
    assert t["actual_afr"] > t["stoichiometric_afr"]


def test_parking_lot_storm_drain_example_swale_carries_the_storm():
    namespace = runpy.run_path(str(_EXAMPLES / "parking_lot_storm_drain.py"))
    d = namespace["drainage_check"]()
    # The rational-method peak runoff and the swale's Manning capacity, with margin > 1.
    assert d["peak_runoff_m3s"] == pytest.approx(0.120, abs=0.005)
    assert d["swale_capacity_m3s"] > d["peak_runoff_m3s"]
    assert d["capacity_margin"] == pytest.approx(1.9, abs=0.1)


def test_highway_curve_superelevation_example_max_speed_matches_design():
    namespace = runpy.run_path(str(_EXAMPLES / "highway_curve_superelevation.py"))
    c = namespace["curve_design"]()
    assert c["radius_m"] == pytest.approx(354.0, abs=2.0)
    # The built curve's max speed returns the 25 m/s design speed.
    assert c["max_speed_m_s"] == pytest.approx(25.0, abs=0.2)
    # The friction-free ideal superelevation far exceeds the 6% actually built.
    assert c["ideal_superelevation_rate"] > 0.06


def test_compressible_pitot_stagnation_example_bernoulli_undercounts():
    namespace = runpy.run_path(str(_EXAMPLES / "compressible_pitot_stagnation.py"))
    r = namespace["stagnation_ratios"]()
    # The compressible pressure ratio exceeds the incompressible Bernoulli approximation.
    assert r["pressure_ratio"] > r["incompressible_pressure_ratio"]
    assert r["pressure_ratio"] == pytest.approx(1.6038, rel=1e-3)
    # The ideal-gas identity holds: p0/p = rho0/rho * T0/T.
    assert r["pressure_ratio"] == pytest.approx(
        r["density_ratio"] * r["temperature_ratio"], rel=1e-9
    )


def test_rocket_nozzle_area_ratio_example_two_roots():
    namespace = runpy.run_path(str(_EXAMPLES / "rocket_nozzle_area_ratio.py"))
    r = namespace["nozzle_area_ratios"]()
    assert r["throat_m1"] == pytest.approx(1.0, rel=1e-9)
    # Mach 3 needs a far larger bell than Mach 2.
    assert r["exit_m3"] > r["exit_m2"]
    # The subsonic M~0.33 shares roughly the Mach-2 area ratio (the two-root property).
    assert r["subsonic_m033"] == pytest.approx(r["exit_m2"], rel=0.05)


def test_control_valve_cavitation_example_heavy_throttle_cavitates():
    namespace = runpy.run_path(str(_EXAMPLES / "control_valve_cavitation.py"))
    v = namespace["valve_cavitation"]()
    assert v["light_sigma"] > 1.0
    assert v["heavy_sigma"] < 1.0


def test_fan_total_pressure_selection_example():
    namespace = runpy.run_path(str(_EXAMPLES / "fan_total_pressure_selection.py"))
    d = namespace["fan_duty"]()
    assert d["velocity_pressure_pa"] == pytest.approx(60.0, rel=1e-9)
    assert d["fan_total_pressure_pa"] == pytest.approx(310.0, rel=1e-9)
    # The pitot relation recovers the duct velocity from the velocity pressure.
    assert d["recovered_velocity_ms"] == pytest.approx(10.0, rel=1e-6)


def test_rectangular_duct_sizing_example_equivalent_exceeds_hydraulic():
    namespace = runpy.run_path(str(_EXAMPLES / "rectangular_duct_sizing.py"))
    r = namespace["duct_and_fan"]()
    # The ASHRAE equivalent diameter is larger than the hydraulic 4A/P.
    assert r["equivalent_mm"] > r["hydraulic_mm"]
    assert r["equivalent_mm"] == pytest.approx(381.0, abs=2.0)
    assert r["fan_watts"] == pytest.approx(774.0, abs=2.0)


def test_fuel_injector_droplet_breakup_example_velocity_squared():
    namespace = runpy.run_path(str(_EXAMPLES / "fuel_injector_droplet_breakup.py"))
    w = namespace["droplet_weber"]()
    # The low-velocity droplet stays intact (We < 12); the high-velocity one breaks up.
    assert w["weber_dribble"] < 12
    assert w["weber_spray"] > 12
    # Weber scales with velocity squared: 40x the speed -> 1600x the Weber.
    assert w["weber_spray"] / w["weber_dribble"] == pytest.approx((80 / 2) ** 2, rel=1e-6)


def test_emergency_accumulator_sizing_example():
    namespace = runpy.run_path(str(_EXAMPLES / "emergency_accumulator_sizing.py"))
    r = namespace["clamp_accumulator"]()
    # Sizing a 3.6 L adiabatic stroke lands near a 10 L bottle...
    assert r["size_l"] == pytest.approx(9.94, rel=1e-2)
    # ...and that same bottle delivers more on a slow (isothermal) cycle.
    assert r["isothermal_l"] > 3.6


def test_clarifier_particle_settling_example_d_squared_law():
    namespace = runpy.run_path(str(_EXAMPLES / "clarifier_particle_settling.py"))
    r = namespace["settling_times"]()
    # Both particles are in the Stokes regime (Re < 1).
    assert r["sand_100um"]["reynolds"] < 1.0
    assert r["silt_10um"]["reynolds"] < 1.0
    # The 10x smaller silt settles ~100x slower (the d^2 law).
    ratio = r["silt_10um"]["settle_minutes"] / r["sand_100um"]["settle_minutes"]
    assert ratio == pytest.approx(100.0, rel=1e-6)


def test_generator_capacity_factor_example():
    namespace = runpy.run_path(str(_EXAMPLES / "generator_capacity_factor.py"))
    c = namespace["capacity_factors"]()
    # Baseload gas beats wind beats solar on capacity factor.
    assert c["wind_cf"] == pytest.approx(0.342, abs=0.005)
    assert c["solar_cf"] == pytest.approx(0.20, abs=0.005)
    assert c["gas_cf"] > c["wind_cf"] > c["solar_cf"]


def test_wind_turbine_power_curve_example_cube_law():
    namespace = runpy.run_path(str(_EXAMPLES / "wind_turbine_power_curve.py"))
    t = namespace["turbine_output"]()
    assert t["power_12ms_mw"] > t["power_8ms_mw"]
    # 8 m/s over 12 m/s power ratio is (8/12)^3 ~ 0.30.
    assert t["light_over_brisk"] == pytest.approx((8 / 12) ** 3, rel=1e-6)
    assert t["betz_limit"] == pytest.approx(16 / 27, rel=1e-9)


def test_pv_summer_derating_example_hot_cell_loses_power():
    namespace = runpy.run_path(str(_EXAMPLES / "pv_summer_derating.py"))
    m = namespace["module_output"]()
    # The summer cell runs ~63 C and loses output; the cooler spring cell keeps more.
    assert m["summer_cell_c"] == pytest.approx(63.1, abs=0.2)
    assert m["summer_power_w"] < m["spring_power_w"]
    assert m["summer_power_w"] < 400.0


def test_incline_conveyor_sizing_example_throughput_and_lift():
    namespace = runpy.run_path(str(_EXAMPLES / "incline_conveyor_sizing.py"))
    c = namespace["conveyor_sizing"]()
    # 540 t/h on a 0.05 m^2 profile -> 2 m/s; a narrower profile needs a faster belt.
    assert c["throughput_tph"] == pytest.approx(540.0, rel=1e-9)
    assert c["belt_speed_ms"] == pytest.approx(2.0, rel=1e-9)
    assert c["narrow_belt_speed_ms"] == pytest.approx(3.03, abs=0.02)
    assert c["narrow_belt_speed_ms"] > c["belt_speed_ms"]
    # Lifting 150 kg/s up 30 m draws ~44 kW.
    assert c["lift_power_kw"] == pytest.approx(44.13, abs=0.1)


def test_press_brake_springback_example_spring_steel_recovers_more():
    namespace = runpy.run_path(str(_EXAMPLES / "press_brake_springback.py"))
    r = namespace["springback_by_material"]()
    mild = r["mild_steel"]
    spring = r["spring_steel"]
    # Mild steel barely springs back (~0.5 deg); spring steel recovers ~2.5 deg.
    assert mild["overbend_deg"] == pytest.approx(0.54, abs=0.05)
    assert spring["overbend_deg"] == pytest.approx(2.52, abs=0.05)
    # The resilient alloy springs back much more, and its factor is further from 1.
    assert spring["overbend_deg"] > mild["overbend_deg"]
    assert spring["springback_factor"] < mild["springback_factor"]
    # Both sprung radii open up past the formed 4 mm.
    assert spring["sprung_radius_mm"] > mild["sprung_radius_mm"] > 4.0


def test_wire_drawing_pass_limit_example_reduction_capped_by_strength():
    namespace = runpy.run_path(str(_EXAMPLES / "wire_drawing_pass_limit.py"))
    d = namespace["drawing_limits"]()
    # Max reduction ~49% with friction, below the frictionless 63% (1 - 1/e).
    assert d["max_reduction"] == pytest.approx(0.492, abs=0.005)
    assert d["ideal_reduction"] == pytest.approx(0.632, abs=0.005)
    assert d["max_reduction"] < d["ideal_reduction"]
    # A 20% working pass draws at ~132 MPa, about a third of the 400 MPa wire strength.
    assert d["pass_stress_mpa"] == pytest.approx(131.7, abs=0.5)
    assert d["stress_ratio"] == pytest.approx(0.329, abs=0.005)
    assert d["stress_ratio"] < 1.0  # the wire survives the pass


def test_surface_grinding_specific_energy_example_governs_on_heat():
    namespace = runpy.run_path(str(_EXAMPLES / "surface_grinding_specific_energy.py"))
    d = namespace["grinding_pass"]()
    # Q'_w = a_e*v_w = 0.02*200 = 4 mm^3/(mm*s).
    assert d["specific_removal_rate_mm2_s"] == pytest.approx(4.0, abs=0.01)
    # h_eq = Q'_w/v_s = 4/30000 mm = 0.133 um; a faster wheel peels a thinner ribbon.
    assert d["equivalent_chip_thickness_um"] == pytest.approx(0.1333, abs=0.001)
    assert d["equivalent_chip_thickness_fast_um"] < d["equivalent_chip_thickness_um"]
    # u = P/(b*Q'_w) = 2400/(20*4) = 30 J/mm^3 — an order of magnitude above a turning cut.
    assert d["specific_energy_j_mm3"] == pytest.approx(30.0, abs=0.1)
    assert d["specific_energy_j_mm3"] > 10.0


def test_broach_pull_force_margin_example_tension_governs():
    namespace = runpy.run_path(str(_EXAMPLES / "broach_pull_force_margin.py"))
    d = namespace["broach_margin"]()
    # Three teeth in cut: floor(25/8).
    assert d["teeth_in_cut"] == 3
    # Cutting force 2500 MPa * 3 * 12 mm * 0.06 mm = 5.4 kN.
    assert d["cutting_force_kn"] == pytest.approx(5.4, abs=0.01)
    # Pull capacity 300 MPa * 120 mm^2 = 36 kN, a margin of ~6.7x over the cut.
    assert d["pull_capacity_kn"] == pytest.approx(36.0, abs=0.05)
    assert d["margin"] == pytest.approx(36.0 / 5.4, abs=0.05)
    assert d["margin"] > 1.0  # the broach survives the stroke


def test_drill_press_torque_limit_example_torque_governs():
    namespace = runpy.run_path(str(_EXAMPLES / "drill_press_torque_limit.py"))
    d = namespace["drill_duty"]()
    # 12 mm drill at 0.2 mm/rev, 600 rpm: MRR ~13.6 cm^3/min.
    assert d["removal_rate_cm3_min"] == pytest.approx(13.57, abs=0.05)
    # Torque u*f*d^2/8 = 2000 MPa * 0.2 mm * 144 mm^2 / 8 = 7.2 N*m, under the 10 N*m rating.
    assert d["torque_nm"] == pytest.approx(7.2, abs=0.01)
    # Feed ceiling at 10 N*m: 8*10/(2000*144) = 0.278 mm/rev; the 0.2 used sits inside it.
    assert d["feed_ceiling_mm"] == pytest.approx(0.2778, abs=0.001)
    assert d["feed_used_mm"] < d["feed_ceiling_mm"]


def test_ecm_gap_regulation_example_gap_self_regulates():
    namespace = runpy.run_path(str(_EXAMPLES / "ecm_gap_regulation.py"))
    d = namespace["ecm_operating_point"]()
    # 1000 A -> ~2.2 cm^3/min, 100 A/cm^2 -> ~2.2 mm/min.
    assert d["removal_rate_cm3_min"] == pytest.approx(2.2, abs=0.05)
    assert d["feed_rate_mm_min"] == pytest.approx(2.2, abs=0.05)
    # Equilibrium gap ~0.3 mm, halving to ~0.15 mm at double the feed.
    assert d["gap_mm"] == pytest.approx(0.3, abs=0.005)
    assert d["gap_double_feed_mm"] == pytest.approx(0.15, abs=0.005)
    assert d["gap_double_feed_mm"] < d["gap_mm"]


def test_laser_cut_thickness_limit_example_power_governs():
    namespace = runpy.run_path(str(_EXAMPLES / "laser_cut_thickness_limit.py"))
    d = namespace["laser_cut_envelope"]()
    # e_m = c*dT + L_f = 1.01 MJ/kg.
    assert d["specific_removal_energy_mj_kg"] == pytest.approx(1.01, abs=0.005)
    # 2 kW at 40% coupling severs 5 mm steel at ~4 m/min.
    assert d["speed_on_5mm_m_min"] == pytest.approx(4.04, abs=0.05)
    # At a reliable 2 m/min the ceiling is ~10 mm; slower reaches thicker plate than the 5 mm cut.
    assert d["max_thickness_at_2m_min_mm"] == pytest.approx(10.09, abs=0.05)
    assert d["max_thickness_at_2m_min_mm"] > 5.0


def test_edm_roughing_vs_finishing_example_energy_trades_off():
    namespace = runpy.run_path(str(_EXAMPLES / "edm_roughing_vs_finishing.py"))
    d = namespace["edm_settings"]()
    rough, finish = d["roughing"], d["finishing"]
    # Roughing: 50 mJ/spark, 50% duty, 20 mm^3/min.
    assert rough["energy_mj"] == pytest.approx(50.0, abs=0.05)
    assert rough["duty_factor"] == pytest.approx(0.5, abs=0.001)
    assert rough["mrr_mm3_min"] == pytest.approx(20.0, abs=0.05)
    # Finishing: 1 mJ/spark (1/50th the crater), ~17% duty, ~1.33 mm^3/min.
    assert finish["energy_mj"] == pytest.approx(1.0, abs=0.02)
    assert finish["duty_factor"] == pytest.approx(10 / 60, abs=0.005)
    # The finish buys surface at the cost of speed: far less energy and far less removal.
    assert finish["energy_mj"] < rough["energy_mj"]
    assert finish["mrr_mm3_min"] < rough["mrr_mm3_min"]


def test_centrifugal_cast_pipe_speed_example_g_factor_sets_speed():
    namespace = runpy.run_path(str(_EXAMPLES / "centrifugal_cast_pipe_speed.py"))
    d = namespace["centrifugal_cast_setup"]()
    # 90 G at a 75 mm bore radius needs ~1036 rpm.
    assert d["speed_rpm"] == pytest.approx(1036.0, abs=2.0)
    # The G-factor checks back out at the design value.
    assert d["achieved_g_factor"] == pytest.approx(90.0, rel=1e-6)
    # Metallostatic wall pressure ~0.10 MPa.
    assert d["wall_pressure_mpa"] == pytest.approx(0.10, abs=0.01)


def test_shot_peening_coverage_time_example_saturates_toward_full():
    namespace = runpy.run_path(str(_EXAMPLES / "shot_peening_coverage_time.py"))
    d = namespace["peening_schedule"]()
    # Coverage rate ~35.3 per s.
    assert d["coverage_rate_per_s"] == pytest.approx(35.34, abs=0.05)
    # 98% coverage in ~0.111 s.
    assert d["full_coverage_time_s"] == pytest.approx(0.1107, abs=0.001)
    # Doubling exposure (200%) reaches ~99.96%, showing the diminishing return.
    assert d["coverage_at_200_percent"] == pytest.approx(0.9996, abs=1e-4)
    assert d["coverage_at_200_percent"] < 1.0


def test_casting_gating_choke_and_sprue_example_sizes_the_gate():
    namespace = runpy.run_path(str(_EXAMPLES / "casting_gating_choke_and_sprue.py"))
    d = namespace["gating_design"]()
    # 2000 cm^3 in 5 s under 0.2 m head needs a ~252 mm^2 choke.
    assert d["choke_area_mm2"] == pytest.approx(252.0, abs=1.0)
    # That choke fills in the target 5 s (round-trip).
    assert d["fill_time_s"] == pytest.approx(5.0, abs=0.01)
    # Sprue taper sqrt(0.22/0.02) = 3.317, wider at the top.
    assert d["sprue_taper_ratio"] == pytest.approx(3.317, abs=0.005)
    assert d["sprue_taper_ratio"] > 1.0


def test_thermoforming_wall_thinning_example_deeper_draw_needs_thicker_blank():
    namespace = runpy.run_path(str(_EXAMPLES / "thermoforming_wall_thinning.py"))
    d = namespace["thermoforming_case"]()
    # Areal draw ratio 200000/90000 = 2.222.
    assert d["areal_draw_ratio"] == pytest.approx(2.2222, abs=0.001)
    # A 2 mm sheet thins to ~0.9 mm average wall.
    assert d["average_wall_mm"] == pytest.approx(0.9, abs=0.005)
    # To leave a 0.5 mm wall the blank must start at ~1.11 mm — thicker than the wall.
    assert d["gauge_for_half_mm_wall_mm"] == pytest.approx(1.111, abs=0.005)
    assert d["gauge_for_half_mm_wall_mm"] > 0.5


def test_nickel_plating_time_example_faraday_sets_tank_time():
    namespace = runpy.run_path(str(_EXAMPLES / "nickel_plating_time.py"))
    d = namespace["nickel_plating"]()
    # 25 um over 100 cm^2 at 10 A, 95% efficiency needs ~12.8 min.
    assert d["plating_time_min"] == pytest.approx(12.8, abs=0.1)
    # About 2.2 g of nickel deposited in that time.
    assert d["mass_deposited_g"] == pytest.approx(2.23, abs=0.02)
    # Thickness checks back to the 25 um spec (round-trip).
    assert d["thickness_check_um"] == pytest.approx(25.0, abs=0.05)


def test_spot_weld_schedule_efficiency_example_needs_kiloamperes():
    namespace = runpy.run_path(str(_EXAMPLES / "spot_weld_schedule_efficiency.py"))
    d = namespace["spot_weld_schedule"]()
    # Nugget melting energy ~198 J.
    assert d["nugget_energy_j"] == pytest.approx(198.2, abs=1.0)
    # At 10% efficiency the machine generates ~1982 J.
    assert d["required_heat_j"] == pytest.approx(1982.0, abs=5.0)
    # That heat over 100 uohm and 0.2 s needs ~10 kA.
    assert d["weld_current_ka"] == pytest.approx(9.95, abs=0.1)
    # The current back-produces the required heat (round-trip through Joule's law).
    assert d["check_heat_j"] == pytest.approx(d["required_heat_j"], rel=1e-6)


def test_shear_spinning_sine_law_example_steep_cone_needs_stages():
    namespace = runpy.run_path(str(_EXAMPLES / "shear_spinning_sine_law.py"))
    d = namespace["spinning_case"]()
    # 30 deg cone from 4 mm -> 2 mm wall, a 50% reduction.
    assert d["wall_at_30deg_mm"] == pytest.approx(2.0, abs=0.005)
    assert d["reduction_at_30deg"] == pytest.approx(0.5, abs=1e-6)
    # A 1.5 mm wall needs a ~22 deg cone, a 62.5% reduction (steeper, likely staged).
    assert d["angle_for_1p5mm_deg"] == pytest.approx(22.02, abs=0.1)
    assert d["reduction_for_1p5mm"] == pytest.approx(0.625, abs=0.002)
    assert d["reduction_for_1p5mm"] > d["reduction_at_30deg"]


def test_steam_condenser_coefficient_example_tube_beats_plate():
    namespace = runpy.run_path(str(_EXAMPLES / "steam_condenser_coefficient.py"))
    d = namespace["condenser_duty"]()
    # Vertical plate ~5738 W/m^2K, horizontal tube ~11155 (roughly double).
    assert d["plate_coefficient"] == pytest.approx(5738.0, abs=5.0)
    assert d["tube_coefficient"] == pytest.approx(11155.0, abs=5.0)
    assert d["tube_coefficient"] > d["plate_coefficient"]
    # Condensate rate over 2 m^2 at the tube coefficient ~0.15 kg/s.
    assert d["condensate_rate_kg_s"] == pytest.approx(0.148, abs=0.005)


def test_boiling_burnout_margin_example_runs_below_critical_heat_flux():
    namespace = runpy.run_path(str(_EXAMPLES / "boiling_burnout_margin.py"))
    d = namespace["boiling_margin"]()
    # Rohsenow flux at 10 K superheat ~137 kW/m^2.
    assert d["operating_flux_kw_m2"] == pytest.approx(137.0, abs=1.0)
    # Zuber critical heat flux ~1.26 MW/m^2.
    assert d["critical_heat_flux_mw_m2"] == pytest.approx(1.259, abs=0.01)
    # Running at ~11% of burnout — a comfortable margin.
    assert d["fraction_of_burnout"] == pytest.approx(0.109, abs=0.005)
    assert d["fraction_of_burnout"] < 1.0


def test_tec_cooler_limit_example_joule_heat_caps_cooling():
    namespace = runpy.run_path(str(_EXAMPLES / "tec_cooler_limit.py"))
    d = namespace["tec_operating_point"]()
    # Seebeck voltage 2.0 V, net cooling 25 W, single-stage ceiling ~98 K.
    assert d["seebeck_voltage_v"] == pytest.approx(2.0, abs=0.01)
    assert d["net_cooling_w"] == pytest.approx(25.0, abs=0.1)
    assert d["max_temperature_difference_k"] == pytest.approx(98.0, abs=0.5)
    assert d["max_temperature_difference_k"] > 40.0  # the 40 K duty is inside the ceiling


def test_normal_shock_inlet_loss_example_static_up_total_lost():
    namespace = runpy.run_path(str(_EXAMPLES / "normal_shock_inlet_loss.py"))
    d = namespace["normal_shock"]()
    # Mach-2 shock: downstream Mach 0.577 (subsonic), p2/p1 = 4.5, p02/p01 ~ 0.721.
    assert d["downstream_mach"] == pytest.approx(0.5774, abs=0.001)
    assert d["downstream_mach"] < 1.0
    assert d["static_pressure_ratio"] == pytest.approx(4.5, abs=0.01)
    assert d["stagnation_pressure_recovery"] == pytest.approx(0.7209, abs=0.001)
    assert d["stagnation_pressure_recovery"] < 1.0  # total pressure is destroyed


def test_rocket_engine_thrust_example_vacuum_beats_sea_level():
    namespace = runpy.run_path(str(_EXAMPLES / "rocket_engine_thrust.py"))
    d = namespace["engine_performance"]()
    # Ideal exhaust velocity ~2457 m/s.
    assert d["exhaust_velocity_m_s"] == pytest.approx(2456.7, abs=1.0)
    # Sea-level thrust ~246 kN (perfectly expanded), vacuum ~276 kN (+30 kN pressure term).
    assert d["thrust_sea_level_kn"] == pytest.approx(245.67, abs=0.1)
    assert d["thrust_vacuum_kn"] == pytest.approx(275.67, abs=0.1)
    assert d["thrust_vacuum_kn"] - d["thrust_sea_level_kn"] == pytest.approx(30.0, abs=0.1)
    # Sea-level specific impulse ~251 s.
    assert d["specific_impulse_sea_s"] == pytest.approx(250.5, abs=0.5)


def test_rocket_delta_v_budget_example_single_stage_impossible():
    namespace = runpy.run_path(str(_EXAMPLES / "rocket_delta_v_budget.py"))
    d = namespace["delta_v_budget"]()
    # Stage Δv ~2952 m/s for a 3.33 mass ratio at 250 s.
    assert d["stage_delta_v_m_s"] == pytest.approx(2951.7, abs=1.0)
    # A 9400 m/s orbital budget on one 250 s stage needs ~98% propellant.
    assert d["orbital_propellant_fraction"] == pytest.approx(0.978, abs=0.003)
    assert d["orbital_propellant_fraction"] > 0.95  # structurally impossible -> staging


def test_leo_orbit_and_escape_example_escape_is_sqrt2_times_orbital():
    namespace = runpy.run_path(str(_EXAMPLES / "leo_orbit_and_escape.py"))
    d = namespace["leo_orbit"]()
    # LEO circular speed ~7.67 km/s, period ~92 min, escape ~10.85 km/s.
    assert d["orbital_speed_km_s"] == pytest.approx(7.673, abs=0.005)
    assert d["period_min"] == pytest.approx(92.4, abs=0.2)
    assert d["escape_velocity_km_s"] == pytest.approx(10.851, abs=0.005)
    # Escape is exactly sqrt(2) times the circular speed.
    assert d["escape_velocity_km_s"] == pytest.approx(2**0.5 * d["orbital_speed_km_s"], rel=1e-9)


def test_leo_to_geo_hohmann_example_total_delta_v():
    namespace = runpy.run_path(str(_EXAMPLES / "leo_to_geo_hohmann.py"))
    d = namespace["hohmann_transfer"]()
    # LEO->GEO Hohmann: first burn ~2.40 km/s, second ~1.46 km/s, total ~3.86 km/s.
    assert d["first_burn_km_s"] == pytest.approx(2.399, abs=0.005)
    assert d["second_burn_km_s"] == pytest.approx(1.457, abs=0.005)
    assert d["total_delta_v_km_s"] == pytest.approx(3.857, abs=0.005)
    # Coast time ~5.3 hours.
    assert d["transfer_time_hours"] == pytest.approx(5.29, abs=0.02)


def test_gto_vis_viva_example_perigee_faster_than_apogee():
    namespace = runpy.run_path(str(_EXAMPLES / "gto_vis_viva.py"))
    d = namespace["transfer_orbit"]()
    # Semi-major axis 24468 km; perigee ~10.07 km/s, apogee ~1.62 km/s.
    assert d["semi_major_axis_km"] == pytest.approx(24467.5, abs=1.0)
    assert d["perigee_speed_km_s"] == pytest.approx(10.072, abs=0.005)
    assert d["apogee_speed_km_s"] == pytest.approx(1.617, abs=0.005)
    assert d["perigee_speed_km_s"] > d["apogee_speed_km_s"]
    # Specific energy negative -> bound orbit.
    assert d["specific_energy_mj_kg"] == pytest.approx(-8.15, abs=0.05)
    assert d["specific_energy_mj_kg"] < 0


def test_ship_turbine_gyroscopic_load_example_couple_in_a_turn():
    namespace = runpy.run_path(str(_EXAMPLES / "ship_turbine_gyroscopic_load.py"))
    d = namespace["turbine_gyro_load"]()
    # Spin angular momentum ~157080 N*m*s, reaction couple ~16.4 kN*m in a 6 deg/s turn.
    assert d["spin_angular_momentum_nms"] == pytest.approx(157080.0, abs=5.0)
    assert d["reaction_moment_kn_m"] == pytest.approx(16.449, abs=0.01)
    # The couple precesses the axis at exactly the ship's turn rate (round-trip).
    assert d["precession_rate_deg_s"] == pytest.approx(6.0, abs=0.001)


def test_muffler_and_pipe_resonance_example_open_vs_closed():
    namespace = runpy.run_path(str(_EXAMPLES / "muffler_and_pipe_resonance.py"))
    d = namespace["resonances"]()
    # Helmholtz ~273 Hz.
    assert d["helmholtz_hz"] == pytest.approx(272.95, abs=0.5)
    # Open pipe 172/343 Hz (all harmonics); closed pipe 86/257 Hz (odd, octave lower).
    assert d["open_pipe_fundamental_hz"] == pytest.approx(171.5, abs=0.1)
    assert d["open_pipe_second_hz"] == pytest.approx(343.0, abs=0.1)
    assert d["closed_pipe_fundamental_hz"] == pytest.approx(85.75, abs=0.1)
    assert d["closed_pipe_second_hz"] == pytest.approx(257.25, abs=0.1)
    # Closed fundamental is an octave (half) below the open fundamental.
    assert d["closed_pipe_fundamental_hz"] == pytest.approx(
        d["open_pipe_fundamental_hz"] / 2, rel=1e-9
    )


def test_doppler_speed_gun_example_recovers_the_source_speed():
    namespace = runpy.run_path(str(_EXAMPLES / "doppler_speed_gun.py"))
    d = namespace["moving_source"]()
    # 1000 Hz from a 30 m/s approaching source heard as ~1096 Hz.
    assert d["shifted_frequency_hz"] == pytest.approx(1095.85, abs=0.1)
    # The Doppler inverse recovers the 30 m/s closing speed.
    assert d["recovered_speed_m_s"] == pytest.approx(30.0, abs=0.01)
    # Mach cone half-angle at Mach 2 is 30 degrees.
    assert d["mach_cone_angle_deg"] == pytest.approx(30.0, abs=0.01)


def test_camera_lens_and_resolution_example_image_and_diffraction_limit():
    namespace = runpy.run_path(str(_EXAMPLES / "camera_lens_and_resolution.py"))
    d = namespace["lens_system"]()
    # 50 mm lens, 2 m object -> image ~51.3 mm behind the lens, magnification ~-0.026.
    assert d["image_distance_mm"] == pytest.approx(51.28, abs=0.05)
    assert d["magnification"] == pytest.approx(-0.02564, abs=0.0005)
    assert d["magnification"] < 0
    # Diffraction limit at 550 nm, 25 mm aperture ~5.5 arcsec.
    assert d["resolution_arcsec"] == pytest.approx(5.54, abs=0.05)


def test_lens_speed_and_depth_example_f_number_trade():
    namespace = runpy.run_path(str(_EXAMPLES / "lens_speed_and_depth.py"))
    d = namespace["lens_speed"]()
    # 50 mm at 25 mm aperture is f/2; Airy spot ~2.7 um; f/8 hyperfocal ~10.4 m.
    assert d["f_number"] == pytest.approx(2.0, rel=1e-9)
    assert d["airy_spot_um"] == pytest.approx(2.684, abs=0.005)
    assert d["hyperfocal_m"] == pytest.approx(10.417, abs=0.02)


def test_fiber_optic_acceptance_example_refraction_and_trapping():
    namespace = runpy.run_path(str(_EXAMPLES / "fiber_optic_acceptance.py"))
    d = namespace["fiber_optics"]()
    # Air->glass 30 deg refracts to ~19.5 deg; glass critical angle ~41.8 deg.
    assert d["refracted_angle_deg"] == pytest.approx(19.471, abs=0.005)
    assert d["critical_angle_deg"] == pytest.approx(41.81, abs=0.01)
    # Fibre NA ~0.24, acceptance half-angle ~14 deg.
    assert d["fiber_numerical_aperture"] == pytest.approx(0.2425, abs=0.001)
    assert d["acceptance_half_angle_deg"] == pytest.approx(14.03, abs=0.05)


def test_lifting_magnet_holding_force_example_coil_to_clamp():
    namespace = runpy.run_path(str(_EXAMPLES / "lifting_magnet_holding_force.py"))
    d = namespace["lifting_magnet"]()
    # Bare coil 2.5 mT; 1 T pole -> 0.40 MPa pressure -> ~4.0 kN over 100 cm^2.
    assert d["coil_field_mt"] == pytest.approx(2.513, abs=0.005)
    assert d["pole_pressure_mpa"] == pytest.approx(0.398, abs=0.002)
    assert d["holding_force_kn"] == pytest.approx(3.979, abs=0.01)


def test_conveyor_discharge_trajectory_example_places_the_chute():
    namespace = runpy.run_path(str(_EXAMPLES / "conveyor_discharge_trajectory.py"))
    d = namespace["discharge_trajectory"]()
    # 3 m/s at 20 deg: ~0.59 m throw, ~5.4 cm peak, ~0.21 s aloft.
    assert d["range_m"] == pytest.approx(0.590, abs=0.005)
    assert d["peak_height_m"] == pytest.approx(0.0537, abs=0.001)
    assert d["time_of_flight_s"] == pytest.approx(0.209, abs=0.002)


def test_highway_cruise_power_example_hills_dominate():
    namespace = runpy.run_path(str(_EXAMPLES / "highway_cruise_power.py"))
    d = namespace["cruise_power"]()
    # Rolling ~177 N, aero ~312 N; flat cruise ~13.6 kW.
    assert d["rolling_force_n"] == pytest.approx(176.5, abs=1.0)
    assert d["aero_force_n"] == pytest.approx(312.0, abs=1.0)
    assert d["flat_power_kw"] == pytest.approx(13.6, abs=0.1)
    # A 5% grade more than doubles the power.
    assert d["grade_power_kw"] == pytest.approx(34.0, abs=0.5)
    assert d["grade_power_kw"] > 2 * d["flat_power_kw"]


def test_radiation_shield_and_view_factor_example():
    namespace = runpy.run_path(str(_EXAMPLES / "radiation_shield_and_view_factor.py"))
    d = namespace["radiation_geometry"]()
    # Parallel strips F12 ~0.414; reciprocity to a 2x surface halves it; 3 shields -> 25%.
    assert d["view_factor_1_to_2"] == pytest.approx(0.4142, abs=0.001)
    assert d["reciprocity_view_factor_2_to_1"] == pytest.approx(0.2071, abs=0.001)
    assert d["shield_reduction_factor"] == pytest.approx(0.25, rel=1e-9)


def test_hopper_feed_and_stockpile_example_sizes_outlet_and_pile():
    namespace = runpy.run_path(str(_EXAMPLES / "hopper_feed_and_stockpile.py"))
    d = namespace["bulk_handling"]()
    # Outlet ~113 mm for 10 kg/s; it passes ~10 kg/s; stockpile ~733 m^3 (~1100 t).
    assert d["outlet_diameter_mm"] == pytest.approx(113.2, abs=0.5)
    assert d["discharge_rate_kg_s"] == pytest.approx(10.0, abs=0.05)
    assert d["stockpile_volume_m3"] == pytest.approx(733.3, abs=1.0)
    assert d["stockpile_tonnes"] == pytest.approx(1100.0, abs=5.0)


def test_screw_conveyor_feeder_example_rates_and_speed():
    namespace = runpy.run_path(str(_EXAMPLES / "screw_conveyor_feeder.py"))
    d = namespace["feeder_rating"]()
    # 250 mm screw, 60 mm core, 250 mm pitch, 0.3 fill, 750 kg/m^3 at 45 rpm.
    assert d["rated_volume_m3_h"] == pytest.approx(9.37, abs=0.05)
    assert d["rated_mass_t_h"] == pytest.approx(7.03, abs=0.05)
    # A 15 t/h target needs ~96 rpm (linear in speed).
    assert d["speed_for_target_rpm"] == pytest.approx(96.1, abs=0.5)


def test_cobalt60_source_decay_example_constant_activity_and_time():
    namespace = runpy.run_path(str(_EXAMPLES / "cobalt60_source_decay.py"))
    d = namespace["source_decay"]()
    # Co-60 5.27 yr: lambda ~0.132/yr, ~26.8 GBq after 10 yr, ~17.5 yr to 10 GBq.
    assert d["decay_constant_per_year"] == pytest.approx(0.1315, abs=0.001)
    assert d["activity_after_10yr_gbq"] == pytest.approx(26.84, abs=0.05)
    assert d["time_to_10pct_yr"] == pytest.approx(17.51, abs=0.05)


def test_piezo_force_sensor_example_charge_voltage_and_force():
    namespace = runpy.run_path(str(_EXAMPLES / "piezo_force_sensor.py"))
    d = namespace["force_sensor"]()
    # PZT-5H, 100 N -> 59.3 nC; 1 MPa over 2 mm -> 39.4 V; force round-trips.
    assert d["charge_nc"] == pytest.approx(59.3, rel=1e-6)
    assert d["open_circuit_voltage_v"] == pytest.approx(39.4, rel=1e-6)
    assert d["recovered_force_n"] == pytest.approx(100.0, rel=1e-9)


def test_hall_sensor_example_voltage_field_and_carrier_density():
    namespace = runpy.run_path(str(_EXAMPLES / "hall_sensor_and_characterization.py"))
    d = namespace["hall_readings"]()
    # 1 mA, 0.1 T, n=1e22 /m^3, 0.5 mm -> ~0.125 mV.
    assert d["hall_voltage_mv"] == pytest.approx(0.1248, abs=0.0005)
    assert d["recovered_field_t"] == pytest.approx(0.1, rel=1e-9)
    assert d["recovered_carrier_density"] == pytest.approx(1e22, rel=1e-9)


def test_strain_gauge_load_cell_example_bridge_output_and_stress():
    namespace = runpy.run_path(str(_EXAMPLES / "strain_gauge_load_cell.py"))
    d = namespace["read_load_cell"]()
    # GF 2.0 at 1000 microstrain: quarter 0.5 mV/V, full 2.0 mV/V.
    assert d["quarter_bridge_mv_per_v"] == pytest.approx(0.5, rel=1e-9)
    assert d["full_bridge_mv_per_v"] == pytest.approx(2.0, rel=1e-9)
    assert d["recovered_strain"] == pytest.approx(0.001, rel=1e-9)
    # 200 GPa * 0.001 = 200 MPa.
    assert d["stress_mpa"] == pytest.approx(200.0, rel=1e-9)


def test_centrifuge_clarification_example_velocity_and_time():
    namespace = runpy.run_path(str(_EXAMPLES / "centrifuge_clarification.py"))
    d = namespace["clarify_suspension"]()
    # 1 um, 1050 kg/m^3 particle at 10,000 rpm, 100 mm wall -> ~0.30 mm/s.
    assert d["wall_velocity_mm_s"] == pytest.approx(0.305, abs=0.005)
    # Surface (50 mm) to wall (100 mm) in ~228 s.
    assert d["settling_time_s"] == pytest.approx(227.5, abs=1.0)


def test_impeller_euler_head_example_tip_speed_and_vane_penalty():
    namespace = runpy.run_path(str(_EXAMPLES / "impeller_euler_head.py"))
    d = namespace["impeller_head"]()
    # 300 mm impeller at 1450 rpm -> ~22.8 m/s tip speed.
    assert d["tip_speed_m_s"] == pytest.approx(22.78, abs=0.05)
    # Backward-curved 25 deg vane ~38 m; radial 90 deg vane ~53 m (more head, less stable).
    assert d["backward_vane_head_m"] == pytest.approx(37.96, abs=0.1)
    assert d["radial_vane_head_m"] == pytest.approx(52.9, abs=0.1)
    assert d["radial_vane_head_m"] > d["backward_vane_head_m"]


def test_aluminium_extrusion_press_example_ratio_pressure_force():
    namespace = runpy.run_path(str(_EXAMPLES / "aluminium_extrusion_press.py"))
    e = namespace["extrusion_press"]()
    # 200 mm -> 32 mm round: ratio (200/32)^2 ~ 39.
    assert e["ratio"] == pytest.approx(39.06, abs=0.05)
    # Ideal ram pressure Y*ln R ~ 183 MPa; the 55% efficiency raises it to ~333 MPa.
    assert e["ideal_pressure_mpa"] == pytest.approx(183.3, abs=0.5)
    assert e["real_pressure_mpa"] == pytest.approx(333.2, abs=0.5)
    assert e["real_pressure_mpa"] > e["ideal_pressure_mpa"]
    # Ram force over the big billet is enormous, ~10,500 kN.
    assert e["ram_force_kn"] == pytest.approx(10467.7, abs=5.0)


def test_rolling_pass_schedule_example_bite_limit_and_force():
    namespace = runpy.run_path(str(_EXAMPLES / "rolling_pass_schedule.py"))
    p = namespace["rolling_pass"]()
    # Bite limit mu^2*R = 0.09*250 = 22.5 mm.
    assert p["max_draft_mm"] == pytest.approx(22.5, rel=1e-9)
    # A 5 mm pass: 35.4 mm contact, ~1414 kN force.
    assert p["contact_length_mm"] == pytest.approx(35.36, abs=0.05)
    assert p["force_kn"] == pytest.approx(1414.2, abs=1.0)
    # 5 mm fits the bite limit; a greedy 30 mm does not.
    assert p["wanted_feasible"] is True
    assert p["greedy_feasible"] is False


def test_forging_press_sizing_example_friction_hill_dominates():
    namespace = runpy.run_path(str(_EXAMPLES / "forging_press_sizing.py"))
    p = namespace["press_sizing"]()
    # 40 -> 25 mm is a 0.47 true strain; Hollomon flow stress ~508 MPa.
    assert p["true_strain"] == pytest.approx(0.470, abs=0.005)
    assert p["flow_stress_mpa"] == pytest.approx(508.2, abs=0.5)
    # The friction hill raises the load ~27% above the frictionless sigma*A.
    assert p["frictionless_kn"] == pytest.approx(3991.2, abs=1.0)
    assert p["load_kn"] == pytest.approx(5055.5, abs=1.0)
    assert p["load_kn"] > p["frictionless_kn"]


def test_injection_molding_machine_pick_example_clamp_and_cooling():
    namespace = runpy.run_path(str(_EXAMPLES / "injection_molding_machine_pick.py"))
    m = namespace["mould_process"]()
    # 120 cm^2 at 45 MPa -> 540 kN (~55 tonnes).
    assert m["clamp_force_kn"] == pytest.approx(540.0, rel=1e-6)
    assert m["clamp_force_tonnes"] == pytest.approx(55.06, abs=0.1)
    # A 980 kN machine holds up to ~218 cm^2 at 45 MPa.
    assert m["max_area_cm2"] == pytest.approx(217.78, abs=0.5)
    # Cooling scales with wall^2: a 3.5 mm wall takes (3.5/2.5)^2 = 1.96x the 2.5 mm time.
    assert m["cooling_3p5mm_s"] / m["cooling_2p5mm_s"] == pytest.approx((3.5 / 2.5) ** 2, rel=1e-6)
    assert m["cooling_3p5mm_s"] > m["cooling_2p5mm_s"]


def test_casting_riser_sizing_example_riser_outlasts_the_casting():
    namespace = runpy.run_path(str(_EXAMPLES / "casting_riser_sizing.py"))
    s = namespace["riser_sizing"]()
    # 200x150x40 mm plate: V/A = 1200/880 = 1.36 cm.
    assert s["casting_modulus_cm"] == pytest.approx(1200.0 / 880.0, rel=1e-6)
    # Chvorinov t = 2 * 1.36^2 ~ 3.72 min.
    assert s["freeze_time_min"] == pytest.approx(2.0 * (1200.0 / 880.0) ** 2, rel=1e-6)
    # The riser modulus target is 1.2x the casting's, so it freezes last.
    assert s["riser_modulus_cm"] == pytest.approx(1.2 * s["casting_modulus_cm"], rel=1e-9)
    assert s["riser_modulus_cm"] > s["casting_modulus_cm"]


def test_turning_speed_and_tool_life_example_trades_speed_for_life():
    namespace = runpy.run_path(str(_EXAMPLES / "turning_speed_and_tool_life.py"))
    t = namespace["turning_tradeoff"]()
    # 157 m/min -> ~1000 rpm, ~63 cm3/min, ~42 min life.
    assert t["slow_rpm"] == pytest.approx(1000.0, abs=2.0)
    assert t["slow_mrr"] == pytest.approx(62.8, abs=0.5)
    assert t["slow_life"] == pytest.approx(42.1, abs=0.5)
    # 250 m/min removes ~60% more metal but the tool lasts far less.
    assert t["fast_mrr"] == pytest.approx(100.0, abs=0.5)
    assert t["fast_mrr"] > t["slow_mrr"]
    assert t["fast_life"] < t["slow_life"]
    assert t["slow_life"] / t["fast_life"] > 6.0


def test_weld_heat_input_window_example_travel_speed_band():
    namespace = runpy.run_path(str(_EXAMPLES / "weld_heat_input_window.py"))
    w = namespace["heat_input_window"]()
    # 5 kW arc at 80% efficiency, 4 mm/s -> 1.0 kJ/mm.
    assert w["nominal_heat_input_kj_mm"] == pytest.approx(1.0, rel=1e-9)
    # The 0.8-1.5 kJ/mm window maps to a 2.67-5.0 mm/s travel band.
    assert w["slowest_speed_mm_s"] == pytest.approx(2.667, abs=0.01)
    assert w["fastest_speed_mm_s"] == pytest.approx(5.0, rel=1e-9)
    assert w["fastest_speed_mm_s"] > w["slowest_speed_mm_s"]


def test_stopping_sight_distance_grade_example_downgrade_governs():
    namespace = runpy.run_path(str(_EXAMPLES / "stopping_sight_distance_grade.py"))
    s = namespace["sight_distance_by_grade"]()
    # 110 km/h AASHTO: ~214 m level, ~232 m on a 4% downgrade.
    assert s["level_m"] == pytest.approx(213.7, abs=1.0)
    assert s["downgrade_m"] == pytest.approx(231.6, abs=1.0)
    # The downgrade always needs more sight distance than the level case.
    assert s["extra_m"] > 0
    assert s["downgrade_m"] > s["level_m"]


def test_hydraulic_motor_drive_example_sizes_from_displacement():
    namespace = runpy.run_path(str(_EXAMPLES / "hydraulic_motor_drive.py"))
    d = namespace["size_hydraulic_drive"]()
    # 50 cc/rev at 1500 rpm, 95% volumetric -> ~71 L/min.
    assert d["flow_lpm"] == pytest.approx(71.25, abs=0.1)
    # 200 bar across 50 cc/rev, 90% mechanical -> ~143 N*m.
    assert d["torque_nm"] == pytest.approx(143.2, abs=0.5)
    # The motor runs a little under the 1500 rpm pump because both leak.
    assert d["motor_rpm"] == pytest.approx(1353.75, abs=1.0)
    assert d["motor_rpm"] < 1500.0


def test_cooling_tower_approach_example_rates_by_approach():
    namespace = runpy.run_path(str(_EXAMPLES / "cooling_tower_approach.py"))
    p = namespace["tower_performance"]()
    # 37 C -> 30 C is a 7 K range; 30 C water vs 25 C wet-bulb is a 5 K approach.
    assert p["range_k"] == pytest.approx(7.0, rel=1e-9)
    assert p["approach_k"] == pytest.approx(5.0, rel=1e-9)
    # Effectiveness 7/12 ~ 0.58; a tighter 2 K approach lifts it well above.
    assert p["effectiveness"] == pytest.approx(7.0 / 12.0, rel=1e-9)
    assert p["tight_effectiveness"] == pytest.approx(7.0 / 9.0, rel=1e-9)
    assert p["tight_effectiveness"] > p["effectiveness"]


def test_carnot_ceiling_engine_grade_example_ranks_by_second_law():
    namespace = runpy.run_path(str(_EXAMPLES / "carnot_ceiling_engine_grade.py"))
    g = namespace["grade_engines"]()
    # Carnot ceiling between 1400 C and 15 C is ~83%.
    assert g["carnot_ceiling"] == pytest.approx(0.828, abs=0.005)
    # Both plants sit under the ceiling; the combined cycle grades far higher on the same duty.
    assert g["simple_second_law"] == pytest.approx(0.459, abs=0.005)
    assert g["combined_second_law"] == pytest.approx(0.725, abs=0.005)
    assert g["combined_second_law"] > g["simple_second_law"]
    assert g["combined_second_law"] < 1.0


def test_micro_hydro_sizing_example_penstock_loss_costs_power():
    namespace = runpy.run_path(str(_EXAMPLES / "micro_hydro_sizing.py"))
    s = namespace["hydro_sizing"]()
    # Net head strips the 4 m penstock loss off the 40 m gross drop.
    assert s["net_head_m"] == pytest.approx(36.0, rel=1e-9)
    # Gross-head power overstates the plant; the net-head number is the honest one.
    assert s["gross_power_kw"] == pytest.approx(16.48, abs=0.05)
    assert s["net_power_kw"] == pytest.approx(14.83, abs=0.05)
    assert s["net_power_kw"] < s["gross_power_kw"]
    # A 12 kW target at the net head needs ~49 L/s, under the 60 L/s the stream carries.
    assert s["flow_for_target_lps"] == pytest.approx(48.6, abs=0.5)
    assert s["flow_for_target_lps"] < 60.0


def test_solar_collector_stagnation_example_hot_fluid_bleeds_efficiency():
    namespace = runpy.run_path(str(_EXAMPLES / "solar_collector_stagnation.py"))
    p = namespace["collector_operating_points"]()
    # A near-ambient fluid keeps the collector near its optical ceiling (~0.77);
    # a hot afternoon fluid (45 C rise) bleeds it to ~0.58.
    assert p["morning_efficiency"] == pytest.approx(0.772, abs=0.01)
    assert p["afternoon_efficiency"] < p["morning_efficiency"]
    assert p["afternoon_efficiency"] == pytest.approx(0.584, abs=0.01)
    # No-flow stagnation on a 35 C day at full sun climbs to ~181 C.
    assert p["stagnation_c"] == pytest.approx(180.8, abs=1.0)
    assert p["stagnation_c"] > 150.0


def test_off_grid_cabin_solar_battery_example_sizes_both():
    namespace = runpy.run_path(str(_EXAMPLES / "off_grid_cabin_solar_battery.py"))
    s = namespace["off_grid_sizing"]()
    # 6 kWh/day at 4.5 sun hours, 0.78 derate -> ~1709 W array.
    assert s["array_watts"] == pytest.approx(1709.0, abs=5.0)
    # 250 W average over 2 days at 48 V, 50% DoD, 90% -> ~556 Ah.
    assert s["bank_amp_hours"] == pytest.approx(555.6, abs=2.0)


def test_post_tensioned_beam_balancing_example_uniform_stress_at_balance():
    namespace = runpy.run_path(str(_EXAMPLES / "post_tensioned_beam_balancing.py"))
    b = namespace["beam_balancing"]()
    assert b["balanced_load_kn_m"] == pytest.approx(25.0, rel=1e-6)
    # Under the balanced load the bottom fibre is uniform -P/A = -10 MPa (no bending).
    assert b["stress_at_balance_mpa"] == pytest.approx(-10.0, rel=1e-6)
    assert b["cracking_moment_kn_m"] == pytest.approx(720.0, rel=1e-3)


def test_timber_header_shear_governs_example_shear_beats_bending():
    namespace = runpy.run_path(str(_EXAMPLES / "timber_header_shear_governs.py"))
    card = namespace["header_scorecard"]()
    names = {e.name: e for e in card.entries}
    # Bending has room; the short span is governed (and failed) by shear.
    assert names["header bending"].status is CheckStatus.PASS
    assert names["header shear"].status is CheckStatus.FAIL
    # The bearing check clears with the C_b bonus.
    assert namespace["bearing_margin"]() > 1.5


def test_pyrometer_color_temperature_example_peak_shifts_and_inverts():
    namespace = runpy.run_path(str(_EXAMPLES / "pyrometer_color_temperature.py"))
    g = namespace["glow_colors"]()
    # The peak wavelength shortens as temperature rises.
    assert g["peak_nm_800K"] > g["peak_nm_1500K"] > g["peak_nm_5800K"]
    assert g["peak_nm_5800K"] == pytest.approx(500, abs=2)
    # The pyrometer inverts a 500 nm peak back to ~5800 K.
    assert g["inferred_T_from_500nm"] == pytest.approx(5796, abs=5)


def test_steam_line_expansion_loop_example_sizes_the_leg():
    namespace = runpy.run_path(str(_EXAMPLES / "steam_line_expansion_loop.py"))
    s = namespace["loop_sizing"]()
    # 60 m of steel over +280 K grows ~200 mm, needing an ~11-12 m loop leg.
    assert s["growth_mm"] == pytest.approx(201.6, abs=1.0)
    assert s["leg_length_m"] == pytest.approx(11.6, abs=0.5)


def test_cooling_coil_bypass_factor_example_deep_vs_shallow():
    namespace = runpy.run_path(str(_EXAMPLES / "cooling_coil_bypass_factor.py"))
    c = namespace["coil_factors"]()
    # The deep coil has a low bypass factor; the shallow one a much higher one.
    assert c["deep_bf"] == pytest.approx(0.09375, abs=0.001)
    assert c["shallow_bf"] == pytest.approx(0.375, abs=0.001)
    assert c["shallow_bf"] > c["deep_bf"]


def test_evaporative_cooler_climate_example_dry_beats_humid():
    namespace = runpy.run_path(str(_EXAMPLES / "evaporative_cooler_climate.py"))
    c = namespace["cooler_climates"]()
    # Same effectiveness both climates, but the dry desert gets far more cooling.
    assert c["desert_effectiveness"] == pytest.approx(0.85, rel=1e-9)
    assert c["humid_effectiveness"] == pytest.approx(0.85, rel=1e-9)
    assert c["desert_leaving_c"] == pytest.approx(23.0, abs=0.1)
    assert c["humid_leaving_c"] > c["desert_leaving_c"]


def test_ahu_mixed_air_example():
    namespace = runpy.run_path(str(_EXAMPLES / "ahu_mixed_air.py"))
    m = namespace["mixed_air"]()
    # The mix is mass-weighted toward the larger return stream.
    assert m["mixed_temperature_c"] == pytest.approx(26.75, rel=1e-6)
    assert m["mixed_humidity_ratio"] == pytest.approx(0.012, rel=1e-6)


def test_cooling_coil_sensible_latent_split_example_typical_shr():
    namespace = runpy.run_path(str(_EXAMPLES / "cooling_coil_sensible_latent_split.py"))
    c = namespace["coil_load_split"]()
    assert c["sensible_kw"] > c["latent_kw"]  # a comfort-cooling job is sensible-heavy
    assert c["shr"] == pytest.approx(0.72, abs=0.02)
    # The SHR is the sensible fraction of the total.
    assert c["shr"] == pytest.approx(
        c["sensible_kw"] / (c["sensible_kw"] + c["latent_kw"]), rel=1e-9
    )


def test_home_heating_degree_days_example_heat_pump_cuts_energy():
    namespace = runpy.run_path(str(_EXAMPLES / "home_heating_degree_days.py"))
    s = namespace["seasonal_heating"]()
    assert s["furnace_kwh"] == pytest.approx(20000.0, rel=1e-6)
    # The COP-3 heat pump delivers the same heat for a third of the furnace's fuel.
    assert s["heat_pump_kwh"] == pytest.approx(6000.0, rel=1e-6)
    assert s["furnace_kwh"] / s["heat_pump_kwh"] == pytest.approx(3.0 / 0.9, rel=1e-6)


def test_quenched_billet_transient_example_biot_and_fourier():
    namespace = runpy.run_path(str(_EXAMPLES / "quenched_billet_transient.py"))
    q = namespace["quench_regime"]()
    # Bi = 0.25 (above the 0.1 lumped limit) and Fo = 1.25 (past the 0.2 one-term mark).
    assert q["biot"] == pytest.approx(0.25, abs=0.01)
    assert q["biot"] > 0.1
    assert q["fourier"] == pytest.approx(1.25, abs=0.02)
    assert q["fourier"] > 0.2


def test_heated_panel_convection_regime_example_height_flips_regime():
    namespace = runpy.run_path(str(_EXAMPLES / "heated_panel_convection_regime.py"))
    r = namespace["panel_regimes"]()
    # The short panel is laminar (Ra < 1e9); the tall one is turbulent (Ra > 1e9).
    assert r["rayleigh_0p3m"] < 1e9
    assert r["rayleigh_2m"] > 1e9


def test_radiant_barrier_shield_example_low_emissivity_cuts_exchange():
    namespace = runpy.run_path(str(_EXAMPLES / "radiant_barrier_shield.py"))
    c = namespace["barrier_comparison"]()
    # The bare steel wall exchanges ~14.5 kW; the low-e barrier cuts it past 10x.
    assert c["bare_steel_w"] == pytest.approx(14516, rel=0.02)
    assert c["bare_steel_w"] / c["radiant_barrier_w"] > 10


def test_insulated_steam_pipe_heat_loss_example_lagging_cuts_loss():
    namespace = runpy.run_path(str(_EXAMPLES / "insulated_steam_pipe_heat_loss.py"))
    p = namespace["pipe_heat_loss"]()
    # Bare pipe sheds ~408 W/m; 50 mm lagging drops it near 45 W/m (~89% less).
    assert p["bare_w_per_m"] == pytest.approx(408.0, abs=5.0)
    assert p["insulated_w_per_m"] == pytest.approx(45.0, abs=2.0)
    assert p["reduction_percent"] > 85.0
    # The pipe radius (50 mm) is far above the 4 mm critical radius.
    assert p["critical_radius_mm"] == pytest.approx(4.0, abs=0.1)


def test_motor_feeder_scorecard_example_long_run_fails_on_drop():
    namespace = runpy.run_path(str(_EXAMPLES / "motor_feeder_scorecard.py"))
    r = namespace["feeder_scorecards"]()
    assert r["short_status"] == "pass"
    assert r["long_status"] == "fail"
    assert r["long_failures"] == "voltage drop"


def test_rc_antialiasing_filter_example_cutoff_and_settling():
    namespace = runpy.run_path(str(_EXAMPLES / "rc_antialiasing_filter.py"))
    r = namespace["rc_filter"]()
    # 10 kohm * 100 nF -> 1 ms tau, ~159 Hz cutoff, ~5 ms settling.
    assert r["time_constant_ms"] == pytest.approx(1.0, rel=1e-6)
    assert r["cutoff_hz"] == pytest.approx(159.2, abs=0.5)
    assert r["settling_ms"] == pytest.approx(5.0, rel=1e-6)


def test_dc_link_capacitor_energy_example_stores_hundreds_of_joules():
    namespace = runpy.run_path(str(_EXAMPLES / "dc_link_capacitor_energy.py"))
    d = namespace["dc_link_design"]()
    # 1500 uF at 650 V stores ~317 J.
    assert d["stored_energy_j"] == pytest.approx(317.0, abs=2.0)
    # The LC filter (2 mH, 1500 uF) rings near 92 Hz.
    assert d["resonant_frequency_hz"] == pytest.approx(92.0, abs=1.0)


def test_battery_round_trip_losses_example():
    namespace = runpy.run_path(str(_EXAMPLES / "battery_round_trip_losses.py"))
    d = namespace["delivered_energy"]()
    # Lithium returns nearly all the surplus; lead-acid loses far more.
    assert d["lithium_kwh"] == pytest.approx(11.28, abs=0.05)
    assert d["lead_acid_kwh"] == pytest.approx(9.6, abs=0.05)
    assert d["lithium_kwh"] > d["lead_acid_kwh"]


def test_ups_battery_bank_sizing_example_shallower_dod_shortens_runtime():
    namespace = runpy.run_path(str(_EXAMPLES / "ups_battery_bank_sizing.py"))
    b = namespace["bank_sizing"]()
    # 3 kW over 2 h at 48 V, 50% DoD, 90% eff -> ~278 Ah.
    assert b["capacity_ah"] == pytest.approx(277.8, abs=1.0)
    # Cycling the same bank to only 40% DoD gives 2 h * 0.4/0.5 = 1.6 h.
    assert b["shallow_runtime_h"] == pytest.approx(1.6, abs=0.05)


def test_busbar_skin_effect_example_depth_falls_with_frequency():
    namespace = runpy.run_path(str(_EXAMPLES / "busbar_skin_effect.py"))
    d = namespace["copper_skin_depths"]()
    # Skin depth shrinks steeply with frequency.
    assert d["depth_mm_60hz"] > d["depth_mm_10khz"] > d["depth_mm_1mhz"]
    assert d["depth_mm_60hz"] == pytest.approx(8.42, abs=0.05)
    assert d["depth_mm_1mhz"] == pytest.approx(0.065, abs=0.002)


def test_ground_electrode_sizing_example_soil_dominates():
    namespace = runpy.run_path(str(_EXAMPLES / "ground_electrode_sizing.py"))
    g = namespace["grounding_study"]()
    # The 10x-more-resistive sand gives a 10x-worse rod.
    assert g["sand_ohm"] == pytest.approx(10 * g["loam_ohm"], rel=1e-6)
    # Four interfering rods land above the ideal one-quarter.
    assert g["sand_four_rods_ohm"] > g["sand_ideal_quarter_ohm"]


def test_transformer_fault_current_rating_example_stiffer_is_harder():
    namespace = runpy.run_path(str(_EXAMPLES / "transformer_fault_current_rating.py"))
    s = namespace["fault_study"]()
    assert s["full_load_a"] == pytest.approx(1202.8, abs=1.0)
    assert s["fault_5p75_a"] == pytest.approx(20918.0, abs=50.0)
    # A stiffer (lower-impedance) transformer delivers a harder fault.
    assert s["fault_4p0_a"] > s["fault_5p75_a"]


def test_tank_floor_corrosion_life_example_methods_agree():
    namespace = runpy.run_path(str(_EXAMPLES / "tank_floor_corrosion_life.py"))
    a = namespace["floor_assessment"]()
    # The two independent methods land within ~10% of each other.
    assert a["coupon_rate_mm_yr"] == pytest.approx(a["probe_rate_mm_yr"], rel=0.1)
    # 8 mm now, 3 mm retirement, ~0.2 mm/yr -> ~25 years left.
    assert a["remaining_life_yr"] == pytest.approx(24.6, abs=1.0)


def test_welding_shop_ventilation_example_dilution_dwarfs_comfort():
    namespace = runpy.run_path(str(_EXAMPLES / "welding_shop_ventilation.py"))
    s = namespace["shop_ventilation"]()
    # ASHRAE comfort air is modest; fume dilution needs orders of magnitude more.
    assert s["comfort_cfm"] == pytest.approx(400.0, abs=1.0)
    assert s["dilution_cfm"] > 50 * s["comfort_cfm"]
    assert s["dilution_ach"] > 50.0


def test_lab_ventilation_air_changes_example():
    namespace = runpy.run_path(str(_EXAMPLES / "lab_ventilation_air_changes.py"))
    f = namespace["lab_airflow"]()
    # 8 ACH on a 180 m3 room is 0.40 m3/s; the office rate is a quarter of it.
    assert f["lab_flow_m3s"] == pytest.approx(0.40, abs=0.005)
    assert f["office_flow_m3s"] == pytest.approx(0.10, abs=0.005)
    assert f["recovered_ach"] == pytest.approx(8.0, rel=1e-6)


def test_office_ventilation_scorecard_example_lab_fails_on_air_changes():
    namespace = runpy.run_path(str(_EXAMPLES / "office_ventilation_scorecard.py"))
    r = namespace["zone_scorecards"]()
    # The office minimum passes; the lab-grade 6 ACH minimum fails on air changes only.
    assert r["office_status"] == "pass"
    assert r["lab_status"] == "fail"
    assert r["lab_fails"] == "air changes per hour"


def test_lighting_energy_tradeoff_example_middle_count_clears_both():
    namespace = runpy.run_path(str(_EXAMPLES / "lighting_energy_tradeoff.py"))
    r = namespace["layout_scorecards"]()
    # Too few fixtures is too dim; too many blows the energy cap; 20 passes both.
    assert r["count_14"] == "fail"
    assert r["count_14_fails"] == "task illuminance"
    assert r["count_20"] == "pass"
    assert r["count_28"] == "fail"
    assert r["count_28_fails"] == "lighting power density"


def test_worker_noise_dose_scorecard_example_niosh_is_stricter():
    namespace = runpy.run_path(str(_EXAMPLES / "worker_noise_dose_scorecard.py"))
    r = namespace["exposure_scorecards"]()
    # The ~94 dBA combined level over 6 h fails both standards.
    assert r["osha_status"] == "fail"
    assert r["niosh_status"] == "fail"
    assert r["osha_dose_percent"] > 100.0
    # NIOSH's tighter criterion and exchange rate multiply the dose well past OSHA's.
    assert r["niosh_dose_percent"] > r["osha_dose_percent"]


def test_office_lighting_cavity_ratio_example_tall_room_needs_more():
    namespace = runpy.run_path(str(_EXAMPLES / "office_lighting_cavity_ratio.py"))
    f = namespace["fixture_counts"]()
    # The tall cavity doubles the RCR and needs more fixtures for the same target.
    assert f["low_rcr"] == pytest.approx(1.75, abs=0.01)
    assert f["tall_rcr"] == pytest.approx(3.5, abs=0.01)
    assert f["tall_fixtures"] > f["low_fixtures"]


def test_office_lighting_layout_example_installed_grid_clears_target():
    namespace = runpy.run_path(str(_EXAMPLES / "office_lighting_layout.py"))
    r = namespace["lighting_layout"]()
    # The lumen-method inverse asks for ~19; the 5x4 grid of 20 clears 400 lux with margin.
    assert r["required_count"] == pytest.approx(19.0, abs=0.5)
    assert r["installed_count"] == 20
    assert r["achieved_lux"] > 400.0
    # High-bay point source: brightest directly below, dimmer offset to the side.
    assert r["highbay_below_lux"] == pytest.approx(555.6, abs=1.0)
    assert r["highbay_offset_lux"] < r["highbay_below_lux"]


def test_motor_feeder_voltage_drop_example_bigger_conductor_passes():
    namespace = runpy.run_path(str(_EXAMPLES / "motor_feeder_voltage_drop.py"))
    f = namespace["feeder_check"]()
    assert f["current_a"] == pytest.approx(51, abs=1)
    # The small conductor exceeds the 3% drop limit; the large one stays within it.
    assert f["small_drop_percent"] > 3.0
    assert f["large_drop_percent"] < 3.0
    assert f["small_drop_percent"] > f["large_drop_percent"]


def test_column_load_combinations_example_lrfd_exceeds_asd():
    namespace = runpy.run_path(str(_EXAMPLES / "column_load_combinations.py"))
    d = namespace["column_demands"]()
    # LRFD strength-level demand governs higher than the ASD service-level one.
    assert d["lrfd_kn"] == pytest.approx(677, abs=1)
    assert d["asd_kn"] == pytest.approx(535, abs=1)
    assert d["lrfd_kn"] > d["asd_kn"]


def test_roof_step_snow_drift_example_drift_dwarfs_balanced():
    namespace = runpy.run_path(str(_EXAMPLES / "roof_step_snow_drift.py"))
    d = namespace["drift_surcharge"]()
    assert d["balanced_kpa"] == pytest.approx(0.84, abs=0.01)
    assert d["drift_height_m"] == pytest.approx(1.16, abs=0.02)
    # The peak drift surcharge is several times the balanced snow load.
    assert d["drift_surcharge_kpa"] > 3 * d["balanced_kpa"]


def test_cold_storage_roof_snow_example_freezer_carries_more():
    namespace = runpy.run_path(str(_EXAMPLES / "cold_storage_roof_snow.py"))
    r = namespace["roof_snow_loads"]()
    # The freezer roof (Ct>1) carries more snow than the heated one...
    assert r["freezer_flat_kpa"] == pytest.approx(1.82, abs=0.01)
    assert r["heated_flat_kpa"] == pytest.approx(1.40, abs=0.01)
    assert r["freezer_flat_kpa"] > r["heated_flat_kpa"]
    # ...and the pitch sheds part of the freezer load back off.
    assert r["freezer_sloped_kpa"] < r["freezer_flat_kpa"]


def test_floor_beam_vibration_governs_capstone():
    namespace = runpy.run_path(str(_EXAMPLES / "floor_beam_vibration_governs.py"))
    card = namespace["screen_floor_beam"]()
    by_name = {e.name: e for e in card.entries}
    # Strength and deflection are comfortable...
    assert by_name["bending strength"].passed
    assert by_name["live-load deflection (L/360)"].passed
    assert "safety factor 4.26" in by_name["bending strength"].detail
    # ...but the long, light span fails the walking-vibration check, which governs.
    vibration = by_name["walking vibration (DG11)"]
    assert vibration.status is CheckStatus.FAIL
    assert "safety factor 0.47" in vibration.detail
    assert card.status is CheckStatus.FAIL


def test_office_floor_vibration_example_springy_bay_fails():
    namespace = runpy.run_path(str(_EXAMPLES / "office_floor_vibration.py"))
    r = namespace["floor_ratios"]()
    # The springy bay exceeds the 0.5% g office comfort limit; the stiff bay clears it.
    assert r["springy_ratio"] > 0.005
    assert r["stiff_ratio"] < 0.005
    assert r["springy_ratio"] > r["stiff_ratio"]


def test_spread_footing_sizing_example_overburden_grows_the_footing():
    namespace = runpy.run_path(str(_EXAMPLES / "spread_footing_sizing.py"))
    f = namespace["footing_area"]()
    assert f["allowable_kpa"] == pytest.approx(200.0, rel=1e-9)
    # The net-pressure footing (accounting for overburden) is bigger than the gross one.
    assert f["gross_area_m2"] == pytest.approx(4.0, rel=1e-9)
    assert f["net_area_m2"] == pytest.approx(4.571, abs=0.01)
    assert f["net_area_m2"] > f["gross_area_m2"]


def test_building_column_load_path_capstone_reduction_decides():
    namespace = runpy.run_path(str(_EXAMPLES / "building_column_load_path.py"))
    card = namespace["screen_column"]()
    by_name = {e.name: e for e in card.entries}
    # With the code-permitted live-load reduction the column passes...
    reduced = by_name["column with code live-load reduction"]
    assert reduced.passed
    assert "safety factor 1.19" in reduced.detail
    # ...but designed for the full unreduced live load it fails — the reduction decides.
    unreduced = by_name["column without the reduction"]
    assert unreduced.status is CheckStatus.FAIL
    assert "safety factor 0.90" in unreduced.detail


def test_flat_roof_rain_vs_snow_example_rain_governs():
    namespace = runpy.run_path(str(_EXAMPLES / "flat_roof_rain_vs_snow.py"))
    r = namespace["roof_loads"]()
    # The blocked-drain rain load narrowly governs over the flat-roof snow.
    assert r["snow_kpa"] == pytest.approx(0.84, abs=0.01)
    assert r["rain_kpa"] == pytest.approx(0.88, abs=0.01)
    assert r["rain_kpa"] > r["snow_kpa"]


def test_column_live_load_reduction_example_cuts_the_demand():
    namespace = runpy.run_path(str(_EXAMPLES / "column_live_load_reduction.py"))
    c = namespace["column_live_load"]()
    # Gathering 360 m2, the live load is floored at 40% of the unreduced value.
    assert c["reduced_live_kpa"] == pytest.approx(0.96, abs=0.01)
    assert c["reduced_live_kpa"] < c["unreduced_live_kpa"]
    # The reduction carries through the LRFD combination to a smaller factored demand.
    assert c["lrfd_reduced_kpa"] < c["lrfd_unreduced_kpa"]


def test_seismic_load_effect_combination_example_grows_the_demand():
    namespace = runpy.run_path(str(_EXAMPLES / "seismic_load_effect_combination.py"))
    d = namespace["seismic_demand"]()
    # The assembled E (rho + vertical) is much larger than the raw horizontal force...
    assert d["assembled_e_kn"] == pytest.approx(174.2, abs=0.5)
    assert d["assembled_e_kn"] > d["raw_qe_kn"]
    # ...and carries through to a larger, correct factored demand.
    assert d["demand_adjusted_kn"] > d["demand_raw_kn"]


def test_seismic_p_delta_stability_example_soft_story_amplifies():
    namespace = runpy.run_path(str(_EXAMPLES / "seismic_p_delta_stability.py"))
    s = namespace["stability_check"]()
    # The stiff story's P-delta is negligible; the soft story crosses the 0.10 threshold.
    assert s["stiff_theta"] < 0.10
    assert s["soft_theta"] == pytest.approx(0.110, abs=0.002)
    # The soft story is still under the stability ceiling (stable, but must be amplified).
    assert 0.10 <= s["soft_theta"] < s["theta_max"]
    assert s["theta_max"] == pytest.approx(0.125, rel=1e-6)


def test_seismic_elf_design_capstone_drift_governs():
    namespace = runpy.run_path(str(_EXAMPLES / "seismic_elf_design.py"))
    card = namespace["screen_seismic_design"]()
    by_name = {e.name: e for e in card.entries}
    # Both serviceability checks pass, but drift is the tight one and P-delta is comfortable.
    assert card.status is CheckStatus.PASS
    assert "safety factor 1.12" in by_name["story drift vs 0.020h limit"].detail
    assert "safety factor 2.24" in by_name["P-delta stability vs ceiling"].detail
    drift_sf = by_name["story drift vs 0.020h limit"].safety_factor
    pdelta_sf = by_name["P-delta stability vs ceiling"].safety_factor
    assert drift_sf < pdelta_sf  # drift governs
    # The long-period cap pulls the governing Cs below the 0.125 SDS/R plateau.
    assert namespace["_governing_cs"]() < 0.125


def test_seismic_story_drift_check_example_amplification_matters():
    namespace = runpy.run_path(str(_EXAMPLES / "seismic_story_drift_check.py"))
    d = namespace["drift_check"]()
    # The Cd-amplified drift is 5.5x the raw elastic value...
    assert d["amplified_mm"] == pytest.approx(66.0, abs=0.5)
    assert d["amplified_mm"] > d["elastic_mm"]
    # ...and the raw drift falsely looks far more comfortable than the real check allows.
    assert d["elastic_mm"] < d["allowable_mm"]
    assert d["amplified_mm"] < d["allowable_mm"]


def test_seismic_accidental_torsion_example_irregular_amplifies():
    namespace = runpy.run_path(str(_EXAMPLES / "seismic_accidental_torsion.py"))
    t = namespace["torsional_moments"]()
    assert t["symmetric_knm"] == pytest.approx(1200.0, rel=1e-9)
    assert t["amplification"] == pytest.approx(1.5625, abs=0.01)
    # The irregular building's amplified torsion is larger than the symmetric baseline.
    assert t["irregular_knm"] == pytest.approx(1875.0, abs=1.0)
    assert t["irregular_knm"] > t["symmetric_knm"]


def test_seismic_diaphragm_force_example_roof_floored():
    namespace = runpy.run_path(str(_EXAMPLES / "seismic_diaphragm_force.py"))
    d = namespace["diaphragm_forces"]()
    # The roof diaphragm force is floored above its proportional value...
    assert d["roof_fpx_kn"] == pytest.approx(400.0, rel=1e-9)
    assert d["roof_fpx_kn"] > d["roof_proportional_kn"]
    # ...while a mid floor takes its in-band proportional value.
    assert d["mid_fpx_kn"] == pytest.approx(600.0, rel=1e-9)


def test_seismic_story_forces_example_top_heavy():
    namespace = runpy.run_path(str(_EXAMPLES / "seismic_story_forces.py"))
    s = namespace["story_forces"]()
    # The story forces sum to the base shear...
    assert sum(s["k1_forces"]) == pytest.approx(s["base_shear_kn"], rel=1e-6)
    assert sum(s["k2_forces"]) == pytest.approx(s["base_shear_kn"], rel=1e-6)
    # ...and both distributions put the most force on the roof, k=2 more so.
    assert s["k1_forces"][-1] == max(s["k1_forces"])
    assert s["k2_forces"][-1] > s["k1_forces"][-1]


def test_cladding_internal_pressure_example_breach_worsens_suction():
    namespace = runpy.run_path(str(_EXAMPLES / "cladding_internal_pressure.py"))
    s = namespace["corner_panel_suction"]()
    # Both are net suction (negative); breaching the envelope makes it worse.
    assert s["enclosed_kpa"] == pytest.approx(-2.05, abs=0.01)
    assert s["breached_kpa"] == pytest.approx(-2.54, abs=0.01)
    assert s["breached_kpa"] < s["enclosed_kpa"] < 0


def test_seismic_cs_period_cap_example_tall_building_capped():
    namespace = runpy.run_path(str(_EXAMPLES / "seismic_cs_period_cap.py"))
    r = namespace["governing_cs"]()
    # The squat building takes the plateau; the tall building's longer period caps Cs lower.
    assert r["squat"]["governing"] == pytest.approx(r["squat"]["plateau"], rel=1e-9)
    assert r["tall"]["governing"] == pytest.approx(r["tall"]["cap"], rel=1e-9)
    assert r["tall"]["governing"] < r["squat"]["governing"]
    assert r["tall"]["period_s"] > r["squat"]["period_s"]


def test_wind_vs_seismic_base_shear_example_seismic_governs():
    namespace = runpy.run_path(str(_EXAMPLES / "wind_vs_seismic_base_shear.py"))
    d = namespace["lateral_demands"]()
    # The heavy building on a strong-shaking site is seismic-governed.
    assert d["wind_shear_kn"] == pytest.approx(770, abs=10)
    assert d["seismic_shear_kn"] == pytest.approx(6667, abs=10)
    assert d["seismic_shear_kn"] > d["wind_shear_kn"]


def test_motor_starting_inrush_example():
    namespace = runpy.run_path(str(_EXAMPLES / "motor_starting_inrush.py"))
    s = namespace["starting_currents"]()
    # The locked-rotor current is several times the running current.
    assert s["locked_rotor_a"] == pytest.approx(151, abs=1)
    assert s["inrush_ratio"] > 5.0
    assert s["locked_rotor_a"] > s["full_load_a"]


def test_induction_motor_speed_slip_example():
    namespace = runpy.run_path(str(_EXAMPLES / "induction_motor_speed_slip.py"))
    s = namespace["motor_speeds"]()
    # The 2-pole motor is twice the 4-pole speed; the 4-pole slip is a few percent.
    assert s["two_pole_rpm"] == pytest.approx(3600.0, rel=1e-9)
    assert s["four_pole_rpm"] == pytest.approx(1800.0, rel=1e-9)
    assert s["full_load_slip"] == pytest.approx((1800 - 1750) / 1800, rel=1e-9)


def test_motor_branch_circuit_example_efficiency_and_nec_factor():
    namespace = runpy.run_path(str(_EXAMPLES / "motor_branch_circuit.py"))
    m = namespace["motor_circuit"]()
    # The true full-load current exceeds the naive nameplate current...
    assert m["full_load_a"] == pytest.approx(28.3, abs=0.1)
    assert m["full_load_a"] > m["naive_a"]
    # ...and the branch circuit is 125% of it.
    assert m["branch_ampacity_a"] == pytest.approx(1.25 * m["full_load_a"], rel=1e-6)


def test_dc_low_voltage_run_example_small_cable_browns_out():
    namespace = runpy.run_path(str(_EXAMPLES / "dc_low_voltage_run.py"))
    f = namespace["dc_run_check"]()
    # On 24 V DC the small cable drops a crippling ~16%; the fat one clears the 3% limit.
    assert f["small_drop_percent"] == pytest.approx(15.8, abs=0.5)
    assert f["small_drop_percent"] > 3.0
    assert f["large_drop_percent"] < 3.0


def test_sign_wind_drag_example_gust_square_law():
    namespace = runpy.run_path(str(_EXAMPLES / "sign_wind_drag.py"))
    w = namespace["sign_wind_load"]()
    # A 40% faster gust nearly doubles the load (V^2): (42/30)^2 = 1.96.
    assert w["gust_over_mean"] == pytest.approx((42 / 30) ** 2, rel=1e-6)
    assert w["gust_load_kn"] > w["mean_load_kn"]
    assert w["mean_load_kn"] == pytest.approx(4.0, abs=0.2)


def test_multistage_compressor_staging_example_cuts_power_and_heat():
    namespace = runpy.run_path(str(_EXAMPLES / "multistage_compressor_staging.py"))
    s = namespace["staging_comparison"]()
    # More stages -> less power and a much lower per-stage discharge temperature.
    assert s["power_3stage_kw"] < s["power_2stage_kw"] < s["power_1stage_kw"]
    assert s["discharge_3stage_degc"] < s["discharge_2stage_degc"] < s["discharge_1stage_degc"]
    # Single stage runs ferociously hot; three stages tame it.
    assert s["discharge_1stage_degc"] == pytest.approx(603, abs=5)
    assert s["discharge_3stage_degc"] == pytest.approx(144, abs=5)


def test_air_receiver_sizing_example_holds_up_and_sizes():
    namespace = runpy.run_path(str(_EXAMPLES / "air_receiver_sizing.py"))
    r = namespace["receiver_sizing"]()
    # A 1 m^3 tank covers the 10 L/s net burst for a few minutes.
    assert r["holdup_s"] == pytest.approx(197, abs=3)
    # Riding a full 5-minute burst needs a larger receiver.
    assert r["volume_for_5min_m3"] == pytest.approx(1.52, abs=0.05)
    assert r["volume_for_5min_m3"] > 1.0


def test_water_main_hazen_williams_example_agrees_with_darcy():
    namespace = runpy.run_path(str(_EXAMPLES / "water_main_hazen_williams.py"))
    r = namespace["main_head_loss"]()
    # The two methods land within about 20% of each other on the same main.
    assert r["hazen_williams_head_m"] == pytest.approx(5.2, abs=0.2)
    assert r["darcy_head_m"] == pytest.approx(6.3, abs=0.3)
    assert 0.7 < r["ratio"] < 1.0
    # The capacity inverse gives a sensible discharge for the head budget.
    assert r["capacity_at_6m_lps"] == pytest.approx(54, abs=3)


def test_orifice_meter_sizing_example_reads_and_sizes():
    namespace = runpy.run_path(str(_EXAMPLES / "orifice_meter_sizing.py"))
    r = namespace["meter_readings"]()
    # A measured 20 kPa drop reads about 7.8 L/s.
    assert r["operating_flow_lps"] == pytest.approx(7.8, abs=0.2)
    # The 12 L/s full-scale flow sits at a much larger drop than the 20 kPa operating point
    # (flow ~ sqrt(dp)), which is what sets the transmitter range.
    assert r["full_scale_drop_kpa"] == pytest.approx(47, abs=2)
    assert r["full_scale_drop_kpa"] > 20.0


def test_tank_drain_down_example_slow_tail():
    namespace = runpy.run_path(str(_EXAMPLES / "tank_drain_down.py"))
    d = namespace["drain_schedule"]()
    # The two halves sum to the total, and the low-head half is much slower.
    assert d["upper_half_s"] + d["lower_half_s"] == pytest.approx(d["total_s"], rel=1e-9)
    assert d["lower_half_s"] > d["upper_half_s"]
    assert d["lower_over_upper"] == pytest.approx(2.4, abs=0.1)


def test_water_hammer_valve_closure_example_surge_dwarfs_working():
    namespace = runpy.run_path(str(_EXAMPLES / "water_hammer_valve_closure.py"))
    s = namespace["surge_check"]()
    # The wave speed is derived (Korteweg) from the steel pipe, not assumed: ~1191 m/s.
    assert s["wave_speed_ms"] == pytest.approx(1191, abs=5)
    # The surge is several times the working pressure.
    assert s["surge_over_working"] > 3.0
    assert s["surge_kpa"] == pytest.approx(3000, abs=50)
    # The critical closure time is the wave round-trip, well under a second here.
    assert s["critical_closure_s"] == pytest.approx(0.83, abs=0.02)


def test_vfd_pump_energy_saving_example_cube_law():
    namespace = runpy.run_path(str(_EXAMPLES / "vfd_pump_energy_saving.py"))
    op = namespace["vfd_operating_point"]()
    # 80% speed -> 80% flow but 0.8^3 = 51% power.
    assert op["flow_lps"] == pytest.approx(40, abs=0.5)
    assert op["power_fraction"] == pytest.approx(0.512, rel=1e-6)
    # A 20% speed cut is nearly a halving of power.
    assert op["power_fraction"] < 0.55


def test_pump_npsh_cavitation_example_hot_water_cavitates():
    namespace = runpy.run_path(str(_EXAMPLES / "pump_npsh_cavitation.py"))
    s = namespace["suction_margins"]()
    # Cold water has a positive cavitation margin; hot water goes negative.
    assert s["cold_margin_m"] > 0
    assert s["hot_margin_m"] < 0
    assert s["cold_margin_m"] == pytest.approx(1.6, abs=0.2)
    # The vapor pressure rise drops the available NPSH sharply.
    assert s["hot_npsh_available_m"] < s["cold_npsh_available_m"]


def test_pump_suction_specific_speed_limit_example():
    namespace = runpy.run_path(str(_EXAMPLES / "pump_suction_specific_speed_limit.py"))
    s = namespace["suction_speeds"]()
    # The slow pump stays under the ~3.5 reliability cap; the fast one crosses it.
    assert s["slow_nss"] == pytest.approx(2.92, abs=0.05)
    assert s["fast_nss"] == pytest.approx(4.54, abs=0.05)
    assert s["slow_nss"] < 3.5 < s["fast_nss"]


def test_turbine_blade_creep_example_shows_temperature_sensitivity():
    namespace = runpy.run_path(str(_EXAMPLES / "turbine_blade_creep_life.py"))
    summary = namespace["creep_life_summary"]()
    # A 100 K rise collapses the creep life by roughly two orders of magnitude.
    assert summary["excursion_life_hours"] < summary["design_life_hours"] / 100
    # The temperature limit for a 100,000 h life sits between the two service points.
    assert 1050 < summary["temperature_limit_K"] < 1150


def test_pipe_expansion_loop_example_shows_the_sif_governs():
    namespace = runpy.run_path(str(_EXAMPLES / "pipe_expansion_loop.py"))
    utils = namespace["loop_utilizations"]()
    # Accounting for the elbow SIF raises the utilization well above the straight-pipe
    # value — both pass, but the fitting is where the real stress is.
    assert utils["at_the_elbow"] > utils["straight_pipe"]
    assert utils["at_the_elbow"] < 1.0
    assert utils["at_the_elbow"] == pytest.approx(0.84, abs=0.03)


def test_spur_gear_agma_example_is_governed_by_pitting():
    namespace = runpy.run_path(str(_EXAMPLES / "spur_gear_agma_check.py"))
    utils = namespace["gear_utilizations"]()
    # Both modes pass, but the flanks (pitting) run a higher utilization than the tooth
    # root (bending) — the pitting-limited case a bending-only check misses.
    assert utils["pitting"] > utils["bending"]
    assert utils["bending"] < 1.0 and utils["pitting"] < 1.0
    assert utils["pitting"] == pytest.approx(0.69, abs=0.03)


def test_plate_girder_design_example_shows_web_penalty_and_shear_reserve():
    namespace = runpy.run_path(str(_EXAMPLES / "plate_girder_design.py"))
    caps = namespace["girder_capacities"]()
    r_pg = caps["bending_reduction"].magnitude
    # The slender web penalizes bending (R_pg < 1) ...
    assert 0.9 < r_pg < 1.0
    assert caps["moment"].to("kN*m").magnitude == pytest.approx(3884, abs=20)
    # ... but stiffening it mobilizes tension-field action for a large shear reserve.
    stiffened = caps["stiffened_shear"].to("kN").magnitude
    unstiffened = caps["unstiffened_shear"].to("kN").magnitude
    assert stiffened > 1.5 * unstiffened


def test_bolted_tension_splice_example_is_governed_by_block_shear():
    namespace = runpy.run_path(str(_EXAMPLES / "bolted_tension_splice.py"))
    caps = namespace["splice_capacities"]()
    yielding = caps["yielding"].to("kN").magnitude
    rupture = caps["rupture"].to("kN").magnitude
    block = caps["block_shear"].to("kN").magnitude
    # Both member checks pass at higher loads, but the end block tears out first —
    # block shear (~450 kN) governs below net rupture (~544) and yielding (~621).
    assert block < rupture < yielding
    assert block == pytest.approx(450, abs=5)


def test_hss_beam_flexure_shear_example_flags_flange_local_buckling():
    namespace = runpy.run_path(str(_EXAMPLES / "hss_beam_flexure_shear.py"))
    result = namespace["hss_beam_capacity"]()
    m_p = result["plastic_moment"].to("kN*m").magnitude
    m_n = result["flexural_strength"].to("kN*m").magnitude
    # The noncompact flange makes §F7 local buckling cut the strength below the plastic
    # moment a naive F_y*Z hand check would use — here about 7% lower.
    assert m_n < m_p
    assert (m_p - m_n) / m_p == pytest.approx(0.068, abs=0.01)
    # Shear (§G5) carries a large margin, as it does for most compact-to-noncompact HSS.
    assert result["shear_strength"].to("kN").magnitude > 500


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


def test_pump_station_electromechanical_capstone_feeder_governs():
    namespace = runpy.run_path(str(_EXAMPLES / "pump_station_electromechanical.py"))
    card = namespace["screen_station"]()
    by_name = {e.name: e for e in card.entries}
    # The hydraulics are all comfortable...
    assert "safety factor 3.45" in by_name["cavitation margin (NPSHa vs NPSHr)"].detail
    assert "safety factor 1.54" in by_name["inlet reliability (suction specific speed)"].detail
    assert "safety factor 1.17" in by_name["motor rating vs shaft power"].detail
    assert by_name["cavitation margin (NPSHa vs NPSHr)"].passed
    assert by_name["inlet reliability (suction specific speed)"].passed
    assert by_name["motor rating vs shaft power"].passed
    # ...but the undersized feeder over a long run governs and fails the station.
    feeder = by_name["feeder voltage drop vs 3% limit"]
    assert feeder.status is CheckStatus.FAIL
    assert "safety factor 0.65" in feeder.detail
    assert card.status is CheckStatus.FAIL
    # The feeder is the single binding constraint -- every other check passes.
    assert sum(1 for e in card.entries if not e.passed) == 1


def test_hydraulic_cylinder_cap_capstone_seal_governs():
    namespace = runpy.run_path(str(_EXAMPLES / "hydraulic_cylinder_cap.py"))
    card = namespace["screen_cap"]()
    by_name = {e.name: e for e in card.entries}
    # All five subsystems pass -- a validated design.
    assert card.status is CheckStatus.PASS
    assert all(e.passed for e in card.entries)
    # The structural parts are comfortable...
    assert "safety factor 3.09" in by_name["cylinder wall (bore von Mises)"].detail
    assert "safety factor 2.86" in by_name["end cover bending"].detail
    # ...while the seal and bolts are the tight ones, gland fill the tightest.
    assert "safety factor 1.79" in by_name["cap bolts vs end force"].detail
    assert "safety factor 1.40" in by_name["O-ring squeeze vs floor"].detail
    assert "safety factor 1.21" in by_name["O-ring gland fill vs ceiling"].detail
    # The binding constraint is the gland fill, not any structural check.
    tightest = min(
        card.entries, key=lambda e: float(e.detail.split("safety factor ")[1].split(" ")[0])
    )
    assert tightest.name == "O-ring gland fill vs ceiling"


def test_isolator_mount_selection_example_softer_is_better():
    namespace = runpy.run_path(str(_EXAMPLES / "isolator_mount_selection.py"))
    firm = namespace["screen_mount"]()
    # The firm 1 mm mount only reaches 34% isolation -- far short of the 90% target.
    assert firm.status is CheckStatus.FAIL
    assert "safety factor 0.15" in firm.entries[0].detail
    # The soft 4.4 mm mount, sized from the transmissibility inverse, meets it.
    soft = namespace["screen_soft_mount"]()
    assert soft.entries[0].passed
    assert "safety factor 1.01" in soft.entries[0].detail
    assert soft.status is CheckStatus.PASS


def test_living_hinge_flip_cap_example_lengthening_fixes_it():
    namespace = runpy.run_path(str(_EXAMPLES / "living_hinge_flip_cap.py"))
    drawn = namespace["screen_hinge"]()
    # The short, sharp web over-strains at 52% vs the 30% allowable.
    assert drawn.status is CheckStatus.FAIL
    assert "safety factor 0.57" in drawn.entries[0].detail
    # Lengthening the web spreads the same fold and brings the strain in band.
    fixed = namespace["screen_redesigned_hinge"]()
    assert fixed.entries[0].passed
    assert "safety factor 1.05" in fixed.entries[0].detail
    assert fixed.status is CheckStatus.PASS


def test_flip_top_closure_capstone_hinge_governs():
    namespace = runpy.run_path(str(_EXAMPLES / "flip_top_closure.py"))
    card = namespace["screen_closure"]()
    by_name = {e.name: e for e in card.entries}
    assert card.status is CheckStatus.PASS
    assert all(e.passed for e in card.entries)
    assert "safety factor 1.20" in by_name["hinge fold strain"].detail
    assert "safety factor 1.42" in by_name["latch flex strain"].detail
    assert "safety factor 4.31" in by_name["thumb close force"].detail
    # The hinge, which folds furthest every use, is the binding feature.
    tightest = min(
        card.entries, key=lambda e: float(e.detail.split("safety factor ")[1].split(" ")[0])
    )
    assert tightest.name == "hinge fold strain"


def test_v_belt_drive_capstone_traction_governs():
    namespace = runpy.run_path(str(_EXAMPLES / "v_belt_drive.py"))
    single = namespace["screen_drive"]()
    by_name = {e.name: e for e in single.entries}
    # Geometry and bearings pass comfortably...
    assert by_name["small-pulley wrap angle"].passed
    assert "safety factor 1.40" in by_name["small-pulley wrap angle"].detail
    assert by_name["belt speed"].passed
    assert by_name["pulley bearing L10 life"].passed
    # ...but a single belt slips under the service-factored load.
    assert by_name["belt grip (slip)"].status is CheckStatus.FAIL
    assert "safety factor 0.83" in by_name["belt grip (slip)"].detail
    assert single.status is CheckStatus.FAIL
    # Two belts split the load and restore the grip.
    two = namespace["screen_two_belt_drive"]()
    two_by_name = {e.name: e for e in two.entries}
    assert two_by_name["belt grip (slip)"].passed
    assert "safety factor 1.65" in two_by_name["belt grip (slip)"].detail
    assert two.status is CheckStatus.PASS


def test_spreader_beam_buckling_capstone_column_governs():
    namespace = runpy.run_path(str(_EXAMPLES / "spreader_beam_buckling.py"))
    slender = namespace["screen_spreader"]()
    by_name = {e.name: e for e in slender.entries}
    # The slings are fine...
    assert by_name["top sling leg tension"].passed
    assert "safety factor 1.13" in by_name["top sling leg tension"].detail
    # ...but the spreader buckles as a slender column under the sling compression.
    assert by_name["spreader column buckling"].status is CheckStatus.FAIL
    assert "safety factor 0.89" in by_name["spreader column buckling"].detail
    assert slender.status is CheckStatus.FAIL
    # A stubbier tube (same length and wall) clears the same compression.
    stubby = namespace["screen_stubbier_spreader"]()
    stubby_by_name = {e.name: e for e in stubby.entries}
    assert stubby_by_name["spreader column buckling"].passed
    assert "safety factor 1.80" in stubby_by_name["spreader column buckling"].detail
    assert stubby.status is CheckStatus.PASS


def test_press_fit_gear_capstone_grip_governs():
    namespace = runpy.run_path(str(_EXAMPLES / "press_fit_gear.py"))
    tight = namespace["screen_press_fit"]()
    by_name = {e.name: e for e in tight.entries}
    # Hub and shaft have plenty of margin...
    assert by_name["hub bore hoop stress"].passed
    assert "safety factor 3.34" in by_name["hub bore hoop stress"].detail
    assert by_name["shaft torsional shear"].passed
    assert "safety factor 2.45" in by_name["shaft torsional shear"].detail
    # ...but the fit slips before anything breaks.
    assert by_name["fit grip (slip) vs required torque"].status is CheckStatus.FAIL
    assert "safety factor 0.93" in by_name["fit grip (slip) vs required torque"].detail
    assert tight.status is CheckStatus.FAIL
    # A longer engagement adds grip area and carries the torque.
    longer = namespace["screen_longer_engagement"]()
    longer_by_name = {e.name: e for e in longer.entries}
    assert longer_by_name["fit grip (slip) vs required torque"].passed
    assert "safety factor 1.40" in longer_by_name["fit grip (slip) vs required torque"].detail
    assert longer.status is CheckStatus.PASS


def test_rotating_shaft_fatigue_capstone_fatigue_governs():
    namespace = runpy.run_path(str(_EXAMPLES / "rotating_shaft_fatigue.py"))
    card = namespace["screen_shaft"]()
    by_name = {e.name: e for e in card.entries}
    assert card.status is CheckStatus.PASS
    # Statically robust...
    assert by_name["static yield (keyway peak)"].passed
    assert "safety factor 3.31" in by_name["static yield (keyway peak)"].detail
    # ...but the fatigue margin is less than half, and it governs the shaft's life.
    assert by_name["fatigue (Goodman, fully reversed)"].passed
    assert "safety factor 1.35" in by_name["fatigue (Goodman, fully reversed)"].detail
    static_sf = float(
        by_name["static yield (keyway peak)"].detail.split("safety factor ")[1].split(" ")[0]
    )
    fatigue_sf = float(
        by_name["fatigue (Goodman, fully reversed)"].detail.split("safety factor ")[1].split(" ")[0]
    )
    assert fatigue_sf < static_sf / 2


def test_thermal_clearance_seizure_example_thermal_closure_governs():
    namespace = runpy.run_path(str(_EXAMPLES / "thermal_clearance_seizure.py"))
    tight = namespace["screen_clearance"]()
    # The 0.10 mm cold fit cannot cover the 0.144 mm thermal closure -> it seizes hot.
    assert tight.status is CheckStatus.FAIL
    assert "safety factor 0.61" in tight.entries[0].detail
    # Opening the cold clearance to 0.20 mm survives the closure with a film.
    opened = namespace["screen_opened_clearance"]()
    assert opened.entries[0].passed
    assert "safety factor 1.22" in opened.entries[0].detail
    assert opened.status is CheckStatus.PASS
    # The closure itself exceeds the tight cold clearance (why it seizes).
    assert namespace["_thermal_closure"]() > 0.10


def test_overhung_fan_resonance_capstone_critical_speed_governs():
    namespace = runpy.run_path(str(_EXAMPLES / "overhung_fan_resonance.py"))
    slender = namespace["screen_fan_shaft"]()
    by_name = {e.name: e for e in slender.entries}
    # Hugely strong in bending...
    assert by_name["shaft bending vs yield"].passed
    assert "safety factor 18.25" in by_name["shaft bending vs yield"].detail
    # ...but it runs at its critical speed and resonates.
    assert by_name["critical-speed separation"].status is CheckStatus.FAIL
    assert "safety factor 0.74" in by_name["critical-speed separation"].detail
    assert slender.status is CheckStatus.FAIL
    # A stiffer shaft raises the critical speed clear of the running speed.
    stiffer = namespace["screen_stiffer_shaft"]()
    stiffer_by_name = {e.name: e for e in stiffer.entries}
    assert stiffer_by_name["critical-speed separation"].passed
    assert "safety factor 1.71" in stiffer_by_name["critical-speed separation"].detail
    assert stiffer.status is CheckStatus.PASS


def test_single_cylinder_flywheel_example_sizes_from_energy_fluctuation():
    namespace = runpy.run_path(str(_EXAMPLES / "single_cylinder_flywheel.py"))
    # The energy fluctuation of the lumpy single-cylinder torque is ~399 J.
    assert namespace["energy_fluctuation"]().to("J").magnitude == pytest.approx(399.0, abs=2.0)
    # A 6.0 kg*m^2 flywheel holds the 2% coefficient of fluctuation...
    adequate = namespace["screen_flywheel"]()
    assert adequate.entries[0].passed
    assert "safety factor 1.19" in adequate.entries[0].detail
    assert adequate.status is CheckStatus.PASS
    # ...a 4.0 kg*m^2 one does not, and the engine hunts.
    light = namespace["screen_undersized_flywheel"]()
    assert light.entries[0].status is CheckStatus.FAIL
    assert "safety factor 0.79" in light.entries[0].detail


def test_bushing_wear_life_example_lubrication_governs():
    namespace = runpy.run_path(str(_EXAMPLES / "bushing_wear_life.py"))
    marginal = namespace["screen_bushing"]()
    # At K = 1e-7 the bushing wears out before its service interval.
    assert marginal.status is CheckStatus.FAIL
    assert "safety factor 0.75" in marginal.entries[0].detail
    # Halving the wear coefficient (a better film) doubles the life.
    improved = namespace["screen_better_lubricated_bushing"]()
    assert improved.entries[0].passed
    assert "safety factor 1.49" in improved.entries[0].detail
    assert improved.status is CheckStatus.PASS


def test_servo_duty_cycle_thermal_example_rms_governs():
    namespace = runpy.run_path(str(_EXAMPLES / "servo_duty_cycle_thermal.py"))
    fast = namespace["screen_fast_cycle"]()
    by_name = {e.name: e for e in fast.entries}
    # Every instant clears the peak rating...
    assert by_name["peak rating vs hardest instant"].passed
    assert "safety factor 1.50" in by_name["peak rating vs hardest instant"].detail
    # ...but the squared-average over the fast cycle exceeds the continuous rating.
    thermal = by_name["continuous rating vs cycle RMS torque"]
    assert thermal.status is CheckStatus.FAIL
    assert "safety factor 0.95" in thermal.detail
    assert fast.status is CheckStatus.FAIL
    # The same moves with a longer dwell cool enough to pass.
    relaxed = namespace["screen_relaxed_cycle"]()
    relaxed_by_name = {e.name: e for e in relaxed.entries}
    assert "safety factor 1.12" in relaxed_by_name["continuous rating vs cycle RMS torque"].detail
    assert relaxed.status is CheckStatus.PASS


def test_servo_inertia_matching_example_ratio_governs():
    namespace = runpy.run_path(str(_EXAMPLES / "servo_inertia_matching.py"))
    # Direct drive fails on both torque and the drive's inertia-ratio bound.
    direct = namespace["screen_direct_drive"]()
    by_name = {e.name: e for e in direct.entries}
    assert by_name["motor peak torque vs acceleration demand"].status is CheckStatus.FAIL
    assert "safety factor 0.30" in by_name["motor peak torque vs acceleration demand"].detail
    assert by_name["drive inertia-ratio bound vs reflected load"].status is CheckStatus.FAIL
    assert direct.status is CheckStatus.FAIL
    # The inertia-matched ratio is sqrt(J_L/J_m) = 15.8 and clears both checks.
    assert namespace["matched_ratio"]() == pytest.approx(15.81, abs=0.005)
    matched = namespace["screen_matched_drive"]()
    matched_by_name = {e.name: e for e in matched.entries}
    assert (
        "safety factor 2.37" in matched_by_name["motor peak torque vs acceleration demand"].detail
    )
    # At the matched ratio the reflected load equals the rotor: inertia ratio exactly 1.
    assert (
        "safety factor 10.00"
        in matched_by_name["drive inertia-ratio bound vs reflected load"].detail
    )
    assert matched.status is CheckStatus.PASS


def test_retaining_compound_hub_example_bond_beats_friction():
    namespace = runpy.run_path(str(_EXAMPLES / "retaining_compound_hub.py"))
    # The thin hub caps the fit pressure, so friction (mu*p) tops out far short.
    press = namespace["screen_press_fit"]()
    assert press.status is CheckStatus.FAIL
    assert "safety factor 0.28" in press.entries[0].detail
    # The same slip-fit interface bonded at the derated datasheet strength carries it.
    bonded = namespace["screen_bonded_hub"]()
    assert bonded.status is CheckStatus.PASS
    assert "safety factor 1.57" in bonded.entries[0].detail


def test_workshop_hoist_system_capstone_full_drum_governs():
    namespace = runpy.run_path(str(_EXAMPLES / "workshop_hoist_system.py"))
    # The friction-amplified lead line, not W/n = 5 kN, sizes the whole chain.
    lead = namespace["lead_line_tension"]()
    assert lead.to("kN").magnitude == pytest.approx(5.82, abs=0.005)
    naive = namespace["screen_hoist_system"]()
    by_name = {e.name: e for e in naive.entries}
    # Rope, sheave, and drum storage all clear against the real lead line...
    assert "safety factor 5.42" in by_name["lead line plus sheave bending vs rope strength"].detail
    assert "safety factor 1.37" in by_name["head-sheave groove pressure vs allowable"].detail
    assert "safety factor 1.07" in by_name["drum rope capacity vs travel"].detail
    # ...and the naive winch even clears the bare drum...
    assert by_name["bare-drum line pull vs lead line"].passed
    assert "safety factor 1.01" in by_name["bare-drum line pull vs lead line"].detail
    # ...but stalls where the lift finishes: on the full drum.
    full = by_name["full-drum line pull vs lead line"]
    assert full.status is CheckStatus.FAIL
    assert "safety factor 0.82" in full.detail
    assert naive.status is CheckStatus.FAIL
    upgraded = namespace["screen_upgraded_winch"]()
    upgraded_by_name = {e.name: e for e in upgraded.entries}
    assert "safety factor 1.14" in upgraded_by_name["full-drum line pull vs lead line"].detail
    assert upgraded.status is CheckStatus.PASS


def test_winch_full_drum_stall_example_top_layer_governs():
    namespace = runpy.run_path(str(_EXAMPLES / "winch_full_drum_stall.py"))
    narrow = namespace["screen_narrow_drum"]()
    by_name = {e.name: e for e in narrow.entries}
    # The rope fits and the bare-drum (catalogue) pull clears...
    assert by_name["stored rope vs required length"].passed
    assert "safety factor 1.06" in by_name["stored rope vs required length"].detail
    assert by_name["line pull at bare drum vs load"].passed
    assert "safety factor 1.14" in by_name["line pull at bare drum vs load"].detail
    # ...but by the fourth layer the grown radius stalls the winch.
    full = by_name["line pull at full drum vs load"]
    assert full.status is CheckStatus.FAIL
    assert "safety factor 0.83" in full.detail
    assert narrow.status is CheckStatus.FAIL
    # Spreading the same rope wider (two layers) buys the lever arm back.
    wide = namespace["screen_wide_drum"]()
    wide_by_name = {e.name: e for e in wide.entries}
    assert "safety factor 1.02" in wide_by_name["line pull at full drum vs load"].detail
    assert wide.status is CheckStatus.PASS


def test_winch_tackle_friction_example_friction_governs():
    namespace = runpy.run_path(str(_EXAMPLES / "winch_tackle_friction.py"))
    plain = namespace["screen_plain_bushing_tackle"]()
    by_name = {e.name: e for e in plain.entries}
    # The frictionless W/n estimate clears the winch rating...
    assert by_name["frictionless lead line vs winch rating"].passed
    assert "safety factor 1.20" in by_name["frictionless lead line vs winch rating"].detail
    # ...but on plain bushings the real lead line overloads it.
    actual = by_name["actual lead line vs winch rating"]
    assert actual.status is CheckStatus.FAIL
    assert "safety factor 0.97" in actual.detail
    assert plain.status is CheckStatus.FAIL
    # Better sheaves — not a bigger winch — recover the margin.
    rolling = namespace["screen_rolling_bearing_tackle"]()
    rolling_by_name = {e.name: e for e in rolling.entries}
    assert "safety factor 1.12" in rolling_by_name["actual lead line vs winch rating"].detail
    assert rolling.status is CheckStatus.PASS


def test_hoist_sheave_bending_example_sheave_governs():
    namespace = runpy.run_path(str(_EXAMPLES / "hoist_sheave_bending.py"))
    compact = namespace["screen_hoist"]()
    by_name = {e.name: e for e in compact.entries}
    # The straight pull is generous...
    assert by_name["static rope tension vs breaking strength"].passed
    assert "safety factor 8.83" in by_name["static rope tension vs breaking strength"].detail
    # ...but the small sheave's equivalent bending load collapses the margin...
    bending = by_name["tension plus sheave bending vs breaking strength"]
    assert bending.status is CheckStatus.FAIL
    assert "safety factor 3.28" in bending.detail
    # ...and over-presses the groove.
    pressure = by_name["sheave bearing pressure vs allowable"]
    assert pressure.status is CheckStatus.FAIL
    assert "safety factor 0.88" in pressure.detail
    assert compact.status is CheckStatus.FAIL
    # A bigger sheave — not a bigger rope — recovers both checks.
    generous = namespace["screen_generous_sheave"]()
    generous_by_name = {e.name: e for e in generous.entries}
    recovered = generous_by_name["tension plus sheave bending vs breaking strength"]
    assert "safety factor 5.18" in recovered.detail
    assert "safety factor 2.11" in generous_by_name["sheave bearing pressure vs allowable"].detail
    assert generous.status is CheckStatus.PASS


def test_hydraulic_rod_buckling_capstone_rod_governs():
    namespace = runpy.run_path(str(_EXAMPLES / "hydraulic_rod_buckling.py"))
    slender = namespace["screen_cylinder"]()
    by_name = {e.name: e for e in slender.entries}
    # The cylinder makes plenty of force...
    assert by_name["extend force vs load"].passed
    assert "safety factor 1.25" in by_name["extend force vs load"].detail
    # ...but the slender rod buckles as a column at full extension.
    assert by_name["rod column buckling at full stroke"].status is CheckStatus.FAIL
    assert "safety factor 0.83" in by_name["rod column buckling at full stroke"].detail
    assert slender.status is CheckStatus.FAIL
    # A stouter rod carries the same thrust standing up.
    stout = namespace["screen_stouter_rod"]()
    stout_by_name = {e.name: e for e in stout.entries}
    assert stout_by_name["rod column buckling at full stroke"].passed
    assert "safety factor 1.41" in stout_by_name["rod column buckling at full stroke"].detail
    assert stout.status is CheckStatus.PASS


def test_hydraulic_meter_out_intensification_example_rod_ratio_governs():
    namespace = runpy.run_path(str(_EXAMPLES / "hydraulic_meter_out_intensification.py"))
    fat = namespace["screen_rodside"]()
    # The fat rod intensifies the rod side past the hose rating.
    assert fat.status is CheckStatus.FAIL
    assert "safety factor 0.82" in fat.entries[0].detail
    # A thinner rod lowers the area ratio and the intensified pressure.
    thin = namespace["screen_thinner_rod"]()
    assert thin.entries[0].passed
    assert "safety factor 1.12" in thin.entries[0].detail
    assert thin.status is CheckStatus.PASS


def test_cylinder_regeneration_circuit_example_trades_force_for_speed():
    namespace = runpy.run_path(str(_EXAMPLES / "cylinder_regeneration_circuit.py"))
    m = namespace["extend_modes"]()
    # Regen is faster than a normal extend but weaker.
    assert m["regen_speed_mms"] > m["normal_speed_mms"]
    assert m["regen_force_kn"] < m["normal_force_kn"]
    assert m["regen_force_kn"] == pytest.approx(77, abs=1)
    assert m["regen_speed_mms"] == pytest.approx(173, abs=1)
    # The 120 kN forming load exceeds the regen force but not the full extend force.
    assert m["regen_force_kn"] < 120 < m["normal_force_kn"]


def test_gear_pair_layout_example_undercut_governs_the_pinion():
    namespace = runpy.run_path(str(_EXAMPLES / "gear_pair_layout.py"))
    coarse = namespace["screen_pinion"]()
    # The 12-tooth coarse-module pinion fits the centre but undercuts.
    assert coarse.status is CheckStatus.FAIL
    assert "safety factor 0.67" in coarse.entries[0].detail
    # More, finer teeth on the same centre and ratio clear the undercut minimum.
    fine = namespace["screen_finer_pinion"]()
    assert fine.entries[0].passed
    assert "safety factor 1.11" in fine.entries[0].detail
    assert fine.status is CheckStatus.PASS


def test_key_vs_spline_example_spline_shares_what_a_key_concentrates():
    namespace = runpy.run_path(str(_EXAMPLES / "key_vs_spline.py"))
    card = namespace["screen_connection"]()
    by_name = {e.name: e for e in card.entries}
    # A single key needs ~114 mm of hub for 2000 N*m, more than the 60 mm available.
    assert by_name["single key: hub length vs length needed"].status is CheckStatus.FAIL
    assert "safety factor 0.53" in by_name["single key: hub length vs length needed"].detail
    # A 10-tooth spline carries the same torque in the same length.
    assert by_name["spline: capacity vs torque"].passed
    assert "safety factor 1.06" in by_name["spline: capacity vs torque"].detail


def test_multi_plate_clutch_example_stacks_surfaces_not_spring_force():
    namespace = runpy.run_path(str(_EXAMPLES / "multi_plate_clutch_stack.py"))
    single = namespace["screen_single_plate_clutch"]()
    # A single plate (2 surfaces) at 2 kN carries 72 N*m against a 135 N*m duty.
    assert single.status is CheckStatus.FAIL
    assert "safety factor 0.53" in single.entries[0].detail
    # Six surfaces from the same spring carry 216 N*m.
    stacked = namespace["screen_stacked_clutch"]()
    assert stacked.status is CheckStatus.PASS
    assert "safety factor 1.60" in stacked.entries[0].detail


def test_flange_coupling_example_adds_bolts_not_diameter():
    namespace = runpy.run_path(str(_EXAMPLES / "flange_coupling_bolt_pattern.py"))
    four = namespace["screen_four_bolt_coupling"]()
    # Four bolts see 5,969 N each against a 5 kN allowable.
    assert four.status is CheckStatus.FAIL
    assert "safety factor 0.84" in four.entries[0].detail
    # The inverse says five bolts minimum; the even pattern is six.
    assert namespace["minimum_bolt_count"]() == 5
    six = namespace["screen_six_bolt_coupling"]()
    assert six.status is CheckStatus.PASS
    assert "safety factor 1.26" in six.entries[0].detail


def test_hoist_hook_example_static_pass_fails_on_impact():
    namespace = runpy.run_path(str(_EXAMPLES / "hoist_hook_sudden_load.py"))
    gentle = namespace["screen_gentle_placement"]()
    # Placed gently the beam holds a 2.5 factor on yield.
    assert gentle.status is CheckStatus.PASS
    assert "safety factor 2.50" in gentle.entries[0].detail
    # Suddenly applied (K = 2) the lifting-duty 1.5 margin is gone.
    sudden = namespace["screen_sudden_application"]()
    assert sudden.status is CheckStatus.FAIL
    assert "safety factor 1.25" in sudden.entries[0].detail
    # A 20 mm snatch amplifies 4.3x, past yield itself.
    snatch = namespace["screen_snatch_drop"]()
    assert snatch.status is CheckStatus.FAIL
    assert "safety factor 0.58" in snatch.entries[0].detail


def test_journal_bearing_example_finish_decides_the_regime():
    namespace = runpy.run_path(str(_EXAMPLES / "journal_bearing_film_regime.py"))
    ground = namespace["screen_ground_journal"]()
    # Ground on honed: lambda = 8.9 against the full-film floor of 3.
    assert ground.status is CheckStatus.PASS
    assert "safety factor 2.98" in ground.entries[0].detail
    # Turned finishes drop the same 8 um film to lambda = 1.8: mixed lubrication.
    turned = namespace["screen_turned_finishes"]()
    assert turned.status is CheckStatus.FAIL
    assert "safety factor 0.59" in turned.entries[0].detail


def test_riveted_lap_joint_example_second_row_balances_the_modes():
    namespace = runpy.run_path(str(_EXAMPLES / "riveted_lap_joint_efficiency.py"))
    single = namespace["screen_single_riveted_seam"]()
    # Single-riveted: shear governs at 39% efficiency, short of the 50% floor.
    assert single.status is CheckStatus.FAIL
    assert "shearing" in single.entries[0].name
    # Double-riveted: the governing mode flips to tearing and efficiency hits 60%.
    double = namespace["screen_double_riveted_seam"]()
    assert double.status is CheckStatus.PASS
    assert "tearing" in double.entries[0].name
    assert "safety factor 1.20" in double.entries[0].detail


def test_scotch_yoke_example_speed_squared_overloads_the_pin():
    namespace = runpy.run_path(str(_EXAMPLES / "scotch_yoke_pump_speed.py"))
    design = namespace["screen_design_speed"]()
    # At 300 rpm the pin loafs at a 5.6 factor.
    assert design.status is CheckStatus.PASS
    assert "safety factor 5.63" in design.entries[0].detail
    # Tripling the speed multiplies the inertia force nine-fold: 320 N on a 200 N pin.
    uprated = namespace["screen_uprated_speed"]()
    assert uprated.status is CheckStatus.FAIL
    assert "safety factor 0.63" in uprated.entries[0].detail


def test_lifting_lug_calc_report_example_shows_its_work():
    namespace = runpy.run_path(str(_EXAMPLES / "lifting_lug_calc_report.py"))
    report = namespace["build_report"]()
    text = report.to_text()
    # The bearing check shows formula, substitution with units, and result.
    assert "σ_p = P / (d · t)" in text
    assert "σ_p = 50.0 kN / (25.00 mm · 12.00 mm)" in text
    assert "σ_p = 166.7 MPa" in text
    assert "ASME BTH-1 §3-3" in text
    # All three checks declare their own work, so nothing falls back.
    assert report.derivation_coverage() == (3, 3)
    assert "derivation not rendered" not in text
    # Pin bearing at 1.50 against a required 2.00 is what has to change, and the
    # report says how: the lug thickness that lands the required margin.
    assert report.governing().name == "padeye pin bearing"
    assert report.status is CheckStatus.FAIL
    assert "repair: increase thickness to 16 mm" in text


def test_rc_floor_beam_example_capacity_and_steel_inverse():
    namespace = runpy.run_path(str(_EXAMPLES / "rc_floor_beam.py"))
    # 1500 mm2 of steel develops ~321 kN.m.
    assert namespace["beam_capacity"]().to("kN*m").magnitude == pytest.approx(320.6, abs=0.5)
    # A 400 kN.m demand needs ~1915 mm2 (about a fourth bar).
    assert namespace["steel_for_demand"]().to("mm**2").magnitude == pytest.approx(1915, abs=5)


def test_cold_formed_stud_flange_example_slender_element_is_reduced():
    namespace = runpy.run_path(str(_EXAMPLES / "cold_formed_stud_flange.py"))
    from anvilate.units import Quantity

    # The 1.5 mm flange is slender: only ~59 mm of the 100 mm is effective.
    thin = namespace["effective_flange_width"](Quantity.parse("1.5 mm"))
    assert thin.to("mm").magnitude == pytest.approx(58.6, abs=0.3)
    # The 3.5 mm flange is compact: fully effective.
    thick = namespace["effective_flange_width"](Quantity.parse("3.5 mm"))
    assert thick.to("mm").magnitude == pytest.approx(100.0, rel=1e-9)


def test_floor_joist_wet_service_example_factor_chain_flips_the_verdict():
    namespace = runpy.run_path(str(_EXAMPLES / "floor_joist_wet_service.py"))
    # The identical joist passes dry and fails wet — the wet-service factor C_M is
    # the whole difference.
    dry = namespace["screen_dry"]()
    assert dry.status is CheckStatus.PASS
    assert dry.entries[0].safety_factor == pytest.approx(1.14, abs=0.01)
    wet = namespace["screen_wet"]()
    assert wet.status is CheckStatus.FAIL
    assert wet.entries[0].safety_factor == pytest.approx(0.97, abs=0.01)


def test_process_pipe_schedule_example_rates_the_available_wall():
    namespace = runpy.run_path(str(_EXAMPLES / "process_pipe_schedule.py"))
    # Schedule 10 looks like plenty at 3.05 mm, but mill tolerance and corrosion leave
    # only ~1.2 mm to hold pressure — below the 5 MPa service.
    sch10 = namespace["screen_schedule_10"]()
    assert sch10.status is CheckStatus.FAIL
    assert sch10.entries[0].safety_factor == pytest.approx(0.57, abs=0.02)
    # Schedule 40 keeps ~3.8 mm available and clears the service with margin.
    sch40 = namespace["screen_schedule_40"]()
    assert sch40.status is CheckStatus.PASS
    assert sch40.entries[0].safety_factor == pytest.approx(1.87, abs=0.03)


def test_power_device_heatsink_example_convection_governs():
    namespace = runpy.run_path(str(_EXAMPLES / "power_device_heatsink.py"))
    # Still air: the sink-to-air convection dominates and the junction cooks.
    still = namespace["screen_natural_convection"]()
    assert still.status is CheckStatus.FAIL
    assert still.entries[0].safety_factor == pytest.approx(0.59, abs=0.02)
    # A fan drops the sink resistance five-fold and the junction sits inside its limit.
    fan = namespace["screen_forced_convection"]()
    assert fan.status is CheckStatus.PASS
    assert fan.entries[0].safety_factor == pytest.approx(1.91, abs=0.03)


def test_welded_bracket_fatigue_example_detail_category_decides_life():
    namespace = runpy.run_path(str(_EXAMPLES / "welded_bracket_fatigue.py"))
    # Identical spectrum, two weld details: the harsh category-56 detail is spent
    # 2.5 times over (fails)...
    harsh = namespace["screen_harsh_detail"]()
    assert harsh.status is CheckStatus.FAIL
    assert harsh.entries[0].safety_factor == pytest.approx(0.394, abs=0.01)
    # ...while the flow-aligned category-90 detail survives the same loads.
    good = namespace["screen_good_detail"]()
    assert good.status is CheckStatus.PASS
    assert good.entries[0].safety_factor == pytest.approx(3.02, abs=0.02)


def test_spec_load_combination_check_example_drives_loads_from_the_spec():
    namespace = runpy.run_path(str(_EXAMPLES / "spec_load_combination_check.py"))
    # The spec aggregates its classified cases: dead sums to 18 kN, and the wind
    # uplift keeps its sign.
    loads = namespace["deck_spec"]().combination_loads()
    from anvilate.loads import LoadNature

    assert loads[LoadNature.DEAD] == pytest.approx(18_000.0)
    assert loads[LoadNature.WIND] == pytest.approx(-30_000.0)

    card = namespace["screen_deck"]()
    by_name = {e.name: e for e in card.entries}
    # Strength is governed by a gravity combination; the anchorage by the uplift.
    assert "LRFD 2" in by_name["deck strength"].detail
    assert "LRFD 5" in by_name["edge anchorage uplift"].detail
    assert card.governing().name == "deck strength"


def test_braced_frame_column_seismic_example_tension_reversal_governs():
    namespace = runpy.run_path(str(_EXAMPLES / "braced_frame_column_seismic.py"))
    card = namespace["screen_column"]()
    by_name = {e.name: e for e in card.entries}
    # The column is comfortable in compression...
    compression = by_name["column axial compression"]
    assert compression.status is CheckStatus.PASS
    assert compression.safety_factor == pytest.approx(600.0 / 348.0, rel=1e-6)
    # ...but the seismic reversal puts the base connection into a net tension that
    # governs and fails — a demand the gravity cases never produce.
    tension = by_name["base connection tension (seismic reversal)"]
    assert tension.status is CheckStatus.FAIL
    assert tension.safety_factor == pytest.approx(220.0 / 192.0, rel=1e-6)
    assert "LRFD 7 (-E)" in tension.detail
    assert card.governing().name == "base connection tension (seismic reversal)"


def test_canopy_beam_load_combinations_example_uplift_is_hidden():
    namespace = runpy.run_path(str(_EXAMPLES / "canopy_beam_load_combinations.py"))
    down_combo, down = namespace["gravity_envelope"]()
    up_combo, up = namespace["uplift_governing"]()
    # The governing gravity combination is not the reflexive 1.2D + 1.6L: roof live
    # as the principal (combination 3) governs at 47.2 kN.
    assert down_combo.name == "LRFD 3 (+L) [Lr]"
    assert down == pytest.approx(47.2)
    # And a net uplift the gravity cases never show governs the hold-down.
    assert up_combo.name == "LRFD 5"
    assert up == pytest.approx(-26.5)


def test_bracket_load_scatter_fragility_example_flags_a_nominal_pass():
    namespace = runpy.run_path(str(_EXAMPLES / "bracket_load_scatter_fragility.py"))
    # On single best-guess numbers the bracket clears the required 1.5.
    assert namespace["nominal_safety_factor"]() == pytest.approx(1.70, abs=0.01)

    result = namespace["screen_bracket"]()
    # But the load scatter drags the safety factor below the required 1.5 in about
    # one run in five — a shortfall a single-point check never reports.
    assert result.mean > 1.5  # nominally comfortable
    assert result.shortfall_probability == pytest.approx(0.21, abs=0.03)
    assert result.is_fragile(threshold=0.05)
    # The load is the input to pin down first, by a wide margin.
    assert result.dominant().name == "load"
    assert result.dominant().variance_share > 0.8


def test_base_plate_revision_governing_shift_moves_the_governing_check():
    namespace = runpy.run_path(str(_EXAMPLES / "base_plate_revision_governing_shift.py"))
    before = namespace["thin_plate"]()
    after = namespace["thick_plate"]()

    # The thin plate fails on bending, which governs; the concrete bearing is idle.
    assert before.status is CheckStatus.FAIL
    assert before.governing().name == "col_base plate bending"

    # Thickening relaxes bending (∝ 1/t²) far past the fixed concrete bearing, which
    # now governs — the plate passes.
    assert after.status is CheckStatus.PASS
    assert after.governing().name == "col_base concrete bearing"

    # The revision moved the governing check, and governing_shift names both.
    shift = namespace["governing_shift"]()
    assert shift is not None
    assert shift.previous == "col_base plate bending"
    assert shift.current == "col_base concrete bearing"


def test_sheave_repair_from_inverse_example_repairs_in_one_solve():
    namespace = runpy.run_path(str(_EXAMPLES / "sheave_repair_from_inverse.py"))
    before = namespace["screen_on_compact_sheave"]()
    by_name = {e.name: e for e in before.entries}

    # The rope is over-heavy for pure tension: a passing OVER_MARGIN warning, not
    # a failure and not a silent green.
    static = by_name["static rope tension vs breaking strength"]
    assert static.status is CheckStatus.OVER_MARGIN
    assert static.passed and static.over_margin

    # The small sheave fails the wire bending, and the failing entry carries the
    # sheave diameter that would fix it — a solved hint, not a bare direction.
    bending = by_name["wire bending over the sheave"]
    assert bending.status is CheckStatus.FAIL
    assert "safety factor 0.74" in bending.detail
    hint = bending.repair_hint
    assert hint is not None
    assert hint.parameter == "sheave_diameter"
    assert hint.direction.value == "increase"
    assert hint.corrective_value == pytest.approx(509.3, abs=0.1)
    assert before.status is CheckStatus.FAIL

    # Applying that one value — no iteration — lands the bending check at exactly
    # the required margin, and the assembly is no longer blocked.
    after = namespace["repaired_scorecard"]()
    repaired_bending = {e.name: e for e in after.entries}["wire bending over the sheave"]
    assert repaired_bending.status is CheckStatus.PASS
    assert "safety factor 1.50" in repaired_bending.detail
    assert after.status is CheckStatus.OVER_MARGIN  # only the over-heavy rope remains
    assert after.passed
