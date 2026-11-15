"""Worked example: a skid frame whose member forces nobody typed in.

`examples/skid_frame_document.py` screens a frame whose member forces the author
already knew. This one is the case that was not possible before: a skid whose load path
is **indeterminate**, so the force in each member is not something an agent can work out
and hand to a check.

The skid is two 3 m longitudinals on four legs, cross-braced at the quarter points, with
a 40 kN package sitting on the middle of one longitudinal. Four legs under two beams tied
together is one redundancy more than statics can resolve: how the package's weight splits
between the near legs and the far ones depends on the stiffness of everything in between.

`anvilate.frame` solves it, and then each member's bending check runs **on the solved
moment** through a dependency chain, so its detail line names where that moment came
from. The serviceability limit on the loaded longitudinal is checked against the
displacement the same solve produced.

What the solve answers that statics could not: the loaded longitudinal takes about ten
times the bending of the far one, and the two legs under it carry about half the package
each, with the rest reaching the far legs through the braces. The skid **fails** — the
loaded longitudinal's bending safety factor lands just under the 1.67 asked of it — and
it fails on strength while passing serviceability, which is the pair a reader wants to
see separately.

Two things the card shows that a typed-force run could not. The frame solve is a check of
its own, with its equilibrium residual on it, so a reader can see how well the arithmetic
closed. And every bending entry says `computed from frame solve`, so a verdict at the end
of a factorisation reads as resting on one.

The example reports the governing member's bending safety factor, the solved mid-span
moment, the mid-span deflection, and the reaction the most heavily loaded leg carries.

Run it directly (``python examples/skid_frame_solved.py``);
:func:`screen_skid` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import bending_stress
from anvilate.dependency import (
    ChainResult,
    CheckNode,
    Consumes,
    DependencyGraph,
    run_chain,
)
from anvilate.derivation import Derivation, SymbolValue
from anvilate.frame import (
    AnalysisBasis,
    DeflectionLimit,
    Frame,
    FrameMaterial,
    FrameMember,
    FrameNode,
    FrameSection,
    Freedom,
    NodeLoad,
    Support,
    frame_check_node,
    frame_outputs,
    screen_solution,
    solve_frame,
)
from anvilate.scorecard import Scorecard, ScorecardEntry
from anvilate.units import Quantity

Q = Quantity.parse

# A36 plate and a 150 x 75 x 6 rectangular hollow section, both declared rather than
# looked up: this example is about the solve, and a table lookup would put a second
# source of truth in the way of reading it.
STEEL = FrameMaterial(
    name="ASTM A36",
    elastic_modulus=Q("200 GPa"),
    shear_modulus=Q("77 GPa"),
    density=Q("7850 kg/m**3"),
    source="ASTM A36/A36M-19 nominal elastic constants, declared for this example",
)
RHS = FrameSection(
    name="RHS 150 x 75 x 6",
    area=Q("2520 mm**2"),
    # The 150 mm depth resists the vertical load, and in this library's local axes that
    # is bending about **y**: for a horizontal member the local z axis points up, so a
    # downward load bends the member in the x–z plane. Writing the strong axis into
    # `second_moment_z` lays the section flat, and the first draft of this example did.
    second_moment_y=Q("7.52e6 mm**4"),
    second_moment_z=Q("2.52e6 mm**4"),
    torsion_constant=Q("5.60e6 mm**4"),
    source="the section's published properties, declared for this example",
)
#: Elastic section modulus about the strong axis, Iy / (depth / 2).
SECTION_MODULUS = Q("1.003e5 mm**3")
YIELD_STRENGTH = Q("250 MPa")
REQUIRED_SAFETY_FACTOR = 1.67

PACKAGE = Q("40 kN")
LENGTH, WIDTH, LEG = 3.0, 1.2, 0.6
DEFLECTION_LIMIT = DeflectionLimit(
    node="a2",
    limit=Q("8.3 mm"),
    source="L/360 on the 3 m longitudinal, the project's serviceability limit",
    freedom=Freedom.UZ,
)

#: The bending members. The legs carry axial load and are not screened for bending here.
BEAMS = ("a1", "a2", "a3", "b1", "b2", "b3", "x1", "x2")


def _node(name: str, x: float, y: float, z: float) -> FrameNode:
    return FrameNode(
        name=name,
        x=Quantity(magnitude=x, unit="m"),
        y=Quantity(magnitude=y, unit="m"),
        z=Quantity(magnitude=z, unit="m"),
    )


def _member(name: str, start: str, end: str) -> FrameMember:
    return FrameMember(name=name, start=start, end=end, section=RHS, material=STEEL)


def skid() -> Frame:
    """The skid: two longitudinals on four legs, cross-braced at the quarter points."""
    quarter, half, three_quarters = LENGTH / 4, LENGTH / 2, 3 * LENGTH / 4
    deck = {
        "a0": (0.0, 0.0), "a1": (quarter, 0.0), "a2": (half, 0.0),
        "a3": (three_quarters, 0.0), "a4": (LENGTH, 0.0),
        "b0": (0.0, WIDTH), "b1": (quarter, WIDTH), "b2": (half, WIDTH),
        "b3": (three_quarters, WIDTH), "b4": (LENGTH, WIDTH),
    }  # fmt: skip
    nodes = [_node(name, x, y, 0.0) for name, (x, y) in deck.items()]
    # The four legs, each reaching down to the ground from a corner.
    feet = {"f_a0": "a0", "f_a4": "a4", "f_b0": "b0", "f_b4": "b4"}
    nodes += [_node(foot, deck[top][0], deck[top][1], -LEG) for foot, top in feet.items()]
    members = [
        _member("a1", "a0", "a1"), _member("a2", "a1", "a2"),
        _member("a3", "a2", "a3"), _member("a4", "a3", "a4"),
        _member("b1", "b0", "b1"), _member("b2", "b1", "b2"),
        _member("b3", "b2", "b3"), _member("b4", "b3", "b4"),
        # The cross braces at the quarter points, which are what makes the two
        # longitudinals share the package and the load path indeterminate.
        _member("x1", "a1", "b1"), _member("x2", "a3", "b3"),
        _member("x0", "a0", "b0"), _member("x4", "a4", "b4"),
    ]  # fmt: skip
    members += [_member(f"leg_{top}", foot, top) for foot, top in feet.items()]
    return Frame(
        name="skid frame",
        nodes=tuple(nodes),
        members=tuple(members),
        # Pinned feet: the skid sits on the ground and is not bolted down.
        supports=tuple(
            Support(node=foot, restrained=(Freedom.UX, Freedom.UY, Freedom.UZ)) for foot in feet
        ),
        node_loads=(
            NodeLoad(node="a2", fz=Quantity(magnitude=-PACKAGE.to("N").magnitude, unit="N")),
        ),
        member_loads=(),
        self_weight=True,
    )


def _bending_entry(member: str, moment: Quantity) -> ScorecardEntry:
    """One member's bending check, on the moment the solve produced."""
    stress = bending_stress(moment=moment, section_modulus=SECTION_MODULUS)
    computed = YIELD_STRENGTH.to("MPa").magnitude / stress.to("MPa").magnitude
    return ScorecardEntry.from_safety_factor(
        f"{member} bending",
        computed=computed,
        required=REQUIRED_SAFETY_FACTOR,
    ).model_copy(
        update={
            "reference": "AISC 360-16 §F1 (allowable bending, Fb = Fy / 1.67)",
            "detail": (
                f"bending stress {stress.to('MPa').magnitude:.1f} MPa from a solved moment "
                f"of {moment.to('kN*m').magnitude:.2f} kN·m against "
                f"{YIELD_STRENGTH} yield"
            ),
            # The worked line, with the solved moment in it. A check whose input came out
            # of a factorisation still has a formula, and showing it is how a reader sees
            # that the one number they cannot re-derive is the moment.
            "derivation": Derivation(
                symbolic="U = F_y/(M/Z)",
                inputs=(
                    SymbolValue(
                        symbol="M",
                        description=f"bending moment on {member}, from the frame solve",
                        value=moment,
                        unit="kN*m",
                    ),
                    SymbolValue(
                        symbol="Z",
                        description="elastic section modulus about the bending axis",
                        value=SECTION_MODULUS,
                        unit="mm**3",
                    ),
                    SymbolValue(
                        symbol="F_y",
                        description="specified minimum yield strength",
                        value=YIELD_STRENGTH,
                        unit="MPa",
                    ),
                ),
                result=SymbolValue(
                    symbol="U",
                    description="yield strength as a multiple of the bending stress",
                    value=computed,
                ),
                citation="AISC 360-16 §F1",
            ),
        }
    )


