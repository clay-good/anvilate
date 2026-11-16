"""CAE handoff: a declared frame as an input deck, read back by an open reader.

Each deck is parsed by a reader written elsewhere — pyNastran (BSD-3-Clause) for the
bulk-data deck, meshio (MIT) for the keyword deck — and has to come back with the
model it was written from: the counts, the coordinates in millimetres, the section on
the right bending axis, the pins, and in each subcase the load the frame declared.
"""

from __future__ import annotations

import json
import math

import pytest

from anvilate.cae import AnalysisDeck, frame_deck
from anvilate.frame import (
    Frame,
    FrameMaterial,
    FrameMember,
    FrameNode,
    FrameSection,
    Freedom,
    MemberLoad,
    NodeLoad,
    Support,
)
from anvilate.refusal import RefusalError
from anvilate.units import Quantity

RHO = 7850.0  # kg/m**3
AREA, IY, IZ, J = 5.0e-3, 10.0e-6, 100.0e-6, 1.0e-6  # m**2, m**4


def _q(magnitude: float, unit: str) -> Quantity:
    return Quantity(magnitude=magnitude, unit=unit)


def _portal(name: str, *, wind: float = 0.0, udl: float = 0.0, weight: bool = False,
            release: tuple[Freedom, ...] = (Freedom.RY, Freedom.RZ)) -> Frame:  # fmt: skip
    """Two 3 m columns and a 4 m beam rolled a quarter turn, pinned at its right end."""
    steel = FrameMaterial(name="S355", elastic_modulus=_q(210e9, "Pa"),
                          shear_modulus=_q(81e9, "Pa"), density=_q(RHO, "kg/m**3"),
                          source="EN 1993-1-1 §3.2.6")  # fmt: skip
    section = FrameSection(name="box", area=_q(AREA, "m**2"), second_moment_y=_q(IY, "m**4"),
                           second_moment_z=_q(IZ, "m**4"), torsion_constant=_q(J, "m**4"),
                           source="a declared section")  # fmt: skip
    nodes = (FrameNode(name="A", x=_q(0, "m"), y=_q(0, "m"), z=_q(0, "m")),
             FrameNode(name="B", x=_q(0, "m"), y=_q(0, "m"), z=_q(3, "m")),
             FrameNode(name="C", x=_q(4, "m"), y=_q(0, "m"), z=_q(3, "m")),
             FrameNode(name="D", x=_q(4, "m"), y=_q(0, "m"), z=_q(0, "m")))  # fmt: skip
    members = (FrameMember(name="left", start="A", end="B", section=section, material=steel),
               FrameMember(name="beam", start="B", end="C", section=section, material=steel,
                           roll=_q(90, "degree"), releases_end=release),
               FrameMember(name="right", start="D", end="C", section=section,
                           material=steel))  # fmt: skip
    supports = tuple(Support(node=n, restrained=tuple(Freedom)) for n in ("A", "D"))
    loads = (NodeLoad(node="B", fx=_q(wind, "kN")),) if wind else ()
    spread = (MemberLoad(member="beam", wz=_q(-udl, "kN/m")),) if udl else ()
    return Frame(name=name, nodes=nodes, members=members, supports=supports, node_loads=loads,
                 member_loads=spread, self_weight=weight)  # fmt: skip


def _cases() -> list[Frame]:
    return [_portal("wind", wind=12.0), _portal("gravity", udl=5.0, weight=True)]


def _written(deck: AnalysisDeck, tmp_path, stem: str = "portal"):
    path, side = deck.write(tmp_path / f"{stem}.{deck.format}")
    return path, json.loads(side.read_text())


# --- the bulk-data deck, read back by pyNastran ------------------------------------------


@pytest.fixture
def bdf(tmp_path):
    pytest.importorskip("pyNastran")  # CI's optional-adapters job: it pins NumPy below 2
    from pyNastran.bdf import bdf as reader

    deck = frame_deck(_cases(), format="bdf")
    path, sidecar = _written(deck, tmp_path)
    model = reader.read_bdf(str(path), xref=True, debug=None)
    return deck, model, sidecar


def test_the_bulk_data_deck_holds_the_frame_node_for_node_in_millimetres(bdf):
    deck, model, _ = bdf
    assert (deck.nodes, deck.elements) == (4, 3)
    assert sorted(model.nodes) == [1, 2, 3, 4] and sorted(model.elements) == [1, 2, 3]
    assert list(model.nodes[3].get_position()) == pytest.approx([4000.0, 0.0, 3000.0])
    assert {e.type for e in model.elements.values()} == {"CBAR"}


