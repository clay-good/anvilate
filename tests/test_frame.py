"""Frame analysis: five closed forms re-derived, and an independent solver that agrees.

A solver nobody checked is a number generator. Every case here pins a quantity against a
solution worked out away from this code — a textbook closed form, or Pynite, which is an
independently written MIT solver — and the two have to agree.

The closed forms run in every suite. The Pynite comparisons skip without it and are in
the dev extra so CI always has it; a referee that is usually absent is not a referee.
"""

from __future__ import annotations

import math
import pathlib

import pytest

from anvilate.dependency import COMPUTED_FROM
from anvilate.frame import (
    MAX_NODES,
    AnalysisBasis,
    DeflectionLimit,
    Frame,
    FrameMaterial,
    FrameMember,
    FrameNode,
    FrameSection,
    Freedom,
    MechanismFound,
    MemberLoad,
    NodeLoad,
    Support,
    screen_frame,
    screen_solution,
    solve_frame,
)
from anvilate.refusal import RefusalError
from anvilate.scorecard import CheckStatus, LimitSense, ScorecardEntry
from anvilate.units import Quantity

# One steel and one section through every case, so a difference between two cases is the
# frame and never the properties.
E_PA, G_PA = 200e9, 77e9
AREA_M2, IY_M4, IZ_M4, J_M4 = 5.0e-3, 10.0e-6, 100.0e-6, 1.0e-6

ALL_SIX = tuple(Freedom)
#: The freedoms that take a three-dimensional frame out of the plane. Restraining them at
#: every node is how a planar case is posed to a solver that only knows space frames.
OUT_OF_PLANE = (Freedom.UY, Freedom.RX, Freedom.RZ)


def _q(magnitude: float, unit: str) -> Quantity:
    return Quantity(magnitude=magnitude, unit=unit)


def _material(density: float | None = None) -> FrameMaterial:
    return FrameMaterial(
        name="steel",
        elastic_modulus=_q(E_PA, "Pa"),
        shear_modulus=_q(G_PA, "Pa"),
        density=None if density is None else _q(density, "kg/m**3"),
        source="a declared elastic steel, for a verification case",
    )


def _section() -> FrameSection:
    return FrameSection(
        name="verification section",
        area=_q(AREA_M2, "m**2"),
        second_moment_y=_q(IY_M4, "m**4"),
        second_moment_z=_q(IZ_M4, "m**4"),
        torsion_constant=_q(J_M4, "m**4"),
        source="a declared section, for a verification case",
    )


def _node(name: str, x: float, y: float, z: float) -> FrameNode:
    return FrameNode(name=name, x=_q(x, "m"), y=_q(y, "m"), z=_q(z, "m"))


def _beam_nodes(count: int, span: float) -> tuple[FrameNode, ...]:
    return tuple(_node(f"n{i}", span * i / count, 0.0, 0.0) for i in range(count + 1))


def _beam_members(count: int) -> tuple[FrameMember, ...]:
    section, material = _section(), _material()
    return tuple(
        FrameMember(
            name=f"m{i}", start=f"n{i}", end=f"n{i + 1}", section=section, material=material
        )
        for i in range(count)
    )


def _planar_supports(count: int, ends: dict[int, tuple[Freedom, ...]]) -> tuple[Support, ...]:
    supports = []
    for i in range(count + 1):
        held = set(OUT_OF_PLANE) | set(ends.get(i, ()))
        supports.append(Support(node=f"n{i}", restrained=tuple(f for f in ALL_SIX if f in held)))
    return tuple(supports)


# --- the closed forms ---------------------------------------------------------------


def test_a_simply_supported_beam_matches_pl_over_four_and_pl3_over_48ei():
    """The case every other one is read against: no redundancy, three exact numbers."""
    span, load, half = 6.0, 10.0e3, 3
    frame = Frame(
        name="simply supported",
        nodes=_beam_nodes(6, span),
        members=_beam_members(6),
        supports=_planar_supports(
            6,
            {
                0: (Freedom.UX, Freedom.UZ),
                6: (Freedom.UZ,),
            },
        ),
        node_loads=(NodeLoad(node=f"n{half}", fz=_q(-load, "N")),),
    )
    solution = solve_frame(frame)

    assert solution.displacement("n3").uz == pytest.approx(
        -load * span**3 / (48 * E_PA * IY_M4), rel=1e-9
    )
    assert solution.reaction("n0").fz == pytest.approx(load / 2, rel=1e-9)
    assert solution.reaction("n6").fz == pytest.approx(load / 2, rel=1e-9)
    # The mid-span moment is PL/4, and it is the end moment of the element meeting there.
    assert abs(solution.forces("m2").moment_y_end) == pytest.approx(load * span / 4, rel=1e-9)
    assert solution.residual == pytest.approx(0.0, abs=1e-6)
    assert solution.basis is AnalysisBasis.FIRST_ORDER


def test_a_propped_cantilever_under_a_uniform_load():
    """Fixed one end, propped the other: the first case with a redundancy in it.

    Fixed-end moment wL²/8, reactions 5wL/8 and 3wL/8, and the deflection at mid-span
    wL⁴/192EI — which is *not* the maximum deflection (that is at 0.5785L, between the
    nodes of this mesh), and reading the maximum formula at mid-span is the mistake this
    case exists to not make.
    """
    span, load, count = 6.0, 12.0e3, 6
    frame = Frame(
        name="propped cantilever",
        nodes=_beam_nodes(count, span),
        members=_beam_members(count),
        supports=_planar_supports(
            count, {0: (Freedom.UX, Freedom.UZ, Freedom.RY), count: (Freedom.UZ,)}
        ),
        member_loads=tuple(MemberLoad(member=f"m{i}", wz=_q(-load, "N/m")) for i in range(count)),
    )
    solution = solve_frame(frame)

    assert abs(solution.forces("m0").moment_y_start) == pytest.approx(load * span**2 / 8, rel=1e-9)
    assert solution.reaction("n0").fz == pytest.approx(5 * load * span / 8, rel=1e-9)
    assert solution.reaction(f"n{count}").fz == pytest.approx(3 * load * span / 8, rel=1e-9)
    assert solution.displacement("n3").uz == pytest.approx(
        -load * span**4 / (192 * E_PA * IY_M4), rel=1e-9
    )
    assert solution.residual == pytest.approx(0.0, abs=1e-6)


def test_a_fixed_fixed_beam_under_a_mid_span_point_load():
    """Two redundancies: end moments PL/8, mid-span moment PL/8, deflection PL³/192EI."""
    span, load, count = 6.0, 20.0e3, 4
    frame = Frame(
        name="fixed fixed",
        nodes=_beam_nodes(count, span),
        members=_beam_members(count),
        supports=_planar_supports(
            count,
            {
                0: (Freedom.UX, Freedom.UZ, Freedom.RY),
                count: (Freedom.UX, Freedom.UZ, Freedom.RY),
            },
        ),
        node_loads=(NodeLoad(node="n2", fz=_q(-load, "N")),),
    )
    solution = solve_frame(frame)

    assert abs(solution.forces("m0").moment_y_start) == pytest.approx(load * span / 8, rel=1e-9)
    assert solution.displacement("n2").uz == pytest.approx(
        -load * span**3 / (192 * E_PA * IY_M4), rel=1e-9
    )
    assert solution.reaction("n0").fz == pytest.approx(load / 2, rel=1e-9)
    assert abs(solution.forces("m1").moment_y_end) == pytest.approx(load * span / 8, rel=1e-9)


