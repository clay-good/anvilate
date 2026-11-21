"""Drive trains: one input, every shaft's speed and torque derived, the graph held consistent.

The golden case is the power-transmission case study of Shigley's Mechanical Engineering
Design, 10th ed. (Budynas and Nisbett, 2015), Chapter 18, sections 18-2 and 18-4: 20 hp at
1,750 rpm into a compound reverted reducer with 16/72 and 16/72 teeth at 6 teeth/in, lossless,
an output band of 82 to 88 rpm. Its printed results: w3 = 388.9 rpm, w5 = 86.42 rpm;
T2 = 60.0, T3 = 270 and T5 = 1,215 lbf-ft; Wt23 = 540.0 lbf and Wt45 = 2,431 lbf.
"""

from __future__ import annotations

import pytest

from anvilate.drivetrain import (
    DriveInput,
    DriveShaft,
    DriveTrain,
    Gear,
    Mesh,
    RequiredOutput,
    check_typed_torque,
    derive_flow,
    screen_output_speed,
)
from anvilate.refusal import RefusalError
from anvilate.scorecard import CheckStatus
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