def test_the_section_bends_about_the_axes_the_solver_uses(bdf):
    _, model, _ = bdf
    bar = model.properties[1]
    # I1 bends the bar in the plane of its axis and orientation vector: about local z.
    assert (bar.i1, bar.i2, bar.j) == pytest.approx((IZ * 1e12, IY * 1e12, J * 1e12))
    assert bar.A == pytest.approx(AREA * 1e6)
    material = model.materials[bar.mid]
    assert (material.e, material.g) == pytest.approx((210e3, 81e3))
    assert material.rho == pytest.approx(RHO * 1e-12)
    # The beam runs along +X; unrolled its local y is Z x X = +Y and its z is +Z, and a
    # quarter-turn roll carries y to where z was. A column's reference is the global X,
    # so its local y is X x Z = -Y.
    assert list(model.elements[2].x) == pytest.approx([0.0, 0.0, 1.0], abs=1e-12)
    assert list(model.elements[1].x) == pytest.approx([0.0, -1.0, 0.0], abs=1e-12)


def test_a_released_end_is_a_pin_flag_on_that_end_only(bdf):
    _, model, _ = bdf
    beam = model.elements[2]
    assert (beam.pa, beam.pb) == (0, 56)
    assert (model.elements[1].pa, model.elements[1].pb) == (0, 0)


def test_each_frame_is_a_subcase_with_its_own_load(bdf):
    _, model, _ = bdf
    subcases = {k: v for k, v in model.case_control_deck.subcases.items() if k}
    assert [s.get_parameter("LABEL")[0] for s in subcases.values()] == ["wind", "gravity"]
    from pyNastran.bdf.mesh_utils.loads import sum_forces_moments

    forces, _moments = sum_forces_moments(model, [0.0, 0.0, 0.0], 1)
    assert list(forces) == pytest.approx([12e3, 0.0, 0.0])
    # pyNastran's sum skips a distributed PLOAD1, so the card itself is read: 5 N/mm down
    # along global Z, over the beam's whole length as a fraction of it.
    (spread,) = model.loads[102]
    assert (spread.type, spread.eid, spread.load_type, spread.scale) == (
        "PLOAD1", 2, "FZ", "FR")  # fmt: skip
    assert (spread.x1, spread.p1, spread.x2, spread.p2) == pytest.approx((0, -5.0, 1, -5.0))
    (combined,) = model.load_combinations[2]
    assert list(combined.load_ids) == [102, 202]
    gravity = [card for cards in model.loads.values() for card in cards if card.type == "GRAV"]
    assert len(gravity) == 1 and gravity[0].scale == pytest.approx(9806.65)
    assert list(gravity[0].N) == pytest.approx([0.0, 0.0, -1.0])


def test_the_deck_weighs_what_the_frame_does(bdf):
    _, model, _ = bdf
    from pyNastran.bdf.mesh_utils.mass_properties import mass_properties

    mass, _cg, _inertia = mass_properties(model)
    steel_kg = RHO * AREA * (3 + 4 + 3)
    assert mass == pytest.approx(steel_kg / 1000.0)  # tonnes


def test_both_supports_hold_all_six(bdf):
    _, model, _ = bdf
    held = {(spc.components, tuple(spc.node_ids)) for cards in model.spcs.values()
            for spc in cards}  # fmt: skip
    assert held == {("123456", (1,)), ("123456", (4,))}


# --- the keyword deck, read back by meshio ----------------------------------------------


def test_the_keyword_deck_reads_back_as_the_same_mesh(tmp_path, monkeypatch):
    meshio = pytest.importorskip("meshio")
    from meshio.abaqus import _abaqus

    # meshio 5.3 files B33 as a three-node line. It is the two-node cubic beam (B32 is the
    # three-node one), so that one entry is corrected here rather than the deck bent to it.
    monkeypatch.setitem(_abaqus.abaqus_to_meshio_type, "B33", "line")
    deck = frame_deck(_cases(), format="inp")
    path, _ = _written(deck, tmp_path)
    mesh = meshio.read(path, file_format="abaqus")
    assert mesh.points.shape == (4, 3)
    assert mesh.points[2].tolist() == pytest.approx([4000.0, 0.0, 3000.0])
    assert sum(len(block.data) for block in mesh.cells) == 3