def test_a_three_span_continuous_beam_matches_its_support_moments():
    """Three equal spans, uniform load: the interior support moments are −0.1 wL².

    The classic three-moment result, and it is a number a reader can check in a table
    rather than one this suite produced.
    """
    span, load, per_span = 5.0, 15.0e3, 2
    count = 3 * per_span
    nodes = _beam_nodes(count, 3 * span)
    members = _beam_members(count)
    supports = _planar_supports(
        count,
        {
            0: (Freedom.UX, Freedom.UZ),
            per_span: (Freedom.UZ,),
            2 * per_span: (Freedom.UZ,),
            3 * per_span: (Freedom.UZ,),
        },
    )
    frame = Frame(
        name="three span",
        nodes=nodes,
        members=members,
        supports=supports,
        member_loads=tuple(MemberLoad(member=f"m{i}", wz=_q(-load, "N/m")) for i in range(count)),
    )
    solution = solve_frame(frame)

    expected = 0.1 * load * span**2
    for element in (f"m{per_span - 1}", f"m{2 * per_span - 1}"):
        assert abs(solution.forces(element).moment_y_end) == pytest.approx(expected, rel=1e-9)
    # And the end supports carry 0.4 wL while the interior ones carry 1.1 wL.
    assert solution.reaction("n0").fz == pytest.approx(0.4 * load * span, rel=1e-9)
    assert solution.reaction(f"n{per_span}").fz == pytest.approx(1.1 * load * span, rel=1e-9)


def test_a_cantilever_column_deflects_by_ph3_over_3ei():
    """A vertical member, which is the one orientation with no vertical to reference.

    The local axes of a column are built from the global X instead, and getting that
    fallback wrong gives a column that bends about the wrong axis — a factor of ten here,
    since Iy and Iz differ by that much on purpose.
    """
    height, load = 4.0, 15.0e3
    frame = Frame(
        name="cantilever column",
        nodes=(_node("base", 0, 0, 0), _node("tip", 0, 0, height)),
        members=(
            FrameMember(
                name="column",
                start="base",
                end="tip",
                section=_section(),
                material=_material(),
            ),
        ),
        supports=(Support(node="base", restrained=ALL_SIX),),
        node_loads=(NodeLoad(node="tip", fx=_q(load, "N")),),
    )
    solution = solve_frame(frame)

    assert solution.displacement("tip").ux == pytest.approx(
        load * height**3 / (3 * E_PA * IY_M4), rel=1e-9
    )
    assert solution.reaction("base").fx == pytest.approx(-load, rel=1e-9)
    assert abs(solution.reaction("base").my) == pytest.approx(load * height, rel=1e-9)


def test_a_bar_in_tension_stretches_by_pl_over_ea_whatever_its_direction():
    """The axial term under a general orientation: the answer cannot depend on the angle."""
    length, load = 5.0, 40.0e3
    for name, (x, y, z) in (
        ("along x", (length, 0.0, 0.0)),
        ("along y", (0.0, length, 0.0)),
        ("diagonal", (length / math.sqrt(3),) * 3),
    ):
        direction = (x / length, y / length, z / length)
        frame = Frame(
            name=name,
            nodes=(_node("a", 0, 0, 0), _node("b", x, y, z)),
            members=(
                FrameMember(
                    name="bar", start="a", end="b", section=_section(), material=_material()
                ),
            ),
            supports=(
                Support(node="a", restrained=ALL_SIX),
                # The far end is held against everything but sliding along the bar.
                Support(node="b", restrained=(Freedom.RX, Freedom.RY, Freedom.RZ)),
            ),
            node_loads=(
                NodeLoad(
                    node="b",
                    fx=_q(load * direction[0], "N"),
                    fy=_q(load * direction[1], "N"),
                    fz=_q(load * direction[2], "N"),
                ),
            ),
        )
        solution = solve_frame(frame)
        moved = solution.displacement("b")
        along = sum(
            component * direction[i] for i, component in enumerate((moved.ux, moved.uy, moved.uz))
        )
        assert along == pytest.approx(load * length / (E_PA * AREA_M2), rel=1e-6), name
        assert solution.forces("bar").axial.magnitude == pytest.approx(load, rel=1e-6), name


# --- the independent referee ---------------------------------------------------------


def _pynite(nodes, members, supports, node_loads=None, member_loads=None):
    """The same frame in Pynite, which is an independently written MIT solver.

    Skipped where it is absent, and it is in the dev extra so CI always has it: a referee
    that is usually not there is not a referee. The closed-form cases above never skip.
    """
    FEModel3D = pytest.importorskip(
        "Pynite", reason="PyNiteFEA is the referee and is in the dev extra"
    ).FEModel3D

    model = FEModel3D()
    model.add_material("steel", E_PA, G_PA, 0.3, 7850.0)
    model.add_section("section", AREA_M2, IY_M4, IZ_M4, J_M4)
    for name, (x, y, z) in nodes.items():
        model.add_node(name, x, y, z)
    for name, (start, end) in members.items():
        model.add_member(name, start, end, "steel", "section")
    for name, held in supports.items():
        model.def_support(name, *(freedom in held for freedom in ALL_SIX))
    for name, components in (node_loads or {}).items():
        for direction, value in components.items():
            model.add_node_load(name, direction, value)
    for name, components in (member_loads or {}).items():
        for direction, value in components.items():
            model.add_member_dist_load(name, direction, value, value)
    model.analyze(check_statics=False)
    return model


def test_a_portal_frame_agrees_with_pynite_on_sway_and_base_reactions():
    """A single-bay portal under a lateral load: a redundant frame with real columns.

    This is the case that catches the congruence transform the wrong way round. The
    matrix stays symmetric and positive definite with ``λ · k · λᵀ`` in place of
    ``λᵀ · k · λ``, so every beam-only case above still passes; only a frame with members
    in two directions tells the difference.
    """
    height, span, lateral = 4.0, 6.0, 25.0e3
    points = {"b1": (0, 0, 0), "t1": (0, 0, height), "t2": (span, 0, height), "b2": (span, 0, 0)}
    links = {"c1": ("b1", "t1"), "beam": ("t1", "t2"), "c2": ("b2", "t2")}
    held = {
        "b1": ALL_SIX,
        "b2": ALL_SIX,
        "t1": OUT_OF_PLANE,
        "t2": OUT_OF_PLANE,
    }
    frame = Frame(
        name="portal",
        nodes=tuple(_node(name, *point) for name, point in points.items()),
        members=tuple(
            FrameMember(name=name, start=start, end=end, section=_section(), material=_material())
            for name, (start, end) in links.items()
        ),
        supports=tuple(Support(node=name, restrained=tuple(f)) for name, f in held.items()),
        node_loads=(NodeLoad(node="t1", fx=_q(lateral, "N")),),
    )
    ours = solve_frame(frame)
    theirs = _pynite(points, links, held, node_loads={"t1": {"FX": lateral}})

    assert ours.displacement("t1").ux == pytest.approx(theirs.nodes["t1"].DX["Combo 1"], rel=1e-9)
    for name in ("b1", "b2"):
        node = theirs.nodes[name]
        reaction = ours.reaction(name)
        assert reaction.fx == pytest.approx(node.RxnFX["Combo 1"], rel=1e-9)
        assert reaction.fz == pytest.approx(node.RxnFZ["Combo 1"], rel=1e-9)
        assert reaction.my == pytest.approx(node.RxnMY["Combo 1"], rel=1e-9)
    # The two columns share the lateral load, which is the sanity check behind the match.
    assert ours.reaction("b1").fx + ours.reaction("b2").fx == pytest.approx(-lateral, rel=1e-9)


