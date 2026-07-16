"""TST-AC-DEPLOY-04a — rollover-ceremony lint unit coverage.

`scripts/check_rollover_ceremony.py` discharges the verbatim AC-DEPLOY-04a
statement (`WBS.md §2.4` / `DOC-CMP-DEPLOY-04.md §9`): *"A merge to the main
branch cannot deploy a worker image whose tool digests differ from those
committed in the substrate decision record without an explicit `env_digest`
rollover ceremony."*

These tests drive the pure `ceremony_reasons` / `ceremony_title_ok` functions
directly with in-memory file-state strings — no git subprocess, no CI. The
`main()` CLI wrapper (git + argv plumbing) is deliberately left to the
integration-level workflow run; unit coverage here proves the *decision logic*
is correct, which is where a false pass or false fail would actually originate.

Source-of-truth: DOC-CMP-DEPLOY-02.md §6.2 step 2 / DOC-CMP-DEPLOY-04.md §6.2
step 1 (verbatim ceremony marker `env_digest rollover`); CLAR-DEPLOY-22.
"""

from __future__ import annotations

import json

import pytest
from scripts.check_rollover_ceremony import ceremony_reasons, ceremony_title_ok

_PINS_V1 = json.dumps({"tools": {"joern": {"version": "v1.0.0", "sha256": "a" * 64}}})
_PINS_V2 = json.dumps({"tools": {"joern": {"version": "v2.0.0", "sha256": "b" * 64}}})

_REG_ONE_ACTIVE = json.dumps(
    {
        "schema_version": 1,
        "entries": [
            {
                "image": "scanipy-snapshot",
                "env_digest": "sha256:" + "a" * 64,
                "tag": "v0.1.0",
                "git_sha": "d" * 40,
                "signed_at": "2026-07-15T00:00:00Z",
                "status": "active",
                "note": "",
            }
        ],
    }
)
_REG_ROLLED_OVER = json.dumps(
    {
        "schema_version": 1,
        "entries": [
            {
                "image": "scanipy-snapshot",
                "env_digest": "sha256:" + "a" * 64,
                "tag": "v0.1.0",
                "git_sha": "d" * 40,
                "signed_at": "2026-07-15T00:00:00Z",
                "status": "superseded",
                "note": "superseded by v0.1.1",
            },
            {
                "image": "scanipy-snapshot",
                "env_digest": "sha256:" + "b" * 64,
                "tag": "v0.1.1",
                "git_sha": "e" * 40,
                "signed_at": "2026-07-16T00:00:00Z",
                "status": "active",
                "note": "",
            },
        ],
    }
)


# ---------------------------------------------------------------------------
# ceremony_title_ok
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_ceremony_title_ok_requires_the_verbatim_marker() -> None:
    assert ceremony_title_ok("env_digest rollover: bump joern to v2.0.0")
    assert ceremony_title_ok("chore: env_digest rollover for CVE-2026-1234")
    assert not ceremony_title_ok("chore: bump joern to v2.0.0")
    assert not ceremony_title_ok("env digest rollover")  # underscore is load-bearing
    assert not ceremony_title_ok("")


# ---------------------------------------------------------------------------
# ceremony_reasons — pins.json changes
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_no_change_requires_no_ceremony() -> None:
    reasons = ceremony_reasons(_PINS_V1, _PINS_V1, None, None)
    assert reasons == []


@pytest.mark.unit
def test_pins_modification_requires_ceremony() -> None:
    reasons = ceremony_reasons(_PINS_V1, _PINS_V2, None, None)
    assert any("pins.json modified" in r for r in reasons)


@pytest.mark.unit
def test_pins_creation_from_absent_requires_ceremony() -> None:
    reasons = ceremony_reasons(None, _PINS_V1, None, None)
    assert any("pins.json modified" in r for r in reasons)


# ---------------------------------------------------------------------------
# ceremony_reasons — registry active-entry changes
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_registry_active_flip_requires_ceremony() -> None:
    reasons = ceremony_reasons(_PINS_V1, _PINS_V1, _REG_ONE_ACTIVE, _REG_ROLLED_OVER)
    assert any("active env_digest registry entries changed" in r for r in reasons)


@pytest.mark.unit
def test_registry_unchanged_requires_no_ceremony() -> None:
    reasons = ceremony_reasons(_PINS_V1, _PINS_V1, _REG_ONE_ACTIVE, _REG_ONE_ACTIVE)
    assert reasons == []


@pytest.mark.unit
def test_registry_non_active_edit_requires_no_ceremony() -> None:
    """Amending a `note` on a non-active row doesn't change the active map."""
    amended = json.loads(_REG_ROLLED_OVER)
    amended["entries"][0]["note"] = "superseded by v0.1.1 (CVE-2026-1234)"
    reasons = ceremony_reasons(_PINS_V1, _PINS_V1, _REG_ROLLED_OVER, json.dumps(amended))
    assert reasons == []


@pytest.mark.unit
def test_registry_absent_at_base_and_created_requires_no_ceremony_by_itself() -> None:
    """Registry bootstrap (file didn't exist at base) is not, by itself, a
    tool-digest rollover — pins.json unchanged, no active-map comparison
    possible against a previously-nonexistent file, `_actives(None) == {}` so
    only an actual active-map change downstream would trip the check."""
    reasons = ceremony_reasons(_PINS_V1, _PINS_V1, None, _REG_ONE_ACTIVE)
    assert any("active env_digest registry entries changed" in r for r in reasons)


@pytest.mark.unit
def test_malformed_new_registry_is_treated_as_active_flip_fail_closed() -> None:
    reasons = ceremony_reasons(_PINS_V1, _PINS_V1, _REG_ONE_ACTIVE, "{not json")
    assert any("unparseable" in r for r in reasons)


@pytest.mark.unit
def test_malformed_old_registry_is_treated_as_active_flip_fail_closed() -> None:
    reasons = ceremony_reasons(_PINS_V1, _PINS_V1, "{not json", _REG_ONE_ACTIVE)
    assert any("unparseable" in r for r in reasons)


@pytest.mark.unit
def test_non_object_registry_is_treated_as_active_flip_fail_closed() -> None:
    reasons = ceremony_reasons(_PINS_V1, _PINS_V1, _REG_ONE_ACTIVE, "[1, 2, 3]")
    assert any("unparseable" in r for r in reasons)


# ---------------------------------------------------------------------------
# Combined: both pins + registry change -> both reasons surfaced
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_both_pins_and_registry_change_yields_both_reasons() -> None:
    reasons = ceremony_reasons(_PINS_V1, _PINS_V2, _REG_ONE_ACTIVE, _REG_ROLLED_OVER)
    assert len(reasons) == 2
    assert any("pins.json modified" in r for r in reasons)
    assert any("active env_digest registry entries changed" in r for r in reasons)
