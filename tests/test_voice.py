"""The tool's voice: an instrument, not a companion (presentation-craft 6.1, 6.2)."""

from __future__ import annotations

import ast
import re

from conftest import library_sources

# The registers docs/voice.md forbids in anything a user reads, each with what it catches.
_FORBIDDEN = {
    "congratulation": re.compile(
        r"(?i)\b(congratulations?|congrats|great job|well done|nice work|hooray|yay|woohoo)\b"
    ),
    "a joke or an apology": re.compile(r"(?i)\b(oops|whoops|sorry|uh-oh|yikes)\b"),
    "an exclamation": re.compile(r"\w!(?!=)"),
    "the tool as a person": re.compile(
        r"(?<![\w'])I(?:'m| am| think| believe| feel)\b|(?i:\b(happy|glad|excited) to\b)"
    ),
    "an emoji": re.compile("[\U0001f300-\U0001faff\u2600-\u27bf]"),
}


def _user_strings() -> list[tuple[str, str]]:
    """Every string literal in the library that is not a docstring, with where it is."""
    found: list[tuple[str, str]] = []
    for path, tree in library_sources():
        docstrings = {
            id(node.body[0].value)
            for node in ast.walk(tree)
            if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
            and node.body
            and isinstance(node.body[0], ast.Expr)
            and isinstance(node.body[0].value, ast.Constant)
        }
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Constant)
                and isinstance(node.value, str)
                and id(node) not in docstrings
            ):
                found.append((f"{path.name}:{node.lineno}", node.value))
    return found


def _violations(strings: list[tuple[str, str]]) -> list[str]:
    return [
        f"{where} ({register}): {text[:60]!r}"
        for where, text in strings
        for register, pattern in _FORBIDDEN.items()
        if pattern.search(text)
    ]


def test_no_user_facing_string_congratulates_jokes_exclaims_or_plays_a_person() -> None:
    strings = _user_strings()
    assert len(strings) >= 5000, f"the scan read only {len(strings)} strings"
    assert _violations(strings) == []


def test_the_voice_gate_catches_each_register_it_names() -> None:
    """The attack: one ordinary slip per register, each of which must be caught."""
    planted = [
        ("a", "Congratulations, every check passed"),
        ("b", "Oops, the material is unknown"),
        ("c", "Pass!"),
        ("d", "I think this plate is too thin"),
        ("e", "all checks passed \u2705"),
    ]
    caught = _violations(planted)
    assert [line.split(" ")[0] for line in caught] == ["a", "b", "c", "d", "e"]
    # And what it must leave alone: a list marker, an inequality, a Roman numeral.
    assert _violations([("m", "  ! part: a → b"), ("n", "x != y"), ("o", "Category I")]) == []


def test_the_voice_pages_figures_are_the_gates_own() -> None:
    """docs/voice.md quotes the gate's reach and a pass line; both are recomputed here."""
    from pathlib import Path

    from anvilate.scorecard import ScorecardEntry

    page = (Path(__file__).resolve().parents[1] / "docs" / "voice.md").read_text(encoding="utf-8")
    assert "It reads over 5,000 strings" in page
    assert len(_user_strings()) > 5000
    entry = ScorecardEntry.from_safety_factor("bracket", computed=2.4, required=2.0)
    assert "safety factor 2.40 vs required minimum 2.00" in entry.detail
    assert '"PASS: safety factor 2.4 vs required 2.0"' in page