def test_a_space_frame_with_torsion_agrees_with_pynite():
    """Three members in three directions, a distributed load, and a twist in the first.

    The torsion term, the out-of-plane bending term and the distributed load's consistent
    nodal vector are all exercised at once, and every one of them has a sign that a
    beam-in-a-plane case cannot see.
    """
    points = {"a": (0, 0, 0), "b": (4, 0, 0), "c": (4, 3, 0), "d": (4, 3, -2.5)}
    links = {"ab": ("a", "b"), "bc": ("b", "c"), "cd": ("c", "d")}
    held = {"a": ALL_SIX}
    frame = Frame(
        name="space frame",
        nodes=tuple(_node(name, *point) for name, point in points.items()),
        members=tuple(
            FrameMember(name=name, start=start, end=end, section=_section(), material=_material())
            for name, (start, end) in links.items()
        ),
        supports=(Support(node="a", restrained=ALL_SIX),),
        node_loads=(
            NodeLoad(node="d", fy=_q(3.0e3, "N"), fz=_q(-8.0e3, "N"), mx=_q(2.0e3, "N*m")),
        ),
        member_loads=(MemberLoad(member="bc", wz=_q(-4.0e3, "N/m")),),
    )
    ours = solve_frame(frame)
    theirs = _pynite(
        points,
        links,
        held,
        node_loads={"d": {"FY": 3.0e3, "FZ": -8.0e3, "MX": 2.0e3}},
        member_loads={"bc": {"FZ": -4.0e3}},
    )

    moved, there = ours.displacement("d"), theirs.nodes["d"]
    for ours_value, theirs_value in (
        (moved.ux, there.DX["Combo 1"]),
        (moved.uy, there.DY["Combo 1"]),
        (moved.uz, there.DZ["Combo 1"]),
        (moved.rx, there.RX["Combo 1"]),
    ):
        assert ours_value == pytest.approx(theirs_value, rel=1e-8)
    base, support = ours.reaction("a"), theirs.nodes["a"]
    for ours_value, theirs_value in (
        (base.fy, support.RxnFY["Combo 1"]),
        (base.fz, support.RxnFZ["Combo 1"]),
        (base.mx, support.RxnMX["Combo 1"]),
        (base.my, support.RxnMY["Combo 1"]),
        (base.mz, support.RxnMZ["Combo 1"]),
    ):
        assert ours_value == pytest.approx(theirs_value, rel=1e-8)
    # A statics check the referee cannot give away: the cantilever's torsion is the
    # applied twist plus the out-of-plane load's lever about the member's own axis.
    assert ours.forces("ab").torsion_start == pytest.approx(base.mx, rel=1e-9)


def test_a_released_end_carries_no_moment_and_the_span_becomes_simply_supported():
    """A pinned end is a static condensation, not a zeroed row.

    Zeroing the released row and column — which is what a first attempt does — leaves the
    diagonal in place and gives a member stiffer than a pin, so the released end still
    carries a moment. Here a hinge at the interior support turns the second span into a
    simply supported one, which is a closed form: no end moments and wL/2 at each end.
    """
    span, load = 4.0, 9.0e3
    section, material = _section(), _material()
    frame = Frame(
        name="hinged",
        nodes=(_node("n0", 0, 0, 0), _node("n1", span, 0, 0), _node("n2", 2 * span, 0, 0)),
        members=(
            FrameMember(name="m0", start="n0", end="n1", section=section, material=material),
            FrameMember(
                name="m1",
                start="n1",
                end="n2",
                section=section,
                material=material,
                releases_start=(Freedom.RY,),
            ),
        ),
        supports=(
            Support(node="n0", restrained=ALL_SIX),
            Support(node="n1", restrained=(*OUT_OF_PLANE, Freedom.UZ)),
            Support(node="n2", restrained=(*OUT_OF_PLANE, Freedom.UZ)),
        ),
        member_loads=(MemberLoad(member="m1", wz=_q(-load, "N/m")),),
    )
    solution = solve_frame(frame)

    # The hinge carries no moment, and nothing reaches the unloaded first span through it.
    assert solution.forces("m1").moment_y_start == pytest.approx(0.0, abs=1e-6)
    assert solution.forces("m0").moment_y_start == pytest.approx(0.0, abs=1e-6)
    # So the second span is simply supported: wL/2 at each end, wL²/8 at mid-span.
    assert solution.reaction("n2").fz == pytest.approx(load * span / 2, rel=1e-9)
    assert solution.reaction("n1").fz == pytest.approx(load * span / 2, rel=1e-9)
    assert solution.displacement("n1").ry == pytest.approx(0.0, abs=1e-12)


def test_zeroing_a_released_row_would_leave_the_member_stiffer_than_a_pin():
    """The adversary of the test above: a release has to change the answer.

    Without the condensation the hinged span would drag the first one into carrying a
    moment, and the second span's reactions would not be the simply supported pair. The
    comparison is against the *same* frame with the release taken out.
    """
    span, load = 4.0, 9.0e3
    section, material = _section(), _material()

    def built(released: tuple[Freedom, ...]) -> Frame:
        return Frame(
            name="comparison",
            nodes=(
                _node("n0", 0, 0, 0),
                _node("n1", span, 0, 0),
                _node("n2", 2 * span, 0, 0),
            ),
            members=(
                FrameMember(name="m0", start="n0", end="n1", section=section, material=material),
                FrameMember(
                    name="m1",
                    start="n1",
                    end="n2",
                    section=section,
                    material=material,
                    releases_start=released,
                ),
            ),
            supports=(
                Support(node="n0", restrained=ALL_SIX),
                Support(node="n1", restrained=(*OUT_OF_PLANE, Freedom.UZ)),
                Support(node="n2", restrained=(*OUT_OF_PLANE, Freedom.UZ)),
            ),
            member_loads=(MemberLoad(member="m1", wz=_q(-load, "N/m")),),
        )

    hinged = solve_frame(built((Freedom.RY,)))
    continuous = solve_frame(built(()))
    assert continuous.forces("m1").moment_y_start != pytest.approx(0.0, abs=1.0)
    assert continuous.reaction("n2").fz != pytest.approx(hinged.reaction("n2").fz, rel=1e-3)


def test_self_weight_is_the_density_times_the_area_and_is_off_unless_asked():
    span, density, count = 6.0, 7850.0, 4
    section = _section()
    material = _material(density=density)
    nodes = _beam_nodes(count, span)
    members = tuple(
        FrameMember(
            name=f"m{i}", start=f"n{i}", end=f"n{i + 1}", section=section, material=material
        )
        for i in range(count)
    )
    supports = _planar_supports(count, {0: (Freedom.UX, Freedom.UZ), count: (Freedom.UZ,)})
    heavy = Frame(
        name="with weight",
        nodes=nodes,
        members=members,
        supports=supports,
        self_weight=True,
    )
    light = heavy.model_copy(update={"self_weight": False})

    carried = sum(r.fz for r in solve_frame(heavy).reactions)
    assert carried == pytest.approx(density * AREA_M2 * 9.80665 * span, rel=1e-9)
    assert sum(r.fz for r in solve_frame(light).reactions) == pytest.approx(0.0, abs=1e-9)


