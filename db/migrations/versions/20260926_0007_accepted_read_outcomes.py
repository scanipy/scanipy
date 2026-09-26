"""Distinguish a missing typed historical row without changing public AL errors.

Revision 0006/resources stay frozen. Two existing entrypoints only: no new
function, table, role, grant, data rewrite or runtime codec dependency.
"""

from alembic import op

revision = "20260926_0007"
down_revision = "20260926_0006"
branch_labels = None
depends_on = None

# Literal predecessor/successor definitions: independent of future owner files.
# The four E501 exceptions preserve the exact reviewed PostgreSQL source bytes.
ORIGINAL_R1 = r"""CREATE FUNCTION scanipy_accepted_inputs.read_publication_receipt_v1(p_namespace uuid,p_publication_key uuid,p_approval_event_id uuid)
RETURNS TABLE(record_bytes bytea)
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,scanipy_accepted_inputs,pg_temp SET bytea_output='hex' AS $$
DECLARE namespace jsonb; row record; approval jsonb; receipt jsonb;
BEGIN
  PERFORM scanipy_accepted_inputs.v1_work_begin(131072);
  namespace:=scanipy_accepted_inputs.v1_namespace(p_namespace);
  PERFORM scanipy_accepted_inputs.v1_require((p_publication_key IS NULL)<>(p_approval_event_id IS NULL));
  PERFORM scanipy_accepted_inputs.v1_control(512);
  SELECT id,publication_key,record_length,publication_receipt_length INTO row
    FROM scanipy_accepted_inputs.authority_events WHERE namespace_id=p_namespace AND kind='approval'
      AND ((p_publication_key IS NOT NULL AND publication_key=p_publication_key)
        OR (p_approval_event_id IS NOT NULL AND id=p_approval_event_id));
  PERFORM scanipy_accepted_inputs.v1_require(FOUND AND row.record_length<=65536
    AND row.publication_receipt_length<=65536,'ledger-mismatch');
  PERFORM scanipy_accepted_inputs.v1_fetch(row.record_length+row.publication_receipt_length);
  SELECT e.record_bytes,e.record_digest,publication_receipt_bytes,publication_receipt_digest,id,publication_key INTO row
    FROM scanipy_accepted_inputs.authority_events e WHERE namespace_id=p_namespace AND kind='approval' AND id=row.id;
  approval:=scanipy_accepted_inputs.v1_stored_document(row.record_bytes,'scanipy-accepted-approval/1');
  receipt:=scanipy_accepted_inputs.v1_stored_document(row.publication_receipt_bytes,'scanipy-accepted-publication/1');
  PERFORM scanipy_accepted_inputs.v1_same_namespace(approval,namespace);
  PERFORM scanipy_accepted_inputs.v1_require(approval->>'event_id'=row.id::text
    AND approval->>'publication_key'=row.publication_key::text
    AND scanipy_accepted_inputs.v1_hash(row.record_bytes,'scanipy-accepted-approval/1')=row.record_digest
    AND scanipy_accepted_inputs.v1_hash(row.publication_receipt_bytes,'scanipy-accepted-publication/1')=row.publication_receipt_digest,
    'content-mismatch');
  PERFORM scanipy_accepted_inputs.v1_publication_links(approval,row.record_digest,receipt);
  record_bytes:=row.publication_receipt_bytes; RETURN NEXT;
END $$;"""  # noqa: E501

