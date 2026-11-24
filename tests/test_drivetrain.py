"""Drive trains: one input, every shaft's speed and torque derived, the graph held consistent.

The golden case is the power-transmission case study of Shigley's Mechanical Engineering
Design, 10th ed. (Budynas and Nisbett, 2015), Chapter 18, sections 18-2 and 18-4: 20 hp at
1,750 rpm into a compound reverted reducer with 16/72 and 16/72 teeth at 6 teeth/in, lossless,
an output band of 82 to 88 rpm. Its printed results: w3 = 388.9 rpm, w5 = 86.42 rpm;
T2 = 60.0, T3 = 270 and T5 = 1,215 lbf-ft; Wt23 = 540.0 lbf and Wt45 = 2,431 lbf.
"""

from __future__ import annotations

from math import pi

import pytest

from anvilate.drivetrain import (
    GEAR_DATA_COLUMNS,
    NOT_DECLARED,
    SHEET_WIDTH,
    DriveInput,
    DriveShaft,
    DriveTrain,
    Gear,
    GearDataRow,
    Mesh,
    RequiredOutput,
    ShaftStation,
    ShaftStiffness,
    ShaftSupport,
    bearing_demands,
    check_typed_torque,
    derive_flow,
    gear_data,
    screen_output_speed,
    screen_shaft_curve,
    solve_shaft_curve,
    solve_shaft_statics,
)
from anvilate.refusal import RefusalError
from anvilate.scorecard import CheckStatus, LimitSense
from anvilate.units import Quantity

_SHIGLEY = "Shigley's Mechanical Engineering Design, 10th ed., Ch. 18: lossless, as the case study"


def _q(text: str) -> Quantity:
    return Quantity.parse(text)


def _gear(item: str, teeth: int) -> Gear:
    return Gear(item=item, teeth=teeth, pitch_diameter=_q(f"{teeth / 6} in"))  # P = 6 teeth/in


def _reducer(**overrides) -> DriveTrain:
    fields = {
        "shafts": (DriveShaft(name="input", carries=("gear 2",)),
                   DriveShaft(name="countershaft", carries=("gear 3", "gear 4")),
                   DriveShaft(name="output", carries=("gear 5",))),
        "gears": (_gear("gear 2", 16), _gear("gear 3", 72), _gear("gear 4", 16),
                  _gear("gear 5", 72)),
        "meshes": (Mesh(name="2-3", driver="gear 2", driven="gear 3", efficiency=1.0,
                        source=_SHIGLEY),
                   Mesh(name="4-5", driver="gear 4", driven="gear 5", efficiency=1.0,
                        source=_SHIGLEY)),
        "input": DriveInput(shaft="input", speed=_q("1750 rpm"), power=_q("20 hp")),
        "output": RequiredOutput(shaft="output", speed_low=_q("82 rpm"),
                                 speed_high=_q("88 rpm"),
                                 source="Shigley Ch. 18 specification: 82 to 88 rev/min"),
        "reverted": True,
    }  # fmt: skip
    fields.update(overrides)
    return DriveTrain(**fields)


def test_the_shigley_reducer_reproduces_its_published_speeds_torques_and_loads():
    flow = derive_flow(_reducer())
    rpm = {s.shaft: s.speed.to("rpm").magnitude for s in flow.shafts}
    torque = {s.shaft: s.torque.to("lbf*ft").magnitude for s in flow.shafts}
    assert rpm["countershaft"] == pytest.approx(388.9, abs=0.05)
    assert rpm["output"] == pytest.approx(86.42, abs=0.005)
    assert torque == pytest.approx({"input": 60.0, "countershaft": 270, "output": 1215}, rel=1e-3)
    loads = {m.mesh: m.tangential_load.to("lbf").magnitude for m in flow.meshes}
    assert loads == pytest.approx({"2-3": 540.0, "4-5": 2431}, rel=1e-3)
    entry = screen_output_speed(_reducer(), flow)
    assert entry.status is CheckStatus.PASS and "86.42 rpm, inside" in entry.detail


def test_mesh_efficiency_reduces_the_power_passed_on():
    lossy = _reducer(meshes=tuple(m.model_copy(update={"efficiency": 0.98})
                                  for m in _reducer().meshes))  # fmt: skip
    out = derive_flow(lossy).shaft("output")
    assert out.power.to("W").magnitude == pytest.approx(_q("20 hp").to("W").magnitude * 0.98**2)
    assert out.speed.to("rpm").magnitude == pytest.approx(86.42, abs=0.005)


def test_an_input_given_as_torque_gives_the_same_flow():
    by_torque = _reducer(input=DriveInput(shaft="input", speed=_q("1750 rpm"),
                                          torque=_q("60.0241 lbf*ft")))  # fmt: skip
    out = derive_flow(by_torque).shaft("output")
    assert out.torque.to("lbf*ft").magnitude == pytest.approx(1215, rel=1e-3)


def test_an_output_outside_its_band_fails_naming_both():
    narrow = _reducer(output=RequiredOutput(shaft="output", speed_low=_q("90 rpm"),
                                            speed_high=_q("95 rpm"), source="spec"))  # fmt: skip
    entry = screen_output_speed(narrow, derive_flow(narrow))
    assert entry.status is CheckStatus.FAIL and "outside the required 90 to 95 rpm" in entry.detail


def test_a_gear_on_no_shaft_is_refused_naming_the_gear_and_the_mesh():
    loose = _reducer(shafts=(DriveShaft(name="input", carries=("gear 2",)),
                             DriveShaft(name="countershaft", carries=("gear 3", "gear 4")),
                             DriveShaft(name="output", carries=("coupling",))))  # fmt: skip
    with pytest.raises(RefusalError, match="mesh 4-5 names gear gear 5, which no shaft carries"):
        derive_flow(loose)


def test_a_reverted_layout_that_does_not_close_is_refused_naming_both_stages():
    """The spec's case: a first stage at 175 mm and a second at 180 mm."""
    distances = ("175 mm", "180 mm")
    meshes = tuple(m.model_copy(update={"center_distance": _q(d)})
                   for m, d in zip(_reducer().meshes, distances, strict=True))  # fmt: skip
    gears = tuple(g.model_copy(update={"pitch_diameter": None}) for g in _reducer().gears)
    with pytest.raises(RefusalError, match="stage 2-3 has 175 mm while 4-5 has 180 mm"):
        derive_flow(_reducer(meshes=meshes, gears=gears))


def test_a_center_distance_that_is_not_the_sum_of_the_pitch_radii_is_refused():
    off = tuple(m.model_copy(update={"center_distance": _q("200 mm")}) for m in _reducer().meshes)
    with pytest.raises(RefusalError, match="declares a center distance of 200 mm"):
        derive_flow(_reducer(meshes=off))


def test_a_shaft_two_paths_turn_at_different_speeds_is_refused():
    loop = Mesh(name="2-5", driver="gear 2", driven="gear 5", efficiency=1.0, source="x")
    with pytest.raises(RefusalError, match="a shaft's speed is determined once"):
        derive_flow(_reducer(meshes=(*_reducer().meshes, loop), reverted=False))


def test_a_shaft_nothing_drives_is_refused():
    idle = _reducer(shafts=(*_reducer().shafts, DriveShaft(name="idler", carries=("pulley",))))
    with pytest.raises(RefusalError, match=r"shafts \['idler'\] are driven by nothing"):
        derive_flow(idle)


def test_a_typed_torque_that_contradicts_the_flow_is_refused_naming_both_values():
    flow = derive_flow(_reducer())
    check_typed_torque(flow, "4-5", _q("270 lbf*ft"))  # the derived value is accepted
    with pytest.raises(RefusalError, match="typed with a driver torque of .* derives"):
        check_typed_torque(flow, "4-5", _q("300 lbf*ft"))


def test_an_input_with_both_or_neither_of_power_and_torque_is_refused():
    with pytest.raises(ValueError, match="one of them"):
        DriveInput(shaft="input", speed=_q("1750 rpm"))
    with pytest.raises(ValueError, match="one of them"):
        DriveInput(shaft="input", speed=_q("1750 rpm"), power=_q("1 kW"), torque=_q("5 N*m"))


def test_the_flow_renders_each_shaft():
    text = str(derive_flow(_reducer()))
    assert text.splitlines()[2].startswith("output: 86.42 rpm, 1648 N·m")


def test_no_required_output_is_not_evaluated_naming_what_to_declare():
    entry = screen_output_speed(_reducer(output=None), derive_flow(_reducer(output=None)))
    assert entry.status is CheckStatus.NOT_EVALUATED
    assert [need.declaration for need in entry.needs] == ["drive_train.output"]


