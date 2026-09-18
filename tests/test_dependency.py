"""The check dependency graph: declared consumption, dependency order, cycles named whole."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from anvilate.dependency import (
    ChainResult,
    CheckNode,
    Consumes,
    DependencyGraph,
    Output,
    find_cycles,
    run_chain,
)
from anvilate.scorecard import CheckStatus, ScorecardEntry
from anvilate.units import Quantity


def _node(
    check: str,
    produces: tuple[tuple[str, str], ...] = (),
    consumes: tuple[tuple[str, str, str, str], ...] = (),
) -> CheckNode:
    return CheckNode(
        id=check,
        produces=tuple(Output(name=name, dimension=dim) for name, dim in produces),
        consumes=tuple(
            Consumes(upstream=up, output=out, parameter=param, dimension=dim)
            for up, out, param, dim in consumes
        ),
    )


def _six_link_chain() -> DependencyGraph:
    """An internal heat source through to a displacement verdict, declared back to front."""
    return DependencyGraph(
        nodes=(
            # Deliberately declared in an order unrelated to the dependencies.
            _node("displacement", consumes=(("shock", "peak_g", "input_g", "dimensionless"),)),
            _node(
                "shock",
                produces=(("peak_g", "dimensionless"),),
                consumes=(("modal", "f_n", "frequency", "[frequency]"),),
            ),
            _node(
                "modal",
                produces=(("f_n", "[frequency]"),),
                consumes=(("modulus", "E_hot", "modulus", "[pressure]"),),
            ),
            _node(
                "modulus",
                produces=(("E_hot", "[pressure]"),),
                consumes=(("temperature", "T_part", "temperature", "[temperature]"),),
            ),
            _node(
                "temperature",
                produces=(("T_part", "[temperature]"),),
                consumes=(("heat", "q", "heat_in", "[power]"),),
            ),
            _node("heat", produces=(("q", "[power]"),)),
        )
    )


def test_evaluation_follows_the_dependencies_not_the_declaration_order() -> None:
    graph = _six_link_chain()
    assert graph.order() == (
        "heat",
        "temperature",
        "modulus",
        "modal",
        "shock",
        "displacement",
    )
    # Every consumption is satisfied before the check that reads it runs.
    position = {name: index for index, name in enumerate(graph.order())}
    for node in graph.nodes:
        for consumed in node.consumes:
            assert position[consumed.upstream] < position[node.id]


def test_the_order_is_stable_and_keeps_declaration_order_among_equals() -> None:
    graph = DependencyGraph(
        nodes=(
            _node("zulu", produces=(("x", "[length]"),)),
            _node("alpha", produces=(("y", "[length]"),)),
            _node("mike", consumes=(("zulu", "x", "p", "[length]"),)),
            _node("bravo"),
        )
    )
    # Not alphabetical, not by dependency where there is none: the order it was declared in.
    assert graph.order() == ("zulu", "alpha", "bravo", "mike")
    assert graph.order() == graph.order()
    assert DependencyGraph.model_validate_json(graph.model_dump_json()).order() == graph.order()


def test_a_cycle_names_all_of_its_members() -> None:
    nodes = (
        _node("a", produces=(("x", "[length]"),), consumes=(("c", "z", "p", "[length]"),)),
        _node("b", produces=(("y", "[length]"),), consumes=(("a", "x", "p", "[length]"),)),
        _node("c", produces=(("z", "[length]"),), consumes=(("b", "y", "p", "[length]"),)),
    )
    # As data, before construction...
    assert find_cycles(nodes) == (("a", "b", "c", "a"),)
    # ...and as a refusal naming all three, not the edge that closed the loop.
    with pytest.raises(ValidationError) as refused:
        DependencyGraph(nodes=nodes)
    message = str(refused.value)
    assert "a -> b -> c -> a" in message
    for member in "abc":
        assert f"'{member}'" in message or member in message


def test_two_separate_cycles_are_both_reported() -> None:
    nodes = (
        _node("a", produces=(("x", "[length]"),), consumes=(("b", "y", "p", "[length]"),)),
        _node("b", produces=(("y", "[length]"),), consumes=(("a", "x", "p", "[length]"),)),
        _node("c", produces=(("z", "[length]"),), consumes=(("d", "w", "p", "[length]"),)),
        _node("d", produces=(("w", "[length]"),), consumes=(("c", "z", "p", "[length]"),)),
        _node("free"),
    )
    assert set(find_cycles(nodes)) == {("a", "b", "a"), ("c", "d", "c")}


def test_a_check_cannot_consume_itself() -> None:
    with pytest.raises(ValidationError, match="cannot be upstream of itself"):
        _node("a", produces=(("x", "[length]"),), consumes=(("a", "x", "p", "[length]"),))


def test_a_dimension_mismatch_is_caught_at_registration() -> None:
    with pytest.raises(ValidationError, match=r"takes 'frequency' in \[frequency\].*\[time\]"):
        DependencyGraph(
            nodes=(
                _node("modal", produces=(("f_n", "[time]"),)),
                _node("shock", consumes=(("modal", "f_n", "frequency", "[frequency]"),)),
            )
        )


@pytest.mark.parametrize(
    ("nodes", "match"),
    [
        (
            (_node("shock", consumes=(("modal", "f_n", "frequency", "[frequency]"),)),),
            "which this graph does not carry",
        ),
        (
            (
                _node("modal", produces=(("mass", "[mass]"),)),
                _node("shock", consumes=(("modal", "f_n", "frequency", "[frequency]"),)),
            ),
            r"which produces \['mass'\]",
        ),
        (
            (_node("modal"), _node("shock", consumes=(("modal", "f_n", "f", "[frequency]"),))),
            "which produces nothing",
        ),
        (
            (_node("modal"), _node("modal")),
            "one check id twice",
        ),
    ],
)
def test_an_unresolvable_consumption_is_refused_naming_it(nodes, match: str) -> None:
    with pytest.raises(ValidationError, match=match):
        DependencyGraph(nodes=nodes)


def test_one_parameter_cannot_be_fed_by_two_upstream_outputs() -> None:
    with pytest.raises(ValidationError, match="binds one parameter twice"):
        _node(
            "shock",
            consumes=(
                ("modal", "f_n", "frequency", "[frequency]"),
                ("other", "f_alt", "frequency", "[frequency]"),
            ),
        )


def test_downstream_is_the_transitive_closure_in_evaluation_order() -> None:
    graph = _six_link_chain()
    # A gap in the heat source reaches everything past it, not just the next hop.
    assert graph.downstream_of("heat") == (
        "temperature",
        "modulus",
        "modal",
        "shock",
        "displacement",
    )
    assert graph.downstream_of("shock") == ("displacement",)
    assert graph.downstream_of("displacement") == ()
    with pytest.raises(ValueError, match="carries no check 'nobody'"):
        graph.downstream_of("nobody")


def test_an_empty_graph_says_so_and_orders_nothing() -> None:
    graph = DependencyGraph()
    assert graph.order() == ()
    assert len(graph) == 0
    assert str(graph) == "dependency graph: no checks declared"


def test_the_rendering_shows_the_chain_in_order_with_what_each_check_reads() -> None:
    lines = str(_six_link_chain()).splitlines()
    assert lines[0] == "dependency graph: 6 checks in order"
    assert lines[1] == "  heat"
    assert lines[2] == "  temperature [reads heat.q -> heat_in]"
    assert lines[-1] == "  displacement [reads shock.peak_g -> input_g]"


@pytest.mark.parametrize(
    "nodes",
    [
        _node("a"),  # ONE node where a sequence belongs: a model iterates its own fields
        "a",  # a bare string, which is iterable over its characters
        {"a": _node("a")},  # a mapping, which iterates its keys
    ],
)
def test_find_cycles_refuses_what_is_not_a_sequence_of_nodes(nodes) -> None:
    with pytest.raises(ValueError, match="nodes"):
        find_cycles(nodes)


# --- running a chain ------------------------------------------------------------------


def _ran(check: str, outputs: dict[str, Quantity] | None = None, **fields) -> ChainResult:
    return ChainResult(
        check=check,
        entry=ScorecardEntry(
            name=check, status=fields.pop("status", CheckStatus.PASS), detail="ran"
        ),
        outputs=outputs or {},
        **fields,
    )


def _runner(values: dict[str, dict[str, Quantity]], blocked: set[str] = frozenset()):
    """A `run_check` that hands back the declared outputs, recording what it was called with."""
    seen: dict[str, dict[str, Quantity]] = {}

    def run_check(check: str, inputs):
        seen[check] = dict(inputs)
        if check in blocked:
            return ChainResult(
                check=check,
                entry=ScorecardEntry(
                    name=check, status=CheckStatus.NOT_EVALUATED, detail="no material property"
                ),
            )
        return _ran(check, values.get(check, {}))

    return run_check, seen


_CHAIN_VALUES = {
    "heat": {"q": Quantity(magnitude=12.0, unit="W")},
    "temperature": {"T_part": Quantity(magnitude=340.0, unit="K")},
    "modulus": {"E_hot": Quantity(magnitude=180.0, unit="GPa")},
    "modal": {"f_n": Quantity(magnitude=95.0, unit="Hz")},
    "shock": {"peak_g": Quantity(magnitude=4.2, unit="")},
}


def test_a_chain_runs_in_dependency_order_and_feeds_each_check_its_inputs() -> None:
    graph = _six_link_chain()
    run_check, seen = _runner(_CHAIN_VALUES)
    run = run_chain(graph, run_check)
    assert run.order == graph.order()
    assert [result.check for result in run.results] == list(graph.order())
    assert run.card().status is CheckStatus.PASS
    # Each check was handed exactly the parameters it declared, bound to upstream values.
    assert seen["temperature"] == {"heat_in": Quantity(magnitude=12.0, unit="W")}
    assert seen["modal"] == {"modulus": Quantity(magnitude=180.0, unit="GPa")}
    assert seen["heat"] == {}


def test_an_upstream_gap_makes_every_downstream_check_not_evaluated_naming_it() -> None:
    graph = _six_link_chain()
    run_check, seen = _runner(_CHAIN_VALUES, blocked={"temperature"})
    run = run_chain(graph, run_check)
    # The defect class: the chain does not compute a displacement from a modulus nobody
    # produced. Nothing past the gap is even called.
    assert set(seen) == {"heat", "temperature"}
    statuses = {result.check: result.entry.status for result in run.results}
    assert statuses["heat"] is CheckStatus.PASS
    for downstream in ("modulus", "modal", "shock", "displacement"):
        assert statuses[downstream] is CheckStatus.NOT_EVALUATED
    # The immediate upstream is named, and so is the head of the broken chain.
    assert "'temperature.T_part'" in run.result("modulus").entry.detail
    far = run.result("displacement").entry.detail
    assert "'shock.peak_g'" in far and "waiting on 'temperature'" in far
    assert run.card().status is CheckStatus.NOT_EVALUATED


def test_a_check_that_did_not_run_cannot_hand_a_value_downstream() -> None:
    with pytest.raises(ValidationError, match="did not run produced no value"):
        _ran(
            "modal", {"f_n": Quantity(magnitude=95.0, unit="Hz")}, status=CheckStatus.NOT_EVALUATED
        )


def test_mutating_a_links_value_changes_every_downstream_input() -> None:
    """The chain is wired, not merely declared: change a link and the change arrives."""
    graph = _six_link_chain()
    hotter = {**_CHAIN_VALUES, "temperature": {"T_part": Quantity(magnitude=420.0, unit="K")}}
    _run_check, before = _runner(_CHAIN_VALUES)
    run_chain(graph, _run_check)
    _run_check, after = _runner(hotter)
    run_chain(graph, _run_check)
    assert before["modulus"]["temperature"].magnitude == 340.0
    assert after["modulus"]["temperature"].magnitude == 420.0


def test_a_downstream_result_inherits_the_conservatism_of_its_whole_chain() -> None:
    from anvilate.margin import MarginAction, MarginEntry, MarginKind

    def factor(check: str, value: float) -> MarginEntry:
        return MarginEntry(
            label=f"{check} allowance",
            kind=MarginKind.CONTINGENCY,
            value=value,
            quantity="displacement",
            action=MarginAction.RAISES_DEMAND,
            origin=f"check {check}",
            authority="company practice DP-104",
        )

    graph = _six_link_chain()

    def run_check(check: str, inputs):
        margins = ()
        if check == "temperature":
            margins = (factor("temperature", 1.2),)
        elif check == "displacement":
            margins = (factor("displacement", 1.1),)
        elif check == "mass_like_sibling":  # pragma: no cover - not in this graph
            margins = (factor(check, 2.0),)
        return _ran(check, _CHAIN_VALUES.get(check, {}), margins=margins)

    run = run_chain(graph, run_check)
    inherited = run.inherited_margins("displacement")
    assert [entry.label for entry in inherited] == [
        "temperature allowance",
        "displacement allowance",
    ]
    # An upstream factor is in force downstream; a downstream one is not in force upstream.
    assert [e.label for e in run.inherited_margins("temperature")] == ["temperature allowance"]
    assert run.inherited_margins("heat") == ()
    from anvilate.margin import MarginLedger

    stack = MarginLedger(entries=inherited).stack("displacement")
    assert stack.cumulative == pytest.approx(1.2 * 1.1, rel=1e-12)


def test_staleness_invalidates_the_whole_closure_never_the_first_hop() -> None:
    run = run_chain(_six_link_chain(), _runner(_CHAIN_VALUES)[0])
    assert run.stale_after("temperature") == (
        "temperature",
        "modulus",
        "modal",
        "shock",
        "displacement",
    )
    assert run.stale_after("displacement") == ("displacement",)
    with pytest.raises(ValueError, match="carries no check 'nobody'"):
        run.stale_after("nobody")


def test_a_mislabelled_result_is_refused_rather_than_recorded() -> None:
    graph = DependencyGraph(nodes=(_node("a"), _node("b")))
    with pytest.raises(ValueError, match="asked for 'a' and returned a result for 'b'"):
        run_chain(graph, lambda _check, _inputs: _ran("b"))


def test_upstream_of_is_the_mirror_of_downstream_of() -> None:
    graph = _six_link_chain()
    assert graph.upstream_of("displacement") == (
        "heat",
        "temperature",
        "modulus",
        "modal",
        "shock",
    )
    assert graph.upstream_of("heat") == ()
    for name in graph.order():
        for other in graph.order():
            assert (other in graph.upstream_of(name)) == (name in graph.downstream_of(other))


def test_the_run_renders_every_check_with_its_verdict_in_the_order_it_ran() -> None:
    run = run_chain(_six_link_chain(), _runner(_CHAIN_VALUES, blocked={"temperature"})[0])
    lines = str(run).splitlines()
    assert lines[0] == "chain of 6 checks, in evaluation order"
    assert [line.split()[-1] for line in lines[1:]] == list(run.order)
    assert lines[1] == "  pass           heat"
    assert lines[2] == "  not_evaluated  temperature"
    # Every check is on the rendering, including the ones the gap stopped.
    assert len(lines) == 1 + len(run.results)