ORIGINAL_R3 = r"""CREATE FUNCTION scanipy_accepted_inputs.read_authority_event_v1(p_namespace uuid,p_kind text,p_event_id uuid,p_record_digest bytea)
RETURNS TABLE(record_bytes bytea,supporting_objects bytea[])
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,scanipy_accepted_inputs,pg_temp SET bytea_output='hex' AS $$
DECLARE namespace jsonb; row record; document jsonb; schema_name text; total bigint;
  frame bytea[]; receipt jsonb;
BEGIN
  PERFORM scanipy_accepted_inputs.v1_work_begin(1179648);
  namespace:=scanipy_accepted_inputs.v1_namespace(p_namespace);
  schema_name:=CASE p_kind WHEN 'policy' THEN 'scanipy-accepted-trust-policy/1'
    WHEN 'admission' THEN 'scanipy-registry-admission/1' WHEN 'approval' THEN 'scanipy-accepted-approval/1'
    WHEN 'seal-authorization' THEN 'scanipy-capture-seal-authorization/1'
    WHEN 'execution-authorization' THEN 'scanipy-execution-authorization/1'
    WHEN 'execution-denial' THEN 'scanipy-execution-denial/1' ELSE NULL END;
  PERFORM scanipy_accepted_inputs.v1_require(schema_name IS NOT NULL AND p_event_id IS NOT NULL
    AND p_record_digest IS NOT NULL AND octet_length(p_record_digest)=32);
  PERFORM scanipy_accepted_inputs.v1_control(512);
  SELECT record_length,publication_input_length,publication_receipt_length INTO row
    FROM scanipy_accepted_inputs.authority_events WHERE namespace_id=p_namespace AND kind=p_kind
      AND id=p_event_id AND record_digest=p_record_digest;
  PERFORM scanipy_accepted_inputs.v1_require(FOUND AND row.record_length<=
    CASE WHEN p_kind='policy' THEN 131072 ELSE 65536 END,'ledger-mismatch');
  total:=row.record_length;
  IF p_kind IN ('policy','admission') THEN total:=total+384;
  ELSIF p_kind='approval' THEN
    PERFORM scanipy_accepted_inputs.v1_require(row.publication_input_length BETWEEN 1 AND 1048576
      AND row.publication_receipt_length BETWEEN 1 AND 65536,'content-mismatch');
    total:=total+row.publication_input_length+row.publication_receipt_length;
  END IF;
  PERFORM scanipy_accepted_inputs.v1_fetch(total);
  SELECT e.record_bytes,record_schema,signature_bytes,publication_input_bytes,
    publication_receipt_bytes,publication_receipt_digest INTO row
    FROM scanipy_accepted_inputs.authority_events e WHERE namespace_id=p_namespace AND kind=p_kind AND id=p_event_id;
  PERFORM scanipy_accepted_inputs.v1_require(row.record_schema=schema_name,'content-mismatch');
  document:=scanipy_accepted_inputs.v1_stored_document(row.record_bytes,schema_name);
  PERFORM scanipy_accepted_inputs.v1_same_namespace(document,namespace);
  PERFORM scanipy_accepted_inputs.v1_require(document->>'event_id'=p_event_id::text
    AND scanipy_accepted_inputs.v1_hash(row.record_bytes,schema_name)=p_record_digest,'content-mismatch');
  supporting_objects:=ARRAY[]::bytea[];
  IF p_kind IN ('policy','admission') THEN
    PERFORM scanipy_accepted_inputs.v1_require(octet_length(row.signature_bytes)=384,'content-mismatch');
    supporting_objects:=ARRAY[row.signature_bytes];
  ELSIF p_kind='approval' THEN
    frame:=scanipy_accepted_inputs.v1_stored_frame(row.publication_input_bytes,'scanipy-publication-input/1');
    PERFORM scanipy_accepted_inputs.v1_require(frame[2]=row.record_bytes,'content-mismatch');
    receipt:=scanipy_accepted_inputs.v1_stored_document(row.publication_receipt_bytes,'scanipy-accepted-publication/1');
    PERFORM scanipy_accepted_inputs.v1_publication_links(document,p_record_digest,receipt);
    PERFORM scanipy_accepted_inputs.v1_publication_record(frame,receipt,namespace,
      jsonb_build_object('registry_id',document->'registry_id','scope',document->'scope','org_id',document->'org_id',
        'bundle_id',document->'bundle_id','S_version',document->'S_version','accepted_content_digest',document->'accepted_content_digest'));
    PERFORM scanipy_accepted_inputs.v1_require(scanipy_accepted_inputs.v1_hash(row.publication_receipt_bytes,
      'scanipy-accepted-publication/1')=row.publication_receipt_digest
      AND receipt->>'approval_signature_sha256'=encode(scanipy_accepted_inputs.v1_hash(frame[3]),'hex'),'content-mismatch');
    supporting_objects:=ARRAY[row.publication_input_bytes,row.publication_receipt_bytes];
  END IF;
  record_bytes:=row.record_bytes; RETURN NEXT;
END $$;"""  # noqa: E501