def test_the_docs_page_quotes_the_flow_this_library_derives():
    """docs/drive-trains.md argues from the case study's numbers; each is the flow's."""
    from pathlib import Path

    page = (Path(__file__).parents[1] / "docs" / "drive-trains.md").read_text(encoding="utf-8")
    flow = derive_flow(_reducer())
    rpm = [round(s.speed.to("rpm").magnitude, 2) for s in flow.shafts]
    assert f"{rpm[1]:.1f} and {rpm[2]:.2f} rpm" in page  # 388.9 and 86.42
    torques = [s.torque.to("lbf*ft").magnitude for s in flow.shafts]
    assert f"torques of {torques[0]:.1f}, {torques[1]:.0f} and {torques[2]:,.0f} lbf·ft" in page
    loads = [m.tangential_load.to("lbf").magnitude for m in flow.meshes]
    assert f"loads of {loads[0]:.1f} and {loads[1]:,.0f} lbf" in page


def test_a_declared_pressure_angle_splits_each_mesh_load_into_radial_and_total():
    """Drive trains 3.1: the radial load that bends the shafts, from the tangential load and
    the declared pressure angle. The case study's gears are 20-degree; 540.2 lbf tangential
    gives 540.2 x tan 20 = 196.6 lbf radial and 540.2 / cos 20 = 574.9 lbf in all."""
    meshes = tuple(m.model_copy(update={"pressure_angle": _q("20 degree")})
                   for m in _reducer().meshes)  # fmt: skip
    first = derive_flow(_reducer(meshes=meshes)).meshes[0]
    assert first.radial_load.to("lbf").magnitude == pytest.approx(196.6, abs=0.1)
    assert first.total_load.to("lbf").magnitude == pytest.approx(574.9, abs=0.1)
    assert derive_flow(_reducer()).meshes[0].radial_load is None  # no angle, no split
    with pytest.raises(ValueError, match="outside 0 to 45 degrees"):
        Mesh(name="m", driver="a", driven="b", efficiency=1.0, source="x",
             pressure_angle=_q("50 degree"))  # fmt: skip


# --- Two-bearing statics (drive trains 3.2) ---------------------------------------------


def _support(name: str, mm: float, **extra) -> ShaftSupport:
    return ShaftSupport(name=name, at=_q(f"{mm} mm"), **extra)


def _station(item: str, mm: float) -> ShaftStation:
    return ShaftStation(item=item, at=_q(f"{mm} mm"))


def _laid_out(**overrides) -> DriveTrain:
    """The case study's reducer with its gears and bearings placed along each shaft.

    These spans are this test's own, and the expected reactions below are hand-derived from
    them rather than quoted. The chapter's force analysis is in its Example 7-2, outside the
    free chapter — but its Fig. 18-2 does give the intermediate shaft's own layout, and
    `_as_the_chapter_lays_out_the_countershaft` below uses that one to hold this library
    against the reactions the chapter prints.
    """
    shafts = (
        DriveShaft(name="input", carries=("gear 2",),
                   supports=(_support("A", 0), _support("B", 200)),
                   stations=(_station("gear 2", 100),)),
        DriveShaft(name="countershaft", carries=("gear 3", "gear 4"),
                   supports=(_support("C", 0), _support("D", 300)),
                   stations=(_station("gear 3", 75), _station("gear 4", 225))),
        DriveShaft(name="output", carries=("gear 5",),
                   supports=(_support("E", 0), _support("F", 300)),
                   stations=(_station("gear 5", 150),)),
    )  # fmt: skip
    angles = ("0 degree", "180 degree")  # reverted: the second stage pulls the other way
    meshes = tuple(m.model_copy(update={"pressure_angle": _q("20 degree"),
                                        "line_of_centers": _q(a)})
                   for m, a in zip(_reducer().meshes, angles, strict=True))  # fmt: skip
    return _reducer(**{"shafts": shafts, "meshes": meshes, **overrides})


def test_one_gear_centred_between_two_bearings_splits_its_mesh_load_in_half():
    """The output shaft: gear 5 at midspan, so each bearing takes half the total mesh load
    and the bending moment at the gear is that half times the half span.

    The total load is the tangential 2,431 lbf and the radial 884.8 lbf in quadrature,
    2,587 lbf = 11,508 N; each bearing takes 5,754 N, and 5,754 N x 0.15 m = 863 N·m.
    """
    train = _laid_out()
    statics = solve_shaft_statics(train, derive_flow(train), "output")
    assert statics.determinate is True
    assert [r.support for r in statics.reactions] == ["E", "F"]
    for reaction in statics.reactions:
        assert reaction.magnitude.to("N").magnitude == pytest.approx(5754, rel=1e-3)
        assert reaction.share is None
    assert statics.peak.at_item == "gear 5"
    assert statics.peak.magnitude.to("N*m").magnitude == pytest.approx(863.1, rel=1e-3)
    ends = [m for m in statics.moments if m.at_item in ("E", "F")]
    assert [m.magnitude.to("N*m").magnitude for m in ends] == pytest.approx([0.0, 0.0], abs=1e-9)


def test_two_meshes_on_a_countershaft_are_resolved_by_their_lines_of_centers():
    """Hand-derived. Gear 3 is driven at 75 mm with its line of centres at 0 degrees: the
    tangential 540.2 lbf (2,403 N) drags it along +z and the radial 196.6 lbf (874.6 N)
    pushes it along +y. Gear 4 drives at 225 mm with the line at 180 degrees, so its
    tangential 2,431 lbf (10,813 N) pulls along -z and its radial 884.8 lbf (3,936 N)
    along +y. Taking moments about C over the 300 mm span gives D, and D and the loads give C.
    """
    train = _laid_out()
    statics = solve_shaft_statics(train, derive_flow(train), "countershaft")
    far = statics.reaction("D")
    assert far.y.to("N").magnitude == pytest.approx(-(874.6 * 0.075 + 3936 * 0.225) / 0.3, rel=2e-3)
    assert far.z.to("N").magnitude == pytest.approx(-(2403 * 0.075 - 10813 * 0.225) / 0.3, rel=2e-3)
    near = statics.reaction("C")
    assert near.y.to("N").magnitude == pytest.approx(-(874.6 + 3936) - far.y.to("N").magnitude,
                                                     rel=2e-3)  # fmt: skip
    assert near.z.to("N").magnitude == pytest.approx(-(2403 - 10813) - far.z.to("N").magnitude,
                                                     rel=2e-3)  # fmt: skip
    assert statics.peak.at_item == "gear 4"  # the heavier mesh, and the longer lever from C
    assert [m.at_item for m in statics.moments] == ["C", "gear 3", "gear 4", "D"]


def test_the_reactions_and_the_loads_close_on_every_shaft():
    """A gate on the solve itself: each shaft's two reactions and its mesh loads sum to zero,
    and so do their moments about the first bearing."""
    train = _laid_out()
    flow = derive_flow(train)
    for shaft in train.shafts:
        statics = solve_shaft_statics(train, flow, shaft.name)
        last = statics.moments[-1]
        assert last.magnitude.to("N*m").magnitude == pytest.approx(0.0, abs=1e-6), shaft.name
        # Past the last bearing nothing is left to bend the shaft, in either plane.
        assert last.in_xy.to("N*m").magnitude == pytest.approx(0.0, abs=1e-6)
        assert last.in_xz.to("N*m").magnitude == pytest.approx(0.0, abs=1e-6)


def test_a_shaft_on_more_than_two_bearings_is_named_indeterminate_not_guessed():
    shafts = tuple(
        s.model_copy(update={"supports": (*s.supports, _support("G", 150))})
        if s.name == "output" else s for s in _laid_out().shafts
    )  # fmt: skip
    train = _laid_out(shafts=shafts)
    with pytest.raises(RefusalError, match="shaft output is statically indeterminate: 3 supports"):
        solve_shaft_statics(train, derive_flow(train), "output")


