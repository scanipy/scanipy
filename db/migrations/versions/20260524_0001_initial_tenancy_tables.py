"""initial tenancy + provenance tables (shape only, no RLS)

Revision ID: 20260524_0001
Revises:
Create Date: 2026-05-24

CMP-CP-03 revision 1 of 2 — TABLE SHAPE ONLY.

Per DOC-CMP-CP-03 §3.1 / DOC-DB §2, migrations that change table shape are split
from migrations that change RLS policies; they are never combined. This revision
materialises every table from the topological order in DOC-DB §4 (column shapes
are reproduced verbatim from DOC-DB §4.1-§4.15). RLS enablement and policies are
shipped separately in revision 20260524_0002.

Tables owned by other components (findings → CMP-FND-02, snapshots → CMP-SNAP-01,
provenance_records → CMP-FND-03, triage_scores → CMP-TRI-01, repartition_events →
CMP-SNAP-04, scans → CMP-ORCH-01, proposed_specs/spec_versions → CMP-TRI-02,
attestations → CMP-CP-05, scm_credentials → CMP-CP-02) are materialised here as
the migration vehicle; CP-03 mirrors the DOC-DB §4 column shapes faithfully.

The INV-1/INV-2/INV-5 NOT NULL + CHECK discharge on findings/provenance_records
lives here (DOC-DB §5 invariant-discharge matrix).
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "20260524_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # pgcrypto provides gen_random_uuid() used as the PK default everywhere.
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto;")

    # --- orgs (DOC-DB §4.1) -------------------------------------------------
    op.execute(
        """
        CREATE TABLE orgs (
            id           uuid        NOT NULL DEFAULT gen_random_uuid(),
            name         text        NOT NULL,
            kms_cmk_arn  text        NULL,
            auth0_org_id text        NULL,
            status       text        NOT NULL DEFAULT 'active',
            created_at   timestamptz NOT NULL DEFAULT now(),
            updated_at   timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT orgs_pkey PRIMARY KEY (id),
            CONSTRAINT orgs_name_key UNIQUE (name),
            CONSTRAINT orgs_auth0_org_id_key UNIQUE (auth0_org_id),
            CONSTRAINT orgs_status_chk
                CHECK (status IN ('active', 'suspended', 'deleted'))
        );
        """
    )

    # --- memberships (DOC-DB §4.2) -----------------------------------------
    op.execute(
        """
        CREATE TABLE memberships (
            id         uuid        NOT NULL DEFAULT gen_random_uuid(),
            org_id     uuid        NOT NULL,
            user_id    uuid        NOT NULL,
            role       text        NOT NULL,
            created_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT memberships_pkey PRIMARY KEY (id),
            CONSTRAINT memberships_org_id_fkey
                FOREIGN KEY (org_id) REFERENCES orgs (id),
            CONSTRAINT memberships_org_user_key UNIQUE (org_id, user_id),
            CONSTRAINT memberships_role_chk
                CHECK (role IN ('org-admin', 'org-viewer', 'scanner'))
        );
        CREATE INDEX memberships_user_id_idx ON memberships (user_id);
        """
    )

    # --- projects (DOC-DB §4.3) --------------------------------------------
    op.execute(
        """
        CREATE TABLE projects (
            id         uuid        NOT NULL DEFAULT gen_random_uuid(),
            org_id     uuid        NOT NULL,
            name       text        NOT NULL,
            created_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT projects_pkey PRIMARY KEY (id),
            CONSTRAINT projects_org_id_fkey
                FOREIGN KEY (org_id) REFERENCES orgs (id),
            CONSTRAINT projects_org_name_key UNIQUE (org_id, name)
        );
        """
    )

    # --- codebases (DOC-DB §4.4) -------------------------------------------
    op.execute(
        """
        CREATE TABLE codebases (
            id             uuid        NOT NULL DEFAULT gen_random_uuid(),
            org_id         uuid        NOT NULL,
            project_id     uuid        NULL,
            name           text        NOT NULL,
            scm_provider   text        NOT NULL,
            scm_repo_url   text        NOT NULL,
            default_branch text        NULL,
            created_at     timestamptz NOT NULL DEFAULT now(),
            updated_at     timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT codebases_pkey PRIMARY KEY (id),
            CONSTRAINT codebases_org_id_fkey
                FOREIGN KEY (org_id) REFERENCES orgs (id),
            CONSTRAINT codebases_project_id_fkey
                FOREIGN KEY (project_id) REFERENCES projects (id),
            CONSTRAINT codebases_scm_provider_chk
                CHECK (scm_provider IN
                    ('github', 'gitlab', 'bitbucket', 'azure-devops')),
            CONSTRAINT codebases_org_provider_url_key
                UNIQUE (org_id, scm_provider, scm_repo_url)
        );
        CREATE INDEX codebases_org_project_idx ON codebases (org_id, project_id);
        """
    )

    # --- scm_credentials (DOC-DB §4.5; owner CMP-CP-02) --------------------
    op.execute(
        """
        CREATE TABLE scm_credentials (
            id                  uuid        NOT NULL DEFAULT gen_random_uuid(),
            org_id              uuid        NOT NULL,
            codebase_id         uuid        NOT NULL,
            auth_mode           text        NOT NULL,
            kms_key_arn         text        NOT NULL,
            ciphertext          bytea       NOT NULL,
            display_fingerprint text        NOT NULL,
            label               text        NULL,
            created_at          timestamptz NOT NULL DEFAULT now(),
            rotated_at          timestamptz NULL,
            CONSTRAINT scm_credentials_pkey PRIMARY KEY (id),
            CONSTRAINT scm_credentials_org_id_fkey
                FOREIGN KEY (org_id) REFERENCES orgs (id),
            CONSTRAINT scm_credentials_codebase_id_fkey
                FOREIGN KEY (codebase_id)
                REFERENCES codebases (id) ON DELETE CASCADE,
            CONSTRAINT scm_credentials_auth_mode_chk
                CHECK (auth_mode IN ('pat', 'app', 'oauth', 'ssh-key'))
        );
        CREATE INDEX scm_credentials_org_codebase_idx
            ON scm_credentials (org_id, codebase_id);
        """
    )

    # --- org_policies (DOC-DB §4.6) ----------------------------------------
    op.execute(
        """
        CREATE TABLE org_policies (
            id         uuid        NOT NULL DEFAULT gen_random_uuid(),
            org_id     uuid        NOT NULL,
            policy     jsonb       NOT NULL DEFAULT '{}'::jsonb,
            version    int         NOT NULL DEFAULT 1,
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT org_policies_pkey PRIMARY KEY (id),
            CONSTRAINT org_policies_org_id_fkey
                FOREIGN KEY (org_id) REFERENCES orgs (id),
            CONSTRAINT org_policies_org_version_key UNIQUE (org_id, version)
        );
        """
    )

    # --- snapshots (DOC-DB §4.7; owner CMP-SNAP-01) ------------------------
    op.execute(
        """
        CREATE TABLE snapshots (
            id                              uuid        NOT NULL
                                                DEFAULT gen_random_uuid(),
            org_id                          uuid        NOT NULL,
            codebase_id                     uuid        NOT NULL,
            commit_sha                      text        NOT NULL,
            env_digest                      text        NOT NULL,
            precondition_status             text        NOT NULL,
            cpg_tarball_uri                 text        NOT NULL,
            reverse_symbol_index_uri        text        NOT NULL,
            dynamic_call_graph_uri          text        NOT NULL,
            delta_g_uri                     text        NULL,
            precondition_status_record_uri  text        NOT NULL,
            parent_snapshot_id              uuid        NULL,
            created_at                      timestamptz NOT NULL DEFAULT now(),
            expires_at                      timestamptz NOT NULL
                                                DEFAULT now() + interval '90 days',
            CONSTRAINT snapshots_pkey PRIMARY KEY (id),
            CONSTRAINT snapshots_org_id_fkey
                FOREIGN KEY (org_id) REFERENCES orgs (id),
            CONSTRAINT snapshots_codebase_id_fkey
                FOREIGN KEY (codebase_id)
                REFERENCES codebases (id) ON DELETE CASCADE,
            CONSTRAINT snapshots_parent_fkey
                FOREIGN KEY (parent_snapshot_id) REFERENCES snapshots (id),
            CONSTRAINT snapshots_commit_sha_chk
                CHECK (commit_sha ~ '^[0-9a-f]{40}$'),
            CONSTRAINT snapshots_env_digest_chk
                CHECK (env_digest ~ '^sha256:[0-9a-f]{64}$'),
            CONSTRAINT snapshots_precondition_status_chk
                CHECK (precondition_status IN
                    ('closed-world', 'degraded', 'full-reparse')),
            CONSTRAINT snapshots_codebase_commit_env_key
                UNIQUE (codebase_id, commit_sha, env_digest)
        );
        CREATE INDEX snapshots_org_codebase_created_idx
            ON snapshots (org_id, codebase_id, created_at DESC);
        """
    )

    # --- proposed_specs (DOC-DB §4.8; owner CMP-TRI-02) --------------------
    op.execute(
        """
        CREATE TABLE proposed_specs (
            id                           uuid        NOT NULL
                                             DEFAULT gen_random_uuid(),
            org_id                       uuid        NOT NULL,
            spec_body                    jsonb       NOT NULL,
            class                        text        NOT NULL,
            e_process_state              jsonb       NOT NULL DEFAULT '{}'::jsonb,
            decision                     text        NOT NULL DEFAULT 'pending',
            accepted_as_spec_version_id  uuid        NULL,
            created_at                   timestamptz NOT NULL DEFAULT now(),
            decided_at                   timestamptz NULL,
            CONSTRAINT proposed_specs_pkey PRIMARY KEY (id),
            CONSTRAINT proposed_specs_org_id_fkey
                FOREIGN KEY (org_id) REFERENCES orgs (id),
            CONSTRAINT proposed_specs_decision_chk
                CHECK (decision IN
                    ('pending', 'accepted', 'rejected', 'quarantined'))
        );
        CREATE INDEX proposed_specs_org_decision_idx
            ON proposed_specs (org_id, decision);
        CREATE INDEX proposed_specs_class_decision_idx
            ON proposed_specs (class, decision);
        """
    )

    # --- spec_versions (DOC-DB §4.9; owner CMP-TRI-02) ---------------------
    # FK proposed_specs.accepted_as_spec_version_id -> spec_versions(id) is
    # added after spec_versions exists (forward reference broken below).
    op.execute(
        """
        CREATE TABLE spec_versions (
            id              uuid        NOT NULL DEFAULT gen_random_uuid(),
            org_id          uuid        NULL,
            "S_version"     text        NOT NULL,
            scope           text        NOT NULL,
            spec_set        jsonb       NOT NULL,
            spec_provenance text        NOT NULL DEFAULT 'global-unrevalidated',
            created_at      timestamptz NOT NULL DEFAULT now(),
            revalidated_at  timestamptz NULL,
            CONSTRAINT spec_versions_pkey PRIMARY KEY (id),
            CONSTRAINT spec_versions_org_id_fkey
                FOREIGN KEY (org_id) REFERENCES orgs (id),
            CONSTRAINT spec_versions_scope_chk
                CHECK (scope IN ('global', 'customer')),
            CONSTRAINT spec_versions_provenance_chk
                CHECK (spec_provenance IN
                    ('global-unrevalidated', 'global-revalidated', 'customer')),
            -- INV-2 integrity: a customer-scoped spec MUST carry its org_id;
            -- a global spec MUST NOT. Matches the two partial unique indexes
            -- below (per-org for customer, global-singleton for global).
            CONSTRAINT spec_versions_scope_org_chk
                CHECK ((scope = 'global'   AND org_id IS NULL)
                    OR (scope = 'customer' AND org_id IS NOT NULL))
        );
        CREATE UNIQUE INDEX spec_versions_org_version_key
            ON spec_versions (org_id, "S_version") WHERE org_id IS NOT NULL;
        CREATE UNIQUE INDEX spec_versions_global_version_key
            ON spec_versions ("S_version") WHERE scope = 'global';
        ALTER TABLE proposed_specs
            ADD CONSTRAINT proposed_specs_accepted_spec_fkey
            FOREIGN KEY (accepted_as_spec_version_id)
            REFERENCES spec_versions (id);
        """
    )

    # --- scans (DOC-DB §4.11; derived, CLAR-DB-01; owner CMP-ORCH-01) ------
    op.execute(
        """
        CREATE TABLE scans (
            id               uuid        NOT NULL DEFAULT gen_random_uuid(),
            org_id           uuid        NOT NULL,
            codebase_id      uuid        NOT NULL,
            snapshot_id      uuid        NOT NULL,
            commit_sha       text        NOT NULL,
            "S_version"      text        NOT NULL,
            env_digest       text        NOT NULL,
            detector_ids     text[]      NOT NULL,
            status           text        NOT NULL DEFAULT 'queued',
            policy_overrides jsonb       NOT NULL DEFAULT '{}'::jsonb,
            idempotency_key  uuid        NULL,
            started_at       timestamptz NOT NULL DEFAULT now(),
            finished_at      timestamptz NULL,
            CONSTRAINT scans_pkey PRIMARY KEY (id),
            CONSTRAINT scans_org_id_fkey
                FOREIGN KEY (org_id) REFERENCES orgs (id),
            CONSTRAINT scans_codebase_id_fkey
                FOREIGN KEY (codebase_id)
                REFERENCES codebases (id) ON DELETE CASCADE,
            CONSTRAINT scans_snapshot_id_fkey
                FOREIGN KEY (snapshot_id) REFERENCES snapshots (id),
            CONSTRAINT scans_commit_sha_chk
                CHECK (commit_sha ~ '^[0-9a-f]{40}$'),
            CONSTRAINT scans_status_chk
                CHECK (status IN ('queued', 'snapshotting', 'analysing',
                    'normalising', 'attested', 'failed'))
        );
        CREATE UNIQUE INDEX scans_org_idempotency_key
            ON scans (org_id, idempotency_key)
            WHERE idempotency_key IS NOT NULL;
        CREATE INDEX scans_codebase_started_idx
            ON scans (codebase_id, started_at DESC);
        CREATE INDEX scans_org_status_idx ON scans (org_id, status);
        """
    )

    # --- attestations (DOC-DB §4.10; owner CMP-CP-05) ----------------------
    # FK to provenance_records(signed_chain_id) added after that table exists.
    op.execute(
        """
        CREATE TABLE attestations (
            id                uuid          NOT NULL DEFAULT gen_random_uuid(),
            org_id            uuid          NOT NULL,
            scan_id           uuid          NOT NULL,
            partition         text          NOT NULL,
            attestor_hash     bytea         NOT NULL,
            result            text          NOT NULL,
            reproduction_rate numeric(5, 4) NULL,
            "S_version"       text          NOT NULL,
            env_digest        text          NOT NULL,
            signed_chain_id   uuid          NULL,
            created_at        timestamptz   NOT NULL DEFAULT now(),
            CONSTRAINT attestations_pkey PRIMARY KEY (id),
            CONSTRAINT attestations_org_id_fkey
                FOREIGN KEY (org_id) REFERENCES orgs (id),
            CONSTRAINT attestations_scan_id_fkey
                FOREIGN KEY (scan_id) REFERENCES scans (id) ON DELETE CASCADE,
            CONSTRAINT attestations_partition_chk
                CHECK (partition IN ('core', 'oracle')),
            CONSTRAINT attestations_result_chk
                CHECK (result IN ('pass', 'fail', 'rate-only')),
            CONSTRAINT attestations_scan_partition_key UNIQUE (scan_id, partition)
        );
        CREATE INDEX attestations_org_created_idx
            ON attestations (org_id, created_at DESC);
        """
    )

    # --- findings (DOC-DB §4.12; owner CMP-FND-02) -------------------------
    # INV-1 / INV-2 / INV-5 schema-level discharge (DOC-DB §5). CP-03 is the
    # migration vehicle; the NOT NULL + CHECK constraints below are the
    # bottom-most defence in depth.
    op.execute(
        """
        CREATE TABLE findings (
            id                        uuid        NOT NULL
                                          DEFAULT gen_random_uuid(),
            org_id                    uuid        NOT NULL,
            codebase_id               uuid        NOT NULL,
            scan_id                   uuid        NOT NULL,
            snapshot_id               uuid        NOT NULL,
            commit_sha                text        NOT NULL,
            class                     text        NOT NULL,
            rule_id                   text        NOT NULL,
            severity                  text        NOT NULL,
            message                   text        NOT NULL,
            physical_location         jsonb       NOT NULL,
            origin                    text        NOT NULL,
            determinism_partition     text        NOT NULL,
            engine                    text        NOT NULL,
            "S_version"               text        NOT NULL,
            env_digest                text        NOT NULL,
            cpg_order_hash            bytea       NOT NULL,
            cpg_order_hash_annotation text        NOT NULL
                DEFAULT 'canonical iff fingerprint_class = strong',
            fingerprint_class         text        NOT NULL,
            slice_fingerprint         bytea       NOT NULL,
            witness_blob_uri          text        NULL,
            precondition_status       text        NOT NULL,
            spec_provenance           text        NULL,
            status                    text        NOT NULL DEFAULT 'open',
            suppression_reason        text        NULL,
            created_at                timestamptz NOT NULL DEFAULT now(),
            updated_at                timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT findings_pkey PRIMARY KEY (id),
            CONSTRAINT findings_org_id_fkey
                FOREIGN KEY (org_id) REFERENCES orgs (id),
            CONSTRAINT findings_codebase_id_fkey
                FOREIGN KEY (codebase_id)
                REFERENCES codebases (id) ON DELETE CASCADE,
            CONSTRAINT findings_scan_id_fkey
                FOREIGN KEY (scan_id) REFERENCES scans (id) ON DELETE CASCADE,
            CONSTRAINT findings_snapshot_id_fkey
                FOREIGN KEY (snapshot_id) REFERENCES snapshots (id),
            CONSTRAINT findings_commit_sha_chk
                CHECK (commit_sha ~ '^[0-9a-f]{40}$'),
            CONSTRAINT findings_class_chk
                CHECK (class IN ('injection', 'path-traversal', 'ssrf',
                    'deserialization', 'xss', 'crypto-misuse', 'authn-authz',
                    'secrets', 'dep-cve', 'memory-safety')),
            CONSTRAINT findings_severity_chk
                CHECK (severity IN ('info', 'low', 'medium', 'high', 'critical')),
            CONSTRAINT findings_origin_chk
                CHECK (origin IN ('deterministic-core', 'oracle-passthrough')),
            CONSTRAINT findings_determinism_partition_chk
                CHECK (determinism_partition IN
                    ('deterministic-core', 'oracle-passthrough')),
            CONSTRAINT findings_engine_chk
                CHECK (engine IN
                    ('ifds', 'ide', 'semgrep', 'cpg-query', 'external')),
            CONSTRAINT findings_env_digest_chk
                CHECK (env_digest ~ '^sha256:[0-9a-f]{64}$'),
            CONSTRAINT findings_cpg_order_hash_len_chk
                CHECK (octet_length(cpg_order_hash) = 32),
            CONSTRAINT findings_cpg_order_hash_annotation_chk
                CHECK (cpg_order_hash_annotation
                    = 'canonical iff fingerprint_class = strong'),
            CONSTRAINT findings_fingerprint_class_chk
                CHECK (fingerprint_class IN ('strong', 'weak')),
            CONSTRAINT findings_slice_fingerprint_len_chk
                CHECK (octet_length(slice_fingerprint) = 32),
            CONSTRAINT findings_precondition_status_chk
                CHECK (precondition_status IN
                    ('closed-world', 'degraded', 'full-reparse')),
            CONSTRAINT findings_spec_provenance_chk
                CHECK (spec_provenance IS NULL OR spec_provenance IN
                    ('global-unrevalidated', 'global-revalidated', 'customer')),
            CONSTRAINT findings_status_chk
                CHECK (status IN ('open', 'suppressed', 'fixed')),
            CONSTRAINT findings_suppression_reason_chk
                CHECK ((status = 'suppressed')
                    = (suppression_reason IS NOT NULL))
        );
        CREATE INDEX findings_codebase_slice_idx
            ON findings (codebase_id, slice_fingerprint);
        CREATE INDEX findings_scan_idx ON findings (scan_id);
        CREATE INDEX findings_org_created_idx
            ON findings (org_id, created_at DESC);
        CREATE INDEX findings_class_severity_idx ON findings (class, severity);
        CREATE INDEX findings_core_origin_idx
            ON findings (origin) WHERE origin = 'deterministic-core';
        """
    )

    # updated_at trigger (DOC-DB §4.12).
    op.execute(
        """
        CREATE FUNCTION set_updated_at() RETURNS trigger AS $$
        BEGIN
            NEW.updated_at = now();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        CREATE TRIGGER findings_set_updated_at
            BEFORE UPDATE ON findings
            FOR EACH ROW EXECUTE FUNCTION set_updated_at();
        """
    )

    # --- provenance_records (DOC-DB §4.13; owner CMP-FND-03) ---------------
    # repartition_oracle_id references snap_oracle_runs, which is OWNED by
    # CMP-SNAP-04 and is OPEN as CLAR-DB-03 (not yet mirrored into DOC-DB §4).
    # Per the column-shape ownership boundary, CP-03 does NOT create
    # snap_oracle_runs here; the column ships as `uuid NULL` with no FK until
    # CMP-SNAP-04 lands the table and the FK in its own migration.
    # TODO: CLAR-DB-03 — add FK repartition_oracle_id -> snap_oracle_runs(id)
    #       when CMP-SNAP-04 ships snap_oracle_runs.
    op.execute(
        """
        CREATE TABLE provenance_records (
            id                        uuid        NOT NULL
                                          DEFAULT gen_random_uuid(),
            parent_record_id          uuid        NULL,
            record_type               text        NOT NULL,
            org_id                    uuid        NOT NULL,
            codebase_id               uuid        NOT NULL,
            commit_sha                text        NOT NULL,
            scm_provider              text        NOT NULL,
            scan_id                   uuid        NOT NULL,
            finding_id                uuid        NULL,
            snapshot_id               uuid        NOT NULL,
            snapshot_digest           text        NOT NULL,
            precondition_status       text        NOT NULL,
            "S_version"               text        NOT NULL,
            env_digest                text        NOT NULL,
            cpg_order_hash            bytea       NULL,
            cpg_order_hash_annotation text        NOT NULL
                DEFAULT 'canonical iff fingerprint_class = strong',
            fingerprint_class         text        NULL,
            witness_blob_uri          text        NULL,
            slice_fingerprint         bytea       NULL,
            rule_id                   text        NULL,
            spec_id                   text        NULL,
            detector_id               text        NULL,
            detector_engine           text        NULL,
            sarif_hash                bytea       NULL,
            origin                    text        NULL,
            determinism_partition     text        NULL,
            repartition_reason        text        NULL,
            repartition_oracle_id     uuid        NULL,
            kms_key_arn               text        NOT NULL,
            kms_key_version           text        NOT NULL,
            signature                 bytea       NOT NULL,
            signature_alg             text        NOT NULL,
            claim_label               text        NOT NULL,
            created_at                timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT provenance_records_pkey PRIMARY KEY (id),
            CONSTRAINT provenance_records_parent_fkey
                FOREIGN KEY (parent_record_id)
                REFERENCES provenance_records (id),
            CONSTRAINT provenance_records_org_id_fkey
                FOREIGN KEY (org_id) REFERENCES orgs (id),
            CONSTRAINT provenance_records_codebase_id_fkey
                FOREIGN KEY (codebase_id)
                REFERENCES codebases (id) ON DELETE CASCADE,
            CONSTRAINT provenance_records_scan_id_fkey
                FOREIGN KEY (scan_id) REFERENCES scans (id) ON DELETE CASCADE,
            CONSTRAINT provenance_records_finding_id_fkey
                FOREIGN KEY (finding_id)
                REFERENCES findings (id) ON DELETE CASCADE,
            CONSTRAINT provenance_records_snapshot_id_fkey
                FOREIGN KEY (snapshot_id) REFERENCES snapshots (id),
            CONSTRAINT provenance_records_record_type_chk
                CHECK (record_type IN ('chain', 'repartition', 'attestation',
                    'spec-acceptance', 'witness-update')),
            CONSTRAINT provenance_records_precondition_status_chk
                CHECK (precondition_status IN
                    ('closed-world', 'degraded', 'full-reparse')),
            CONSTRAINT provenance_records_cpg_annotation_chk
                CHECK (cpg_order_hash_annotation
                    = 'canonical iff fingerprint_class = strong'),
            CONSTRAINT provenance_records_fingerprint_class_chk
                CHECK (fingerprint_class IS NULL
                    OR fingerprint_class IN ('strong', 'weak')),
            CONSTRAINT provenance_records_detector_engine_chk
                CHECK (detector_engine IS NULL OR detector_engine IN
                    ('ifds', 'ide', 'semgrep', 'cpg-query', 'external')),
            CONSTRAINT provenance_records_origin_chk
                CHECK (origin IS NULL OR origin IN
                    ('deterministic-core', 'oracle-passthrough')),
            CONSTRAINT provenance_records_signature_alg_chk
                CHECK (signature_alg IN
                    ('RSASSA_PSS_SHA_256', 'RSASSA_PSS_SHA_384')),
            CONSTRAINT provenance_records_claim_label_chk
                CHECK (claim_label IN ('CONDITIONAL_THEOREM', 'EMPIRICAL',
                    'STAGED', 'UNCONDITIONAL')),
            CONSTRAINT provenance_records_origin_present_chk
                CHECK (record_type NOT IN ('chain', 'repartition')
                    OR origin IS NOT NULL)
        );
        CREATE INDEX provenance_records_codebase_commit_idx
            ON provenance_records (codebase_id, commit_sha);
        CREATE INDEX provenance_records_snapshot_idx
            ON provenance_records (snapshot_id);
        CREATE INDEX provenance_records_codebase_slice_idx
            ON provenance_records (codebase_id, slice_fingerprint);
        CREATE INDEX provenance_records_parent_idx
            ON provenance_records (parent_record_id);
        CREATE INDEX provenance_records_scan_type_idx
            ON provenance_records (scan_id, record_type);
        CREATE INDEX provenance_records_finding_idx
            ON provenance_records (finding_id) WHERE finding_id IS NOT NULL;
        """
    )

    # Late-bind attestations.signed_chain_id -> provenance_records(id).
    op.execute(
        """
        ALTER TABLE attestations
            ADD CONSTRAINT attestations_signed_chain_fkey
            FOREIGN KEY (signed_chain_id) REFERENCES provenance_records (id);
        """
    )

    # --- triage_scores (DOC-DB §4.14; owner CMP-TRI-01) --------------------
    op.execute(
        """
        CREATE TABLE triage_scores (
            id            uuid          NOT NULL DEFAULT gen_random_uuid(),
            org_id        uuid          NOT NULL,
            finding_id    uuid          NOT NULL,
            triage_score  numeric(5, 4) NOT NULL,
            triage_reason text          NOT NULL,
            model_id      text          NOT NULL,
            model_version text          NOT NULL,
            "S_version"   text          NOT NULL,
            env_digest    text          NOT NULL,
            created_at    timestamptz   NOT NULL DEFAULT now(),
            CONSTRAINT triage_scores_pkey PRIMARY KEY (id),
            CONSTRAINT triage_scores_org_id_fkey
                FOREIGN KEY (org_id) REFERENCES orgs (id),
            CONSTRAINT triage_scores_finding_id_fkey
                FOREIGN KEY (finding_id)
                REFERENCES findings (id) ON DELETE CASCADE,
            CONSTRAINT triage_scores_score_chk
                CHECK (triage_score >= 0 AND triage_score <= 1),
            CONSTRAINT triage_scores_finding_model_key
                UNIQUE (finding_id, model_id, model_version)
        );
        CREATE INDEX triage_scores_finding_idx ON triage_scores (finding_id);
        """
    )

    # INV-3 fence at the grant level (DOC-CMP-CP-03 §8 / DOC-DB §4.14):
    # CMP-TRI-01 (the LLM triage worker) may INSERT into triage_scores but must
    # NEVER write any detection column on findings — the DB rejects the grant
    # even if a programming bug attempts it. The scanipy_triage role is created
    # idempotently here because no other migration owns its lifecycle; a
    # NOLOGIN role is a connect-only privilege holder assumed by a LOGIN role.
    op.execute(
        """
        DO $$
        BEGIN
            CREATE ROLE scanipy_triage NOLOGIN;
        EXCEPTION WHEN duplicate_object THEN
            NULL;
        END
        $$;
        GRANT INSERT ON triage_scores TO scanipy_triage;
        REVOKE ALL ON findings FROM scanipy_triage;
        GRANT SELECT (id, class, rule_id, severity, physical_location, message)
            ON findings TO scanipy_triage;
        """
    )

    # --- repartition_events (DOC-DB §4.15; owner CMP-SNAP-04) --------------
    op.execute(
        """
        CREATE TABLE repartition_events (
            id                    uuid        NOT NULL DEFAULT gen_random_uuid(),
            org_id                uuid        NOT NULL,
            snapshot_id           uuid        NOT NULL,
            scan_id               uuid        NULL,
            finding_id            uuid        NULL,
            trigger               text        NOT NULL,
            previous_origin       text        NOT NULL,
            new_origin            text        NOT NULL,
            evidence_payload      jsonb       NOT NULL,
            provenance_record_id  uuid        NOT NULL,
            created_at            timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT repartition_events_pkey PRIMARY KEY (id),
            CONSTRAINT repartition_events_org_id_fkey
                FOREIGN KEY (org_id) REFERENCES orgs (id),
            CONSTRAINT repartition_events_snapshot_id_fkey
                FOREIGN KEY (snapshot_id) REFERENCES snapshots (id),
            CONSTRAINT repartition_events_scan_id_fkey
                FOREIGN KEY (scan_id) REFERENCES scans (id),
            CONSTRAINT repartition_events_finding_id_fkey
                FOREIGN KEY (finding_id)
                REFERENCES findings (id) ON DELETE CASCADE,
            CONSTRAINT repartition_events_provenance_fkey
                FOREIGN KEY (provenance_record_id)
                REFERENCES provenance_records (id),
            CONSTRAINT repartition_events_trigger_chk
                CHECK (trigger IN
                    ('differential-oracle-disagreement', 'operator-override')),
            CONSTRAINT repartition_events_previous_origin_chk
                CHECK (previous_origin = 'deterministic-core'),
            CONSTRAINT repartition_events_new_origin_chk
                CHECK (new_origin = 'oracle-passthrough')
        );
        CREATE INDEX repartition_events_snapshot_created_idx
            ON repartition_events (snapshot_id, created_at DESC);
        CREATE INDEX repartition_events_finding_idx
            ON repartition_events (finding_id);
        """
    )


def downgrade() -> None:
    # Reverse topological order. DROP TABLE ... CASCADE is intentionally NOT
    # used so that an orphaned dependency surfaces as an error (the AC-CP-03a
    # falsifier requires a clean reversal, not a forced one). Tables are dropped
    # children-first so every FK is already gone by the time its parent drops.
    op.execute("DROP TABLE repartition_events;")
    # Reverse the INV-3 grant fence: revoke every privilege the role holds, then
    # drop the role so the downgrade leaves no residual catalog object. Revokes
    # precede the table drops so no dependency on the role survives.
    op.execute(
        """
        REVOKE ALL ON triage_scores FROM scanipy_triage;
        REVOKE ALL ON findings FROM scanipy_triage;
        DROP ROLE IF EXISTS scanipy_triage;
        """
    )
    op.execute("DROP TABLE triage_scores;")
    # Break the late-bound FK before dropping the table it points at.
    op.execute("ALTER TABLE attestations DROP CONSTRAINT attestations_signed_chain_fkey;")
    op.execute("DROP TABLE provenance_records;")
    op.execute("DROP TRIGGER findings_set_updated_at ON findings;")
    op.execute("DROP TABLE findings;")
    op.execute("DROP FUNCTION set_updated_at();")
    op.execute("DROP TABLE attestations;")
    op.execute("DROP TABLE scans;")
    # Break the late-bound FK from proposed_specs into spec_versions.
    op.execute("ALTER TABLE proposed_specs DROP CONSTRAINT proposed_specs_accepted_spec_fkey;")
    op.execute("DROP TABLE spec_versions;")
    op.execute("DROP TABLE proposed_specs;")
    op.execute("DROP TABLE snapshots;")
    op.execute("DROP TABLE org_policies;")
    op.execute("DROP TABLE scm_credentials;")
    op.execute("DROP TABLE codebases;")
    op.execute("DROP TABLE projects;")
    op.execute("DROP TABLE memberships;")
    op.execute("DROP TABLE orgs;")
    # pgcrypto is left installed: it is a shared extension, not a CP-03-owned
    # object, and dropping it could break unrelated schemas on the same DB.