UPDATED_R1 = r"""CREATE OR REPLACE FUNCTION scanipy_accepted_inputs.read_publication_receipt_v1(p_namespace uuid,p_publication_key uuid,p_approval_event_id uuid)
RETURNS TABLE(record_bytes bytea)
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,scanipy_accepted_inputs,pg_temp SET bytea_output='hex' AS $$
DECLARE namespace jsonb; row record; approval jsonb; receipt jsonb;
BEGIN
  PERFORM scanipy_accepted_inputs.v1_work_begin(131072);
  namespace:=scanipy_accepted_inputs.v1_namespace(p_namespace);
  PERFORM scanipy_accepted_inputs.v1_require((p_publication_key IS NULL)<>(p_approval_event_id IS NULL));
  PERFORM scanipy_accepted_inputs.v1_control(512);
  SELECT id,publication_key,record_length,publication_receipt_length INTO row
    FROM scanipy_accepted_inputs.authority_events WHERE namespace_id=p_namespace AND kind='approval'
      AND ((p_publication_key IS NOT NULL AND publication_key=p_publication_key)
        OR (p_approval_event_id IS NOT NULL AND id=p_approval_event_id));
  IF NOT FOUND THEN
    RAISE EXCEPTION 'ledger-mismatch' USING ERRCODE='P0001',
      DETAIL='accepted-historical-row-missing';
  END IF;
  PERFORM scanipy_accepted_inputs.v1_require(row.record_length<=65536
    AND row.publication_receipt_length<=65536,'ledger-mismatch');
  PERFORM scanipy_accepted_inputs.v1_fetch(row.record_length+row.publication_receipt_length);
  SELECT e.record_bytes,e.record_digest,publication_receipt_bytes,publication_receipt_digest,id,publication_key INTO row
    FROM scanipy_accepted_inputs.authority_events e WHERE namespace_id=p_namespace AND kind='approval' AND id=row.id;
  approval:=scanipy_accepted_inputs.v1_stored_document(row.record_bytes,'scanipy-accepted-approval/1');
  receipt:=scanipy_accepted_inputs.v1_stored_document(row.publication_receipt_bytes,'scanipy-accepted-publication/1');
  PERFORM scanipy_accepted_inputs.v1_same_namespace(approval,namespace);
  PERFORM scanipy_accepted_inputs.v1_require(approval->>'event_id'=row.id::text
    AND approval->>'publication_key'=row.publication_key::text
    AND scanipy_accepted_inputs.v1_hash(row.record_bytes,'scanipy-accepted-approval/1')=row.record_digest
    AND scanipy_accepted_inputs.v1_hash(row.publication_receipt_bytes,'scanipy-accepted-publication/1')=row.publication_receipt_digest,
    'content-mismatch');
  PERFORM scanipy_accepted_inputs.v1_publication_links(approval,row.record_digest,receipt);
  record_bytes:=row.publication_receipt_bytes; RETURN NEXT;
END $$;"""  # noqa: E501