def test_a_declared_split_carries_its_basis_and_derives_no_bending():
    """The remedy the refusal names: each support's share, with the source it rests on."""
    basis = "the bearing maker's three-point mounting note, table 4"
    shafts = tuple(
        s.model_copy(update={"supports": (_support("E", 0, share=0.25, source=basis),
                                          _support("G", 150, share=0.5, source=basis),
                                          _support("F", 300, share=0.25, source=basis))})
        if s.name == "output" else s for s in _laid_out().shafts
    )  # fmt: skip
    train = _laid_out(shafts=shafts)
    statics = solve_shaft_statics(train, derive_flow(train), "output")
    assert statics.determinate is False and statics.moments == ()
    assert statics.basis == (basis, basis, basis)
    middle = statics.reaction("G")
    assert middle.share == 0.5
    assert middle.magnitude.to("N").magnitude == pytest.approx(11508 * 0.5, rel=1e-3)
    assert "a declared split over 3 supports" in str(statics)


def test_a_share_without_its_source_is_refused_and_so_is_a_source_without_a_share():
    with pytest.raises(ValueError, match="declares a share of 0.5 and no source"):
        ShaftSupport(name="A", at=_q("0 mm"), share=0.5)
    with pytest.raises(ValueError, match="gives a source and no share"):
        ShaftSupport(name="A", at=_q("0 mm"), source="a note")


def test_shares_that_do_not_cover_the_load_or_cover_only_some_supports_are_refused():
    source = "a note"
    with pytest.raises(ValueError, match="support shares summing to 0.75, not 1"):
        DriveShaft(name="s", carries=("g",),
                   supports=(_support("A", 0, share=0.25, source=source),
                             _support("B", 100, share=0.25, source=source),
                             _support("C", 200, share=0.25, source=source)))  # fmt: skip
    with pytest.raises(ValueError, match="share on some of its supports and not others"):
        DriveShaft(name="s", carries=("g",),
                   supports=(_support("A", 0, share=0.5, source=source),
                             _support("B", 100)))  # fmt: skip


def test_a_split_declared_on_a_shaft_equilibrium_already_answers_is_refused():
    source = "a note"
    shafts = tuple(
        s.model_copy(update={"supports": (_support("E", 0, share=0.5, source=source),
                                          _support("F", 300, share=0.5, source=source))})
        if s.name == "output" else s for s in _laid_out().shafts
    )  # fmt: skip
    train = _laid_out(shafts=shafts)
    with pytest.raises(RefusalError, match="drop the shares and let the statics answer"):
        solve_shaft_statics(train, derive_flow(train), "output")


def test_a_shaft_on_fewer_than_two_bearings_is_refused():
    shafts = tuple(s.model_copy(update={"supports": s.supports[:1]})
                   if s.name == "output" else s for s in _laid_out().shafts)  # fmt: skip
    train = _laid_out(shafts=shafts)
    with pytest.raises(RefusalError, match="shaft output declares 1 support"):
        solve_shaft_statics(train, derive_flow(train), "output")


def test_two_bearings_at_one_position_are_refused():
    shafts = tuple(s.model_copy(update={"supports": (_support("E", 40), _support("F", 40))})
                   if s.name == "output" else s for s in _laid_out().shafts)  # fmt: skip
    train = _laid_out(shafts=shafts)
    with pytest.raises(RefusalError, match="puts both its supports at 40 mm"):
        solve_shaft_statics(train, derive_flow(train), "output")


def test_a_second_mesh_on_a_shaft_without_a_line_of_centers_is_refused():
    meshes = tuple(m.model_copy(update={"line_of_centers": None}) for m in _laid_out().meshes)
    train = _laid_out(meshes=meshes)
    solve_shaft_statics(train, derive_flow(train), "output")  # one loaded gear needs no angle
    with pytest.raises(RefusalError, match="carries 2 meshing gears, whose loads do not act"):
        solve_shaft_statics(train, derive_flow(train), "countershaft")


def test_a_gear_the_shaft_does_not_station_is_refused_naming_it():
    shafts = tuple(s.model_copy(update={"stations": ()}) if s.name == "output" else s
                   for s in _laid_out().shafts)  # fmt: skip
    train = _laid_out(shafts=shafts)
    with pytest.raises(RefusalError, match="carries gear 5 and does not station it"):
        solve_shaft_statics(train, derive_flow(train), "output")


def test_a_mesh_without_a_pressure_angle_has_no_load_to_apply():
    meshes = tuple(m.model_copy(update={"pressure_angle": None}) for m in _laid_out().meshes)
    train = _laid_out(meshes=meshes)
    with pytest.raises(RefusalError, match="mesh 4-5 has no tangential and radial load"):
        solve_shaft_statics(train, derive_flow(train), "output")


def test_a_station_the_shaft_does_not_carry_is_refused():
    with pytest.raises(ValueError, match=r"stations \['gear 9'\], which it does not carry"):
        DriveShaft(name="s", carries=("gear 5",), stations=(_station("gear 9", 10),))


def test_a_support_or_station_declared_twice_is_refused():
    with pytest.raises(ValueError, match=r"declares supports \['A'\] twice"):
        DriveShaft(name="s", carries=("g",), supports=(_support("A", 0), _support("A", 100)))
    with pytest.raises(ValueError, match=r"declares stations \['g'\] twice"):
        DriveShaft(name="s", carries=("g",), stations=(_station("g", 0), _station("g", 100)))


def test_an_unplaceable_position_or_angle_is_refused():
    with pytest.raises(ValueError, match=r"support A at is a \[length\] quantity"):
        ShaftSupport(name="A", at=_q("5 kg"))
    # A non-finite position is refused by the document's finite rule, on the field, which
    # every model a product document declares opts into.
    with pytest.raises(ValueError, match="at is nan, which is not a number a document can state"):
        ShaftSupport(name="A", at=Quantity(magnitude=float("nan"), unit="mm"))
    with pytest.raises(ValueError, match="line_of_centers .* outside -360 to 360 degrees"):
        Mesh(name="m", driver="a", driven="b", efficiency=1.0, source="x",
             line_of_centers=_q("400 degree"))  # fmt: skip


def test_an_unknown_shaft_or_support_names_what_the_train_has():
    train = _laid_out()
    flow = derive_flow(train)
    with pytest.raises(RefusalError, match="no shaft is named 'layshaft'"):
        solve_shaft_statics(train, flow, "layshaft")
    with pytest.raises(RefusalError, match="no support named 'Z'"):
        solve_shaft_statics(train, flow, "output").reaction("Z")
    with pytest.raises(RefusalError, match="flow must be the DriveFlow"):
        solve_shaft_statics(train, "not a flow", "output")


def test_the_statics_renders_its_reactions_and_its_peak_moment():
    train = _laid_out()
    lines = str(solve_shaft_statics(train, derive_flow(train), "output")).splitlines()
    assert lines[0] == "output: two-bearing statics"
    assert lines[1] == "  E at 0 mm: 5754 N (+1968, -5407)"
    assert lines[-1].startswith("  peak gear 5 at 150 mm: 863.1 N·m bending")


def test_the_docs_page_quotes_the_statics_this_library_solves():
    """docs/drive-trains.md prints a reaction and a peak moment; both are the solve's."""
    from pathlib import Path

    page = (Path(__file__).parents[1] / "docs" / "drive-trains.md").read_text(encoding="utf-8")
    train = _laid_out()
    statics = solve_shaft_statics(train, derive_flow(train), "output")
    assert f"{statics.reaction('E').magnitude.to('N').magnitude:,.0f} N" in page
    assert f"# {statics.peak}" in page

    # And the curve's own line, which the page prints beside the call that returns it.
    stiff = _stiff()
    assert f"# {solve_shaft_curve(stiff, derive_flow(stiff), 'output').point('gear 5')}" in page


def test_a_flow_derived_from_another_train_is_refused_rather_than_read():
    """An ordinary mistake: the right shaft name, the wrong flow. The mesh loads it carries
    are another machine's, so the reactions would be another machine's too."""
    train = _laid_out()
    other = _laid_out(meshes=tuple(m.model_copy(update={"name": f"{m.name} b"})
                                   for m in _laid_out().meshes))  # fmt: skip
    with pytest.raises(RefusalError, match=r"does not carry meshes \['2-3', '4-5'\]"):
        solve_shaft_statics(train, derive_flow(other), "output")


# --- The derived loads reach the existing screens (drive trains 3.3) ---------------------


def _bearing_record(rating_kn: float):
    from anvilate.components import ComponentRecord

    def q(v: float, unit: str) -> dict:
        return {"magnitude": v, "unit": unit}

    return ComponentRecord.model_validate({
        "manufacturer": "Acme", "part_number": "6210", "description": "deep groove ball bearing",
        "family": "ball_bearing",
        "suppliers": [{"supplier": "Distributor", "number": "D-1"}],
        "envelope": [q(90, "mm"), q(90, "mm"), q(20, "mm")], "envelope_source": "datasheet p.1",
        "mass": q(0.46, "kg"), "mass_source": "datasheet p.1",
        "ratings": [{"name": "dynamic_load_rating", "value": q(rating_kn, "kN"),
                     "source": "datasheet p.2"}],
    })  # fmt: skip


