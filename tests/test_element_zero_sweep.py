"""Every registered element, every number in it set to zero: refused or screened, never a crash.

Zero passes a sign check. A zero plate thickness reached `force / (width · thickness)`,
and `anvilate check` ended with an internal error on the likeliest typo a person makes in a
dimension. A sweep over the 29 registered elements found fifteen such fields in twelve of
them. They included the plate and bearing dimensions, a nested cross-section's area and
extreme fibre, and two dimensionless requirements the screens divide by.

`tests/element_params.json` holds one valid parameter set per registered element,
harvested from the suite's own fixtures. Each number in it, at any depth, is set to zero in
turn. The element must then either refuse to build, which is a sentence, or screen: a
`ValueError` or `LookupError` from the screen is a refusal the card reports. Anything else
reaches a user as a traceback, and fails here.
"""

from __future__ import annotations

import copy
import inspect
import json
from collections.abc import Iterator
from pathlib import Path

from pydantic import ValidationError

from anvilate.screening import element_registry

_PARAMS = Path(__file__).resolve().parent / "element_params.json"


def _documents() -> dict[str, dict]:
    return json.loads(_PARAMS.read_text(encoding="utf-8"))


def _numbers(node: object, path: tuple = ()) -> Iterator[tuple]:
    if isinstance(node, dict):
        for key, value in node.items():
            yield from _numbers(value, (*path, key))
    elif isinstance(node, list):
        for index, value in enumerate(node):
            yield from _numbers(value, (*path, index))
    elif isinstance(node, int | float) and not isinstance(node, bool):
        yield path


def _with(document: dict, path: tuple, value: object) -> dict:
    changed = copy.deepcopy(document)
    target = changed
    for part in path[:-1]:
        target = target[part]
    target[path[-1]] = value
    return changed


def _crashes() -> tuple[list[str], int]:
    registry = element_registry()
    documents = _documents()
    crashes, probes = [], 0
    for tag, (model, screen) in sorted(registry.items()):
        parameters = inspect.signature(screen).parameters
        keywords = {"required_safety_factor": 2.0} if "required_safety_factor" in parameters else {}
        for path in _numbers(documents[tag]):
            probes += 1
            try:
                element = model.model_validate(_with(documents[tag], path, 0))
            except (ValidationError, ValueError, LookupError):
                continue
            try:
                screen(element, **keywords)
            except (ValueError, LookupError):
                continue
            except Exception as failure:  # noqa: BLE001 - reporting what escaped is the point
                where = ".".join(str(part) for part in path)
                crashes.append(f"{tag}.{where} = 0 -> {type(failure).__name__}: {failure}")
    return crashes, probes


def test_the_parameter_corpus_is_one_valid_document_per_registered_element():
    registry = element_registry()
    documents = _documents()
    assert set(documents) == set(registry)
    for tag, document in documents.items():
        registry[tag][0].model_validate(document)


def test_no_element_crashes_on_a_zero_anywhere_in_it():
    crashes, probes = _crashes()
    # The floor goes first: a corpus that lost its numbers would find nothing to crash on.
    assert probes >= 180, f"only {probes} numbers were zeroed"
    assert not crashes, "\n".join(crashes)


def test_the_sweep_finds_the_crash_a_missing_declaration_lets_through(monkeypatch):
    """The adversary: take `thickness` out of the lug's positive fields and the sweep must
    report the ZeroDivisionError it used to end `anvilate check` with."""
    from anvilate.packs.structural import LiftingLug

    monkeypatch.setattr(LiftingLug, "positive_fields", ())
    crashes, _probes = _crashes()
    assert any(
        crash.startswith("lifting_lug.thickness.magnitude = 0 -> ZeroDivisionError")
        for crash in crashes
    ), crashes


def test_a_document_cannot_declare_its_own_signed_fields():
    """`signed_fields` was a model field: a document could write `signed_fields: [width]`,
    have it accepted and echoed in every dump, while the guard ignored it. It is a class
    attribute now, so a document naming it is refused and no element schema publishes it."""
    import pytest

    from anvilate.contracts import element_json_schemas
    from anvilate.packs.structural import LiftingLug

    document = {**_documents()["lifting_lug"], "signed_fields": ["width"]}
    with pytest.raises(ValidationError, match="signed_fields"):
        LiftingLug.model_validate(document)
    assert LiftingLug.signed_fields == ("load",)
    schemas = element_json_schemas()
    assert not [tag for tag, schema in schemas.items() if "signed_fields" in str(schema)]