UPDATED_R3 = r"""CREATE OR REPLACE FUNCTION scanipy_accepted_inputs.read_authority_event_v1(p_namespace uuid,p_kind text,p_event_id uuid,p_record_digest bytea)
RETURNS TABLE(record_bytes bytea,supporting_objects bytea[])
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,scanipy_accepted_inputs,pg_temp SET bytea_output='hex' AS $$
DECLARE namespace jsonb; row record; document jsonb; schema_name text; total bigint;
  frame bytea[]; receipt jsonb;
BEGIN
  PERFORM scanipy_accepted_inputs.v1_work_begin(1179648);
  namespace:=scanipy_accepted_inputs.v1_namespace(p_namespace);
  schema_name:=CASE p_kind WHEN 'policy' THEN 'scanipy-accepted-trust-policy/1'
    WHEN 'admission' THEN 'scanipy-registry-admission/1' WHEN 'approval' THEN 'scanipy-accepted-approval/1'
    WHEN 'seal-authorization' THEN 'scanipy-capture-seal-authorization/1'
    WHEN 'execution-authorization' THEN 'scanipy-execution-authorization/1'
    WHEN 'execution-denial' THEN 'scanipy-execution-denial/1' ELSE NULL END;
  PERFORM scanipy_accepted_inputs.v1_require(schema_name IS NOT NULL AND p_event_id IS NOT NULL
    AND p_record_digest IS NOT NULL AND octet_length(p_record_digest)=32);
  PERFORM scanipy_accepted_inputs.v1_control(512);
  SELECT record_digest,record_length,publication_input_length,publication_receipt_length INTO row
    FROM scanipy_accepted_inputs.authority_events WHERE namespace_id=p_namespace AND kind=p_kind
      AND id=p_event_id;
  IF NOT FOUND THEN
    RAISE EXCEPTION 'ledger-mismatch' USING ERRCODE='P0001',
      DETAIL='accepted-historical-row-missing';
  END IF;
  PERFORM scanipy_accepted_inputs.v1_require(row.record_digest=p_record_digest,'ledger-mismatch');
  PERFORM scanipy_accepted_inputs.v1_require(row.record_length<=
    CASE WHEN p_kind='policy' THEN 131072 ELSE 65536 END,'ledger-mismatch');
  total:=row.record_length;
  IF p_kind IN ('policy','admission') THEN total:=total+384;
  ELSIF p_kind='approval' THEN
    PERFORM scanipy_accepted_inputs.v1_require(row.publication_input_length BETWEEN 1 AND 1048576
      AND row.publication_receipt_length BETWEEN 1 AND 65536,'content-mismatch');
    total:=total+row.publication_input_length+row.publication_receipt_length;
  END IF;
  PERFORM scanipy_accepted_inputs.v1_fetch(total);
  SELECT e.record_bytes,record_schema,signature_bytes,publication_input_bytes,
    publication_receipt_bytes,publication_receipt_digest INTO row
    FROM scanipy_accepted_inputs.authority_events e WHERE namespace_id=p_namespace AND kind=p_kind AND id=p_event_id;
  PERFORM scanipy_accepted_inputs.v1_require(row.record_schema=schema_name,'content-mismatch');
  document:=scanipy_accepted_inputs.v1_stored_document(row.record_bytes,schema_name);
  PERFORM scanipy_accepted_inputs.v1_same_namespace(document,namespace);
  PERFORM scanipy_accepted_inputs.v1_require(document->>'event_id'=p_event_id::text
    AND scanipy_accepted_inputs.v1_hash(row.record_bytes,schema_name)=p_record_digest,'content-mismatch');
  supporting_objects:=ARRAY[]::bytea[];
  IF p_kind IN ('policy','admission') THEN
    PERFORM scanipy_accepted_inputs.v1_require(octet_length(row.signature_bytes)=384,'content-mismatch');
    supporting_objects:=ARRAY[row.signature_bytes];
  ELSIF p_kind='approval' THEN
    frame:=scanipy_accepted_inputs.v1_stored_frame(row.publication_input_bytes,'scanipy-publication-input/1');
    PERFORM scanipy_accepted_inputs.v1_require(frame[2]=row.record_bytes,'content-mismatch');
    receipt:=scanipy_accepted_inputs.v1_stored_document(row.publication_receipt_bytes,'scanipy-accepted-publication/1');
    PERFORM scanipy_accepted_inputs.v1_publication_links(document,p_record_digest,receipt);
    PERFORM scanipy_accepted_inputs.v1_publication_record(frame,receipt,namespace,
      jsonb_build_object('registry_id',document->'registry_id','scope',document->'scope','org_id',document->'org_id',
        'bundle_id',document->'bundle_id','S_version',document->'S_version','accepted_content_digest',document->'accepted_content_digest'));
    PERFORM scanipy_accepted_inputs.v1_require(scanipy_accepted_inputs.v1_hash(row.publication_receipt_bytes,
      'scanipy-accepted-publication/1')=row.publication_receipt_digest
      AND receipt->>'approval_signature_sha256'=encode(scanipy_accepted_inputs.v1_hash(frame[3]),'hex'),'content-mismatch');
    supporting_objects:=ARRAY[row.publication_input_bytes,row.publication_receipt_bytes];
  END IF;
  record_bytes:=row.record_bytes; RETURN NEXT;
END $$;"""  # noqa: E501

FUNCTIONS: tuple[
    tuple[str, tuple[str, ...], tuple[str, ...], tuple[str, ...], str, str, str], ...
] = (
    (
        "read_publication_receipt_v1(uuid,uuid,uuid)",
        ("uuid", "uuid", "uuid"),
        ("bytea",),
        ("p_namespace", "p_publication_key", "p_approval_event_id", "record_bytes"),
        "bytea",
        ORIGINAL_R1,
        UPDATED_R1,
    ),
    (
        "read_authority_event_v1(uuid,text,uuid,bytea)",
        ("uuid", "text", "uuid", "bytea"),
        ("bytea", "bytea[]"),
        (
            "p_namespace",
            "p_kind",
            "p_event_id",
            "p_record_digest",
            "record_bytes",
            "supporting_objects",
        ),
        "record",
        ORIGINAL_R3,
        UPDATED_R3,
    ),
)