def test_the_derived_reaction_and_speed_are_what_the_bearing_screen_reads():
    """Drive trains 3.3. The bearing screen already reads an equivalent load, a speed and a
    required life. Two of the three are not free, and this is where they come from.
    """
    from anvilate.components import _rating_entries

    train = _laid_out(output=RequiredOutput(
        shaft="output", speed_low=_q("82 rpm"), speed_high=_q("88 rpm"),
        source="Shigley Ch. 18 specification: 82 to 88 rev/min", life=_q("12000 hour"),
    ))  # fmt: skip
    flow = derive_flow(train)
    demands = bearing_demands(train, flow, "output")
    assert sorted(demands) == ["E", "F"]
    asked = {d.name: d for d in demands["E"]}
    statics = solve_shaft_statics(train, flow, "output")
    assert asked["equivalent_load"].value == statics.reaction("E").magnitude
    assert asked["speed"].value == flow.shaft("output").speed
    assert asked["required_life"].value.to("hour").magnitude == 12000
    assert "the radial reaction at E" in asked["equivalent_load"].source
    assert "turns at 86.42 rpm" in asked["speed"].source

    # 5,754 N at 86.42 rpm against a 50 kN rating: (50/5.754)^3 = 656.2 Mrev, and
    # 656.2e6 / (60 x 86.42) = 126,540 h, past the 12,000 h the train requires.
    (entry,) = _rating_entries(_bearing_record(50.0), demands["E"])
    assert entry.name == "bearing rating life" and entry.status is CheckStatus.PASS
    assert entry.derivation.result.value == pytest.approx(126_540, rel=1e-3)
    assert entry.life.value.to("hour").magnitude == pytest.approx(126_540, rel=1e-3)
    # The detail line names the rating and the required life; the load's own source rides on
    # the derivation, where the reader finds what P was and where it came from.
    load_symbol = next(s for s in entry.derivation.inputs if s.symbol == "P")
    assert "the radial reaction at E" in load_symbol.description


def test_a_bearing_too_small_for_the_derived_load_fails_against_the_required_life():
    from anvilate.components import _rating_entries

    train = _laid_out(output=RequiredOutput(
        shaft="output", speed_low=_q("82 rpm"), speed_high=_q("88 rpm"),
        source="Shigley Ch. 18 specification", life=_q("12000 hour"),
    ))  # fmt: skip
    demands = bearing_demands(train, derive_flow(train), "output")
    (entry,) = _rating_entries(_bearing_record(14.0), demands["E"])
    assert entry.status is CheckStatus.FAIL
    assert entry.derivation.result.value < 12000


def test_a_train_declaring_no_life_leaves_the_bearing_entry_not_evaluated_naming_it():
    """The honest answer: nothing in the train knows how long the product must run."""
    from anvilate.components import _rating_entries

    train = _laid_out()  # its RequiredOutput declares a speed band and no life
    assert train.output.life is None
    demands = bearing_demands(train, derive_flow(train), "output")
    assert [d.name for d in demands["E"]] == ["equivalent_load", "speed"]
    (entry,) = _rating_entries(_bearing_record(50.0), demands["E"])
    assert entry.status is CheckStatus.NOT_EVALUATED
    assert "no required life" in entry.detail
    assert [need.declaration for need in entry.needs] == ["definitions[].demands[required_life]"]


def test_a_declared_split_sources_each_bearing_demand_to_the_split_not_to_statics():
    basis = "the bearing maker's three-point mounting note, table 4"
    shafts = tuple(
        s.model_copy(update={"supports": (_support("E", 0, share=0.25, source=basis),
                                          _support("G", 150, share=0.5, source=basis),
                                          _support("F", 300, share=0.25, source=basis))})
        if s.name == "output" else s for s in _laid_out().shafts
    )  # fmt: skip
    train = _laid_out(shafts=shafts)
    demands = bearing_demands(train, derive_flow(train), "output")
    assert sorted(demands) == ["E", "F", "G"]
    load = {d.name: d for d in demands["G"]}["equivalent_load"]
    assert load.value.to("N").magnitude == pytest.approx(11508 * 0.5, rel=1e-3)
    assert "a declared support split" in load.source


def test_the_shaft_and_key_screens_run_on_the_derived_torque_and_bending_moment():
    """The other two screens the spec names. Neither needs a new wrapper: the torque is the
    flow's and the bending moment is the statics', and both are Quantities the existing
    analysis functions already take."""
    from anvilate.analysis.keys import key_shear_stress
    from anvilate.analysis.section import bending_stress

    train = _laid_out()
    flow = derive_flow(train)
    statics = solve_shaft_statics(train, flow, "output")
    torque = flow.shaft("output").torque
    modulus = Quantity(magnitude=pi * 50**3 / 32, unit="mm**3")  # a solid 50 mm shaft
    bending = bending_stress(moment=statics.peak.magnitude, section_modulus=modulus)
    # 863.1 N·m over pi x 0.05^3 / 32 = 1.2272e-5 m^3.
    assert bending.to("MPa").magnitude == pytest.approx(863.1 / 1.2272e-5 / 1e6, rel=2e-3)
    shear = key_shear_stress(torque=torque, shaft_diameter=_q("50 mm"),
                             key_width=_q("14 mm"), key_length=_q("70 mm"))  # fmt: skip
    # F = 2T/d = 2 x 1,648 / 0.05 = 65,900 N over 14 x 70 mm = 9.8e-4 m^2.
    assert shear.to("MPa").magnitude == pytest.approx(
        2 * torque.to("N*m").magnitude / 0.05 / 9.8e-4 / 1e6, rel=1e-3
    )


# --- Deflection and slope at the gears and the bearings (drive trains 3.4) ---------------


_STEEL = ShaftStiffness(diameter=Quantity.parse("50 mm"),
                        elastic_modulus=Quantity.parse("207 GPa"),
                        source="AISI 1045 steel, Shigley Table A-5: E = 30 Mpsi")  # fmt: skip


def _stiff(**overrides) -> DriveTrain:
    """The laid-out reducer with one prismatic 50 mm steel shaft diameter throughout."""
    shafts = tuple(s.model_copy(update={"stiffness": _STEEL}) for s in _laid_out().shafts)
    return _laid_out(**{"shafts": shafts, **overrides})


def test_a_central_gear_bends_its_shaft_by_the_closed_form_the_library_already_has():
    """The output shaft is the textbook case, so the curve must land on the textbook answer.

    One load at midspan of a 300 mm span: the total mesh load on gear 5 is 11,508 N, the
    second moment of a 50 mm shaft is pi x 50^4 / 64 = 306,796 mm^4, and E = 207 GPa, so
    the deflection is F·L^3/(48·E·I) and the support slope is F·L^2/(16·E·I).
    """
    train = _stiff()
    curve = solve_shaft_curve(train, derive_flow(train), "output")
    load, span, ei = 11508.0, 300.0, 207_000 * pi * 50**4 / 64
    assert curve.point("gear 5").deflection.to("mm").magnitude == pytest.approx(
        load * span**3 / (48 * ei), rel=1e-3
    )
    assert curve.point("E").slope.to("radian").magnitude == pytest.approx(
        load * span**2 / (16 * ei), rel=1e-3
    )
    # A simply-supported beam does not move at its supports, and does not tilt under a
    # central load: the two conditions that say the curve was evaluated and not guessed.
    assert curve.point("E").deflection.to("mm").magnitude == pytest.approx(0.0, abs=1e-12)
    assert curve.point("F").deflection.to("mm").magnitude == pytest.approx(0.0, abs=1e-12)
    assert curve.point("gear 5").slope.to("degree").magnitude == pytest.approx(0.0, abs=1e-12)
    assert curve.worst.at_item == "gear 5"
    assert curve.second_moment.to("mm**4").magnitude == pytest.approx(306_796, rel=1e-4)


