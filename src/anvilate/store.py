"""The content-addressed store an MCP tool resolves its subject from.

Four of the published tools named nothing in their input to act on — `render_viewport` an
image of *what*, `read_scorecard` a scorecard of *what* — and each was asking the server to
remember what the last call produced. That is a session, and `headless-automation` requires
the server to operate statelessly. Three ways to resolve the contradiction were set out in
`openspec/changes/archive/2026-09-01-resolve-mcp-tool-subjects`, and this is the third: **a
tool returns a handle to what it produced, and a later tool takes that handle as its
subject.**

What the choice buys, said plainly, because the alternatives each bought something too:

* **No per-connection memory.** Any instance can serve any call and a reconnect loses
  nothing, which is what "stateless" means in the requirement — as against a session, where
  a reconnect starts over and two processes behind a load balancer are not interchangeable.
* **The payload stays off the wire.** A handle is 71 bytes; the alternative was sending the
  whole geometry on every call, and `read_scorecard(scorecard)` — a tool that returns its own
  argument, which is not an operation.

And what it costs, which is a dependency rather than a detail: **the store has to exist, be
reachable by every instance that serves a handle, and have a stated retention policy.** All
three are here rather than assumed.

**Where it lives.** ``$ANVILATE_SUBJECT_STORE`` if set, else ``subjects/`` under the same
cache root the dataset cache uses. One file per handle. "Reachable by every instance" is a
filesystem claim, not a network one: this package ships a stdio server, so every instance is
a process on one machine, and a deployment that spreads instances across machines must point
them at one shared directory — the environment variable is how, and a handle that does not
resolve is refused rather than guessed at.

**What a handle is.** ``sha256:`` and the digest of the canonical JSON of the record — the
same content addressing the evidence bundles already use, so a handle is a name for the
bytes and not a key into a table. Two calls that produce the same document produce the same
handle, and a store that already holds it is left alone.

**What lands in it, which is the part worth saying out loud.** The documents themselves — a
compiled Design Spec, a screened scorecard. A spec is somebody's design: dimensions, loads,
materials, the part's name. Publishing a handle writes that document to disk under the cache
root, where it stays until the directory is removed. Nothing leaves the machine and nothing
is sent anywhere, but "the server remembers nothing" is a claim about the *protocol*, not
about the filesystem, and a reader is owed the difference. Point
``$ANVILATE_SUBJECT_STORE`` somewhere deliberate to keep the documents where you want them,
and delete the directory to clear them.

**Retention.** Nothing here evicts anything. The directory may be deleted at any time,
whole or in part, and the only consequence is that a handle stops resolving: `resolve`
raises :class:`UnknownSubject` naming it. There is no path by which a missing entry becomes a
*wrong* answer, which is the property that matters for a store a screening result is read
back out of. A caller that needs the record to outlive the cache should keep the document it
published, not the handle.
"""

from __future__ import annotations

import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any

from .attestation import canonical_json, sha256_hex
from .fetch import cache_root

__all__ = [
    "SUBJECT_PATTERN",
    "SubjectStore",
    "UnknownSubject",
    "subject_store",
    "subject_store_root",
]

# The shape of a handle, published in the tool schemas so a client is refused a malformed one
# by the argument checker rather than by the store.
SUBJECT_PATTERN = r"^sha256:[0-9a-f]{64}$"
_SUBJECT = re.compile(SUBJECT_PATTERN)


class UnknownSubject(KeyError):
    """A handle the store does not hold — an expired entry, a wrong digest, another store."""


def subject_store_root(explicit: str | Path | None = None) -> Path:
    """Where handles resolve: ``explicit``, else ``$ANVILATE_SUBJECT_STORE``, else the cache.

    One function, so the server, the tests and an operator pointing several instances at one
    directory all agree about the answer.
    """
    if explicit is not None:
        if str(explicit) == "":
            raise ValueError(
                "an empty store path is not the current directory: pass a real path, or "
                "None to use $ANVILATE_SUBJECT_STORE or the default cache"
            )
        return Path(explicit)
    named = os.environ.get("ANVILATE_SUBJECT_STORE")
    if named:
        return Path(named)
    return cache_root() / "subjects"


