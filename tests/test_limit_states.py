"""Limit states by identity (add-physical-domain-modules 2.3).

The dynamic half — every check a module screen emits resolves to a registered limit state,
and every registered check is emitted — reads what the suite built and lives in conftest.
This file holds the registry's own rules and the static half: a limit state two screens
evaluate is computed by the one implementation it names, read off each screen's own calls.
"""

from __future__ import annotations

import ast
import importlib
from pathlib import Path

import pytest

from anvilate.limit_states import (
    DEFAULT_LIMIT_STATES,
    LimitState,
    LimitStateRegistry,
    ScreenCheck,
)
from anvilate.modules import MODULE_MANIFESTS

_PACKS = Path(__file__).parents[1] / "src" / "anvilate" / "packs"


def _state(identifier: str, *checks: tuple[str, str], implementation: str | None = None):
    return LimitState(
        id=identifier,
        description="a limit state under test",
        evaluated_by=tuple(ScreenCheck(screen=s, check=c) for s, c in checks),
        implementation=implementation,
    )


def _calls_reached(module: str, screen: str) -> set[str]:
    """Every name the screen calls, through the module-level functions of its own pack."""
    tree = ast.parse((_PACKS / f"{module}.py").read_text())
    functions = {node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)}
    reached, pending, called = set(), [screen], set()
    while pending:
        name = pending.pop()
        if name in reached or name not in functions:
            continue
        reached.add(name)
        for node in ast.walk(functions[name]):
            if isinstance(node, ast.Call):
                func = node.func
                callee = func.id if isinstance(func, ast.Name) else getattr(func, "attr", None)
                if callee is not None:
                    called.add(callee)
                    pending.append(callee)
    assert screen in reached, f"{module}.{screen} is not a function in its pack"
    return called


def test_every_evaluating_screen_is_a_screen_a_module_declares():
    declared = {f"{m.id}.{screen}" for m in MODULE_MANIFESTS.manifests for screen in m.screens}
    bound = {binding.screen for state in DEFAULT_LIMIT_STATES for binding in state.evaluated_by}
    assert len(bound) >= 25, bound
    assert bound <= declared, sorted(bound - declared)


def test_a_limit_state_two_screens_evaluate_is_computed_by_its_one_implementation():
    """The composition rule, read from the code: each screen calls the named symbol."""
    shared = [state for state in DEFAULT_LIMIT_STATES if state.implementation is not None]
    assert shared, "no registered limit state is evaluated by two screens, so this checks nothing"
    for state in shared:
        module, _, symbol = state.implementation.rpartition(".")
        target = getattr(importlib.import_module(f"anvilate.{module}"), symbol)
        for screen in sorted({binding.screen for binding in state.evaluated_by}):
            pack, _, function = screen.partition(".")
            called = _calls_reached(pack, function)
            # By name in the call graph AND by identity in the pack's namespace, so a local
            # function that happens to share the name is a second implementation, not this one.
            bound = getattr(importlib.import_module(f"anvilate.packs.{pack}"), symbol, None)
            assert symbol in called and bound is target, (
                f"{screen} evaluates '{state.id}' without calling {state.implementation}; "
                "compose the registered implementation rather than computing it a second time"
            )


def test_a_duplicate_under_a_different_name_is_caught_by_its_id():
    """Two screens, two names, one limit state: refused naming both implementations."""
    original = DEFAULT_LIMIT_STATES.limit_states[0]
    impostor = _state(original.id, ("hydraulics.screen_pipe_run", "conductor rating"))
    with pytest.raises(ValueError) as refusal:
        DEFAULT_LIMIT_STATES.extended(impostor)
    message = str(refusal.value)
    assert original.implemented_by() in message and "hydraulics.screen_pipe_run" in message


def test_one_name_covering_two_limit_states_does_not_collide():
    """The shipped case: the base plate's and the pedestal's `concrete bearing` differ."""
    base = DEFAULT_LIMIT_STATES.identify("structural.screen_base_plate", "bp concrete bearing")
    pedestal = DEFAULT_LIMIT_STATES.identify(
        "structural.screen_concrete_bearing", "ped concrete bearing"
    )
    assert base is not None and pedestal is not None
    assert base.id != pedestal.id


def test_an_unregistered_check_identifies_as_nothing():
    assert DEFAULT_LIMIT_STATES.identify("structural.screen_lifting_lug", "lug weld shear") is None
    # A check is its screen's: the same words on another screen are not a match.
    assert DEFAULT_LIMIT_STATES.identify("structural.screen_beam_member", "lug net tension") is None


def test_the_longest_matching_check_wins():
    state = DEFAULT_LIMIT_STATES._match(
        "structural.screen_column_member", "post buckling (AISC E3 elastic)"
    )
    assert state is not None and state[1].check == "buckling (AISC E3 elastic)"


def test_a_check_bound_to_two_limit_states_is_refused():
    with pytest.raises(ValueError, match="bound to both"):
        LimitStateRegistry(
            limit_states=(
                _state("a.one", ("m.screen_x", "bending")),
                _state("a.two", ("m.screen_x", "bending")),
            )
        )


def test_two_screens_and_no_implementation_is_two_implementations():
    with pytest.raises(ValueError, match="names no implementation"):
        _state("a.one", ("m.screen_x", "bending"), ("m.screen_y", "bending"))


def test_the_registry_renders_its_population_and_round_trips():
    assert str(DEFAULT_LIMIT_STATES).startswith(f"{len(DEFAULT_LIMIT_STATES)} limit states")
    shared = next(state for state in DEFAULT_LIMIT_STATES if state.implementation is not None)
    assert "implemented by analysis.aisc_flexural_buckling_stress" in str(shared)
    rebuilt = LimitStateRegistry.model_validate(DEFAULT_LIMIT_STATES.model_dump())
    assert rebuilt == DEFAULT_LIMIT_STATES


def test_the_modules_page_counts_what_the_registry_holds():
    import re

    page = (Path(__file__).parents[1] / "docs" / "discipline-modules.md").read_text()
    found = re.search(r"(\d+) limit states across the (\d+) checks", page)
    assert found is not None, "the modules page no longer states the registry's size"
    checks = sum(len(state.evaluated_by) for state in DEFAULT_LIMIT_STATES)
    assert (int(found.group(1)), int(found.group(2))) == (len(DEFAULT_LIMIT_STATES), checks)
