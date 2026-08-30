# Open-source readiness — Scanipy (OSS-01 / OSS-02, CLAR-DEPLOY-25)

Tracks the preconditions for making the repository public (the `OSS-02` gate).

## OSS-01 — done

- [x] `LICENSE` — Apache-2.0 (patent grant; appropriate for a security tool). `pyproject.toml`
      `license` updated `Proprietary` → `Apache-2.0`.
- [x] `CONTRIBUTING.md`, `SECURITY.md`, `CODE_OF_CONDUCT.md`.
- [x] `README.md` one-command quickstart; `deploy/README.md` self-hosting guide (OSS-03).
- [x] Secret / sensitive-data audit of the working tree **and full git history** (below).

## Secret audit result (2026-08-28)

Audited the full history (`git log --all -p`) and the tracked tree.

- **No hard credentials in history.** All Postgres DSN matches are env-var references
  (`${SCANIPY_RDS_MASTER_PASSWORD}`), placeholders (`<password>`, `scanipy_admin:...`), or the
  dev/test defaults (`scanipy:scanipy_dev`, `scanipy:scanipy_test`) that are the compose defaults, not
  secrets. **No** AWS access keys (`AKIA…`/`ASIA…`), private keys, GitHub tokens, or Slack tokens were
  found.
- **Low-sensitivity identifiers present:** the AWS account id `123456789012` (~34 occurrences, from the
  now-superseded AWS track) and one role ARN `arn:aws:iam::123456789012:role/scanipy-ecs-worker`. These
  are **identifiers, not credentials** — an account id and a role name do not grant access on their own,
  and both reference infrastructure that is being decommissioned under the Docker/OSS pivot.

**Conclusion:** it is **safe to make the repository public without rewriting history.** No credential
would be exposed. Rewriting history to remove the account id is *optional tidiness*, not a security
requirement, and is a destructive operation (force-push, breaks clones/PRs) — do it only if the owner
explicitly wants it.

## OSS-02 — flip public (GATED — not done here)

Requires, in order:

1. [x] OSS-01 complete (above).
2. [ ] **Explicit owner confirmation** to make the repo public (irreversible; exposes history).
3. [ ] Optional: decommission the referenced AWS account / rotate anything the owner considers
       sensitive before or independent of the flip.

When confirmed: `gh repo edit scanipy/scanipy --visibility public --accept-visibility-change-consequences`.
