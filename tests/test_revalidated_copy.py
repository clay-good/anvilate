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
    """Every class in the package declaring an invariant ``model_copy`` would bypass.

    A ``mode="after"`` model validator, or a ``field_validator``. Both are skipped by
    ``model_copy`` and both are restored by the re-validating base, so both are reasons to
    inherit it — and the gate below, which refuses a class that inherits the base and protects
    nothing, read only the first. `export.dxf.Hole` was the counterexample: its invariant is
    that a diameter is a positive length, one field at a time, and a rule stated per field is
    still a rule an update can break.

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
                    (
                        "model_validator" in ast.unparse(decorator)
                        and "after" in ast.unparse(decorator)
                    )
                    or "field_validator" in ast.unparse(decorator)
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


def _models_with_an_annotated_validator() -> list[tuple[str, str, list[str]]]:
    """Every model with a field whose *annotation* carries a validator.

    Read off the imported models rather than the source, and that is the point. The census
    above looks for a decorator in a file, and pydantic's other idiom for an invariant is
    ``Annotated[str, AfterValidator(...)]`` — which is how `Named` and `Provenance` are built
    in `_models.py`, and how `FrozenMap` freezes a mapping. A model whose whole invariant
    arrives through a shared type alias declared in another module has no decorator anywhere
    in its own file, so a source scan sees nothing to protect. Thirty-seven models were in
    that gap.

    Resolving the alias by AST would mean following an import to a module-level
    ``Annotated[...]`` assignment. `model_fields[...].metadata` already holds the answer.
    """
    found: list[tuple[str, str, list[str]]] = []
    for model in _every_model_class():
        fields = sorted(
            name
            for name, field in model.model_fields.items()
            if any(type(item).__name__.endswith("Validator") for item in field.metadata or ())
        )
        if fields:
            found.append((model.__module__, model.__qualname__, fields))
    return found


def _every_model_class() -> list[type]:
    """Every pydantic model the package defines, by importing all of it."""
    from pydantic import BaseModel

    found: dict[str, type] = {}
    for path in sorted(_SRC.rglob("*.py")):
        module_name = ".".join(("anvilate", *path.relative_to(_SRC).with_suffix("").parts))
        module_name = module_name.removesuffix(".__init__")
        module = importlib.import_module(module_name)
        for value in vars(module).values():
            if (
                isinstance(value, type)
                and issubclass(value, BaseModel)
                and value is not BaseModel
                and value.__module__.startswith("anvilate")
            ):
                found[f"{value.__module__}.{value.__qualname__}"] = value
    return [found[key] for key in sorted(found)]


def test_the_annotated_census_finds_the_models_it_is_meant_to_walk():
    """Without this the check below passes on a metadata read that matched nothing."""
    found = _models_with_an_annotated_validator()
    assert len(found) > 50, len(found)
    # `Named` is the alias this is really about, and `SectionStatus.name` is one of them.
    assert ("anvilate.bundle", "SectionStatus", ["name"]) in found


@pytest.mark.parametrize(
    ("module_name", "class_name", "fields"),
    [(m, c, f) for m, c, f in _models_with_an_annotated_validator()],
    ids=lambda value: value if isinstance(value, str) else ",".join(value),
)
def test_a_model_whose_invariant_is_in_its_annotation_revalidates_its_copies(
    module_name, class_name, fields
):
    """The same rule as above, for the invariants a decorator scan cannot see.

    Two things were getting through. `Named` and `Provenance` refuse a blank, so a copy could
    put an empty name on a section or an empty citation on a derivation — a blank provenance
    field in the library whose product is provenance. And `FrozenMap` is what makes a frozen
    model's mapping actually immutable: `model_copy` replaced a `mappingproxy` with a plain
    `dict`, which was then mutated in place. `frozen=True` stops attribute assignment;
    `FrozenMap` stops mutation *through* the value, and the copy dropped the second.
    """
    model = getattr(importlib.import_module(module_name), class_name)
    assert issubclass(model, RevalidatedModel), (
        f"{module_name}.{class_name} carries an invariant in the annotation of {fields}, and "
        f"`model_copy` walks straight past it. Inherit RevalidatedModel — see "
        f"anvilate/_models.py"
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
    """Nothing inherits the re-validating copy without an invariant to protect.

    Making every model in the library re-validate its copies would put a parse on paths used
    in loops, for nothing. The rule is opt-in *by declaration*, and this is that property
    stated over the whole package rather than over one example: the version before it named
    `ScorecardEntry`, which was the hottest copy path in the library right up until the
    entry acquired an invariant of its own, at which point a true statement about the rule
    read as a failure of it.
    """
    # Both censuses, because both kinds of declaration are a reason to inherit the base. Read
    # only the decorators and the thirty-seven models whose invariant arrives through an
    # `Annotated` alias look like models protecting nothing — this assertion would then refuse
    # the very fix the check above demands.
    declaring = {name for _, name in _classes_with_an_after_validator()}
    declaring |= {name for _, name, _fields in _models_with_an_annotated_validator()}
    inheriting = _model_classes_inheriting_the_base()
    assert len(inheriting) > 20, "the walk found almost nothing, so it proves almost nothing"
    without = sorted(
        f"{model.__module__}.{model.__qualname__}"
        for model in inheriting
        if not any(ancestor.__name__ in declaring for ancestor in model.__mro__)
    )
    assert not without, (
        "these re-validate every copy and declare no invariant anywhere in their "
        f"ancestry, so the parse buys nothing: {without}"
    )


def _model_classes_inheriting_the_base() -> list[type]:
    """Every ``RevalidatedModel`` subclass the package defines, by importing all of it."""
    found: dict[str, type] = {}
    for path in sorted(_SRC.rglob("*.py")):
        module_name = ".".join(("anvilate", *path.relative_to(_SRC).with_suffix("").parts))
        module_name = module_name.removesuffix(".__init__")
        module = importlib.import_module(module_name)
        for value in vars(module).values():
            if (
                isinstance(value, type)
                and issubclass(value, RevalidatedModel)
                and value is not RevalidatedModel
                and value.__module__.startswith("anvilate")
            ):
                found[f"{value.__module__}.{value.__qualname__}"] = value
    return list(found.values())


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


# --- what `Any` costs on the way back in ---------------------------------------------------
#
# `Any` is the one annotation pydantic cannot rebuild from. Everything else in this package
# carries enough type to reconstruct itself; an `Any` field hands back whatever JSON says,
# which for a Quantity is a two-key dictionary. There are three such fields, they are listed
# here by name, and a fourth appearing without a case below fails rather than shipping.


def _any_typed_fields():
    """Every ``(module, class, field)`` in the package whose annotation mentions ``Any``."""
    import pkgutil

    from pydantic import BaseModel

    import anvilate

    found: set[tuple[str, str, str]] = set()
    for info in pkgutil.walk_packages(anvilate.__path__, "anvilate."):
        try:
            module = importlib.import_module(info.name)
        except Exception:  # pragma: no cover - an optional dependency is absent
            continue
        for value in vars(module).values():
            if not (isinstance(value, type) and issubclass(value, BaseModel)):
                continue
            if not value.__module__.startswith("anvilate"):
                continue
            for name, field in value.model_fields.items():
                if "Any" in str(field.annotation):
                    found.add((value.__module__, value.__name__, name))
    assert found, "the walk imported no models, so this census checked nothing"
    return found


def _any_field_probes():
    """One instance per ``Any``-typed field, holding the values that field really carries."""
    from anvilate.compilation import CompilationTask
    from anvilate.mcp import tool_catalog
    from anvilate.screening import StructureMember
    from anvilate.spec import (
        AcceptanceCriteria,
        DesignSpec,
        Manufacturing,
        ManufacturingProcess,
        MaterialRef,
        Provenanced,
        ValidationTier,
    )
    from anvilate.units import Quantity, UnitSystem

    task = CompilationTask(
        task_id="t1",
        prompt="a bracket carrying 5 kN",
        reference={
            # The value that broke: dumped to {"magnitude", "unit"} and read back as that.
            "load_cases.0.force": Quantity.parse("5 kN"),
            # And the values that must survive *unconverted*, in both directions.
            "element.kind": "beam",
            "element.count": 3,
            "element.ratio": 1.5,
            "element.checked": True,
            "element.absent": None,
            "element.label": "5 kN",
            "element.shape": {"magnitude": "not a number", "unit": "kN"},
            "element.other": {"a": 1, "b": 2},
        },
    )
    tool = tool_catalog()[0]
    # A pack element's fields are quantities, numbers, strings and enum tags, so a spec
    # declaring one carries the same `Any` and needs the same repair.
    spec = DesignSpec(
        name="padeye",
        description="A lifting padeye.",
        units=Provenanced.stated(UnitSystem.SI),
        material=MaterialRef(ref="ASTM-A36"),
        manufacturing=Manufacturing(process=ManufacturingProcess.SHEET_METAL),
        element_type="lifting_lug",
        element_params={
            "name": "padeye",
            "material": "ASTM-A36",
            "width": Quantity.parse("120 mm"),
            "hole_diameter": Quantity.parse("40 mm"),
            "thickness": Quantity.parse("20 mm"),
            "load": Quantity.parse("60 kN"),
        },
        acceptance=AcceptanceCriteria(tiers=[ValidationTier.T1_ANALYTICAL]),
    )
    # A structure's members carry the same `Any` map one level further down, where the
    # spec's own repair does not reach: a member's quantities sit inside a list.
    member = StructureMember(
        element_type="lifting_lug",
        element_params={"name": "padeye", "load": Quantity.parse("60 kN"), "grade": "A36"},
    )
    return {
        ("anvilate.compilation", "CompilationTask", "reference"): task,
        ("anvilate.mcp", "ToolDefinition", "input_schema"): tool,
        ("anvilate.mcp", "ToolDefinition", "output_schema"): tool,
        ("anvilate.screening", "StructureMember", "element_params"): member,
        ("anvilate.spec.ir", "DesignSpec", "element_params"): spec,
    }


def test_every_any_typed_field_is_one_this_file_round_trips():
    """A census, so a fourth `Any` field cannot land with nothing holding it."""
    assert _any_typed_fields() == set(_any_field_probes()), (
        "the Any-typed fields in the package and the ones probed below have diverged: "
        f"unprobed {sorted(_any_typed_fields() - set(_any_field_probes()))}, "
        f"probed but gone {sorted(set(_any_field_probes()) - _any_typed_fields())}"
    )


@pytest.mark.parametrize(("where", "instance"), sorted(_any_field_probes().items()))
def test_a_model_reads_back_what_it_writes(where, instance):
    """The defect: a task set this library wrote could not be read back as itself.

    `CompilationTask.reference` is typed `Any` because a spec field can be a string, a number
    or a quantity. A task stating `force` as `5 kN` dumped to `{"magnitude": 5.0, "unit":
    "kN"}` and read back as exactly that dictionary — so the reloaded task did not compare
    equal to the one it was written from, and every report scored against it rendered its own
    expected value as `{'magnitude': 5.0, 'unit': 'kN'}` where the original printed `5 kN`.
    The *verdict* was right either way, because `_compare` already recognises that shape as a
    quantity, which is exactly what kept it quiet.
    """
    model = type(instance)
    assert model.model_validate(instance.model_dump()) == instance, f"{where} via model_dump"
    assert model.model_validate_json(instance.model_dump_json()) == instance, f"{where} via JSON"


def test_only_the_serialisers_own_shape_is_rebuilt():
    """The other half: the repair must not turn every mapping into a quantity.

    Two-key and unparseable, three-key, and a string that *would* parse — a task stating
    `"5 kN"` as a string is asking for a string, and answering with a quantity would be
    scoring a different question than the task asked.
    """
    from anvilate.compilation import CompilationTask
    from anvilate.units import Quantity

    task = _any_field_probes()[("anvilate.compilation", "CompilationTask", "reference")]
    for reloaded in (
        CompilationTask.model_validate(task.model_dump()),
        CompilationTask.model_validate_json(task.model_dump_json()),
    ):
        reference = reloaded.reference
        assert isinstance(reference["load_cases.0.force"], Quantity)
        assert reference["element.label"] == "5 kN"
        assert not isinstance(reference["element.label"], Quantity)
        assert reference["element.shape"] == {"magnitude": "not a number", "unit": "kN"}
        assert reference["element.other"] == {"a": 1, "b": 2}
        assert reference["element.count"] == 3 and reference["element.checked"] is True
        assert reference["element.absent"] is None


def test_a_blank_name_cannot_be_copied_onto_a_model_that_refuses_one():
    """A probe for the `Named` shape, because the census cannot see a base that does nothing.

    `Named` is `Annotated[str, AfterValidator(refuse_a_blank)]`, so the rule lives in the
    annotation and no decorator names it. A copy put `'   '` on a bundle section's name, and
    `Provenance` behaves the same way — which in this library means a copy could blank the
    citation on a `Derivation`, in the package whose product is provenance.
    """
    from anvilate.bundle import SectionStatus
    from anvilate.evidence import SourceRecord
    from anvilate.scorecard import CheckStatus

    section = SectionStatus(name="checks", status=CheckStatus.PASS, detail="2 run, 0 failing")
    with pytest.raises(ValidationError):
        section.model_copy(update={"name": "   "})
    assert section.model_copy(update={"name": "verification"}).name == "verification"

    record = SourceRecord(
        ref="AISC-360", kind="material", name="AISC 360-22", sources=("bundled table",)
    )
    with pytest.raises(ValidationError):
        record.model_copy(update={"ref": ""})


def test_a_copy_cannot_unfreeze_a_frozen_mapping():
    """The `FrozenMap` shape, and the sharper of the two.

    `frozen=True` stops attribute assignment; `FrozenMap`'s validator is what stops mutation
    *through* the value, by wrapping the mapping in a `MappingProxyType`. `model_copy` runs no
    validators, so it handed back a plain `dict` in a frozen model's field — and it could then
    be mutated in place. An "immutable" object whose contents change is worse than a mutable
    one, because every reader has been told it cannot.
    """
    from types import MappingProxyType

    from anvilate.screening import StructureMember

    member = StructureMember(element_type="lifting_lug", element_params={"width": 120.0})
    assert isinstance(member.element_params, MappingProxyType)

    copied = member.model_copy(update={"element_params": {"width": 200.0}})
    assert isinstance(copied.element_params, MappingProxyType), (
        "the copy handed back a plain dict, so a frozen model's mapping is mutable again"
    )
    with pytest.raises(TypeError):
        copied.element_params["injected"] = 99  # type: ignore[index]
    assert dict(copied.element_params) == {"width": 200.0}
