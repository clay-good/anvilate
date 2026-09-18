"""A refusal's remedy names what to act on (interaction-quality 2.2, 2.3)."""

from __future__ import annotations

import ast
import re

from conftest import library_sources

_IMPERATIVE = (
    r"(?:declare|supply|pass|state|add|provide|set|give|specify|use|fix|correct|change|"
    r"remove|name|delete|install|choose|pick|rename|lower|raise|increase|reduce|run)"
)
# An imperative whose object is only a pronoun, or nothing: "declare it", "fix this", a
# sentence that ends on the verb. The reader is told to act and not told on what.
_SUBJECTLESS = re.compile(
    rf"(?:^|[;.:—-]\s*|\band\s+|\bor\s+)({_IMPERATIVE})\s+"
    r"(it|this|that|them|one|something|these|those)\b"
    rf"|(?:^|[;.:—]\s*)({_IMPERATIVE})\s*[.;]?\s*$",
    re.IGNORECASE,
)
# An imperative with a real object — what the floor below counts, so a detector that stopped
# matching anything would fail rather than report a clean library.
_WITH_A_SUBJECT = re.compile(
    rf"(?:^|[;.:—]\s*|\band\s+|\bor\s+){_IMPERATIVE}\s+(?:the|a|an|each|every|its|`)\b",
    re.IGNORECASE,
)


def _message(node: ast.expr) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr):
        return "".join(v.value if isinstance(v, ast.Constant) else "{}" for v in node.values)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        return (_message(node.left) or "") + (_message(node.right) or "")
    return None


def _refusals() -> list[tuple[str, str]]:
    found = []
    for path, tree in library_sources():
        for node in ast.walk(tree):
            if isinstance(node, ast.Raise) and isinstance(node.exc, ast.Call) and node.exc.args:
                text = _message(node.exc.args[0])
                if text is not None:
                    found.append((f"{path.name}:{node.lineno}", text))
    return found


def test_every_remedy_a_refusal_gives_names_what_to_act_on() -> None:
    refusals = _refusals()
    assert len(refusals) >= 5000, f"the scan read only {len(refusals)} refusal messages"
    remedies = [text for _, text in refusals if _WITH_A_SUBJECT.search(text)]
    assert len(remedies) >= 25, f"the detector recognised only {len(remedies)} remedies"
    subjectless = [
        f"{where}: {text[:100]!r}" for where, text in refusals if _SUBJECTLESS.search(text)
    ]
    assert subjectless == [], (
        "these refusals tell the reader to act and not on what — name the declaration, "
        f"the value or the file: {subjectless}"
    )


def test_the_remedy_gate_catches_a_pronoun_and_a_bare_imperative() -> None:
    """The attack: the two shapes it forbids are caught, and a named subject is not."""
    assert _SUBJECTLESS.search("a blank line reads as declared; state it or leave it out")
    assert _SUBJECTLESS.search("the store is stale; delete this")
    assert _SUBJECTLESS.search("no material was named. Declare.")
    assert not _SUBJECTLESS.search("declare constraints.min_safety_factor")
    assert not _SUBJECTLESS.search("state the assumption or leave the line out")
