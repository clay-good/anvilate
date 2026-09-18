"""An interrupted export leaves no partial artifact presented as complete (IQ 7.2)."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from conftest import parsed_source

_SRC = Path(__file__).resolve().parents[1] / "src" / "anvilate"


def test_an_interrupted_write_leaves_the_old_file_and_no_partial_one(tmp_path: Path) -> None:
    from anvilate.export.dxf import _atomic_path

    target = tmp_path / "plate.dxf"
    target.write_text("the drawing that was there")
    with pytest.raises(KeyboardInterrupt), _atomic_path(target) as partial:
        partial.write_text("half a draw")
        raise KeyboardInterrupt
    assert target.read_text() == "the drawing that was there"
    assert sorted(p.name for p in tmp_path.iterdir()) == ["plate.dxf"]
    with _atomic_path(target) as partial:
        partial.write_text("the whole new drawing")
    assert target.read_text() == "the whole new drawing"
    assert sorted(p.name for p in tmp_path.iterdir()) == ["plate.dxf"]


def test_every_dxf_write_goes_through_the_atomic_path() -> None:
    tree = parsed_source(_SRC / "export" / "dxf.py")
    saves = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "saveas"
    ]
    assert len(saves) >= 3, f"found only {len(saves)} saveas calls"
    for call in saves:
        (argument,) = call.args
        assert isinstance(argument, ast.Name) and argument.id == "partial", ast.dump(call)


def test_the_step_writer_removes_its_file_on_an_interrupt_too() -> None:
    """`except Exception` lets a KeyboardInterrupt past the cleanup that deletes the file."""
    tree = ast.parse((_SRC / "geometry.py").read_text(encoding="utf-8"))
    (writer,) = [
        n
        for n in ast.walk(tree)
        if isinstance(n, ast.FunctionDef) and n.name == "_write_step_shape"
    ]
    cleanups = [
        handler
        for node in ast.walk(writer)
        if isinstance(node, ast.Try)
        for handler in node.handlers
        if any(
            isinstance(c, ast.Call)
            and isinstance(c.func, ast.Attribute)
            and c.func.attr == "unlink"
            for c in ast.walk(handler)
        )
    ]
    assert cleanups, "the STEP writer no longer removes a failed file"
    for handler in cleanups:
        assert isinstance(handler.type, ast.Name) and handler.type.id == "BaseException"
