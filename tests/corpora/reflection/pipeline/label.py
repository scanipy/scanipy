"""Label-validation helpers for CMP-CORP-REFL-01 (DOC §3.3, §7).

Two severities (DOC §7 distinguishes hard rejects from quality advisories):
  HARD  (blocks corpus.lock emission):
    - label in {closed-world, not-closed-world}
    - expected_sites non-empty IFF label == not-closed-world (DOC §3.2 invariant 4)
    - every expected_site has file/line/kind
    - review_status in {single-pass, second-pass}
  WARN  (does NOT block; reported; affects the N>=50 hand-curated tally):
    - a hand-labelled (non-pipeline) item that is not yet second-pass does NOT count
      toward AC-CORP-REFL-01a's N>=50 hand-curated bar (DOC §7). It is a valid corpus
      member at v0.1.0, just not a quality-bar item.
"""

from __future__ import annotations

from dataclasses import dataclass

VALID_LABELS = {"closed-world", "not-closed-world"}
VALID_REVIEW = {"single-pass", "second-pass"}


@dataclass(frozen=True)
class LabelIssue:
    item_id: str
    message: str
    severity: str  # "hard" | "warn"


def validate_label(item_id: str, label_doc: dict) -> list[LabelIssue]:
    """Return label issues; any severity=='hard' must block corpus.lock emission."""
    issues: list[LabelIssue] = []

    def hard(msg: str) -> None:
        issues.append(LabelIssue(item_id, msg, "hard"))

    def warn(msg: str) -> None:
        issues.append(LabelIssue(item_id, msg, "warn"))

    label = label_doc.get("label")
    if label not in VALID_LABELS:
        hard(f"label {label!r} not in {VALID_LABELS}")

    sites = label_doc.get("expected_sites") or []
    if label == "not-closed-world" and not sites:
        hard("label=not-closed-world requires non-empty expected_sites")
    if label == "closed-world" and sites:
        hard("label=closed-world must have empty expected_sites")

    for s in sites:
        if not all(k in s for k in ("file", "line", "kind")):
            hard(f"expected_site missing file/line/kind: {s!r}")

    review = label_doc.get("review_status")
    labelled_by = label_doc.get("labelled_by")
    if review not in VALID_REVIEW:
        hard(f"review_status {review!r} not in {VALID_REVIEW}")

    if labelled_by != "pipeline" and review != "second-pass":
        warn(
            "hand-labelled item is not second-pass; does NOT count toward "
            "AC-CORP-REFL-01a N>=50 hand-curated bar (DOC §7)"
        )

    return issues


def counts_toward_hand_bar(label_doc: dict) -> bool:
    """True iff this item is a second-pass hand-curated item (AC-CORP-REFL-01a)."""
    return (
        label_doc.get("labelled_by") != "pipeline"
        and label_doc.get("review_status") == "second-pass"
    )


__all__ = ["LabelIssue", "validate_label", "counts_toward_hand_bar", "VALID_LABELS", "VALID_REVIEW"]