def screen_skid() -> Scorecard:
    """Solve the skid, screen every beam on its solved moment, and return the card."""
    frame = skid()
    solution = solve_frame(frame, basis=AnalysisBasis.FIRST_ORDER)
    produced = frame_outputs(solution)

    graph = DependencyGraph(
        nodes=(
            frame_check_node(frame),
            *(
                CheckNode(
                    id=f"{beam} bending",
                    consumes=(
                        Consumes(
                            upstream="frame solve",
                            output=f"{beam}.moment_y",
                            parameter="moment",
                            dimension="[force] * [length]",
                        ),
                    ),
                )
                for beam in BEAMS
            ),
        )
    )
    solved_card = screen_solution(frame, solution, limits=(DEFLECTION_LIMIT,))

    def run(check: str, inputs: dict[str, Quantity]) -> ChainResult:
        if check == "frame solve":
            return ChainResult(check=check, entry=solved_card.entries[0], outputs=produced)
        member = check.removesuffix(" bending")
        return ChainResult(check=check, entry=_bending_entry(member, inputs["moment"]))

    chained = run_chain(graph, run).card()
    # The deflection entry rides beside the chain: it is about a node, not a member, so it
    # has no place in a graph keyed on member forces.
    card = Scorecard(entries=(*chained.entries, *solved_card.entries[1:]))

    return card


def skid_numbers() -> dict[str, float]:
    """The four figures this example's prose quotes, each read off the same solve."""
    frame = skid()
    solution = solve_frame(frame)
    produced = frame_outputs(solution)
    bending = [
        entry.safety_factor
        for entry in screen_skid().entries
        if entry.name.endswith(" bending") and entry.safety_factor is not None
    ]
    return {
        "governing_safety_factor": min(bending),
        "mid_span_moment_knm": produced["a2.moment_y"].to("kN*m").magnitude,
        "far_side_moment_knm": produced["b2.moment_y"].to("kN*m").magnitude,
        "mid_span_deflection_mm": abs(solution.displacement("a2").uz) * 1000.0,
        "heaviest_leg_kn": max(reaction.fz for reaction in solution.reactions) / 1000.0,
        "equilibrium_residual_n": solution.residual,
    }


def main() -> None:
    card, numbers = screen_skid(), skid_numbers()
    print(card)
    for entry in card.entries:
        print(f"[{entry.status.name}] {entry.name}: {entry.detail}")
    print()
    for name, value in numbers.items():
        print(f"{name}: {value:.4g}")


if __name__ == "__main__":
    main()
