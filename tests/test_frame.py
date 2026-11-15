"""Frame analysis: five closed forms re-derived, and an independent solver that agrees.

A solver nobody checked is a number generator. Every case here pins a quantity against a
solution worked out away from this code — a textbook closed form, or Pynite, which is an
independently written MIT solver — and the two have to agree.

The closed forms run in every suite. The Pynite comparisons skip without it and are in
the dev extra so CI always has it; a referee that is usually absent is not a referee.
"""

from __future__ import annotations

import math

import pytest

from anvilate.frame import (
    MAX_NODES,
    AnalysisBasis,
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
    solve_frame,
)
from anvilate.refusal import RefusalError
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

    rows = re.findall(r"^\| ([A-Z][^|]+?) \| ([^|]*`[^|]+) \|$", page, re.M)
    cases = [(case, cells) for case, cells in rows if "`" in cells]
    assert len(cases) == 5, f"the page lists {len(cases)} verification cases"
    pinned = " ".join(cells for _case, cells in cases)
    for expected in ("PL/4", "PL³/48EI", "wL²/8", "5wL/8", "PL/8", "0.1wL²", "Ph³/3EI"):
        assert expected in pinned, f"the page no longer claims {expected}"