def test_two_gears_bend_a_countershaft_at_both_of_them():
    """Superposition, in two planes. Neither support moves, both tilt, and the heavier
    second-stage gear is the point that has moved furthest."""
    train = _stiff()
    curve = solve_shaft_curve(train, derive_flow(train), "countershaft")
    assert [p.at_item for p in curve.points] == ["C", "gear 3", "gear 4", "D"]
    for support in ("C", "D"):
        assert curve.point(support).deflection.to("mm").magnitude == pytest.approx(0.0, abs=1e-12)
        assert curve.point(support).slope.to("degree").magnitude > 0.0
    assert curve.worst.at_item == "gear 4"
    assert (
        curve.point("gear 4").deflection.to("mm").magnitude
        > curve.point("gear 3").deflection.to("mm").magnitude
    )


def test_a_declared_limit_passes_or_fails_the_point_it_is_declared_on():
    source = "the bearing maker's permissible-misalignment table, page 84"
    shafts = tuple(
        s.model_copy(update={
            "supports": (_support("E", 0, slope_limit=_q("0.0573 degree"), limit_source=source),
                         _support("F", 300)),
            "stations": (ShaftStation(item="gear 5", at=_q("150 mm"),
                                      deflection_limit=_q("0.13 mm"), limit_source=source),),
        }) if s.name == "output" else s for s in _stiff().shafts
    )  # fmt: skip
    train = _stiff(shafts=shafts)
    entries = screen_shaft_curve(train, derive_flow(train), "output")
    verdicts = {e.name: e.status for e in entries}
    # 0.0584 degrees of slope against a 0.0573 limit, and 0.1019 mm against a 0.13 mm one.
    assert verdicts == {"output E slope": CheckStatus.FAIL,
                        "output gear 5 deflection": CheckStatus.PASS}  # fmt: skip
    slope = next(e for e in entries if e.name == "output E slope")
    assert slope.reference == source
    assert slope.comparison.sense is LimitSense.AT_MOST
    assert (
        slope.comparison.measured
        == solve_shaft_curve(train, derive_flow(train), "output").point("E").slope
    )


def test_a_shaft_where_nothing_declares_a_limit_is_not_evaluated_naming_the_declaration():
    """A shaft screened on nothing looks exactly like a shaft that passed."""
    train = _stiff()
    (entry,) = screen_shaft_curve(train, derive_flow(train), "output")
    assert entry.status is CheckStatus.NOT_EVALUATED
    assert "gear 5 at 150 mm" in entry.detail and "no point on it declares a limit" in entry.detail
    assert [need.declaration for need in entry.needs] == [
        "drive_train.shafts[].supports[].slope_limit",
        "drive_train.shafts[].stations[].deflection_limit",
    ]


def test_a_shaft_with_no_declared_stiffness_is_refused_rather_than_given_one():
    train = _laid_out()  # no stiffness on any shaft
    with pytest.raises(RefusalError, match="shaft output declares no stiffness"):
        solve_shaft_curve(train, derive_flow(train), "output")


def test_a_declared_split_has_no_shape_either():
    basis = "the bearing maker's three-point mounting note, table 4"
    shafts = tuple(
        s.model_copy(update={"supports": (_support("E", 0, share=0.25, source=basis),
                                          _support("G", 150, share=0.5, source=basis),
                                          _support("F", 300, share=0.25, source=basis))})
        if s.name == "output" else s for s in _stiff().shafts
    )  # fmt: skip
    train = _stiff(shafts=shafts)
    with pytest.raises(RefusalError, match="neither does its shape"):
        solve_shaft_curve(train, derive_flow(train), "output")


def test_an_overhung_gear_is_refused_rather_than_solved_as_a_simple_beam():
    shafts = tuple(
        s.model_copy(update={
            "supports": (_support("E", 0), _support("F", 100)),
            "stations": (_station("gear 5", 150),),
        }) if s.name == "output" else s for s in _stiff().shafts
    )  # fmt: skip
    train = _stiff(shafts=shafts)
    with pytest.raises(RefusalError, match="an overhung shaft bends as an overhanging beam"):
        solve_shaft_curve(train, derive_flow(train), "output")


def test_a_limit_without_its_source_is_refused_and_so_is_a_source_without_a_limit():
    with pytest.raises(ValueError, match="declares a bending limit and no limit_source"):
        ShaftSupport(name="E", at=_q("0 mm"), slope_limit=_q("0.05 degree"))
    with pytest.raises(ValueError, match="gives a limit_source and no slope_limit"):
        ShaftStation(item="gear 5", at=_q("150 mm"), limit_source="a note")
    with pytest.raises(ValueError, match="shaft diameter must be positive"):
        ShaftStiffness(diameter=_q("0 mm"), elastic_modulus=_q("207 GPa"), source="a note")


def test_the_curve_renders_its_span_and_every_point_and_names_an_unknown_one():
    train = _stiff()
    curve = solve_shaft_curve(train, derive_flow(train), "output")
    lines = str(curve).splitlines()
    assert lines[0] == "output over 300 mm"
    assert lines[2] == "  gear 5 at 150 mm: 0.1019 mm, 0°"
    with pytest.raises(RefusalError, match="no point named 'Z'"):
        curve.point("Z")


# --- the gear data block ------------------------------------------------------------------
# A drawing view dimensions a gear's bore and face width and nothing about its teeth, so the
# block is how a gear is made or bought. Its rule is that it states what the declaration
# holds and what the train derives, and names the rest as not declared rather than filling it
# in: a basic rack or an accuracy class nobody declared is a number a gear shop would cut to.


def test_the_block_states_one_row_per_gear_per_mesh_with_the_module_and_ratio_derived():
    data = gear_data(_reducer())
    assert [(r.item, r.mesh, r.role, r.mates_with) for r in data.rows] == [
        ("gear 2", "2-3", "driver", "gear 3"),
        ("gear 3", "2-3", "driven", "gear 2"),
        ("gear 4", "4-5", "driver", "gear 5"),
        ("gear 5", "4-5", "driven", "gear 4"),
    ]
    first = data.rows[0]
    # P = 6 teeth/in, so the module is 1/6 in = 4.2333 mm, and 16 teeth give 2.6667 in.
    assert first.module.to("mm").magnitude == pytest.approx(25.4 / 6, rel=1e-12)
    assert first.pitch_diameter.to("in").magnitude == pytest.approx(16 / 6, rel=1e-12)
    assert first.ratio() == "16:72" and data.rows[1].ratio() == "16:72"
    # No mesh declares a centre distance, so every row says the sum of the pitch radii is
    # where its own came from: (2.6667 + 12)/2 in = 7.3333 in = 186.267 mm.
    assert first.center_distance_basis == "from the pitch radii"
    assert first.center_distance.to("mm").magnitude == pytest.approx(186.2666, rel=1e-5)


def test_a_declared_centre_distance_is_the_rows_and_says_so():
    meshes = tuple(m.model_copy(update={"center_distance": _q("7.3333 in")})
                   for m in _reducer().meshes)  # fmt: skip
    row = gear_data(_reducer(meshes=meshes)).rows[0]
    assert row.center_distance_basis == "declared"
    assert row.center_distance.to("in").magnitude == pytest.approx(7.3333, rel=1e-9)


def test_every_declared_field_reaches_the_block_and_an_undeclared_one_says_so():
    gears = (Gear(item="gear 2", teeth=16, pitch_diameter=_q("2.6667 in"), profile_shift=0.3,
                  basic_rack="ISO 53:1998 profile A", accuracy_class="ISO 1328-1:2013 class 7",
                  span_measurement=_q("23.14 mm"), over_pins_measurement=_q("29.08 mm")),
             _gear("gear 3", 72), _gear("gear 4", 16), _gear("gear 5", 72))  # fmt: skip
    rows = gear_data(_reducer(gears=gears)).rows
    cells = dict(zip(GEAR_DATA_COLUMNS, rows[0].cells(), strict=True))
    assert cells["profile shift"] == "0.3" and cells["basic rack"] == "ISO 53:1998 profile A"
    assert cells["accuracy class"] == "ISO 1328-1:2013 class 7"
    assert (cells["span measurement"], cells["over-pins measurement"]) == ("23.14 mm", "29.08 mm")
    # The reducer's meshes declare no pressure angle and gear 3 declares none of the rest.
    assert cells["pressure angle"] == NOT_DECLARED
    bare = dict(zip(GEAR_DATA_COLUMNS, rows[1].cells(), strict=True))
    assert bare["profile shift"] == bare["basic rack"] == NOT_DECLARED
    assert bare["accuracy class"] == bare["span measurement"] == NOT_DECLARED
    assert bare["over-pins measurement"] == NOT_DECLARED


