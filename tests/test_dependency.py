"""The check dependency graph: declared consumption, dependency order, cycles named whole."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from anvilate.dependency import CheckNode, Consumes, DependencyGraph, Output, find_cycles


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