def test_the_keyword_deck_states_its_section_release_and_steps():
    text = frame_deck(_cases(), format="inp").text
    assert "*ELEMENT, TYPE=B33, ELSET=M2" in text
    assert "*BEAM GENERAL SECTION, ELSET=M2, SECTION=GENERAL, DENSITY=7.85e-09" in text
    assert "5000.0, 10000000.0, 0.0, 100000000.0, 1000000.0" in text  # A, I11, I12, I22, J
    assert "*RELEASE\n2, S2, M1-M2" in text
    assert text.count("*STEP") == 2 and text.count("*CLOAD, OP=NEW") == 2
    assert "\n2, 1, 12000.0\n" in text  # 12 kN along X at node B
    assert "\n2, PZ, -5.0\n" in text
    assert "WEIGHED, GRAV, 9806.65, 0.0, 0.0, -1.0" in text


# --- what every deck says about itself ---------------------------------------------------


@pytest.mark.parametrize("fmt", ["inp", "bdf"])
def test_every_deck_says_it_is_unsolved_input_and_states_its_units(fmt, tmp_path):
    deck = frame_deck(_cases(), format=fmt)
    head = deck.text[:900]
    assert "UNSOLVED INPUT written by Anvilate" in head
    assert "force N, length mm, time s, mass t, stress MPa" in head
    assert frame_deck(_cases(), format=fmt).text == deck.text  # no date: same frames, same bytes
    path, sidecar = _written(deck, tmp_path)
    assert sidecar["unsolved"] is True and sidecar["cases"] == ["wind", "gravity"]
    assert sidecar["units"]["length"] == "mm" and sidecar["units"]["mass"] == "t"
    import hashlib

    assert sidecar["sha256"] == hashlib.sha256(path.read_bytes()).hexdigest() == deck.digest


def test_each_load_names_the_declaration_it_came_from():
    text = frame_deck(_cases(), format="bdf").text
    assert "$ node_loads[0].fx at node B" in text
    assert "$ member_loads on beam (0)" in text
    assert "$ self_weight: gravity along -Z" in text


# --- what is refused -----------------------------------------------------------------------


def test_cases_that_disagree_on_the_model_are_refused():
    other = _portal("braced", wind=1.0, release=(Freedom.RZ,))
    with pytest.raises(RefusalError, match="declares different members"):
        frame_deck([_portal("wind", wind=1.0), other], format="bdf")


def test_a_released_translation_is_refused_in_the_keyword_deck_and_kept_in_bulk_data():
    sliding = _portal("slide", wind=1.0, release=(Freedom.UX,))
    with pytest.raises(RefusalError, match="releases rotations only"):
        frame_deck([sliding], format="inp")
    assert "CBAR" in frame_deck([sliding], format="bdf").text


def test_a_case_with_no_load_a_value_past_the_field_and_a_case_named_twice_are_refused():
    with pytest.raises(RefusalError, match="applies no load"):
        frame_deck([_portal("empty")], format="inp")
    with pytest.raises(RefusalError, match="16-character field"):
        frame_deck([_portal("huge", wind=1e120)], format="bdf")
    with pytest.raises(RefusalError, match="named twice"):
        frame_deck([_portal("w", wind=1.0), _portal("w", wind=2.0)], format="bdf")
    with pytest.raises(RefusalError, match="format"):
        frame_deck([_portal("w", wind=1.0)], format="nas")  # type: ignore[arg-type]
    with pytest.raises(RefusalError, match="frames"):
        frame_deck(_portal("w", wind=1.0), format="bdf")  # type: ignore[arg-type]


def test_a_deck_is_written_to_a_file_of_its_own_format(tmp_path):
    deck = frame_deck([_portal("w", wind=1.0)], format="bdf")
    with pytest.raises(RefusalError, match=r"\.bdf file"):
        deck.write(tmp_path / "portal.inp")
    assert math.isclose(len(deck.digest), 64)


def test_the_page_shows_what_the_library_prints_and_writes():
    import pathlib

    page = (pathlib.Path(__file__).resolve().parents[1] / "docs" / "cae-handoff.md").read_text()
    deck = frame_deck(_cases(), format="bdf")
    shown = "bdf deck: 4 nodes, 3 elements, 2 load case(s) (wind, gravity); N-mm-s-t-MPa;"
    assert str(deck).startswith(shown) and shown in page
    assert "gravity 9806.65 mm/s²" in page and "9.806650000E+03" in deck.text
    assert "sixteen-column field" in page and "GRID*" in deck.text