class SubjectStore:
    """Documents addressed by the digest of their own content.

    ``kind`` travels with the record so a tool can refuse a handle to the wrong sort of
    document — reading a scorecard from a handle to a spec is a mistake worth naming, and
    without the kind it would be a schema failure three layers down.
    """

    def __init__(self, root: str | Path | None = None) -> None:
        self._root = subject_store_root(root)

    def publish(self, kind: str, document: Any) -> str:
        """Store ``document`` under its own digest and return the handle.

        Idempotent by construction: the same document publishes to the same handle, and an
        entry already present is left exactly as it is rather than rewritten — a store whose
        files change under a handle is not content-addressed.
        """
        if not kind.strip():
            raise ValueError("a stored record must name its kind; a handle to 'something' is")
        payload = canonical_json({"kind": kind, "document": document})
        handle = f"sha256:{sha256_hex(payload.encode('utf-8'))}"
        path = self._path(handle)
        if path.exists():
            return handle
        path.parent.mkdir(parents=True, exist_ok=True)
        # Written to a temporary file in the same directory and renamed, so a run killed
        # mid-write leaves no half-file that reads as a record. `os.replace` is atomic on
        # every platform this ships to.
        with tempfile.NamedTemporaryFile(
            "w", dir=path.parent, delete=False, encoding="utf-8"
        ) as scratch:
            scratch.write(payload)
            scratch.flush()
            os.fsync(scratch.fileno())
            temporary = Path(scratch.name)
        os.replace(temporary, path)
        return handle

    def resolve(self, handle: str, *, kind: str | None = None) -> Any:
        """The document a handle names, or :class:`UnknownSubject` saying it is not here.

        ``kind`` refuses a handle to the wrong sort of document by name. Passing it is how a
        tool says what it is asking for; omitting it returns whatever the handle holds.
        """
        if not _SUBJECT.match(handle):
            raise UnknownSubject(
                f"{handle!r} is not a subject handle; a handle is 'sha256:' and 64 hex digits"
            )
        path = self._path(handle)
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError as unreadable:
            # The same fact as unreadable JSON, one layer earlier: an entry that is present
            # and undecodable. `UnicodeDecodeError` is a `ValueError` and not an `OSError`, so
            # it went past both guards below and out of `resolve` unwrapped — which is exactly
            # the trap the comment below describes, and it would 500 an MCP tool call instead
            # of refusing it.
            raise UnknownSubject(
                f"{handle} is in the subject store at {self._root} and is not UTF-8 text: "
                f"{unreadable}. Publishing is atomic and writes UTF-8, so this is a file "
                f"something outside this library wrote; delete it and publish the document "
                f"again"
            ) from unreadable
        except OSError as missing:
            raise UnknownSubject(
                f"{handle} is not in the subject store at {self._root}. A handle resolves "
                f"only where its document was published, and nothing here evicts an entry — "
                f"so this is a store that never held it, or one whose directory was removed"
            ) from missing
        # **The address, against the content it addresses.** Everything above this line
        # checks the entry's *shape* — present, decodable, readable, the right kind — and
        # the docstrings all reason from "this is a file something outside this library
        # wrote". The one thing that mattered about such a file was the one thing nothing
        # looked at: whether it still hashes to the handle it is filed under. `publish`
        # writes these bytes and computes the handle from them, and its own docstring says
        # a store whose files change under a handle is not content-addressed — an invariant
        # held on the writing side and nowhere else. Edit one byte of a stored scorecard's
        # verdict and every reader of that handle, up to and including an exported evidence
        # bundle, served the edit.
        #
        # Byte-exact rather than re-canonicalised: the file *is* the payload the digest was
        # taken over, so re-serialising to compare would be asking a different question and
        # would answer it wrong for anything this build canonicalises differently.
        actual = sha256_hex(text.encode("utf-8"))
        if actual != handle.removeprefix("sha256:"):
            raise UnknownSubject(
                f"{handle} is in the subject store at {self._root} and its content hashes "
                f"to sha256:{actual}, so the file no longer holds the document the handle "
                f"names. A handle is the digest of its own record and nothing here rewrites "
                f"an entry, so this file was edited or replaced after it was published; "
                f"delete it and publish the document again"
            )
        try:
            record = json.loads(text)
        except ValueError as unreadable:
            # An entry that is present and unreadable is a different fact from one that is
            # absent, and both are "this handle gives you no document" to a caller — so it is
            # the same exception with a message that says which. Raw `JSONDecodeError` here
            # would raise straight past a caller handling `UnknownSubject`, which is the trap
            # `parse_dcc` had against `ValueError`: an entry a killed process or an editor
            # truncated would 500 a tool call instead of refusing it.
            raise UnknownSubject(
                f"{handle} is in the store at {self._root} and is not readable JSON: "
                f"{unreadable}. Publishing is atomic, so this is a file something outside "
                f"this library wrote or truncated; delete it and publish the document again"
            ) from unreadable
        if not isinstance(record, dict):
            raise UnknownSubject(
                f"{handle} is in the store at {self._root} and holds a JSON "
                f"{type(record).__name__}, not a record. Every entry is an object with a "
                f"'kind' and a 'document'; delete it and publish the document again"
            )
        if kind is not None and record.get("kind") != kind:
            raise UnknownSubject(
                f"{handle} names a {record.get('kind')!r}, and a {kind!r} was asked for"
            )
        if "document" not in record:
            # A `KeyError` here is not an `UnknownSubject`, so it left `resolve` unwrapped
            # and past every caller handling one — the same trap the two guards above were
            # written for, on the one line that had not been given the treatment.
            raise UnknownSubject(
                f"{handle} is in the store at {self._root} and carries no 'document'. Every "
                f"entry is an object with a 'kind' and a 'document'; delete it and publish "
                f"the document again"
            )
        return record["document"]

    def _path(self, handle: str) -> Path:
        # Sharded by the first two hex digits, so a store that accumulates does not put
        # every entry in one directory.
        digest = handle.removeprefix("sha256:")
        return self._root / digest[:2] / f"{digest}.json"


def subject_store(root: str | Path | None = None) -> SubjectStore:
    """The store this process publishes to and resolves from."""
    return SubjectStore(root)