def test_the_sheet_block_and_the_csv_say_the_same_thing():
    """Two renderings of one block, and only the CSV's columns are named in one place.

    The sheet prints field and value down the page because a row of the CSV is over two
    hundred characters wide; that is a second renderer, and a second renderer is where a
    field added to one and not the other goes unnoticed. So the gate is every value of
    every row: a cell the sheet drops is a cell this finds.
    """
    gears = (Gear(item="gear 2", teeth=16, pitch_diameter=_q("2.6667 in"), profile_shift=0.3,
                  basic_rack="ISO 53:1998 profile A", accuracy_class="ISO 1328-1:2013 class 7",
                  span_measurement=_q("23.14 mm"), over_pins_measurement=_q("29.08 mm")),
             _gear("gear 3", 72), _gear("gear 4", 16), _gear("gear 5", 72))  # fmt: skip
    data = gear_data(_reducer(gears=gears))
    sheet = "\n".join(data.lines())
    assert data.lines()[0] == "gear data"
    for row in data.rows:
        for column, cell in zip(GEAR_DATA_COLUMNS, row.cells(), strict=True):
            assert cell in sheet, f"the sheet block drops the {column} {cell!r}"
    # Every column name too, so a field the gear does not declare is still named: the sheet
    # gathers those onto one "not declared" line instead of repeating the phrase per field.
    # All but the five the heading line already states and the basis, which the sheet
    # carries inside the centre distance it qualifies rather than as a field of its own.
    stated_in_the_heading = ("item", "shaft", "mesh", "role", "mating teeth")
    for column in GEAR_DATA_COLUMNS:
        if column not in (*stated_in_the_heading, "center distance basis"):
            assert column in sheet, f"the sheet block never names the {column!r} field"
    # Gear 2 declares every field of its own; the reducer's meshes declare no pressure
    # angle, so that is the one thing missing from its row. Gear 3 declares none of them.
    assert "not declared: pressure angle\n" in sheet
    assert ("not declared: pressure angle, profile shift, basic rack, accuracy class\n"
            "      span measurement, over-pins measurement") in sheet  # fmt: skip


def test_no_line_of_the_sheet_block_is_drawn_off_the_page():
    """The renderer does not wrap. A line past the paper's width is simply drawn past it.

    So the gate is the sheet's own arithmetic, not the string's length: `release` draws at
    1,100 px and `projection._text_width` says how wide a line of that sheet's small text
    is. The first block written here overflowed by nine characters and every string-length
    assertion over it passed.
    """
    from anvilate.projection import _plain, _text_width

    width_px = 1100  # what `release._assembly_drawings` asks for
    small = max(11.0, min(18.0, width_px / 50)) * 0.72
    # And the constant itself against that sheet, so raising it fails here rather than on
    # the paper: 89 characters reach the edge, and a block line is indented three under its
    # gear.
    assert SHEET_WIDTH + 3 <= (width_px - 12) / _text_width("x", small)
    cited = "ISO 1328-1:2013 class 7 to a tolerance class nobody would write out this long"
    gears = (Gear(item="gear 2", teeth=16, pitch_diameter=_q("2.6667 in"), profile_shift=0.3,
                  basic_rack=cited, accuracy_class=cited, span_measurement=_q("23.14 mm"),
                  over_pins_measurement=_q("29.08 mm")),
             _gear("gear 3", 72), _gear("gear 4", 16), _gear("gear 5", 72))  # fmt: skip
    for line in gear_data(_reducer(gears=gears)).lines():
        drawn = 12 + _text_width(_plain(line).upper(), small)
        assert drawn <= width_px, f"{line!r} is drawn {drawn - width_px:.0f} px off the page"


def test_the_csv_header_is_the_blocks_columns_and_a_negative_shift_is_not_a_formula():
    gears = (Gear(item="gear 2", teeth=16, pitch_diameter=_q("2.6667 in"), profile_shift=-0.3),
             _gear("gear 3", 72), _gear("gear 4", 16), _gear("gear 5", 72))  # fmt: skip
    text = gear_data(_reducer(gears=gears)).to_csv()
    header, first = text.splitlines()[:2]
    assert header == ",".join(GEAR_DATA_COLUMNS)
    # "-0.3" is a number a spreadsheet would read as the start of a formula.
    assert "'-0.3" in first and first.startswith("gear 2,input,16,")


def test_an_idler_gets_a_row_per_mesh_with_its_own_mating_data_in_each():
    """A gear in two meshes has one set of teeth and two mating gears, and the row is per
    mesh so neither row has to be read against the other to be understood."""
    train = DriveTrain(
        shafts=(DriveShaft(name="input", carries=("gear 2",)),
                DriveShaft(name="idler", carries=("gear 3",)),
                DriveShaft(name="output", carries=("gear 4",))),
        gears=(_gear("gear 2", 16), _gear("gear 3", 24), _gear("gear 4", 48)),
        meshes=(Mesh(name="2-3", driver="gear 2", driven="gear 3", efficiency=1.0,
                     source=_SHIGLEY),
                Mesh(name="3-4", driver="gear 3", driven="gear 4", efficiency=1.0,
                     source=_SHIGLEY)),
        input=DriveInput(shaft="input", speed=_q("1750 rpm"), power=_q("20 hp")),
    )  # fmt: skip
    rows = [r for r in gear_data(train).rows if r.item == "gear 3"]
    assert [(r.mesh, r.role, r.mates_with, r.ratio()) for r in rows] == [
        ("2-3", "driven", "gear 2", "16:24"),
        ("3-4", "driver", "gear 4", "24:48"),
    ]
    assert {r.teeth for r in rows} == {24} and {r.shaft for r in rows} == {"idler"}


def test_a_module_that_does_not_follow_from_the_diameter_and_the_teeth_is_refused():
    """The module is carried because a gear is ordered by it, and carried means writable."""
    fields = {"item": "gear 2", "shaft": "input", "teeth": 16, "mesh": "2-3",
              "role": "driver", "mates_with": "gear 3", "mating_teeth": 72,
              "pitch_diameter": _q("2.6667 in"), "center_distance_basis": NOT_DECLARED}  # fmt: skip
    # A refusal raised inside a model validator reaches the caller as pydantic's own
    # ValidationError, which is a ValueError; the message is the refusal's.
    with pytest.raises(ValueError, match="which is a module of 4.23"):
        GearDataRow(**fields, module=_q("5 mm"))
    with pytest.raises(ValueError, match="gives a pitch diameter and no module"):
        GearDataRow(**fields)
    with pytest.raises(ValueError, match="gives a module and no pitch diameter"):
        GearDataRow(**{**fields, "pitch_diameter": None}, module=_q("5 mm"))


def test_a_mesh_whose_gears_are_cut_to_different_modules_is_refused():
    """And the centre-distance check cannot see it: the sum of the two pitch radii closes
    whatever the two modules are, so this is the only thing standing between a pair that
    cannot run and a flow derived from it."""
    gears = (_gear("gear 2", 16), Gear(item="gear 3", teeth=48, pitch_diameter=_q("12 in")),
             _gear("gear 4", 16), _gear("gear 5", 72))  # fmt: skip
    closes = tuple(m.model_copy(update={"center_distance": _q("7.3333 in")})
                   if m.name == "2-3" else m for m in _reducer().meshes)  # fmt: skip
    with pytest.raises(RefusalError, match="joins gear 2 at a module of 4.233 mm to gear 3 "
                                           "at 6.35 mm"):  # fmt: skip
        derive_flow(_reducer(gears=gears, meshes=closes, reverted=False))


def test_a_gear_two_meshes_cut_to_different_pressure_angles_is_refused():
    angled = (_reducer().meshes[0].model_copy(update={"pressure_angle": _q("20 degree")}),
              Mesh(name="3-4", driver="gear 3", driven="gear 4", efficiency=1.0,
                   source=_SHIGLEY, pressure_angle=_q("25 degree")))  # fmt: skip
    shafts = (DriveShaft(name="input", carries=("gear 2",)),
              DriveShaft(name="countershaft", carries=("gear 3",)),
              DriveShaft(name="output", carries=("gear 4",)))  # fmt: skip
    with pytest.raises(RefusalError, match="gear 3 runs in mesh 2-3 at a pressure angle of 20 "
                                           "degrees and in mesh 3-4 at 25 degrees"):  # fmt: skip
        derive_flow(_reducer(shafts=shafts, meshes=angled, reverted=False,
                             gears=(_gear("gear 2", 16), _gear("gear 3", 72),
                                    _gear("gear 4", 16))))  # fmt: skip


