"""Deterministic BigVul held-out / training-eligible splitter (CMP-CORP-VULN-01).

This module is the load-bearing implementation of DOC-CMP-CORP-VULN-01 §3.2 — the
BigVul training-exclusion contract. The held-out evaluation split MUST be provably
disjoint from any BigVul row that could ever reach a spec-inference run (CMP-TRI-02),
a spec-curator review, or a detector-DSL design loop. A held-out / training-eligible
intersection is a HARD RELEASE BLOCKER (DOC §7).

Deterministic procedure (DOC §3.2, item 1):
  1. Each BigVul row has a stable `row_id`. If absent, it is derived deterministically
     as sha256("{commit_sha}\\0{file_path}\\0{func_name}") so the partition does not
     depend on dataset row ordering, dict order, or wall clock.
  2. Rows are sorted by (commit_sha, file_path, func_name) — a total order over the
     dataset — purely for reproducible enumeration; the partition itself is a pure
     function of each row_id (below), independent of sort order.
  3. A row is HELD-OUT iff   int(sha256(row_id), 16) % 10 == 9   (a fixed ~10% slice).
     Everything else is TRAINING-ELIGIBLE. The partition is total and disjoint by
     construction: every row lands in exactly one side.

Outputs (DOC §3.2, items 2-3):
  - heldout_split.lock      : version-pinned; sha256 over the sorted held-out row_id set.
  - training_eligible digest: sha256 over the sorted complement row_id set.
  - emptiness assertion      : heldout ∩ training_eligible == ∅ (true by construction;
                               re-verified at every build so a future bug cannot leak).

The held-out lock is PRESERVED ACROSS RELEASES (AC-CORP-VULN-01a). Any change to the
held-out row_id set requires a new corpus semver AND a regenerated proof.
"""

from __future__ import annotations

import csv
import hashlib
from dataclasses import dataclass
from pathlib import Path

HELDOUT_MODULUS = 10
HELDOUT_RESIDUE = 9  # rows whose sha256(row_id) % 10 == 9 are held out (~10%)


def derive_row_id(commit_sha: str, file_path: str, func_name: str) -> str:
    """Stable, order-independent row id when the dataset has no explicit id."""
    h = hashlib.sha256()
    h.update(commit_sha.encode("utf-8"))
    h.update(b"\0")
    h.update(file_path.encode("utf-8"))
    h.update(b"\0")
    h.update(func_name.encode("utf-8"))
    # Intentional 128-bit (32 hex) prefix: at full BigVul scale (~180k rows) the
    # birthday-collision probability is ~1e-31 — negligible — and a shorter id keeps
    # heldout_split.lock compact. Do not "fix" to the full digest: it would change the
    # held-out row_id set and break the preserved-across-releases lock (AC-CORP-VULN-01a).
    return "bigvul:" + h.hexdigest()[:32]


def _is_heldout(row_id: str) -> bool:
    digest_int = int(hashlib.sha256(row_id.encode("utf-8")).hexdigest(), 16)
    return digest_int % HELDOUT_MODULUS == HELDOUT_RESIDUE


def _digest_of_id_set(row_ids: tuple[str, ...]) -> str:
    """sha256 over the SORTED, newline-joined row_id set — canonical + reproducible."""
    canonical = "\n".join(sorted(row_ids)).encode("utf-8")
    return "sha256:" + hashlib.sha256(canonical).hexdigest()


@dataclass(frozen=True)
class SplitResult:
    # Tuples (not lists) so frozen=True yields a genuinely immutable id contract:
    # the held-out / training-eligible partition must not be mutable after split.
    heldout_ids: tuple[str, ...]
    training_ids: tuple[str, ...]
    heldout_digest: str
    training_digest: str

    def assert_disjoint(self) -> None:
        """HARD release-blocker check (DOC §7): held-out ∩ training-eligible == ∅."""
        overlap = set(self.heldout_ids) & set(self.training_ids)
        if overlap:
            raise AssertionError(
                "BigVul TRAINING LEAKAGE: held-out ∩ training-eligible is non-empty "
                f"({len(overlap)} rows); this is a HARD RELEASE BLOCKER (DOC §7). "
                f"sample={sorted(overlap)[:5]}"
            )


def split_rows(rows: list[dict]) -> SplitResult:
    """Partition BigVul rows into held-out vs training-eligible row_id sets.

    Each row is a dict with at least commit_sha, file_path, func_name; an explicit
    `row_id` is used verbatim when present, else derived deterministically.
    """
    enriched: list[tuple[str, str, str, str]] = []
    for r in rows:
        commit_sha = str(r.get("commit_sha", ""))
        file_path = str(r.get("file_path", ""))
        func_name = str(r.get("func_name", ""))
        row_id = str(r.get("row_id") or derive_row_id(commit_sha, file_path, func_name))
        enriched.append((commit_sha, file_path, func_name, row_id))

    # Total order for reproducible enumeration (DOC §3.2 item 2).
    enriched.sort(key=lambda t: (t[0], t[1], t[2], t[3]))

    heldout_ids = tuple(rid for (_, _, _, rid) in enriched if _is_heldout(rid))
    training_ids = tuple(rid for (_, _, _, rid) in enriched if not _is_heldout(rid))

    result = SplitResult(
        heldout_ids=heldout_ids,
        training_ids=training_ids,
        heldout_digest=_digest_of_id_set(heldout_ids),
        training_digest=_digest_of_id_set(training_ids),
    )
    result.assert_disjoint()
    return result


def load_rows_from_csv(csv_path: Path) -> list[dict]:
    """Load BigVul-shaped rows from a CSV with commit_sha,file_path,func_name[,row_id]."""
    with csv_path.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))
