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


# The main corpus leaves every optional field at its default, so a sweep over it never
# reaches one: a zero `hole_diameter` refused as "the hole (0 mm) must be smaller than the
# plate", and a beam's shear entry vanishing under an off-centre load, were both found by
# hand. Each variant here fills optional fields of one element.
_OPTIONAL = Path(__file__).resolve().parent / "element_params_optional.json"


def _corpus() -> list[tuple[str, str, dict]]:
    """Every document the sweeps read, as (label, element_type, element_params)."""
    corpus = [(tag, tag, document) for tag, document in sorted(_documents().items())]
    variants = json.loads(_OPTIONAL.read_text(encoding="utf-8"))
    corpus += [
        (label, variant["element_type"], variant["element_params"])
        for label, variant in sorted(variants.items())
    ]
    return corpus


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
    crashes, probes = [], 0
    for tag, element_type, document in _corpus():
        model, screen = registry[element_type]
        parameters = inspect.signature(screen).parameters
        keywords = {"required_safety_factor": 2.0} if "required_safety_factor" in parameters else {}
        for path in _numbers(document):
            probes += 1
            try:
                element = model.model_validate(_with(document, path, 0))
            except (ValidationError, ValueError, LookupError):
                continue
            try:
                screen(element, **keywords)
            except ValidationError as failure:
                # A pydantic error from inside a screen is the screen building one of its
                # own models wrongly: a zero required life put `None` into a derivation's
                # SymbolValue and reached the card as "Input should be a valid dictionary
                # or instance of Quantity". It is a ValueError, so it used to pass as a
                # refusal here.
                where = ".".join(str(part) for part in path)
                crashes.append(f"{tag}.{where} = 0 -> {type(failure).__name__}: {failure}")
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


# The one refusal that does not name the field it refuses, and why that is right.
_UNNAMED = {
    "spur_gear_mesh.pinion_torque.magnitude=0": (
        "a zero torque is no demand, and the gear screen says 'torque is zero' and that there "
        "is nothing to evaluate"
    ),
}


def _refusals_not_naming_the_field() -> tuple[list[str], int]:
    registry = element_registry()
    unnamed, probes = [], 0
    for tag, element_type, document in _corpus():
        model, screen = registry[element_type]
        parameters = inspect.signature(screen).parameters
        keywords = {"required_safety_factor": 2.0} if "required_safety_factor" in parameters else {}
        for path in _numbers(document):
            value = document
            for part in path:
                value = value[part]
            for changed in (0, -abs(value) if value else -1):
                probes += 1
                message = None
                try:
                    element = model.model_validate(_with(document, path, changed))
                except ValidationError as refusal:
                    message = "; ".join(error["msg"] for error in refusal.errors())
                except (ValueError, LookupError) as refusal:
                    message = str(refusal)
                if message is None:
                    try:
                        screen(element, **keywords)
                    except (ValueError, LookupError) as refusal:
                        message = str(refusal)
                names = [part for part in path if isinstance(part, str) and part != "magnitude"]
                if message is None or not names:
                    continue
                field = names[-1]
                if field not in message and field.replace("_", " ") not in message:
                    where = ".".join(str(part) for part in path)
                    unnamed.append(f"{tag}.{where}={changed}")
    return unnamed, probes


def test_a_refusal_names_the_field_the_document_wrote():
    """interaction-quality 7.3 at the element front door. A refused number used to be named
    by the analysis function's parameter, not by the document's field: a zero or negative
    `load_power` was refused as "real_power and line_voltage must be positive", and a zero
    `electrode_strength` as "allowable_shear must be positive". A person holding the YAML
    has no `real_power` to fix. Each number is set to zero and to its negative in turn."""
    unnamed, probes = _refusals_not_naming_the_field()
    assert probes >= 380, f"only {probes} numbers were changed"
    assert sorted(unnamed) == sorted(_UNNAMED), (
        f"refused without naming the field: {sorted(set(unnamed) - set(_UNNAMED))}; listed "
        f"as unnamed but now named: {sorted(set(_UNNAMED) - set(unnamed))}"
    )


def test_every_optional_variant_is_a_valid_document_of_its_element():
    registry = element_registry()
    variants = json.loads(_OPTIONAL.read_text(encoding="utf-8"))
    assert len(variants) >= 11, f"only {len(variants)} optional variants"
    for label, variant in variants.items():
        assert label.startswith(variant["element_type"] + "/"), label
        registry[variant["element_type"]][0].model_validate(variant["element_params"])