def test_asking_for_self_weight_with_no_density_anywhere_is_refused():
    """The load would be zero and would read as applied."""
    with pytest.raises(RefusalError, match="no member's material states a density"):
        Frame(
            name="weightless",
            nodes=_beam_nodes(1, 3.0),
            members=_beam_members(1),
            supports=(Support(node="n0", restrained=ALL_SIX),),
            self_weight=True,
        )


# --- what the declaration refuses ----------------------------------------------------


def test_a_member_at_a_node_the_frame_does_not_have_is_refused_by_name():
    with pytest.raises(RefusalError, match="is not a node of this frame"):
        Frame(
            name="dangling",
            nodes=(_node("a", 0, 0, 0), _node("b", 1, 0, 0)),
            members=(
                FrameMember(
                    name="ab",
                    start="a",
                    end="elsewhere",
                    section=_section(),
                    material=_material(),
                ),  # fmt: skip
            ),
        )


def test_a_support_on_no_node_is_refused():
    with pytest.raises(RefusalError, match="is on no node of this frame"):
        Frame(
            name="floating support",
            nodes=_beam_nodes(1, 3.0),
            members=_beam_members(1),
            supports=(Support(node="nowhere", restrained=ALL_SIX),),
        )


def test_an_unreferenced_node_is_refused_as_the_mechanism_it_would_make():
    with pytest.raises(RefusalError, match="no member reaches"):
        Frame(
            name="orphan",
            nodes=(*_beam_nodes(1, 3.0), _node("lonely", 9, 9, 9)),
            members=_beam_members(1),
        )


def test_a_support_that_restrains_nothing_is_refused():
    with pytest.raises(RefusalError, match="restrains nothing"):
        Support(node="a", restrained=())


def test_a_section_property_of_zero_is_a_release_and_not_a_section():
    with pytest.raises(RefusalError, match="is positive"):
        FrameSection(
            name="hollow",
            area=_q(0.0, "m**2"),
            second_moment_y=_q(IY_M4, "m**4"),
            second_moment_z=_q(IZ_M4, "m**4"),
            torsion_constant=_q(J_M4, "m**4"),
            source="declared",
        )


def test_a_section_property_in_the_wrong_dimension_is_refused():
    with pytest.raises(RefusalError, match="second_moment_y"):
        FrameSection(
            name="wrong",
            area=_q(AREA_M2, "m**2"),
            second_moment_y=_q(1.0, "m**2"),
            second_moment_z=_q(IZ_M4, "m**4"),
            torsion_constant=_q(J_M4, "m**4"),
            source="declared",
        )


def test_a_zero_modulus_is_a_mechanism_stated_as_a_material():
    with pytest.raises(RefusalError, match="no stiffness"):
        FrameMaterial(
            name="nothing",
            elastic_modulus=_q(0.0, "Pa"),
            shear_modulus=_q(G_PA, "Pa"),
            source="declared",
        )


def test_a_member_of_zero_length_is_refused():
    with pytest.raises(RefusalError, match="has no direction"):
        FrameMember(name="point", start="a", end="a", section=_section(), material=_material())


def test_a_freedom_released_at_both_ends_is_refused_before_it_is_a_mechanism():
    with pytest.raises(RefusalError, match="at both ends"):
        FrameMember(
            name="free",
            start="a",
            end="b",
            section=_section(),
            material=_material(),
            releases_start=(Freedom.RY,),
            releases_end=(Freedom.RY,),
        )


def test_a_node_declared_twice_or_supported_twice_is_refused():
    with pytest.raises(RefusalError, match="more than once"):
        Frame(
            name="doubled",
            nodes=(_node("a", 0, 0, 0), _node("a", 1, 0, 0)),
            members=_beam_members(1),
        )
    with pytest.raises(RefusalError, match="twice"):
        Frame(
            name="doubly held",
            nodes=_beam_nodes(1, 3.0),
            members=_beam_members(1),
            supports=(
                Support(node="n0", restrained=(Freedom.UX,)),
                Support(node="n0", restrained=(Freedom.UZ,)),
            ),
        )


def test_a_load_on_nothing_is_refused():
    with pytest.raises(RefusalError, match="states no component"):
        NodeLoad(node="a")
    with pytest.raises(RefusalError, match="is on no node"):
        Frame(
            name="phantom load",
            nodes=_beam_nodes(1, 3.0),
            members=_beam_members(1),
            supports=(Support(node="n0", restrained=ALL_SIX),),
            node_loads=(NodeLoad(node="elsewhere", fz=_q(-1.0, "N")),),
        )
    with pytest.raises(RefusalError, match="is on no member"):
        Frame(
            name="phantom udl",
            nodes=_beam_nodes(1, 3.0),
            members=_beam_members(1),
            supports=(Support(node="n0", restrained=ALL_SIX),),
            member_loads=(MemberLoad(member="elsewhere", wz=_q(-1.0, "N/m")),),
        )


def test_a_frame_past_the_cap_is_refused_pointing_at_the_external_doorway():
    many = MAX_NODES + 1
    with pytest.raises(RefusalError, match="anvilate.interop"):
        Frame(
            name="too big",
            nodes=_beam_nodes(many - 1, float(many)),
            members=_beam_members(many - 1),
        )


# --- the mechanism --------------------------------------------------------------------


def test_an_unrestrained_frame_is_a_mechanism_named_by_node_and_freedom():
    """Not solved around. A regularised matrix would return numbers that look like one."""
    frame = Frame(
        name="floating",
        nodes=_beam_nodes(1, 3.0),
        members=_beam_members(1),
        node_loads=(NodeLoad(node="n1", fz=_q(-1.0e3, "N")),),
    )
    with pytest.raises(MechanismFound) as refused:
        solve_frame(frame)
    mechanism = refused.value.mechanism
    assert mechanism.node in {"n0", "n1"}
    assert mechanism.freedom in ALL_SIX
    assert "free in" in str(mechanism)
    assert "mechanism" in str(refused.value)


def test_a_frame_held_in_every_freedom_but_one_names_that_one():
    held = tuple(f for f in ALL_SIX if f is not Freedom.UY)
    frame = Frame(
        name="one free",
        nodes=_beam_nodes(1, 3.0),
        members=_beam_members(1),
        supports=(
            Support(node="n0", restrained=ALL_SIX),
            Support(node="n1", restrained=held),
        ),
        node_loads=(NodeLoad(node="n1", fy=_q(1.0e3, "N")),),
    )
    # Held at one end in all six, the cantilever is *not* a mechanism: it bends.
    assert solve_frame(frame).displacement("n1").uy != 0.0


def test_the_solver_takes_a_frame_and_says_so_when_it_is_handed_something_else():
    with pytest.raises(RefusalError, match="takes a Frame"):
        solve_frame({"name": "not a frame"})  # type: ignore[arg-type]


# --- what travels with the answer -------------------------------------------------------


