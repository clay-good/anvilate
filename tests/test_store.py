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


def _file_at_its_own_digest(root, text: str) -> str:
    """Put ``text`` in the store under the handle its own bytes hash to, and return it.

    Every entry the store refuses on its *shape* has to be written this way now. Corrupting
    a published file instead makes it fail the address check, which fires first — so a test
    that corrupts one is testing the address check under the name of something else.
    """
    from anvilate.attestation import sha256_hex

    digest = sha256_hex(text.encode("utf-8"))
    path = Path(root) / digest[:2] / f"{digest}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return f"sha256:{digest}"


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
    #
    # **Filed at its own digest**, or the entry no longer hashes to the handle and the
    # address check refuses it first — which is what this line used to do, so the guard it
    # names was never reached. An unreadable entry is only reachable as a file whose bytes
    # are self-consistently addressed and are not JSON, and that is what this writes.
    with pytest.raises(UnknownSubject, match="not readable JSON"):
        store.resolve(_file_at_its_own_digest(tmp_path, "{not json"))


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


def test_an_entry_that_is_not_utf8_text_refuses_rather_than_raising_past_the_caller(tmp_path):
    """One layer above the unreadable-JSON case, and the same trap its comment describes.

    `resolve` guards the read against `OSError` and the parse against `ValueError`.
    `UnicodeDecodeError` is raised in between — by `read_text`, on the way from bytes to text
    — and descends from `ValueError` rather than `OSError`, so it went past both and out of
    `resolve` unwrapped. A caller handling `UnknownSubject` is every MCP tool in this package,
    and an entry some outside process truncated mid-write would have 500'd a tool call instead
    of refusing it.
    """
    store = SubjectStore(tmp_path)
    handle = store.publish("scorecard", {"status": "pass"})
    next(Path(tmp_path).rglob("*.json")).write_bytes(b"\xff\xfe{\x00}\x00")
    with pytest.raises(UnknownSubject, match="is not UTF-8 text"):
        store.resolve(handle)


def test_an_entry_that_no_longer_hashes_to_its_handle_is_refused(tmp_path):
    """The invariant the class is named for, checked where documents are read.

    `publish` writes the bytes and takes the handle from them, and its own docstring says a
    store whose files change under a handle is not content-addressed — held on the writing
    side and nowhere else. Everything `resolve` checked was the entry's *shape*: present,
    decodable, readable, the right kind. A stored scorecard whose verdict was edited from
    `fail` to `pass` still resolved under the handle it was published as, and every reader of
    that handle served the edit — `read_scorecard` returns the record's document as stored
    rather than a re-serialisation of it, and an exported evidence bundle is built from the
    same record.
    """
    store = SubjectStore(tmp_path)
    handle = store.publish("scorecard", {"status": "fail", "entries": []})
    entry = next(Path(tmp_path).rglob("*.json"))
    original = entry.read_text(encoding="utf-8")
    assert store.resolve(handle)["status"] == "fail"

    entry.write_text(original.replace('"fail"', '"pass"'), encoding="utf-8")
    assert entry.read_text(encoding="utf-8") != original, "the edit did not take"
    with pytest.raises(UnknownSubject, match="no longer holds the document the handle names"):
        store.resolve(handle)

    # A byte is a byte. An editor adding a trailing newline changes the entry under its
    # handle as surely as changing the verdict does, and a check that normalised whitespace
    # away before comparing would wave it through.
    entry.write_text(original + "\n", encoding="utf-8")
    with pytest.raises(UnknownSubject, match="no longer holds the document the handle names"):
        store.resolve(handle)

    # Restoring the bytes restores the handle: the check is on the content, not a flag.
    entry.write_text(original, encoding="utf-8")
    assert store.resolve(handle)["status"] == "fail"


def test_a_self_consistent_record_that_is_not_one_is_refused_by_shape(tmp_path):
    """The two shape failures below the address check, each written at its own digest.

    `record["document"]` was a bare subscript: a KeyError, which is not an `UnknownSubject`
    and so left `resolve` past every caller handling one — the one line in this method that
    had not been given the treatment the two guards above it were written for.
    """
    store = SubjectStore(tmp_path)
    with pytest.raises(UnknownSubject, match="carries no 'document'"):
        store.resolve(_file_at_its_own_digest(tmp_path, '{"kind":"scorecard"}'))
    with pytest.raises(UnknownSubject, match="holds a JSON list, not a record"):
        store.resolve(_file_at_its_own_digest(tmp_path, "[1,2]"))
