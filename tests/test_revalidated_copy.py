"""Every model that declares an invariant keeps it across ``model_copy``.

Pydantic runs no ``mode="after"`` validator on a copy, so a model that refuses to be
*constructed* in a broken state could still be *copied* into one — and the result is a
fully typed instance every downstream check accepts. This library found that three times in
three unrelated modules and fixed it three times with the same comment, so it is one base
class now (:class:`anvilate._models.RevalidatedModel`) and this file is the ratchet.

The two halves matter separately. The **census** below fails when a new model declares an
after-validator without the base, which is the drift that put the hole in three modules.
The **probes** fail when the base stops working, which a census can never see: a base class
that returned `super().model_copy(...)` unchanged would satisfy every inheritance check in
this file.
"""

from __future__ import annotations

import ast
import importlib
import pathlib

import pytest
from pydantic import ValidationError

from anvilate._models import RevalidatedModel

_SRC = pathlib.Path(__file__).resolve().parent.parent / "src" / "anvilate"


def _classes_with_an_after_validator() -> list[tuple[str, str]]:
    """Every class in the package declaring a ``mode="after"`` model validator.

    Read out of the source rather than off the imported classes, because a validator
    inherited from a base is not the thing this gate is about: the question is which classes
    *declare* an invariant, and a declaration is a decorator in a file.
    """
    found: list[tuple[str, str]] = []
    for path in sorted(_SRC.rglob("*.py")):
        module = ".".join(("anvilate", *path.relative_to(_SRC).with_suffix("").parts))
        module = module.removesuffix(".__init__")
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if not isinstance(node, ast.ClassDef):
                continue
            declares = any(
                isinstance(item, ast.FunctionDef)
                and any(
                    "model_validator" in ast.unparse(decorator)
                    and "after" in ast.unparse(decorator)
                    for decorator in item.decorator_list
                )
                for item in node.body
            )
            if declares:
                found.append((module, node.name))
    return found


def test_the_census_finds_the_models_it_is_meant_to_walk():
    """Without this the file passes on an AST walk that matched nothing."""
    found = _classes_with_an_after_validator()
    assert len(found) > 50, found
    assert ("anvilate.uncertainty", "Normal") in found


@pytest.mark.parametrize(("module_name", "class_name"), _classes_with_an_after_validator())
def test_every_model_with_an_invariant_revalidates_its_copies(module_name, class_name):
    model = getattr(importlib.import_module(module_name), class_name)
    assert issubclass(model, RevalidatedModel), (
        f"{module_name}.{class_name} declares an after-validator that `model_copy` walks "
        f"straight past. Inherit RevalidatedModel — see anvilate/_models.py"
    )


# --- the base actually does something ----------------------------------------------------
#
# A census cannot see a base class that re-validates nothing. Each probe below builds a real
# model from the library, copies it into a state its own constructor refuses, and requires
# the copy to raise.


def _probes():
    from anvilate.gdt import Characteristic, FeatureControlFrame, FeatureType
    from anvilate.uncertainty import Normal
    from anvilate.units import Quantity

    frame = FeatureControlFrame(
        characteristic=Characteristic.FLATNESS,
        tolerance=Quantity.parse("0.1 mm"),
        feature_type=FeatureType.SURFACE,
    )
    return [
        ("Normal", Normal(mean=1.0, std=0.5), {"std": -1.0}, "non-negative"),
        ("FeatureControlFrame", frame, {"characteristic": Characteristic.POSITION}, "datum"),
    ]


@pytest.mark.parametrize(
    ("label", "model", "update", "expected"),
    [(label, model, update, expected) for label, model, update, expected in _probes()],
)
def test_a_copy_into_a_state_the_constructor_refuses_is_refused(label, model, update, expected):
    with pytest.raises(ValidationError, match=expected):
        model.model_copy(update=update)


def test_a_copy_with_no_update_does_not_revalidate():
    """The other half: the base must not have turned every copy into a re-parse.

    A copy with no update is the same field values, so it cannot have moved — and paying to
    re-validate it would make `model_copy()` quietly expensive on a path used in loops. The
    first version of this test compared the copy to the original, which is true either way:
    deleting the early return kept every assertion passing. It counts the validator instead.
    """
    from pydantic import model_validator

    runs = []

    class _Counted(RevalidatedModel):
        value: int

        @model_validator(mode="after")
        def _count(self) -> _Counted:
            runs.append(self.value)
            return self

    original = _Counted(value=1)
    assert runs == [1]
    assert original.model_copy() == original
    assert runs == [1], "a copy with no update re-validated, which it has no reason to do"
    assert original.model_copy(update={"value": 2}).value == 2
    assert runs == [1, 2], "a copy WITH an update must re-validate"


def test_the_base_is_not_paid_for_by_models_with_no_invariant():
    """`ScorecardEntry` is copied per check in every pack, and declares no after-validator.

    Making every model in the library re-validate its copies would put a parse on that path
    for nothing. The rule is opt-in by declaration, and this pins that it stayed opt-in.
    """
    from anvilate.scorecard import ScorecardEntry

    assert not issubclass(ScorecardEntry, RevalidatedModel)