def test_a_declared_gear_in_no_mesh_is_refused_naming_it():
    gears = (*_reducer().gears, _gear("spare", 20))
    holds = DriveShaft(name="output", carries=("gear 5", "spare"))
    shafts = (*_reducer().shafts[:2], holds)
    with pytest.raises(RefusalError, match=r"gears \['spare'\] are declared and mesh with "
                                           "nothing"):  # fmt: skip
        derive_flow(_reducer(gears=gears, shafts=shafts))


def test_the_block_refuses_what_is_not_a_drive_train():
    with pytest.raises(RefusalError, match="train must be a DriveTrain"):
        gear_data("a reducer")


def test_a_helix_angle_is_not_a_field_a_gear_can_declare():
    """A declared helix angle would make an axial load `solve_shaft_statics` does not carry,
    and a helical gear screened as a spur one is a wrong answer rather than a missing one."""
    with pytest.raises(ValueError, match="helix_angle"):
        Gear(item="gear 2", teeth=16, helix_angle=_q("20 degree"))


def test_the_docs_page_quotes_the_refusals_the_block_rests_on():
    """docs/drive-trains.md argues the block from three refusals; each is the library's.

    A number quoted only in prose has no gate, and these three are the whole case for why
    the block can state one module and one pressure angle per gear.
    """
    from pathlib import Path

    page = (Path(__file__).parents[1] / "docs" / "drive-trains.md").read_text(encoding="utf-8")
    gears = (_gear("gear 2", 16), Gear(item="gear 3", teeth=48, pitch_diameter=_q("12 in")),
             _gear("gear 4", 16), _gear("gear 5", 72))  # fmt: skip
    with pytest.raises(RefusalError) as modules:
        derive_flow(_reducer(gears=gears, reverted=False))
    assert "4.233 mm and 6.35 mm" in page
    for figure in ("4.233 mm", "6.35 mm"):
        assert figure in str(modules.value)
    angled = (_reducer().meshes[0].model_copy(update={"pressure_angle": _q("20 degree")}),
              Mesh(name="3-4", driver="gear 3", driven="gear 4", efficiency=1.0,
                   source=_SHIGLEY, pressure_angle=_q("25 degree")))  # fmt: skip
    shafts = (DriveShaft(name="input", carries=("gear 2",)),
              DriveShaft(name="countershaft", carries=("gear 3",)),
              DriveShaft(name="output", carries=("gear 4",)))  # fmt: skip
    with pytest.raises(RefusalError) as angles:
        derive_flow(_reducer(shafts=shafts, meshes=angled, reverted=False,
                             gears=(_gear("gear 2", 16), _gear("gear 3", 72),
                                    _gear("gear 4", 16))))  # fmt: skip
    assert "20° and 25°" in page
    assert "of 20 degrees" in str(angles.value) and "at 25 degrees" in str(angles.value)
    # The page's claim that a gear no mesh names is refused, and the block's own columns.
    assert "a gear no mesh names" in page
    for column in GEAR_DATA_COLUMNS:
        assert column in page, f"the page does not say what the {column!r} column is"


def test_a_pitch_diameter_rounded_to_three_figures_is_not_a_module_mismatch():
    """The case study prints 2.67 in for 16/6, which is 0.125% off the module it came from.

    The module gate has to be loose enough not to refuse that and tight enough to catch a
    real mismatch, and the two are three orders of magnitude apart: the closest two stock
    modules are 8% apart.
    """
    rounded = (Gear(item="gear 2", teeth=16, pitch_diameter=_q("2.67 in")),
               _gear("gear 3", 72), _gear("gear 4", 16), _gear("gear 5", 72))  # fmt: skip
    flow = derive_flow(_reducer(gears=rounded, reverted=False))
    assert flow.shaft("output").speed.to("rpm").magnitude == pytest.approx(86.42, rel=1e-3)
    # And the smallest real step is still caught: module 3 against 3.25 on the same teeth.
    stepped = (Gear(item="gear 2", teeth=16, pitch_diameter=_q("48 mm")),
               Gear(item="gear 3", teeth=72, pitch_diameter=_q("234 mm")),
               _gear("gear 4", 16), _gear("gear 5", 72))  # fmt: skip
    with pytest.raises(RefusalError, match="at a module of 3 mm to gear 3 at 3.25 mm"):
        derive_flow(_reducer(gears=stepped, reverted=False))


def test_a_blank_citation_is_refused_rather_than_read_as_not_declared():
    """`not declared` in a cell stands for a field that is absent, and only for that.

    The block renders a missing citation as `not declared`, which would read the same for a
    citation that is there and says nothing — so the field refuses blank at the document,
    and the cell never has to tell the two apart.
    """
    for blank in ("", "   "):
        with pytest.raises(ValueError, match="basic_rack"):
            Gear(item="gear 2", teeth=16, basic_rack=blank)
        with pytest.raises(ValueError, match="accuracy_class"):
            Gear(item="gear 2", teeth=16, accuracy_class=blank)
    with pytest.raises(ValueError, match="span_measurement must be positive"):
        Gear(item="gear 2", teeth=16, span_measurement=_q("0 mm"))


# --- The published case study, end to end (drive trains 4.4) ------------------------------
#
# Edition, read and not recalled: the chapter itself prints no edition or copyright line.
# Its page print-marks carry the book's ISBN-10, 0073398209, and McGraw-Hill's own
# information centre for that ISBN says "The tenth edition of Shigley's Mechanical
# Engineering Design..." — which is where the 10th-edition citation in this file comes from.
# https://highered.mheducation.com/sites/0073398209/information_center_view0/index.html


def _as_the_chapter_lays_out_the_countershaft(**overrides) -> DriveTrain:
    """The case study's intermediate shaft, placed off its own Fig. 18-2 (page 936).

    The figure's dimension chain along that shaft, in inches, is

        1/4, 1, 3/4, 1 1/2, 4, 2, 3/4, 1, 1/4

    which sums to the 11.5 in the text states and whose 4 in is the gear spacing it names.
    Read as segment lengths from the left end, the middle of each component sits at 0.75 in
    (bearing A), 2.75 in (gear 3, 1.5 in face), 8.50 in (gear 4, 2.0 in face) and 10.75 in
    (bearing B).
    """
    shafts = tuple(
        s.model_copy(update={
            "supports": (ShaftSupport(name="A", at=_q("0.75 in")),
                         ShaftSupport(name="B", at=_q("10.75 in"))),
            "stations": (ShaftStation(item="gear 3", at=_q("2.75 in")),
                         ShaftStation(item="gear 4", at=_q("8.50 in"))),
        }) if s.name == "countershaft" else s
        for s in _laid_out().shafts
    )  # fmt: skip
    return _laid_out(**{"shafts": shafts, **overrides})


def test_the_case_studys_countershaft_reproduces_its_published_bearing_reactions():
    """The whole chain against numbers somebody else published, on their own layout.

    Flow, mesh split, two-bearing statics and bearing demand, from one declared input to the
    two reactions Section 18-9 prints:

        RAz = 115.0 lbf   RAy = 356.7 lbf   RA = 375 lbf
        RBz = 1776.0 lbf  RBy = 725.3 lbf   RB = 1918 lbf

    Nothing about them is typed into this library: the layout is the chapter's Fig. 18-2 and
    everything else follows from 20 hp at 1,750 rpm through 16/72 and 16/72 at 6 teeth/in.

    Two tenths of a percent, and not tighter, because the chapter's own inputs are rounded:
    it prints Wt23 = 540.0 lbf for a load of 540.217, and RAz is the difference of 1,891 and
    1,776 — two numbers an order of magnitude larger — so that rounding arrives at A
    magnified about fifteen times. RB, which is not a difference of near-equals, lands within
    two parts in a hundred thousand.
    """
    train = _as_the_chapter_lays_out_the_countershaft()
    statics = solve_shaft_statics(train, derive_flow(train), "countershaft")
    assert statics.determinate
    published = {"A": (356.7, 115.0, 375.0), "B": (725.3, 1776.0, 1918.0)}
    for support, (radial_plane, tangential_plane, resultant) in published.items():
        reaction = statics.reaction(support)
        # A reaction opposes the load that raised it, so the signed components are the
        # chapter's magnitudes with the sense the library carries them in.
        assert abs(reaction.y.to("lbf").magnitude) == pytest.approx(radial_plane, rel=2e-3)
        assert abs(reaction.z.to("lbf").magnitude) == pytest.approx(tangential_plane, rel=2e-3)
        assert reaction.magnitude.to("lbf").magnitude == pytest.approx(resultant, rel=2e-3)
    # The two planes are not interchangeable, and that is the whole reason B carries five
    # times what A does: the two radial loads act the same way and ADD, while the two
    # tangential loads oppose and the bearings carry only their DIFFERENCE. Equilibrium in
    # each plane says so in the chapter's own numbers.
    loads = {m.mesh: m for m in derive_flow(train).meshes}
    tangential = [loads[n].tangential_load.to("lbf").magnitude for n in ("2-3", "4-5")]
    radial = [loads[n].radial_load.to("lbf").magnitude for n in ("2-3", "4-5")]
    carried = [statics.reaction(name) for name in ("A", "B")]
    assert sum(r.z.to("lbf").magnitude for r in carried) == pytest.approx(
        tangential[1] - tangential[0], rel=1e-9
    )
    assert sum(abs(r.y.to("lbf").magnitude) for r in carried) == pytest.approx(
        radial[0] + radial[1], rel=1e-9
    )
    # And the chapter's bending-moment remark: "The bending moment is largest at gear 4."
    assert statics.peak is not None and statics.peak.at_item == "gear 4"


