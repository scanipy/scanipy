"""Independent graph/slice identity metadata; preserve legacy signed records.

Old rows retain their original class and signatures. New independent classes
remain NULL on those rows, never copied from the ambiguous legacy value.
"""

from alembic import op

revision = "20260925_0003"
down_revision = "20260524_0002"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        ALTER TABLE findings
          ADD COLUMN identity_schema_version integer NOT NULL DEFAULT 1,
          ADD COLUMN cpg_order_class text NULL,
          ADD COLUMN slice_fingerprint_class text NULL,
          ADD COLUMN cpg_order_status text NOT NULL DEFAULT 'legacy-ambiguous',
          ADD COLUMN slice_status text NOT NULL DEFAULT 'legacy-ambiguous',
          ADD COLUMN cpg_order_namespace text NULL,
          ADD COLUMN slice_namespace text NULL,
          ALTER COLUMN cpg_order_hash DROP NOT NULL,
          ALTER COLUMN slice_fingerprint DROP NOT NULL,
          ALTER COLUMN fingerprint_class DROP NOT NULL,
          ALTER COLUMN precondition_status DROP NOT NULL,
          ADD CONSTRAINT findings_identity_version_chk CHECK (identity_schema_version IN (1, 2)),
          ADD CONSTRAINT findings_no_shared_class_chk CHECK (
            identity_schema_version <> 2 OR fingerprint_class IS NULL),
          ADD CONSTRAINT findings_graph_class_chk CHECK (
            cpg_order_class IS NULL OR cpg_order_class IN ('strong', 'weak')),
          ADD CONSTRAINT findings_slice_class_chk CHECK (
            slice_fingerprint_class IS NULL OR slice_fingerprint_class IN ('strong', 'weak')),
          ADD CONSTRAINT findings_legacy_identity_chk CHECK (
            identity_schema_version <> 1 OR (
              cpg_order_hash IS NOT NULL AND slice_fingerprint IS NOT NULL
              AND fingerprint_class IS NOT NULL AND precondition_status IS NOT NULL
              AND cpg_order_class IS NULL AND slice_fingerprint_class IS NULL
              AND cpg_order_status = 'legacy-ambiguous' AND slice_status = 'legacy-ambiguous'
              AND cpg_order_namespace IS NULL AND slice_namespace IS NULL
            )
          ),
          ADD CONSTRAINT findings_core_identity_chk CHECK (
            identity_schema_version <> 2 OR origin <> 'deterministic-core' OR (
              cpg_order_status = 'completed' AND slice_status = 'completed'
              AND precondition_status IS NOT NULL
            )
          );
    """)
    for prefix, digest, klass in (
        ("cpg_order", "cpg_order_hash", "cpg_order_class"),
        ("slice", "slice_fingerprint", "slice_fingerprint_class"),
    ):
        op.execute(f"""
          ALTER TABLE findings ADD CONSTRAINT findings_{prefix}_artifact_chk CHECK (
            ({prefix}_status = 'completed' AND {digest} IS NOT NULL
              AND {klass} IS NOT NULL AND {prefix}_namespace IS NOT NULL
              AND length({prefix}_namespace) > 0)
            OR ({prefix}_status = 'legacy-ambiguous' AND {klass} IS NULL
              AND {prefix}_namespace IS NULL)
            OR ({prefix}_status IN ('pending', 'running', 'failed', 'not-applicable')
              AND {digest} IS NULL AND {klass} IS NULL AND {prefix}_namespace IS NULL)
          );
        """)
    op.execute("""
        ALTER TABLE provenance_records
          ADD COLUMN record_schema_version integer NOT NULL DEFAULT 1,
          ADD COLUMN artifact_identity jsonb NULL,
          ALTER COLUMN precondition_status DROP NOT NULL,
          ADD CONSTRAINT provenance_identity_version_chk CHECK ((
            (record_schema_version = 1 AND artifact_identity IS NULL
              AND precondition_status IS NOT NULL)
            OR (record_schema_version = 2 AND artifact_identity IS NOT NULL
              AND fingerprint_class IS NULL
              AND artifact_identity->'schema_version' = '2'::jsonb
              AND jsonb_typeof(artifact_identity->'cpg_order') = 'object'
              AND jsonb_typeof(artifact_identity->'slice') = 'object')
          ) IS TRUE),
          ADD CONSTRAINT provenance_core_identity_chk CHECK ((
            record_schema_version <> 2 OR origin IS DISTINCT FROM 'deterministic-core' OR (
              artifact_identity->'cpg_order'->>'status' = 'completed'
              AND artifact_identity->'slice'->>'status' = 'completed'
              AND precondition_status IS NOT NULL
            )
          ) IS TRUE);
    """)
    for prefix, digest in (("cpg_order", "cpg_order_hash"), ("slice", "slice_fingerprint")):
        descriptor = f"artifact_identity->'{prefix}'"
        op.execute(f"""
          ALTER TABLE provenance_records
          ADD CONSTRAINT provenance_{prefix}_artifact_chk CHECK (
            record_schema_version <> 2 OR ((
              {descriptor}->>'annotation' = 'canonical iff fingerprint_class = strong'
              AND (encode({digest}, 'hex') IS NOT DISTINCT FROM {descriptor}->>'digest')
              AND (
                ({descriptor}->>'status' = 'completed'
                  AND {descriptor}->>'digest' ~ '^[0-9a-f]{{64}}$'
                  AND {descriptor}->>'fingerprint_class' IN ('strong', 'weak')
                  AND jsonb_typeof({descriptor}->'namespace') = 'string'
                  AND length({descriptor}->>'namespace') > 0)
                OR ({descriptor}->>'status' IN
                    ('pending', 'running', 'failed', 'not-applicable', 'legacy-ambiguous')
                  AND {descriptor}->'fingerprint_class' = 'null'::jsonb
                  AND {descriptor}->'namespace' = 'null'::jsonb
                  AND ({descriptor}->'digest' = 'null'::jsonb OR
                    ({descriptor}->>'status' = 'legacy-ambiguous'
                     AND {descriptor}->>'digest' ~ '^[0-9a-f]{{64}}$')))
              )
            ) IS TRUE)
          );
        """)


def downgrade():
    # Dropping v2 identity columns would destroy signed history and make nullable
    # oracle evidence unrepresentable. Require an explicit migration, not loss.
    op.execute("""
      DO $$ BEGIN
        IF EXISTS (SELECT 1 FROM findings WHERE identity_schema_version = 2)
          OR EXISTS (SELECT 1 FROM provenance_records WHERE record_schema_version = 2)
        THEN RAISE EXCEPTION 'cannot downgrade while v2 artifact records exist'; END IF;
      END $$;
      ALTER TABLE provenance_records DROP CONSTRAINT provenance_identity_version_chk,
        DROP CONSTRAINT provenance_core_identity_chk,
        DROP CONSTRAINT provenance_cpg_order_artifact_chk,
        DROP CONSTRAINT provenance_slice_artifact_chk,
        ALTER COLUMN precondition_status SET NOT NULL,
        DROP COLUMN artifact_identity, DROP COLUMN record_schema_version;
      ALTER TABLE findings
        DROP CONSTRAINT findings_cpg_order_artifact_chk,
        DROP CONSTRAINT findings_slice_artifact_chk,
        DROP CONSTRAINT findings_core_identity_chk,
        DROP CONSTRAINT findings_legacy_identity_chk,
        DROP CONSTRAINT findings_graph_class_chk,
        DROP CONSTRAINT findings_slice_class_chk,
        DROP CONSTRAINT findings_identity_version_chk,
        DROP CONSTRAINT findings_no_shared_class_chk,
        DROP COLUMN cpg_order_namespace, DROP COLUMN slice_namespace,
        DROP COLUMN cpg_order_status, DROP COLUMN slice_status,
        DROP COLUMN cpg_order_class, DROP COLUMN slice_fingerprint_class,
        DROP COLUMN identity_schema_version,
        ALTER COLUMN cpg_order_hash SET NOT NULL,
        ALTER COLUMN slice_fingerprint SET NOT NULL,
        ALTER COLUMN fingerprint_class SET NOT NULL,
        ALTER COLUMN precondition_status SET NOT NULL;
    """)
