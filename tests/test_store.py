"""The content-addressed store an MCP tool resolves its subject from.

The store is what option C of `resolve-mcp-tool-subjects` costs, so what it promises is what
has to be held: a handle names the bytes, publishing is atomic and idempotent, and a handle
either gives you the document it names or a refusal saying why — never something else.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from anvilate.store import SUBJECT_PATTERN, SubjectStore, UnknownSubject, subject_store_root


def test_a_handle_names_the_bytes(tmp_path):
    """Content addressing, not a counter: the same document publishes to the same handle from
    a different store object, and a different document does not."""
    store = SubjectStore(tmp_path)
    handle = store.publish("scorecard", {"status": "pass", "entries": []})
    assert handle.startswith("sha256:") and len(handle) == 71

    again = SubjectStore(tmp_path).publish("scorecard", {"entries": [], "status": "pass"})
    assert again == handle, "key order changed the handle; the JSON is not canonical"
    assert store.publish("scorecard", {"status": "fail", "entries": []}) != handle
    # The kind is part of the name, so the same bytes under two kinds are two handles.
    assert store.publish("design-spec", {"status": "pass", "entries": []}) != handle


def test_publishing_twice_leaves_the_entry_alone(tmp_path):
    """A store whose file changes under a handle is not content-addressed. Held by writing a
    marker into the entry and watching a re-publish leave it there."""
    store = SubjectStore(tmp_path)
    handle = store.publish("scorecard", {"status": "pass"})
    entry = next(Path(tmp_path).rglob("*.json"))
    written = entry.stat().st_mtime_ns
    entry.write_text(json.dumps({"kind": "scorecard", "document": {"status": "pass"}, "x": 1}))
    assert store.publish("scorecard", {"status": "pass"}) == handle
    assert json.loads(entry.read_text())["x"] == 1, "the re-publish rewrote the entry"
    assert written  # the first write happened at all


def test_a_handle_gives_the_document_or_says_why_not(tmp_path):
    """Three ways to get nothing back, and each says which — because 'this handle gives you no
    document' covers an absent entry, an unreadable one and a handle to another kind, and a
    caller acts differently on each."""
    store = SubjectStore(tmp_path)
    handle = store.publish("scorecard", {"status": "pass"})
    assert store.resolve(handle) == {"status": "pass"}
    assert store.resolve(handle, kind="scorecard") == {"status": "pass"}

    with pytest.raises(UnknownSubject, match="names a 'scorecard'"):
        store.resolve(handle, kind="design-spec")

    with pytest.raises(UnknownSubject, match="is not in the subject store"):
        store.resolve("sha256:" + "0" * 64)

    # Present and unreadable is not the same fact as absent, and a raw JSONDecodeError here
    # would raise straight past a caller handling UnknownSubject.
    next(Path(tmp_path).rglob("*.json")).write_text("{not json")
    with pytest.raises(UnknownSubject, match="not readable JSON"):
        store.resolve(handle)


@pytest.mark.parametrize(
    "handle",
    [
        "",
        "the last one",
        "sha1:" + "a" * 40,
        "sha256:" + "A" * 64,  # the pattern is lowercase hex
        "sha256:../" + "a" * 61,  # a path, not a digest
        "sha256:" + "a" * 63,
    ],
)
def test_a_handle_that_is_not_one_never_reaches_the_filesystem(handle, tmp_path):
    """The store builds a path out of caller input, so the shape is checked before the path
    is. `../` is in the list because that is the way this goes wrong."""
    import re

    assert re.match(SUBJECT_PATTERN, handle) is None
    with pytest.raises(UnknownSubject, match="is not a subject handle"):
        SubjectStore(tmp_path).resolve(handle)


def test_the_root_is_resolved_in_one_place(monkeypatch, tmp_path):
    """Explicit, then the environment, then the cache — one function, so an operator pointing
    several instances at one directory and the tests keeping out of the user's cache are
    saying the same thing."""
    monkeypatch.setenv("ANVILATE_SUBJECT_STORE", str(tmp_path / "named"))
    assert subject_store_root() == tmp_path / "named"
    assert subject_store_root(tmp_path / "explicit") == tmp_path / "explicit"

    monkeypatch.delenv("ANVILATE_SUBJECT_STORE")
    assert subject_store_root().name == "subjects"

    with pytest.raises(ValueError, match="not the current directory"):
        subject_store_root("")


def test_a_record_names_its_kind(tmp_path):
    """A handle to 'something' is a handle whose consumer cannot refuse the wrong document."""
    with pytest.raises(ValueError, match="must name its kind"):
        SubjectStore(tmp_path).publish("   ", {"a": 1})