def test_the_case_studys_bearings_are_asked_for_the_life_the_specification_names():
    """Section 18-9's design life, through the demands the bearing screen reads.

    The chapter writes LD = (12 000 h)(60 min/h)(389 rev/min) = 2.8e8 rev. The 389 is this
    library's 388.9 rounded, and the demands carry the hours and the speed separately, so
    the product is formed here and held to the revolutions the chapter prints.
    """
    life = _laid_out().output.model_copy(update={"life": _q("12000 hour")})
    train = _as_the_chapter_lays_out_the_countershaft(output=life)
    flow = derive_flow(train)
    demands = bearing_demands(train, flow, "countershaft")
    assert set(demands) == {"A", "B"}
    carried = {d.name: d.value for d in demands["B"]}
    assert carried["required_life"].to("hour").magnitude == pytest.approx(12_000)
    assert carried["speed"].to("rpm").magnitude == pytest.approx(388.89, rel=1e-4)
    # In revolutions, which means reading the speed as rpm and not as "1/minute": a
    # rotational speed converted to an inverse time comes back in RADIANS per minute, 2*pi
    # times the number wanted, and the chapter's 2.8e8 would land at 1.76e9.
    revolutions = (carried["required_life"].to("hour").magnitude * 60
                   * carried["speed"].to("rpm").magnitude)  # fmt: skip
    assert revolutions == pytest.approx(2.8e8, rel=5e-3)
    # The load the bearing is screened on is B's reaction, not a number typed beside it.
    assert carried["equivalent_load"].to("lbf").magnitude == pytest.approx(1918.0, rel=2e-3)
    assert "two-bearing statics" in next(d for d in demands["B"]
                                         if d.name == "equivalent_load").source  # fmt: skip


def test_the_docs_page_quotes_the_reactions_this_library_derives():
    """docs/drive-trains.md prints both columns of the case-study table side by side.

    The left column is the chapter's and the test above holds the library to it. The right
    column is this library's own, to four figures — a number quoted only in prose, which is
    exactly the kind that goes stale without anything noticing.
    """
    from pathlib import Path

    page = (Path(__file__).parents[1] / "docs" / "drive-trains.md").read_text(encoding="utf-8")
    life = _laid_out().output.model_copy(update={"life": _q("12000 hour")})
    train = _as_the_chapter_lays_out_the_countershaft(output=life)
    flow = derive_flow(train)
    statics = solve_shaft_statics(train, flow, "countershaft")
    for support in ("A", "B"):
        reaction = statics.reaction(support)
        for value in (reaction.magnitude, reaction.z, reaction.y):
            printed = f"{abs(value.to('lbf').magnitude):.1f}"
            assert printed in page, f"the page does not print {support}'s {printed} lbf"
    # And the layout the page reads off Fig. 18-2, taken from the train rather than retyped.
    here = next(s for s in train.shafts if s.name == "countershaft")
    placed = [(s.name, s.at) for s in here.supports] + [(s.item, s.at) for s in here.stations]
    for name, at in placed:
        inches = at.to("in").magnitude
        assert f"{inches:g}" in page or f"{inches:.2f}" in page, f"{name} is not on the page"
    assert "2.80e8 rev" in page
    carried = {d.name: d.value for d in bearing_demands(train, flow, "countershaft")["B"]}
    revolutions = (carried["required_life"].to("hour").magnitude * 60
                   * carried["speed"].to("rpm").magnitude)  # fmt: skip
    assert f"{revolutions:.3g}".replace("+0", "") == "2.8e8"


def test_the_block_renders_itself_as_a_row_and_as_a_sheet():
    """Both `__str__`s, read against the row's own values rather than against `cells`.

    A rendering nobody has read can drop the field that tells two objects apart and stay
    green, so the assertions here go to the data the row holds, not to the method the
    rendering is built from — which would agree with itself however wrong it was.
    """
    data = gear_data(_reducer())
    row = data.rows[0]
    rendered = str(row)
    assert rendered.startswith(f"{row.item}  {row.shaft}  {row.teeth}  ")
    for value in (row.mesh, row.role, row.mates_with, str(row.mating_teeth), row.ratio()):
        assert value in rendered, f"the row's rendering drops {value!r}"
    assert f"{row.pitch_diameter.to('mm').magnitude:.4g} mm" in rendered
    assert f"{row.center_distance.to('mm').magnitude:.4g} mm" in rendered
    assert row.center_distance_basis in rendered
    # The reducer's meshes declare no pressure angle and its gears no rack or class, and
    # the row says so in each of those four places rather than leaving them blank.
    assert rendered.count(NOT_DECLARED) == len(row.unstated())

    sheet = str(data)
    assert sheet.splitlines() == list(data.lines())
    assert sheet.startswith("gear data\n")
    for each in data.rows:
        assert f"{each.item} on {each.shaft}, {each.role} in {each.mesh}" in sheet


def test_a_row_with_neither_module_nor_pitch_diameter_is_a_row():
    """The gear data block of a gear nobody has sized yet: teeth and a mesh, and no more."""
    row = GearDataRow(item="gear 2", shaft="input", teeth=16, mesh="2-3", role="driver",
                      mates_with="gear 3", mating_teeth=72,
                      center_distance_basis=NOT_DECLARED)  # fmt: skip
    cells = dict(zip(GEAR_DATA_COLUMNS, row.cells(), strict=True))
    assert cells["module"] == cells["pitch diameter"] == NOT_DECLARED
    assert cells["teeth"] == "16" and cells["ratio"] == "16:72"
    assert "module" in " ".join(row.unstated()) and "teeth 16" in row.stated()


def test_a_gear_with_no_pitch_diameter_has_no_centre_distance_to_state():
    """Both pitch radii or a declared centre distance; one gear sized is neither."""
    gears = (_gear("gear 2", 16), Gear(item="gear 3", teeth=72),
             _gear("gear 4", 16), _gear("gear 5", 72))  # fmt: skip
    row = next(r for r in gear_data(_reducer(gears=gears, reverted=False)).rows
               if r.item == "gear 3")  # fmt: skip
    assert row.center_distance is None and row.center_distance_basis == NOT_DECLARED
    assert row.module is None and row.pitch_diameter is None
    # Its partner is sized, and its row says the same thing: a centre distance is the pair's.
    partner = next(r for r in gear_data(_reducer(gears=gears, reverted=False)).rows
                   if r.item == "gear 2")  # fmt: skip
    assert partner.center_distance is None and partner.module is not None


def test_the_block_refuses_a_train_whose_mesh_names_a_gear_it_does_not_declare():
    """`gear_data` can be called without deriving the flow first, so it checks for itself.

    Both refusals below are the ones `derive_flow` would have raised; reaching them means
    reaching the block on a train nothing validated, which is a caller's mistake worth a
    message rather than a KeyError.
    """
    stray = _reducer().meshes[0].model_copy(update={"driven": "gear 9"})
    with pytest.raises(RefusalError, match="mesh 2-3 names gear 9, which is not a declared "
                                           "gear on a shaft"):  # fmt: skip
        gear_data(_reducer(meshes=(stray, _reducer().meshes[1])))
    # And a train whose gears are in none of its meshes has no block at all to write.
    apart = tuple(m.model_copy(update={"driver": f"x{i}", "driven": f"y{i}"})
                  for i, m in enumerate(_reducer().meshes))  # fmt: skip
    with pytest.raises(RefusalError, match="declares no gear in any mesh"):
        gear_data(_reducer(meshes=apart))