def _execute_literal(statement: str) -> None:
    # Preserve literal PostgreSQL colons; Alembic otherwise invents text binds.
    # The dialect remains responsible for psycopg2 percent escaping.
    op.execute(statement.replace(":", r"\:"))


def _types(names: tuple[str, ...]) -> str:
    return (
        "ARRAY[" + ",".join("'pg_catalog." + name + "'::pg_catalog.regtype" for name in names) + "]"
    )


def _guard(index: int, definition: str, *, remember: bool) -> str:
    signature, inputs, outputs, names, result, _old, _new = FUNCTIONS[index]
    body = definition.split(" AS $$", 1)[1].removesuffix("$$;")
    quoted_body = "$expected$" + body + "$expected$"
    modes = ",".join("'i'" for _ in inputs) + "," + ",".join("'t'" for _ in outputs)
    arguments = ",".join("'" + name + "'" for name in names)
    identity = (
        "pg_catalog.jsonb_build_object('oid',target.oid,'owner',target.proowner,"
        "'acl',target.proacl)"
    )
    preservation = (
        f"identity_{index}:={identity};"
        if remember
        else f"""IF identity_{index} IS DISTINCT FROM {identity} THEN
          RAISE EXCEPTION 'accepted read migration identity drift'; END IF;"""
    )
    # Both targets are validated BEFORE either replacement. Names and all values
    # interpolated here are frozen migration constants, never caller input.
    return f"""
      SELECT p.* INTO target FROM pg_catalog.pg_proc p
        WHERE p.oid=pg_catalog.to_regprocedure('scanipy_accepted_inputs.{signature}');
      IF NOT FOUND THEN RAISE EXCEPTION 'accepted read migration target missing'; END IF;
      IF target.proowner IS DISTINCT FROM pg_catalog.to_regrole('scanipy_accepted_owner')
        OR target.prolang IS DISTINCT FROM
          (SELECT oid FROM pg_catalog.pg_language WHERE lanname='plpgsql')
        OR target.prokind<>'f' OR NOT target.prosecdef OR target.proleakproof
        OR target.proisstrict OR NOT target.proretset
        OR target.provolatile<>'v' OR target.proparallel<>'u'
        OR target.procost<>100 OR target.prorows<>1000 OR target.prosupport<>0
        OR target.pronargs<>{len(inputs)} OR target.pronargdefaults<>0
        OR target.provariadic<>0 OR target.proargdefaults IS NOT NULL
        OR target.protrftypes IS NOT NULL OR target.probin IS NOT NULL
        OR target.prosqlbody IS NOT NULL
        OR target.proargtypes IS DISTINCT FROM {_types(inputs)}::pg_catalog.oidvector
        OR target.proallargtypes IS DISTINCT FROM {_types(inputs + outputs)}::oid[]
        OR target.proargmodes IS DISTINCT FROM ARRAY[{modes}]::"char"[]
        OR target.proargnames IS DISTINCT FROM ARRAY[{arguments}]::text[]
        OR target.prorettype IS DISTINCT FROM 'pg_catalog.{result}'::pg_catalog.regtype
        OR target.proconfig IS DISTINCT FROM
          ARRAY['search_path=pg_catalog, scanipy_accepted_inputs, pg_temp',
            'bytea_output=hex']::text[]
        OR target.prosrc IS DISTINCT FROM {quoted_body}
      THEN RAISE EXCEPTION 'accepted read migration target drift'; END IF;
      {preservation}
    """  # noqa: S608 -- frozen migration signatures, types and literal bodies only


def _replacement(*, forward: bool) -> str:
    before = tuple(item[5] if forward else item[6] for item in FUNCTIONS)
    after = tuple(item[6] if forward else item[5] for item in FUNCTIONS)
    preflight = "".join(_guard(index, body, remember=True) for index, body in enumerate(before))
    replacements = "".join(
        "EXECUTE $definition$"
        + body.replace("CREATE FUNCTION ", "CREATE OR REPLACE FUNCTION ", 1)
        + "$definition$;\n"
        for body in after
    )
    readback = "".join(_guard(index, body, remember=False) for index, body in enumerate(after))
    return f"""DO $migration$
      DECLARE target pg_catalog.pg_proc%ROWTYPE; identity_0 jsonb; identity_1 jsonb;
      BEGIN
        {preflight}
        {replacements}
        {readback}
      END $migration$;"""


def upgrade() -> None:
    _execute_literal(_replacement(forward=True))


def downgrade() -> None:
    _execute_literal(_replacement(forward=False))