def test_every_force_record_states_the_analysis_that_produced_it():
    """A code's member check amplifies first-order forces and would double count."""
    frame = Frame(
        name="basis",
        nodes=_beam_nodes(2, 4.0),
        members=_beam_members(2),
        supports=_planar_supports(2, {0: (Freedom.UX, Freedom.UZ), 2: (Freedom.UZ,)}),
        node_loads=(NodeLoad(node="n1", fz=_q(-5.0e3, "N")),),
    )
    solution = solve_frame(frame)
    assert solution.basis is AnalysisBasis.FIRST_ORDER
    assert all(force.basis is AnalysisBasis.FIRST_ORDER for force in solution.member_forces)
    assert "first_order_elastic" in str(solution.member_forces[0])


def test_axial_is_reported_tension_positive_whichever_end_is_pushed():
    """The convention a member check reads, stated once and travelling with the record."""
    length, load = 5.0, 30.0e3
    for sign, expected in ((+1.0, +load), (-1.0, -load)):
        frame = Frame(
            name="bar",
            nodes=(_node("a", 0, 0, 0), _node("b", length, 0, 0)),
            members=(
                FrameMember(
                    name="bar", start="a", end="b", section=_section(), material=_material()
                ),
            ),
            supports=(
                Support(node="a", restrained=ALL_SIX),
                Support(
                    node="b",
                    restrained=(Freedom.UY, Freedom.UZ, Freedom.RX, Freedom.RY, Freedom.RZ),
                ),
            ),
            node_loads=(NodeLoad(node="b", fx=_q(sign * load, "N")),),
        )
        axial = solve_frame(frame).forces("bar").axial.magnitude
        assert axial == pytest.approx(expected, rel=1e-9)


def test_the_solution_names_the_node_that_moved_furthest():
    span, count = 6.0, 4
    frame = Frame(
        name="deflection",
        nodes=_beam_nodes(count, span),
        members=_beam_members(count),
        supports=_planar_supports(count, {0: (Freedom.UX, Freedom.UZ), count: (Freedom.UZ,)}),
        node_loads=(NodeLoad(node="n2", fz=_q(-10.0e3, "N")),),
    )
    solution = solve_frame(frame)
    worst = solution.largest_translation
    assert worst is not None and worst.node == "n2"
    assert worst.translation.magnitude > 0


def test_a_frame_and_its_solution_each_render_what_a_reader_needs():
    frame = Frame(
        name="rendered",
        nodes=_beam_nodes(2, 4.0),
        members=_beam_members(2),
        supports=_planar_supports(2, {0: (Freedom.UX, Freedom.UZ), 2: (Freedom.UZ,)}),
        node_loads=(NodeLoad(node="n1", fz=_q(-5.0e3, "N")),),
    )
    assert "3 nodes, 2 members" in str(frame)
    assert "free degrees of freedom" in str(frame)
    solution = solve_frame(frame)
    assert "first_order_elastic" in str(solution)
    assert "equilibrium residual" in str(solution)
    assert str(frame.nodes[0]).startswith("n0 at (")
    assert "uz" in str(solution.displacements[0])
    assert "Fz" in str(solution.reactions[0])
    assert str(frame.members[0]).startswith("m0: n0 to n1")
    assert "ux" in str(frame.node_loads[0]) or "fz" in str(frame.node_loads[0])
    assert "wz" in str(MemberLoad(member="m0", wz=_q(-1.0, "N/m")))
    assert "steel" in str(frame.members[0].material)
    assert "verification section" in str(frame.members[0].section)
    assert "n0: ux" in str(frame.supports[0])


def test_an_unknown_node_or_member_is_a_key_error_naming_what_was_asked_for():
    frame = Frame(
        name="lookup",
        nodes=_beam_nodes(1, 3.0),
        members=_beam_members(1),
        supports=(Support(node="n0", restrained=ALL_SIX),),
        node_loads=(NodeLoad(node="n1", fz=_q(-1.0e3, "N")),),
    )
    solution = solve_frame(frame)
    for lookup in (solution.displacement, solution.forces, solution.reaction):
        with pytest.raises(KeyError, match="nope"):
            lookup("nope")


def test_the_docs_page_quotes_the_cap_and_the_closed_forms_it_claims():
    """The page argues from the node cap and from five closed-form results.

    Each row of its verification table names a formula this suite actually pins, so a
    page claiming a case the suite stopped running fails here.
    """
    import re
    from pathlib import Path

    page = (Path(__file__).resolve().parent.parent / "docs" / "frame-analysis.md").read_text()

    quoted = re.search(r"`MAX_NODES` is (\d+)", page)
    assert quoted is not None, "the page's cap sentence has moved"
    assert int(quoted.group(1)) == MAX_NODES

    # The measured timings are the module's own claim; the page must not invent others.
    timings = dict(re.findall(r"(\d+) nodes in ([\d.]+) s", page))
    assert timings, "the page's measurements have moved"
    assert set(timings) <= {"20", "60", "120"}
    assert max(int(n) for n in timings) == MAX_NODES

    # Scoped to the section the table is in, and not to the whole page: the first draft
    # read every two-column row with a backtick in it, so the next table added to the
    # page — the frame-over-combination checks — counted as two more verification cases.
    # A detector shaped like "any table" cannot hold a claim about one table.
    section = page.split("## How it is checked", 1)
    assert len(section) == 2, "the verification section's heading has moved"
    body = section[1].split("\n## ", 1)[0]
    rows = re.findall(r"^\| ([A-Z][^|]+?) \| ([^|]*`[^|]+) \|$", body, re.M)
    cases = [(case, cells) for case, cells in rows if "`" in cells]
    assert len(cases) == 5, f"the section lists {len(cases)} verification cases"
    # The scoping has to still be doing something: the page's other tables are outside it.
    elsewhere = re.findall(r"^\| ([A-Z][^|]+?) \| ([^|]*`[^|]+) \|$", page, re.M)
    assert len(elsewhere) > len(cases), (
        "the page has only one such table now, so the scoping above is unexercised; "
        "either it is no longer needed or a table was lost"
    )
    pinned = " ".join(cells for _case, cells in cases)
    for expected in ("PL/4", "PL³/48EI", "wL²/8", "5wL/8", "PL/8", "0.1wL²", "Ph³/3EI"):
        assert expected in pinned, f"the page no longer claims {expected}"


# --- second order ---------------------------------------------------------------------


def _sway_column(height: float, lateral: float, axial: float) -> Frame:
    return Frame(
        name="sway column",
        nodes=(_node("base", 0, 0, 0), _node("tip", 0, 0, height)),
        members=(
            FrameMember(
                name="col", start="base", end="tip", section=_section(), material=_material()
            ),
        ),
        supports=(Support(node="base", restrained=ALL_SIX),),
        node_loads=(NodeLoad(node="tip", fx=_q(lateral, "N"), fz=_q(-axial, "N")),),
    )


def test_second_order_is_a_declaration_and_first_order_is_what_you_get_otherwise():
    """Running P-Delta silently and then applying a code's amplifier would double count."""
    frame = _sway_column(4.0, 10.0e3, 200.0e3)
    default = solve_frame(frame)
    asked = solve_frame(frame, basis=AnalysisBasis.SECOND_ORDER)

    assert default.basis is AnalysisBasis.FIRST_ORDER
    assert asked.basis is AnalysisBasis.SECOND_ORDER
    assert default.method != asked.method
    assert "P-Delta" in asked.method
    assert all(force.basis is AnalysisBasis.SECOND_ORDER for force in asked.member_forces)
    assert asked.passes > default.passes
    # The whole point: the two answers differ, and by a lot under this axial load.
    assert abs(asked.displacement("tip").ux) > 2 * abs(default.displacement("tip").ux)


