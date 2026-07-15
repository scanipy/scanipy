"""Focused unit coverage for the CLAR-DEPLOY-22 env_digest registry.

`workers/build/env_digest_registry.py` is the canonical, machine-readable,
append-only surface for the production `env_digest` (the CP-06 / INV-2
bootstrap — see `workers/env_digest_history.json`'s own `comment` field and
`docs/cross-cutting/DOC-DEPLOY-DECISIONS.md`'s "env_digest history" pointer
section). These tests are fully hermetic — no docker, no ECR, no network, no
git — driven entirely from `tmp_path` fixture files.

Source-of-truth: decision record CLAR-DEPLOY-22 `implementation_contract` §2/§5.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from workers.build.env_digest_registry import (
    CEREMONY_MARKER,
    PLACEHOLDER_DIGEST,
    VALID_IMAGES,
    EnvDigestRegistryError,
    active_digest,
    active_map,
    check_append_only,
    check_registry,
    find_active_digest,
    load_registry,
    main,
    register,
)

_DIGEST_A = "sha256:" + "a" * 64
_DIGEST_B = "sha256:" + "b" * 64
_DIGEST_C = "sha256:" + "c" * 64
_GIT_SHA = "d" * 40
_SIGNED_AT = "2026-07-15T00:00:00Z"


def _entry(
    *,
    image: str = "scanipy-snapshot",
    env_digest: str = _DIGEST_A,
    tag: str = "v0.1.0",
    git_sha: str = _GIT_SHA,
    signed_at: str = _SIGNED_AT,
    status: str = "active",
    note: str = "",
) -> dict[str, Any]:
    return {
        "image": image,
        "env_digest": env_digest,
        "tag": tag,
        "git_sha": git_sha,
        "signed_at": signed_at,
        "status": status,
        "note": note,
    }


def _doc(entries: list[dict[str, Any]]) -> dict[str, Any]:
    return {"schema_version": 1, "entries": entries}


# ---------------------------------------------------------------------------
# check_registry — schema + invariant violations
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_check_registry_accepts_a_well_formed_doc() -> None:
    doc = _doc(
        [
            _entry(image="scanipy-snapshot", env_digest=_DIGEST_A, status="active", note=""),
            _entry(image="scanipy-detector", env_digest=_DIGEST_B, status="active", note=""),
        ]
    )
    assert check_registry(doc) == []


@pytest.mark.unit
def test_check_registry_rejects_wrong_schema_version() -> None:
    doc = _doc([_entry()])
    doc["schema_version"] = 2
    violations = check_registry(doc)
    assert any("schema_version" in v for v in violations)


@pytest.mark.unit
def test_check_registry_rejects_two_active_entries_same_image() -> None:
    doc = _doc(
        [
            _entry(env_digest=_DIGEST_A, status="active", note=""),
            _entry(env_digest=_DIGEST_B, status="active", note=""),
        ]
    )
    violations = check_registry(doc)
    assert any("at most 1 allowed" in v for v in violations)


@pytest.mark.unit
def test_check_registry_zero_active_is_legal_bootstrap_state() -> None:
    """CLAR-CP-06-02 record-and-warn: zero active entries is a valid state."""
    doc = _doc([_entry(status="void", note="never deployed")])
    assert check_registry(doc) == []


@pytest.mark.unit
def test_check_registry_rejects_duplicate_digest_across_entries() -> None:
    doc = _doc(
        [
            _entry(image="scanipy-snapshot", env_digest=_DIGEST_A, status="active", note=""),
            _entry(image="scanipy-detector", env_digest=_DIGEST_A, status="active", note=""),
        ]
    )
    violations = check_registry(doc)
    assert any("duplicate digest" in v for v in violations)


@pytest.mark.unit
def test_check_registry_rejects_placeholder_digest() -> None:
    doc = _doc([_entry(env_digest=PLACEHOLDER_DIGEST, status="active", note="")])
    violations = check_registry(doc)
    assert any("placeholder" in v for v in violations)


@pytest.mark.unit
def test_check_registry_rejects_missing_note_on_non_active_row() -> None:
    doc = _doc([_entry(status="superseded", note="")])
    violations = check_registry(doc)
    assert any("note" in v for v in violations)


@pytest.mark.unit
def test_check_registry_rejects_unknown_and_missing_keys() -> None:
    entry = _entry()
    entry["bogus"] = "field"
    doc = _doc([entry])
    violations = check_registry(doc)
    assert any("unknown key" in v for v in violations)

    entry2 = _entry()
    del entry2["note"]
    doc2 = _doc([entry2])
    violations2 = check_registry(doc2)
    assert any("missing key" in v for v in violations2)


@pytest.mark.unit
@pytest.mark.parametrize(
    "field,value",
    [
        ("env_digest", "not-a-digest"),
        ("tag", "0.1.0"),
        ("git_sha", "short"),
        ("signed_at", "2026-07-15 00:00:00"),
        ("status", "unknown-status"),
        ("image", "scanipy-other"),
    ],
)
def test_check_registry_rejects_malformed_fields(field: str, value: str) -> None:
    entry = _entry(status="active", note="")
    entry[field] = value
    doc = _doc([entry])
    assert check_registry(doc) != []


# ---------------------------------------------------------------------------
# load_registry — fail-closed parsing
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_load_registry_raises_on_missing_file(tmp_path: Path) -> None:
    with pytest.raises(EnvDigestRegistryError):
        load_registry(tmp_path / "nope.json")


@pytest.mark.unit
def test_load_registry_raises_on_malformed_json(tmp_path: Path) -> None:
    path = tmp_path / "bad.json"
    path.write_text("{not json", encoding="utf-8")
    with pytest.raises(EnvDigestRegistryError):
        load_registry(path)


@pytest.mark.unit
def test_load_registry_raises_on_non_object_document(tmp_path: Path) -> None:
    path = tmp_path / "bad.json"
    path.write_text("[1, 2, 3]", encoding="utf-8")
    with pytest.raises(EnvDigestRegistryError):
        load_registry(path)


@pytest.mark.unit
def test_load_registry_raises_on_invariant_violation(tmp_path: Path) -> None:
    path = tmp_path / "bad.json"
    path.write_text(
        json.dumps(
            _doc(
                [
                    _entry(env_digest=_DIGEST_A, status="active", note=""),
                    _entry(env_digest=_DIGEST_B, status="active", note=""),
                ]
            )
        ),
        encoding="utf-8",
    )
    with pytest.raises(EnvDigestRegistryError):
        load_registry(path)


@pytest.mark.unit
def test_load_registry_accepts_valid_doc(tmp_path: Path) -> None:
    path = tmp_path / "good.json"
    path.write_text(json.dumps(_doc([_entry(status="active", note="")])), encoding="utf-8")
    doc = load_registry(path)
    assert doc["schema_version"] == 1


# ---------------------------------------------------------------------------
# find_active_digest / active_digest / active_map
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_find_active_digest_returns_none_when_absent() -> None:
    doc = _doc([_entry(status="void", note="never deployed")])
    assert find_active_digest(doc, "scanipy-snapshot") is None


@pytest.mark.unit
def test_find_active_digest_returns_the_active_entry() -> None:
    doc = _doc([_entry(env_digest=_DIGEST_A, status="active", note="")])
    assert find_active_digest(doc, "scanipy-snapshot") == _DIGEST_A


@pytest.mark.unit
def test_active_digest_raises_when_absent() -> None:
    doc = _doc([_entry(status="void", note="never deployed")])
    with pytest.raises(EnvDigestRegistryError):
        active_digest(doc, "scanipy-snapshot")


@pytest.mark.unit
def test_active_map_omits_images_with_no_active_entry() -> None:
    doc = _doc(
        [
            _entry(image="scanipy-snapshot", env_digest=_DIGEST_A, status="active", note=""),
            _entry(image="scanipy-detector", status="void", note="never deployed"),
        ]
    )
    m = active_map(doc)
    assert m == {"scanipy-snapshot": _DIGEST_A}
    assert set(VALID_IMAGES) == {"scanipy-snapshot", "scanipy-detector"}


# ---------------------------------------------------------------------------
# register() — append-only rollover semantics
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_register_flips_active_to_superseded_and_appends(tmp_path: Path) -> None:
    path = tmp_path / "registry.json"
    path.write_text(
        json.dumps(_doc([_entry(env_digest=_DIGEST_A, tag="v0.1.0", status="active", note="")])),
        encoding="utf-8",
    )

    register(
        path,
        image="scanipy-snapshot",
        env_digest=_DIGEST_B,
        tag="v0.1.1",
        git_sha="e" * 40,
        signed_at=_SIGNED_AT,
    )

    doc = json.loads(path.read_text(encoding="utf-8"))
    assert len(doc["entries"]) == 2
    old, new = doc["entries"]
    assert old["env_digest"] == _DIGEST_A
    assert old["status"] == "superseded"
    assert old["note"] == "superseded by v0.1.1"
    assert new["env_digest"] == _DIGEST_B
    assert new["status"] == "active"
    assert check_registry(doc) == []


@pytest.mark.unit
def test_register_never_deletes_rows(tmp_path: Path) -> None:
    path = tmp_path / "registry.json"
    path.write_text(
        json.dumps(_doc([_entry(env_digest=_DIGEST_A, status="void", note="never deployed")])),
        encoding="utf-8",
    )
    register(
        path,
        image="scanipy-snapshot",
        env_digest=_DIGEST_B,
        tag="v0.1.1",
        git_sha="e" * 40,
        signed_at=_SIGNED_AT,
    )
    doc = json.loads(path.read_text(encoding="utf-8"))
    digests = {e["env_digest"] for e in doc["entries"]}
    assert {_DIGEST_A, _DIGEST_B} <= digests


@pytest.mark.unit
def test_register_is_idempotent_on_already_active_digest(tmp_path: Path) -> None:
    path = tmp_path / "registry.json"
    original = _doc([_entry(env_digest=_DIGEST_A, tag="v0.1.0", status="active", note="")])
    path.write_text(json.dumps(original), encoding="utf-8")
    before = path.read_text(encoding="utf-8")

    register(
        path,
        image="scanipy-snapshot",
        env_digest=_DIGEST_A,
        tag="v0.1.0",
        git_sha=_GIT_SHA,
        signed_at=_SIGNED_AT,
    )

    assert path.read_text(encoding="utf-8") == before  # untouched — no-op


@pytest.mark.unit
def test_register_two_images_are_independent(tmp_path: Path) -> None:
    path = tmp_path / "registry.json"
    path.write_text(
        json.dumps(
            _doc(
                [
                    _entry(
                        image="scanipy-snapshot", env_digest=_DIGEST_A, status="active", note=""
                    ),
                    _entry(
                        image="scanipy-detector", env_digest=_DIGEST_B, status="active", note=""
                    ),
                ]
            )
        ),
        encoding="utf-8",
    )
    register(
        path,
        image="scanipy-snapshot",
        env_digest=_DIGEST_C,
        tag="v0.2.0",
        git_sha="f" * 40,
        signed_at=_SIGNED_AT,
    )
    doc = json.loads(path.read_text(encoding="utf-8"))
    assert active_map(doc) == {"scanipy-snapshot": _DIGEST_C, "scanipy-detector": _DIGEST_B}


# ---------------------------------------------------------------------------
# check_append_only — the CI history-comparison contract
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_check_append_only_accepts_a_pure_rollover() -> None:
    old = _doc([_entry(env_digest=_DIGEST_A, tag="v0.1.0", status="active", note="")])
    new = _doc(
        [
            _entry(
                env_digest=_DIGEST_A,
                tag="v0.1.0",
                status="superseded",
                note="superseded by v0.1.1",
            ),
            _entry(env_digest=_DIGEST_B, tag="v0.1.1", status="active", note=""),
        ]
    )
    assert check_append_only(old, new) == []


@pytest.mark.unit
def test_check_append_only_rejects_row_deletion() -> None:
    old = _doc([_entry(env_digest=_DIGEST_A, status="active", note="")])
    new = _doc([])
    violations = check_append_only(old, new)
    assert any("deleted" in v for v in violations)


@pytest.mark.unit
def test_check_append_only_rejects_immutable_field_mutation() -> None:
    old = _doc([_entry(env_digest=_DIGEST_A, tag="v0.1.0", status="active", note="")])
    new = _doc([_entry(env_digest=_DIGEST_A, tag="v0.9.9", status="active", note="")])
    violations = check_append_only(old, new)
    assert any("immutable field" in v for v in violations)


@pytest.mark.unit
def test_check_append_only_rejects_active_to_void_and_back_to_active() -> None:
    old = _doc([_entry(env_digest=_DIGEST_A, status="active", note="")])
    illegal = _doc([_entry(env_digest=_DIGEST_A, status="void", note="oops")])
    assert any("illegal status transition" in v for v in check_append_only(old, illegal))

    # superseded -> active is also illegal — nothing ever returns to active.
    superseded_old = _doc(
        [_entry(env_digest=_DIGEST_A, status="superseded", note="superseded by v0.1.1")]
    )
    back_to_active = _doc([_entry(env_digest=_DIGEST_A, status="active", note="")])
    assert any(
        "illegal status transition" in v for v in check_append_only(superseded_old, back_to_active)
    )


@pytest.mark.unit
def test_check_append_only_allows_note_amendment_on_non_active_row() -> None:
    old = _doc([_entry(env_digest=_DIGEST_A, status="void", note="original note")])
    new = _doc([_entry(env_digest=_DIGEST_A, status="void", note="amended note")])
    assert check_append_only(old, new) == []


# ---------------------------------------------------------------------------
# CLI (main) — check / register subcommands
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_cli_check_returns_zero_on_valid_registry(tmp_path: Path) -> None:
    path = tmp_path / "registry.json"
    path.write_text(json.dumps(_doc([_entry(status="active", note="")])), encoding="utf-8")
    assert main(["check", str(path)]) == 0


@pytest.mark.unit
def test_cli_check_returns_one_on_invalid_registry(tmp_path: Path) -> None:
    path = tmp_path / "registry.json"
    path.write_text(
        json.dumps(_doc([_entry(env_digest=PLACEHOLDER_DIGEST, status="active", note="")])),
        encoding="utf-8",
    )
    assert main(["check", str(path)]) == 1


@pytest.mark.unit
def test_cli_check_returns_one_on_malformed_json(tmp_path: Path) -> None:
    path = tmp_path / "registry.json"
    path.write_text("{not json", encoding="utf-8")
    assert main(["check", str(path)]) == 1


@pytest.mark.unit
def test_cli_register_writes_a_valid_rollover(tmp_path: Path) -> None:
    path = tmp_path / "registry.json"
    path.write_text(
        json.dumps(_doc([_entry(env_digest=_DIGEST_A, tag="v0.1.0", status="active", note="")])),
        encoding="utf-8",
    )
    rc = main(
        [
            "register",
            "--path",
            str(path),
            "--image",
            "scanipy-snapshot",
            "--digest",
            _DIGEST_B,
            "--tag",
            "v0.1.1",
            "--git-sha",
            "e" * 40,
            "--signed-at",
            _SIGNED_AT,
        ]
    )
    assert rc == 0
    doc = json.loads(path.read_text(encoding="utf-8"))
    assert active_map(doc) == {"scanipy-snapshot": _DIGEST_B}


# ---------------------------------------------------------------------------
# CEREMONY_MARKER — shared constant consumed by check_rollover_ceremony.py
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_ceremony_marker_is_the_doc_specified_string() -> None:
    """DOC-CMP-DEPLOY-02 §6.2 step 2 / DOC-CMP-DEPLOY-04 §6.2 step 1 (verbatim)."""
    assert CEREMONY_MARKER == "env_digest rollover"
