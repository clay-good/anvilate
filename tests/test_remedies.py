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


def _pack_screens() -> list[tuple[str, object, object]]:
    """Every pack screen with the element model its first parameter takes."""
    import importlib
    import inspect

    from anvilate.modules import MODULE_MANIFESTS

    found = []
    for manifest in MODULE_MANIFESTS.manifests:
        module = importlib.import_module(f"anvilate.packs.{manifest.id}")
        for screen in manifest.screens:
            function = getattr(module, screen)
            first = next(iter(inspect.signature(function).parameters.values()), None)
            annotation = None if first is None else first.annotation
            model = getattr(module, annotation, None) if isinstance(annotation, str) else annotation
            found.append((f"{manifest.id}.{screen}", function, model))
    return found


def test_a_gap_that_says_which_field_to_declare_names_a_field_that_exists() -> None:
    """A remedy naming `applied_lod` is an instruction the reader cannot carry out.

    Over the reasons a screen gives for a check it could not run (`unavailable=`), against
    the fields of the element that screen takes — read from its own signature, so a reason
    moved to another screen is checked against that screen's element. A reason may also name
    something else the reader can act on, such as the screen to use instead, so a symbol the
    pack exports counts too; what fails is a name that is neither.
    """
    import ast
    import importlib
    import re

    from conftest import library_sources

    models = {}
    for name, _function, model in _pack_screens():
        if model is not None and hasattr(model, "model_fields"):
            models[name.split(".")[1]] = (name, set(model.model_fields))
    assert len(models) >= 20, sorted(models)

    named = 0
    wrong = []
    for path, tree in library_sources():
        if path.parent.name != "packs":
            continue
        for function in ast.walk(tree):
            if not isinstance(function, ast.FunctionDef) or function.name not in models:
                continue
            where, fields = models[function.name]
            pack = importlib.import_module(f"anvilate.packs.{path.stem}")
            for node in ast.walk(function):
                if not isinstance(node, ast.Call):
                    continue
                for keyword in node.keywords:
                    if keyword.arg != "unavailable":
                        continue
                    reason = " ".join(
                        part.value
                        for part in ast.walk(keyword.value)
                        if isinstance(part, ast.Constant) and isinstance(part.value, str)
                    )
                    for field in re.findall(r"`([a-z_]+)`", reason):
                        named += 1
                        if field not in fields and not hasattr(pack, field):
                            wrong.append(
                                f"{where} names `{field}`, which is neither a field of its "
                                "element nor a symbol its pack carries"
                            )
    assert named >= 15, f"only {named} field names were read out of the gaps' reasons"
    assert not wrong, wrong