# --- frozen means frozen ------------------------------------------------------------------
#
# `ConfigDict(frozen=True)` stops a field being *rebound*. It does not reach inside the
# value, so a `dict` field on a frozen model is writable by anyone holding the model, and
# the writes land after every validator has run.


def test_a_frozen_models_mapping_field_refuses_writes():
    """The defect that motivated `FrozenMap`, in the module where it did real damage.

    `CompilationTask.reference` names the spec fields a correct compilation must carry. Its
    constructor refuses a task naming none — the whole point, since every output including
    an empty one would then score fully correct. But `del task.reference["material"]` on a
    *frozen* task turned a compilation that got the material wrong into one scoring 1 of 1
    fields, which is the wrong-but-valid case the module exists to report.
    """
    from anvilate.compilation import CompilationTask, score_candidate

    task = CompilationTask(
        task_id="lug", prompt="a lug", reference={"name": "lug", "material": "ASTM-A36"}
    )
    honest = score_candidate(task, {"name": "lug", "material": "wrong"})
    assert (honest.correct_fields, len(honest.fields)) == (1, 2)
    assert honest.wrong_but_valid

    # A mappingproxy has no `__delitem__` or `clear` at all, and refuses `__setitem__` with
    # a TypeError. All three are the same answer for a caller: the write does not happen.
    for attack in (
        lambda: task.reference.__delitem__("material"),
        lambda: task.reference.__setitem__("material", "wrong"),
        lambda: task.reference.clear(),
        lambda: task.reference.update({"material": "wrong"}),
    ):
        with pytest.raises((TypeError, AttributeError)):
            attack()
    assert len(score_candidate(task, {"name": "lug", "material": "wrong"}).fields) == 2


def _frozen_models_with_a_mapping_field():
    """Every frozen model in the package carrying a mapping-shaped field."""
    import importlib
    import pkgutil

    from pydantic import BaseModel

    import anvilate

    found: list[tuple[type, str]] = []
    seen: set[type] = set()
    for info in pkgutil.walk_packages(anvilate.__path__, "anvilate."):
        try:
            module = importlib.import_module(info.name)
        except Exception:  # pragma: no cover - an optional dependency is absent
            continue
        for value in vars(module).values():
            if not (isinstance(value, type) and issubclass(value, BaseModel)):
                continue
            if value in seen or not value.model_config.get("frozen"):
                continue
            seen.add(value)
            for name, field in value.model_fields.items():
                annotation = str(field.annotation)
                if annotation.startswith(("dict[", "Mapping[", "collections.abc.Mapping[")):
                    found.append((value, name))
    assert seen, "the walk imported no models, so this gate checked nothing"
    return found


@pytest.mark.parametrize(
    ("model", "field"),
    [(model, field) for model, field in _frozen_models_with_a_mapping_field()],
)
def test_every_frozen_mapping_field_is_a_frozen_mapping(model, field):
    """The census, so a new `dict` field on a frozen model cannot land unfrozen.

    `anvilate.mcp.ToolDefinition` is the one exemption and it is a real one: its two fields
    hold arbitrarily nested JSON Schema documents, where freezing the top level would read
    as a guarantee it does not make. That module holds them a different way — a fresh
    catalog per call, and a deep copy on the way out — and its docstring says so.
    """
    from types import MappingProxyType

    if model.__module__ == "anvilate.mcp":
        pytest.skip("nested JSON documents; see the docstring above and mcp.ToolDefinition")
    built = model.model_construct()
    example = getattr(built, field, None)
    annotation = str(model.model_fields[field].annotation)
    assert annotation.startswith(("Mapping[", "collections.abc.Mapping[")), (
        f"{model.__module__}.{model.__name__}.{field} is a bare dict on a frozen model, so "
        f"anyone holding the model can write to it after every validator has run. Use "
        f"FrozenMap from anvilate._models"
    )
    assert example is None or isinstance(example, MappingProxyType)


def test_the_frozen_mapping_census_is_looking_at_something():
    found = _frozen_models_with_a_mapping_field()
    assert len(found) >= 9, found
    assert any(model.__module__ == "anvilate.interop" for model, _ in found)


def test_a_frozen_mapping_still_serializes_as_a_plain_object():
    """The freeze must be invisible downstream, or it is a breaking change wearing a fix."""
    import json

    from anvilate.compilation import CompilationTask

    task = CompilationTask(task_id="t", prompt="p", reference={"name": "x"})
    assert task.model_dump() == {
        "task_id": "t",
        "prompt": "p",
        "reference": {"name": "x"},
        "notes": None,
    }
    assert json.loads(task.model_dump_json())["reference"] == {"name": "x"}
    assert CompilationTask.model_validate(task.model_dump()) == task