def test_the_second_order_base_moment_is_exactly_h_times_h_plus_p_times_delta():
    """The defining relation of P-Delta, and an exact one for a single cantilever.

    This is the test that says the geometric stiffness is right rather than merely
    bigger: the base moment has to be the first-order moment plus the axial load times
    the deflection the solve itself produced.
    """
    height, lateral, axial = 4.0, 10.0e3, 200.0e3
    solution = solve_frame(_sway_column(height, lateral, axial), basis=AnalysisBasis.SECOND_ORDER)
    sway = abs(solution.displacement("tip").ux)
    assert abs(solution.reaction("base").my) == pytest.approx(
        lateral * height + axial * sway, rel=1e-6
    )


def test_a_tensile_axial_load_stiffens_the_same_column():
    """Tension positive is not a convention here, it is a direction the answer moves in."""
    height, lateral, axial = 4.0, 10.0e3, 200.0e3
    pushed = solve_frame(_sway_column(height, lateral, axial), basis=AnalysisBasis.SECOND_ORDER)
    pulled = solve_frame(_sway_column(height, lateral, -axial), basis=AnalysisBasis.SECOND_ORDER)
    plain = solve_frame(_sway_column(height, lateral, 0.0))

    assert abs(pushed.displacement("tip").ux) > abs(plain.displacement("tip").ux)
    assert abs(pulled.displacement("tip").ux) < abs(plain.displacement("tip").ux)


def test_the_member_force_under_second_order_is_the_elastic_one_at_those_displacements():
    """The geometric term is how the displacements were found, not what the member carries.

    Adding it to the recovery as well would count the P-Delta effect twice in the one
    number a member check reads.
    """
    solution = solve_frame(_sway_column(4.0, 10.0e3, 200.0e3), basis=AnalysisBasis.SECOND_ORDER)
    # The axial force is still the applied one; only the moments moved.
    assert solution.forces("col").axial.magnitude == pytest.approx(-200.0e3, rel=1e-6)


def test_a_column_driven_past_its_critical_load_is_refused_rather_than_answered():
    """A softened matrix that stops being positive definite is the buckling it can see."""
    height = 4.0
    critical = math.pi**2 * E_PA * IY_M4 / (4 * height**2)
    with pytest.raises((MechanismFound, RefusalError)):
        solve_frame(
            _sway_column(height, 1.0e3, 4.0 * critical),
            basis=AnalysisBasis.SECOND_ORDER,
        )


def test_a_basis_that_is_not_one_of_the_two_is_refused():
    with pytest.raises(RefusalError, match="basis is one of"):
        solve_frame(_sway_column(4.0, 1.0e3, 0.0), basis="third order")  # type: ignore[arg-type]


def test_second_order_agrees_with_pynites_own_p_delta():
    """An independently written implementation of the same analysis."""
    height, lateral, axial = 4.0, 10.0e3, 200.0e3
    ours = solve_frame(_sway_column(height, lateral, axial), basis=AnalysisBasis.SECOND_ORDER)
    FEModel3D = pytest.importorskip(
        "Pynite", reason="PyNiteFEA is the referee and is in the dev extra"
    ).FEModel3D
    model = FEModel3D()
    model.add_material("steel", E_PA, G_PA, 0.3, 7850.0)
    model.add_section("section", AREA_M2, IY_M4, IZ_M4, J_M4)
    model.add_node("base", 0, 0, 0)
    model.add_node("tip", 0, 0, height)
    model.add_member("col", "base", "tip", "steel", "section")
    model.def_support("base", True, True, True, True, True, True)
    model.add_node_load("tip", "FX", lateral)
    model.add_node_load("tip", "FZ", -axial)
    model.analyze_PDelta(check_stability=False)

    assert ours.displacement("tip").ux == pytest.approx(model.nodes["tip"].DX["Combo 1"], rel=1e-6)


def test_every_basis_names_a_method_and_the_table_is_total():
    from anvilate.frame import METHODS

    assert set(METHODS) == set(AnalysisBasis)
    assert all(text.strip() for text in METHODS.values())


# --- the card the solve produces -------------------------------------------------------


def _floor_beam(span: float = 6.0, load: float = 8.0e3, count: int = 4) -> Frame:
    return Frame(
        name="floor beam",
        nodes=_beam_nodes(count, span),
        members=_beam_members(count),
        supports=_planar_supports(count, {0: (Freedom.UX, Freedom.UZ), count: (Freedom.UZ,)}),
        member_loads=tuple(MemberLoad(member=f"m{i}", wz=_q(-load, "N/m")) for i in range(count)),
    )


def _limit(node: str, millimetres: float, freedom: Freedom | None = None) -> DeflectionLimit:
    return DeflectionLimit(
        node=node,
        limit=_q(millimetres, "mm"),
        source="the project's declared deflection limit, specification §3.2",
        freedom=freedom,
    )


def test_the_solve_is_a_check_of_its_own_and_comes_first():
    """Every deflection entry says what it was computed from, and this is that thing."""
    screening = screen_frame(_floor_beam(), limits=(_limit("n2", 500.0),))
    first = screening.entries[0]

    assert first.name == "floor beam frame solve"
    assert first.status is CheckStatus.PASS
    assert "equilibrium residual" in first.detail
    assert "first-order linear elastic" in first.detail
    assert COMPUTED_FROM in screening.entries[1].detail
    assert "floor beam frame solve" in screening.entries[1].detail


def test_a_deflection_past_its_declared_limit_fails_and_names_the_source():
    screening = screen_frame(_floor_beam(), limits=(_limit("n2", 5.0, Freedom.UZ),))
    entry = screening.entries[1]

    assert entry.status is CheckStatus.FAIL
    assert entry.comparison is not None
    assert entry.comparison.sense is LimitSense.AT_MOST
    assert "specification §3.2" in entry.detail
    assert screening.status is CheckStatus.FAIL


def test_a_deflection_inside_its_limit_passes_and_the_card_rolls_up():
    screening = screen_frame(_floor_beam(), limits=(_limit("n2", 500.0, Freedom.UZ),))
    assert screening.status is CheckStatus.PASS
    assert all(entry.status is CheckStatus.PASS for entry in screening.entries)


def test_two_limits_on_one_node_are_two_entries_a_reader_can_tell_apart():
    screening = screen_frame(
        _floor_beam(),
        limits=(_limit("n2", 500.0, Freedom.UZ), _limit("n2", 5.0)),
    )
    names = [entry.name for entry in screening.entries]
    assert len(set(names)) == len(names)
    assert "n2 uz deflection" in names
    assert "n2 resultant translation deflection" in names


def test_a_mechanism_is_one_not_evaluated_entry_and_no_deflection_verdicts():
    """A limit judged against displacements that do not exist is a verdict on nothing."""
    frame = Frame(
        name="floating",
        nodes=_beam_nodes(1, 3.0),
        members=_beam_members(1),
        node_loads=(NodeLoad(node="n1", fz=_q(-1.0e3, "N")),),
    )
    screening = screen_frame(frame, limits=(_limit("n1", 5.0),))

    assert len(screening.entries) == 1
    entry = screening.entries[0]
    assert entry.status is CheckStatus.NOT_EVALUATED
    assert "mechanism" in entry.detail
    assert entry.needs and "supports[" in entry.needs[0].declaration


