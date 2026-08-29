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