def test_a_limit_on_a_node_the_frame_does_not_have_is_refused():
    with pytest.raises(RefusalError, match="is on no node of this frame"):
        screen_frame(_floor_beam(), limits=(_limit("elsewhere", 5.0),))


def test_a_limit_that_is_not_a_length_or_is_on_a_rotation_is_refused():
    with pytest.raises(RefusalError, match="is a length"):
        DeflectionLimit(node="n2", limit=_q(5.0, "N"), source="declared")
    with pytest.raises(RefusalError, match="is positive"):
        DeflectionLimit(node="n2", limit=_q(0.0, "mm"), source="declared")
    with pytest.raises(RefusalError, match="is a rotation"):
        DeflectionLimit(node="n2", limit=_q(5.0, "mm"), source="declared", freedom=Freedom.RY)


def test_an_uncited_deflection_limit_is_refused_one_layer_down():
    """A limit nobody can attribute is a number nobody can argue with."""
    from pydantic import ValidationError

    with pytest.raises(ValidationError, match="state where it came from"):
        DeflectionLimit(node="n2", limit=_q(5.0, "mm"), source="  ")


def test_the_screening_can_be_asked_for_second_order_too():
    screening = screen_frame(
        _sway_column(4.0, 10.0e3, 200.0e3),
        limits=(_limit("tip", 500.0, Freedom.UX),),
        basis=AnalysisBasis.SECOND_ORDER,
    )
    assert "P-Delta" in screening.entries[0].detail
    assert "P-Delta" in screening.entries[1].detail


def test_a_deflection_limit_renders_what_it_is_about():
    assert str(_limit("n2", 20.0, Freedom.UZ)).startswith("n2 uz at most 20 mm")
    assert "resultant translation" in str(_limit("n2", 20.0))


# --- the frame as a node of a dependency chain ----------------------------------------


def test_a_member_check_runs_on_the_solved_force_and_says_so():
    """The whole point of the chain: a downstream check is ordered after the solve, fed
    the number it produced, and its detail line names where that number came from."""
    from anvilate.dependency import ChainResult, CheckNode, Consumes, DependencyGraph, run_chain
    from anvilate.frame import frame_check_node, frame_outputs

    frame = _floor_beam()
    solution = solve_frame(frame)
    node = frame_check_node(frame)
    downstream = CheckNode(
        id="m1 bending",
        consumes=(
            Consumes(
                upstream="frame solve",
                output="m1.moment_z",
                parameter="moment",
                dimension="[force] * [length]",
            ),
        ),
    )
    graph = DependencyGraph(nodes=(node, downstream))

    def run(check: str, inputs) -> ChainResult:
        if check == "frame solve":
            return ChainResult(
                check=check,
                entry=screen_solution(frame, solution).entries[0],
                outputs=frame_outputs(solution),
            )
        moment = inputs["moment"]
        return ChainResult(
            check=check,
            entry=ScorecardEntry.from_safety_factor(check, computed=1.8, required=1.5).model_copy(
                update={"detail": f"against a solved moment of {moment}"}
            ),
        )

    card = run_chain(graph, run).card()
    bending = next(entry for entry in card.entries if entry.name == "m1 bending")
    assert bending.status is CheckStatus.PASS
    assert COMPUTED_FROM in bending.detail
    assert "frame solve.m1.moment_z" in bending.detail


def test_the_node_declares_every_member_and_the_dimensions_the_values_really_are():
    """The graph compares these textually at registration, so a mismatch is caught there."""
    from anvilate.frame import MEMBER_OUTPUTS, frame_check_node, frame_outputs

    frame = _floor_beam()
    node = frame_check_node(frame)
    produced = frame_outputs(solve_frame(frame))

    assert {output.name for output in node.produces} == set(produced)
    assert len(node.produces) == len(frame.members) * len(MEMBER_OUTPUTS)
    for output in node.produces:
        assert produced[output.name].has_dimension(output.dimension), output.name


def test_the_moments_handed_downstream_are_the_governing_end():
    """A member check takes one number, and the end that is not governing is not it."""
    from anvilate.frame import frame_outputs

    frame = _floor_beam()
    solution = solve_frame(frame)
    produced = frame_outputs(solution)
    for force in solution.member_forces:
        assert produced[f"{force.member}.moment_z"] == force.worst_moment_z
        assert produced[f"{force.member}.moment_y"].magnitude == pytest.approx(
            max(abs(force.moment_y_start), abs(force.moment_y_end))
        )
        assert produced[f"{force.member}.axial"] == force.axial


def test_a_member_check_downstream_of_a_mechanism_is_not_evaluated_and_names_the_frame():
    """A check handed a default in place of a force nobody computed is the silent green."""
    from anvilate.dependency import ChainResult, CheckNode, Consumes, DependencyGraph, run_chain
    from anvilate.frame import frame_check_node

    frame = Frame(
        name="floating",
        nodes=_beam_nodes(1, 3.0),
        members=_beam_members(1),
        node_loads=(NodeLoad(node="n1", fz=_q(-1.0e3, "N")),),
    )
    graph = DependencyGraph(
        nodes=(
            frame_check_node(frame),
            CheckNode(
                id="m0 bending",
                consumes=(
                    Consumes(
                        upstream="frame solve",
                        output="m0.moment_z",
                        parameter="moment",
                        dimension="[force] * [length]",
                    ),
                ),
            ),
        )
    )

    def run(check: str, inputs) -> ChainResult:
        assert check != "m0 bending", "a check downstream of a mechanism must not be called"
        return ChainResult(check=check, entry=screen_frame(frame).entries[0])

    card = run_chain(graph, run).card()
    bending = next(entry for entry in card.entries if entry.name == "m0 bending")
    assert bending.status is CheckStatus.NOT_EVALUATED
    assert "frame solve" in bending.detail


# --- A frame over a combination -------------------------------------------------------
#
# A frame and a combination are two documents about one structure, and until this nothing
# held them to each other: the frame solves, the combination draws and exports, and a
# member modelling the wrong part passes every check it has on a force computed for a
# structure nobody is building.


def _portal_combination():
    """The shipped portal-frame combination, built: two IPE 200 columns and a beam."""
    import yaml

    from anvilate.combination import build_combination, parse_combination

    path = pathlib.Path(__file__).resolve().parents[1] / "examples" / "combinations"
    document = yaml.safe_load((path / "portal_frame.combination.yaml").read_text("utf-8"))
    return build_combination(parse_combination(document))


def _portal_frame(**overrides) -> Frame:
    """A frame declared over that combination, each member naming the part it models."""
    section, material = _section(), _material()
    nodes = (
        FrameNode(name="base_left", x=_q(0, "mm"), y=_q(0, "mm"), z=_q(-1500, "mm")),
        FrameNode(name="top_left", x=_q(0, "mm"), y=_q(0, "mm"), z=_q(1500, "mm"), at="left_seat"),
        FrameNode(
            name="top_right",
            x=_q(0, "mm"),
            y=_q(1800, "mm"),
            z=_q(1500, "mm"),
            at="right_seat",
        ),
        FrameNode(name="base_right", x=_q(0, "mm"), y=_q(1800, "mm"), z=_q(-1500, "mm")),
    )
    members = (
        FrameMember(
            name="lc",
            start="base_left",
            end="top_left",
            section=section,
            material=material,
            item="left_column",
        ),
        FrameMember(
            name="bm",
            start="top_left",
            end="top_right",
            section=section,
            material=material,
            item="beam",
        ),
        FrameMember(
            name="rc",
            start="base_right",
            end="top_right",
            section=section,
            material=material,
            item="right_column",
        ),
    )
    declared = {
        "name": "portal",
        "nodes": nodes,
        "members": members,
        "supports": (
            Support(node="base_left", restrained=ALL_SIX),
            Support(node="base_right", restrained=ALL_SIX),
        ),
    }
    return Frame(**{**declared, **overrides})


def _by_name(card, fragment: str):
    return next(entry for entry in card.entries if fragment in entry.name)


def test_a_frame_over_the_combination_it_models_agrees_with_it():
    from anvilate.frame import frame_over_combination_scorecard

    card = frame_over_combination_scorecard(_portal_frame(), _portal_combination())
    assert [entry.status for entry in card.entries] == [CheckStatus.PASS] * 4
    # The beam is 2 m of steel modelled as a 1.8 m centreline, and the difference is the
    # two column depths it seats on: the check says so rather than calling it a mismatch.
    length = _by_name(card, "lengths are ones the build")
    assert "1.8 m of a 2 m part" in length.detail
    assert "0.2 m short against a 0.4 m joint allowance" in length.detail


def test_a_member_naming_a_part_that_is_not_there_fails_by_name():
    from anvilate.frame import frame_over_combination_scorecard

    frame = _portal_frame()
    strayed = frame.model_copy(
        update={
            "members": (
                frame.members[0].model_copy(update={"item": "left_post"}),
                *frame.members[1:],
            )
        }
    )
    card = frame_over_combination_scorecard(strayed, _portal_combination())
    named = _by_name(card, "members name built parts")
    assert named.status is CheckStatus.FAIL
    assert "left_post is not a part of this combination" in named.detail
    # And the part it should have named is now unmodelled, which is the other half.
    covers = _by_name(card, "covers every built part")
    assert covers.status is CheckStatus.FAIL and "left_column" in covers.detail


def test_a_part_no_member_models_is_a_part_that_carries_load_anyway():
    from anvilate.frame import frame_over_combination_scorecard

    frame = _portal_frame()
    short = frame.model_copy(
        update={"members": (frame.members[0].model_copy(update={"item": ""}), *frame.members[1:])}
    )
    covers = _by_name(
        frame_over_combination_scorecard(short, _portal_combination()), "covers every"
    )
    assert covers.status is CheckStatus.FAIL
    assert "left_column carries no force in this frame" in covers.detail


def test_a_member_longer_than_its_part_is_steel_that_is_not_there():
    """The asymmetric half of the length rule, and the one that is always an error.

    A centreline model is shorter than its part by whatever the joints swallow, so the
    two are not compared for equality. Longer is different: there is no joint that adds
    steel, so any excess past the tolerance fails.
    """
    from anvilate.frame import frame_over_combination_scorecard

    frame = _portal_frame()
    stretched = frame.model_copy(
        update={
            "nodes": (
                frame.nodes[0].model_copy(update={"z": _q(-2500, "mm")}),
                *frame.nodes[1:],
            )
        }
    )
    length = _by_name(
        frame_over_combination_scorecard(stretched, _portal_combination()), "lengths are ones"
    )
    assert length.status is CheckStatus.FAIL
    assert "left_column" in length.detail
    assert "steel that is not there" in length.detail


def test_a_shortfall_past_two_joints_is_a_member_modelling_another_part():
    """The other bound, and the reason it is two section depths and not a percentage.

    A joint can swallow at most the depth of what the member frames into, at each end.
    A member a quarter of its part's length is not a member of that part, whatever the
    joints are.
    """
    from anvilate.frame import frame_over_combination_scorecard

    frame = _portal_frame()
    stubbed = frame.model_copy(
        update={
            "nodes": (
                frame.nodes[0].model_copy(update={"z": _q(1000, "mm")}),
                *frame.nodes[1:],
            )
        }
    )
    length = _by_name(
        frame_over_combination_scorecard(stubbed, _portal_combination()), "lengths are ones"
    )
    assert length.status is CheckStatus.FAIL
    assert "joint allowance" in length.detail


def test_a_node_at_a_connection_the_build_does_not_have_fails():
    from anvilate.frame import frame_over_combination_scorecard

    frame = _portal_frame()
    astray = frame.model_copy(
        update={
            "nodes": (
                frame.nodes[0],
                frame.nodes[1].model_copy(update={"at": "left_bolt_group"}),
                *frame.nodes[2:],
            )
        }
    )
    sits = _by_name(frame_over_combination_scorecard(astray, _portal_combination()), "sit at mates")
    assert sits.status is CheckStatus.FAIL
    assert "left_bolt_group is not a mate of this combination" in sits.detail


def test_a_frame_claiming_nothing_confirms_nothing():
    """A frame with no item on any member is NOT_EVALUATED, not agreement.

    Agreement and "nobody claimed anything" are different facts, and the untagged frame
    is what every frame in the library was before this: reporting it as a pass would
    make the check vacuous for exactly the documents that need it.
    """
    from anvilate.frame import frame_over_combination_scorecard

    frame = _portal_frame()
    untagged = frame.model_copy(
        update={"members": tuple(m.model_copy(update={"item": ""}) for m in frame.members)}
    )
    card = frame_over_combination_scorecard(untagged, _portal_combination())
    assert len(card.entries) == 1
    assert card.entries[0].status is CheckStatus.NOT_EVALUATED
    assert card.entries[0].needs[0].declaration == "members[].item"


def test_the_nodes_check_is_silent_when_no_node_claims_a_connection():
    """A check that did not apply and a check that passed are different facts, so the
    entry is absent rather than a pass nobody earned."""
    from anvilate.frame import frame_over_combination_scorecard

    frame = _portal_frame()
    plain = frame.model_copy(
        update={"nodes": tuple(n.model_copy(update={"at": ""}) for n in frame.nodes)}
    )
    card = frame_over_combination_scorecard(plain, _portal_combination())
    assert not any("sit at mates" in entry.name for entry in card.entries)
    assert len(card.entries) == 3


def test_the_solve_still_works_on_a_frame_that_names_its_parts():
    """`item` and `at` are tags: they must not reach the stiffness matrix."""
    tagged = _portal_frame()
    plain = tagged.model_copy(
        update={
            "members": tuple(m.model_copy(update={"item": ""}) for m in tagged.members),
            "nodes": tuple(n.model_copy(update={"at": ""}) for n in tagged.nodes),
        }
    )
    loads = (NodeLoad(node="top_left", fy=_q(10.0, "kN")),)
    first = solve_frame(tagged.model_copy(update={"node_loads": loads}))
    second = solve_frame(plain.model_copy(update={"node_loads": loads}))
    for a, b in zip(first.displacements, second.displacements, strict=True):
        assert (a.ux, a.uy, a.uz) == pytest.approx((b.ux, b.uy, b.uz))
        assert (a.rx, a.ry, a.rz) == pytest.approx((b.rx, b.ry, b.rz))
    # And the tagged frame did deflect, so the comparison is not two sets of zeros.
    assert max(abs(d.uy) for d in first.displacements) > 1e-9
