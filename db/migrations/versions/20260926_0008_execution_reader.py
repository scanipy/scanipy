"""Add a function-limited execution reader; no runtime reader or installation.

Only a new NOLOGIN role and seven privileges are owned here. Frozen predecessor
bodies are assertions, never replacements. Downgrade refuses unknown custody.
"""

from alembic import op

revision = "20260926_0008"
down_revision = "20260926_0007"
branch_labels = None
depends_on = None

ROLE = "scanipy_accepted_execution_reader"
SCHEMA = "scanipy_accepted_inputs"
Target = tuple[str, tuple[str, ...], tuple[str, ...], tuple[str, ...], str, bool, str]

TARGETS: tuple[Target, ...] = (
    (
        "read_publication_receipt_v1(uuid,uuid,uuid)",
        ("uuid", "uuid", "uuid"),
        ("bytea",),
        ("p_namespace", "p_publication_key", "p_approval_event_id", "record_bytes"),
        "bytea",
        True,
        """
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
END """,  # noqa: E501 -- exact frozen owning SQL body
    ),
    (
        "read_exact_bundle_v1(uuid,uuid,bytea)",
        ("uuid", "uuid", "bytea"),
        ("bytea", "bytea[]", "bytea[]"),
        (
            "p_namespace",
            "p_bundle_id",
            "p_content_digest",
            "spec_bytes",
            "detector_blobs",
            "rule_blobs",
        ),
        "record",
        True,
        """
DECLARE namespace jsonb; bundle record;
BEGIN
  PERFORM scanipy_accepted_inputs.v1_work_begin(1048576);
  namespace:=scanipy_accepted_inputs.v1_namespace(p_namespace);
  SELECT * INTO bundle FROM scanipy_accepted_inputs.v1_fetch_bundle(p_namespace,p_bundle_id,p_content_digest);
  PERFORM scanipy_accepted_inputs.v1_same_namespace(bundle.manifest,namespace);
  spec_bytes:=bundle.spec_bytes; detector_blobs:=bundle.detector_blobs; rule_blobs:=bundle.rule_blobs;
  RETURN NEXT;
END """,  # noqa: E501 -- exact frozen owning SQL body
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
        True,
        """
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
END """,  # noqa: E501 -- exact frozen owning SQL body
    ),
    (
        "read_request_binding_v1(uuid,uuid,uuid,uuid)",
        ("uuid", "uuid", "uuid", "uuid"),
        ("bytea",),
        ("p_namespace", "p_org", "p_codebase", "p_request", "sealed_bytes"),
        "bytea",
        True,
        """
DECLARE namespace jsonb; row record; frame bytea[]; manifest jsonb; policy jsonb; checkpoint jsonb;
BEGIN
  PERFORM scanipy_accepted_inputs.v1_work_begin(1048576);
  namespace:=scanipy_accepted_inputs.v1_namespace(p_namespace);
  PERFORM scanipy_accepted_inputs.v1_require(p_org IS NOT NULL AND namespace->>'scope'='customer'
    AND namespace->>'org_id'=p_org::text,'scope-mismatch');
  PERFORM scanipy_accepted_inputs.v1_require(p_codebase IS NOT NULL AND p_request IS NOT NULL);
  PERFORM scanipy_accepted_inputs.v1_control(1024);
  SELECT sealed_length INTO row FROM scanipy_accepted_inputs.request_bundle_bindings
    WHERE namespace_id=p_namespace AND org_id=p_org AND codebase_id=p_codebase AND request_id=p_request;
  PERFORM scanipy_accepted_inputs.v1_require(FOUND,'ledger-mismatch');
  PERFORM scanipy_accepted_inputs.v1_fetch(row.sealed_length);
  SELECT b.sealed_bytes,sealed_sha256,registry_id,bundle_id,approval_event_id,policy_event_id,
    admission_event_id,accepted_content_digest,resolved_at INTO row
    FROM scanipy_accepted_inputs.request_bundle_bindings b
    WHERE namespace_id=p_namespace AND org_id=p_org AND codebase_id=p_codebase AND request_id=p_request;
  PERFORM scanipy_accepted_inputs.v1_require(scanipy_accepted_inputs.v1_hash(row.sealed_bytes)=row.sealed_sha256,'content-mismatch');
  frame:=scanipy_accepted_inputs.v1_stored_frame(row.sealed_bytes,'scanipy-sealed-acceptance/1');
  PERFORM scanipy_accepted_inputs.v1_sealed_material(frame,namespace);
  manifest:=scanipy_accepted_inputs.v1_stored_document(frame[1],'scanipy-sealed-acceptance/1');
  policy:=scanipy_accepted_inputs.v1_stored_document(frame[10],'scanipy-accepted-trust-policy/1');
  checkpoint:=scanipy_accepted_inputs.v1_stored_document(frame[15],'scanipy-registry-admission/1');
  PERFORM scanipy_accepted_inputs.v1_require(manifest->>'registry_id'=row.registry_id::text
    AND manifest->>'registry_id'=namespace->>'registry_id' AND manifest->>'org_id'=p_org::text
    AND manifest->>'codebase_id'=p_codebase::text AND manifest->>'request_id'=p_request::text
    AND manifest->>'bundle_id'=row.bundle_id::text AND manifest->>'approval_event_id'=row.approval_event_id::text
    AND manifest->>'accepted_content_digest'=encode(row.accepted_content_digest,'hex')
    AND policy->>'event_id'=row.policy_event_id::text AND checkpoint->>'event_id'=row.admission_event_id::text
    AND (manifest->>'resolved_at')::timestamptz=row.resolved_at,'content-mismatch');
  sealed_bytes:=row.sealed_bytes; RETURN NEXT;
END """,  # noqa: E501 -- exact frozen owning SQL body
    ),
    (
        "read_execution_authority_v1(uuid,bytea,bytea)",
        ("uuid", "bytea", "bytea"),
        ("bytea", "bytea", "text"),
        (
            "p_namespace",
            "binding_bytes",
            "admission_bytes",
            "ledger_bytes",
            "live_bytes",
            "reference_time",
        ),
        "record",
        True,
        """
DECLARE input record;
BEGIN
  PERFORM scanipy_accepted_inputs.v1_work_begin(5701632,8519808,131106);
  SELECT * INTO input FROM scanipy_accepted_inputs.v1_read_inputs(binding_bytes,admission_bytes);
  RETURN QUERY SELECT * FROM scanipy_accepted_inputs.v1_read_current(p_namespace,input.binding,input.admission);
END """,  # noqa: E501 -- exact frozen owning SQL body
    ),
    (
        "recheck_execution_authority_v1(uuid,bytea,bytea,bytea,bytea,text)",
        ("uuid", "bytea", "bytea", "bytea", "bytea", "text"),
        (),
        (
            "p_namespace",
            "binding_bytes",
            "admission_bytes",
            "prior_ledger_bytes",
            "prior_live_bytes",
            "prior_reference_time",
        ),
        "void",
        False,
        """
DECLARE input record; prior_ledger jsonb; prior_live bytea[]; prior_manifest jsonb; current_read record; key text;
BEGIN
  PERFORM scanipy_accepted_inputs.v1_work_begin(5701632,8519808,131106);
  SELECT * INTO input FROM scanipy_accepted_inputs.v1_read_inputs(binding_bytes,admission_bytes);
  prior_ledger:=scanipy_accepted_inputs.v1_json(prior_ledger_bytes,65536);
  PERFORM scanipy_accepted_inputs.v1_shape(prior_ledger,scanipy_accepted_inputs.v1_shapes()->'records'->'LEDGER_EXPECTATION');
  PERFORM scanipy_accepted_inputs.v1_shape(to_jsonb(prior_reference_time),'"instant"');
  PERFORM scanipy_accepted_inputs.v1_require(prior_ledger->'binding'=input.binding
    AND prior_ledger->'execution_authorization_digest'=input.binding->'authorization_digest'
    AND prior_ledger->>'policy_event_id' IS NOT NULL AND prior_ledger->>'admission_event_id' IS NOT NULL,'ledger-mismatch');
  prior_live:=scanipy_accepted_inputs.v1_frame(prior_live_bytes,'scanipy-registry-current-authority/1');
  prior_manifest:=scanipy_accepted_inputs.v1_document(prior_live[1],'scanipy-registry-current-authority/1');
  FOR key IN SELECT jsonb_object_keys(input.admission) LOOP
    PERFORM scanipy_accepted_inputs.v1_require(prior_manifest->key=input.admission->key,'policy-stale');
  END LOOP;
  SELECT * INTO current_read FROM scanipy_accepted_inputs.v1_read_current(p_namespace,input.binding,input.admission);
  PERFORM scanipy_accepted_inputs.v1_require(current_read.ledger_bytes=prior_ledger_bytes
    AND current_read.live_bytes=prior_live_bytes,'policy-stale');
  PERFORM scanipy_accepted_inputs.v1_require(current_read.reference_time::timestamptz>=prior_reference_time::timestamptz,'fence-stale');
  RETURN;
END """,  # noqa: E501 -- exact frozen owning SQL body
    ),
)


def _literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _types(names: tuple[str, ...]) -> str:
    return (
        "ARRAY["
        + ",".join(_literal("pg_catalog." + name) + "::pg_catalog.regtype" for name in names)
        + "]"
    )


def _acl(expression: str, kind: str, owner: str) -> str:
    # The callers supply only private frozen expressions, not input SQL.
    return f"""(SELECT coalesce(jsonb_agg(
      jsonb_build_array(a.grantor,a.grantee,a.privilege_type,a.is_grantable)
      ORDER BY a.grantor,a.grantee,a.privilege_type COLLATE "C",a.is_grantable),'[]'::jsonb)
      FROM pg_catalog.aclexplode(coalesce({expression},pg_catalog.acldefault('{kind}',{owner}))) a
      WHERE a.grantee IS DISTINCT FROM role_oid)"""  # noqa: S608 -- fixed internal ACL expressions


def _function_guard(index: int, *, remember: bool) -> str:
    signature, inputs, outputs, names, result, retset, body = TARGETS[index]
    label = f"$ear_body_{index}$"
    assert label not in body
    all_types = _types(inputs + outputs) + "::oid[]" if outputs else "NULL::oid[]"
    modes = (
        "ARRAY["
        + ",".join(_literal(v) for v in ("i",) * len(inputs) + ("t",) * len(outputs))
        + ']::"char"[]'
        if outputs
        else 'NULL::"char"[]'
    )
    argnames = "ARRAY[" + ",".join(_literal(v) for v in names) + "]::text[]"
    append_oid = (
        "target_oids:=array_append(target_oids,f.oid);"
        if remember
        else f"""IF f.oid IS DISTINCT FROM target_oids[{index + 1}] THEN
          RAISE EXCEPTION 'execution reader target identity changed'; END IF;"""
    )
    destination = "before_objects" if remember else "after_objects"
    return f"""
      SELECT p.* INTO f FROM pg_catalog.pg_proc p
        WHERE p.oid=pg_catalog.to_regprocedure('scanipy_accepted_inputs.{signature}');
      IF NOT FOUND THEN RAISE EXCEPTION 'execution reader target missing'; END IF;
      IF f.proowner IS DISTINCT FROM pg_catalog.to_regrole('scanipy_accepted_owner')
        OR f.pronamespace IS DISTINCT FROM accepted_schema_oid
        OR f.prolang IS DISTINCT FROM
          (SELECT oid FROM pg_catalog.pg_language WHERE lanname='plpgsql')
        OR f.prokind<>'f' OR NOT f.prosecdef OR f.proleakproof OR f.proisstrict
        OR f.proretset IS DISTINCT FROM {str(retset).lower()}
        OR f.provolatile<>'v' OR f.proparallel<>'u'
        OR f.procost<>100 OR f.prorows<>{1000 if retset else 0} OR f.prosupport<>0
        OR f.pronargs<>{len(inputs)} OR f.pronargdefaults<>0 OR f.provariadic<>0
        OR f.proargdefaults IS NOT NULL OR f.protrftypes IS NOT NULL
        OR f.probin IS NOT NULL OR f.prosqlbody IS NOT NULL
        OR f.proargtypes IS DISTINCT FROM {_types(inputs)}::pg_catalog.oidvector
        OR f.proallargtypes IS DISTINCT FROM {all_types}
        OR f.proargmodes IS DISTINCT FROM {modes}
        OR f.proargnames IS DISTINCT FROM {argnames}
        OR f.prorettype IS DISTINCT FROM 'pg_catalog.{result}'::pg_catalog.regtype
        OR f.proconfig IS DISTINCT FROM
          ARRAY['search_path=pg_catalog, scanipy_accepted_inputs, pg_temp',
            'bytea_output=hex']::text[]
        OR f.prosrc IS DISTINCT FROM {label}{body}{label}
        OR coalesce(cardinality(f.proacl),0)>64
      THEN RAISE EXCEPTION 'execution reader target drift'; END IF;
      IF EXISTS(SELECT 1 FROM pg_catalog.aclexplode(
          coalesce(f.proacl,pg_catalog.acldefault('f',f.proowner))) a WHERE a.grantee=0) THEN
        RAISE EXCEPTION 'execution reader target PUBLIC privilege'; END IF;
      {append_oid}
      {destination}:={destination}||jsonb_build_array(jsonb_build_object(
        'kind','function','properties',to_jsonb(f)-'proacl',
        'acl',{_acl("f.proacl", "f", "f.proowner")}));
    """  # noqa: S608 -- private frozen target metadata/body expressions only


def _objects(*, remember: bool) -> str:
    destination = "before_objects" if remember else "after_objects"
    functions = "".join(_function_guard(i, remember=remember) for i in range(len(TARGETS)))
    schemas = f"""
      FOR v_n IN SELECT * FROM pg_catalog.pg_namespace
        WHERE oid IN (accepted_schema_oid,execution_schema_oid) ORDER BY oid
      LOOP
        IF coalesce(cardinality(v_n.nspacl),0)>64 THEN
          RAISE EXCEPTION 'execution reader schema ACL overflow'; END IF;
        IF EXISTS(SELECT 1 FROM pg_catalog.aclexplode(
          coalesce(v_n.nspacl,pg_catalog.acldefault('n',v_n.nspowner))) a WHERE a.grantee=0) THEN
          RAISE EXCEPTION 'execution reader schema PUBLIC privilege'; END IF;
        {destination}:={destination}||jsonb_build_array(jsonb_build_object(
          'kind','schema','properties',to_jsonb(v_n)-'nspacl',
          'acl',{_acl("v_n.nspacl", "n", "v_n.nspowner")}));
      END LOOP;
      IF jsonb_array_length({destination})<>8 THEN
        RAISE EXCEPTION 'execution reader object inventory changed'; END IF;
    """  # noqa: S608 -- fixed snapshot destinations and protected schemas only
    return functions + schemas


def _role_guard(*, granted: bool) -> str:
    expected_count = 7 if granted else 0
    expected_usage = "true" if granted else "false"
    expected_functions = "p.oid=ANY(target_oids)" if granted else "false"
    # pg_authid inspection returns flags/absence booleans, never credential bytes.
    return f"""
      SELECT r.oid,r.rolsuper,r.rolinherit,r.rolcreaterole,r.rolcreatedb,
        r.rolcanlogin,r.rolreplication,r.rolbypassrls,r.rolconnlimit,
        r.rolpassword IS NULL AS no_password,r.rolvaliduntil IS NULL AS no_expiry
        INTO reader FROM pg_catalog.pg_authid r WHERE r.rolname='{ROLE}';
      IF NOT FOUND OR reader.oid IS DISTINCT FROM role_oid OR reader.rolsuper
        OR reader.rolinherit OR reader.rolcreaterole OR reader.rolcreatedb
        OR reader.rolcanlogin OR reader.rolreplication OR reader.rolbypassrls
        OR reader.rolconnlimit<>-1 OR NOT reader.no_password OR NOT reader.no_expiry
      THEN RAISE EXCEPTION 'execution reader role drift'; END IF;
      IF EXISTS(SELECT 1 FROM pg_catalog.pg_auth_members
          WHERE roleid=role_oid OR member=role_oid OR grantor=role_oid)
        OR EXISTS(SELECT 1 FROM pg_catalog.pg_db_role_setting WHERE setrole=role_oid)
        OR EXISTS(SELECT 1 FROM pg_catalog.pg_shdescription
          WHERE classoid='pg_catalog.pg_authid'::regclass AND objoid=role_oid)
        OR EXISTS(SELECT 1 FROM pg_catalog.pg_shseclabel
          WHERE classoid='pg_catalog.pg_authid'::regclass AND objoid=role_oid)
      THEN RAISE EXCEPTION 'execution reader foreign role metadata'; END IF;
      WITH dependencies AS MATERIALIZED (
        SELECT dbid,classid,objid,objsubid,deptype FROM pg_catalog.pg_shdepend
        WHERE refclassid='pg_catalog.pg_authid'::regclass AND refobjid=role_oid LIMIT 8
      )
      SELECT count(*),coalesce(bool_and(dbid=database_oid AND objsubid=0 AND deptype='a'
        AND ((classid='pg_catalog.pg_proc'::regclass AND objid=ANY(target_oids))
          OR (classid='pg_catalog.pg_namespace'::regclass AND objid=accepted_schema_oid))),true)
        INTO dependency_count,dependencies_owned FROM dependencies;
      IF dependency_count<>{expected_count} OR NOT dependencies_owned THEN
        RAISE EXCEPTION 'execution reader foreign dependency'; END IF;
      WITH entries AS (
        SELECT 'function'::text AS object_kind,p.oid AS object_oid,p.proowner AS owner,
          a.grantor,a.privilege_type,a.is_grantable,
          'EXECUTE'::text AS expected
        FROM pg_catalog.pg_proc p CROSS JOIN LATERAL pg_catalog.aclexplode(
          coalesce(p.proacl,pg_catalog.acldefault('f',p.proowner))) a
        WHERE p.oid=ANY(target_oids) AND a.grantee=role_oid
        UNION ALL
        SELECT 'schema',n.oid,n.nspowner,a.grantor,a.privilege_type,a.is_grantable,'USAGE'
        FROM pg_catalog.pg_namespace n CROSS JOIN LATERAL pg_catalog.aclexplode(
          coalesce(n.nspacl,pg_catalog.acldefault('n',n.nspowner))) a
        WHERE n.oid=accepted_schema_oid AND a.grantee=role_oid
      )
      SELECT count(*),count(DISTINCT (object_kind,object_oid)),
        coalesce(bool_and(grantor=owner AND privilege_type=expected AND NOT is_grantable),true)
        INTO entry_count,object_count,entries_owned FROM entries;
      IF entry_count<>{expected_count} OR object_count<>{expected_count} OR NOT entries_owned THEN
        RAISE EXCEPTION 'execution reader grant drift'; END IF;
      IF EXISTS(SELECT 1 FROM pg_catalog.pg_namespace n
        WHERE n.oid IN (accepted_schema_oid,execution_schema_oid) AND
          (n.nspowner=role_oid
           OR pg_catalog.has_schema_privilege(role_oid,n.oid,'CREATE')
           OR pg_catalog.has_schema_privilege(role_oid,n.oid,'USAGE WITH GRANT OPTION')
           OR pg_catalog.has_schema_privilege(role_oid,n.oid,'USAGE')
             IS DISTINCT FROM (n.oid=accepted_schema_oid AND {expected_usage}))) THEN
        RAISE EXCEPTION 'execution reader schema privilege drift'; END IF;
      IF EXISTS(SELECT 1 FROM pg_catalog.pg_proc p
        WHERE p.pronamespace IN (accepted_schema_oid,execution_schema_oid) AND
          (p.proowner=role_oid
           OR pg_catalog.has_function_privilege(role_oid,p.oid,'EXECUTE')
             IS DISTINCT FROM ({expected_functions})
           OR pg_catalog.has_function_privilege(role_oid,p.oid,'EXECUTE WITH GRANT OPTION'))) THEN
        RAISE EXCEPTION 'execution reader function privilege drift'; END IF;
      IF EXISTS(SELECT 1 FROM pg_catalog.pg_class c
        WHERE c.relnamespace IN (accepted_schema_oid,execution_schema_oid) AND
          (c.relowner=role_oid OR CASE
            WHEN c.relkind='S' THEN
              pg_catalog.has_sequence_privilege(role_oid,c.oid,'USAGE,SELECT,UPDATE')
            WHEN c.relkind IN ('r','p','v','m','f') THEN
              pg_catalog.has_table_privilege(role_oid,c.oid,'SELECT,INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER')
              OR pg_catalog.has_any_column_privilege(
                role_oid,c.oid,'SELECT,INSERT,UPDATE,REFERENCES')
            ELSE false END)) THEN
        RAISE EXCEPTION 'execution reader data privilege drift'; END IF;
    """  # noqa: S608 -- exact role, booleans and closed integer counts only


def _privileges(*, grant: bool) -> str:
    verb = "GRANT" if grant else "REVOKE"
    preposition = "TO" if grant else "FROM"
    suffix = "" if grant else " RESTRICT"
    statements = [f"{verb} USAGE ON SCHEMA {SCHEMA} {preposition} {ROLE}{suffix}"]
    statements.extend(
        f"{verb} EXECUTE ON FUNCTION {SCHEMA}.{item[0]} {preposition} {ROLE}{suffix}"
        for item in TARGETS
    )
    return "".join("EXECUTE " + _literal(statement) + ";\n" for statement in statements)


def _migration_sql(*, forward: bool) -> str:
    expected_revision = down_revision if forward else revision
    preflight = f"""
      IF current_setting('server_encoding')<>'UTF8'
        OR current_setting('server_version_num')::integer NOT BETWEEN 160000 AND 169999
        OR current_setting('standard_conforming_strings')<>'on'
        OR NOT EXISTS(SELECT 1 FROM pg_catalog.pg_roles
          WHERE rolname=current_user AND rolsuper) THEN
        RAISE EXCEPTION 'execution reader requires trusted PostgreSQL16 UTF8 superuser migration';
      END IF;
      IF ARRAY(SELECT version_num::text FROM public.alembic_version ORDER BY version_num LIMIT 2)
        IS DISTINCT FROM ARRAY['{expected_revision}']::text[] THEN
        RAISE EXCEPTION 'execution reader predecessor revision mismatch'; END IF;
      SELECT oid INTO database_oid FROM pg_catalog.pg_database WHERE datname=current_database();
      SELECT oid INTO accepted_schema_oid FROM pg_catalog.pg_namespace WHERE nspname='{SCHEMA}';
      SELECT oid INTO execution_schema_oid FROM pg_catalog.pg_namespace
        WHERE nspname='scanipy_execution';
      IF accepted_schema_oid IS NULL OR execution_schema_oid IS NULL
        OR accepted_schema_oid=execution_schema_oid
        OR NOT EXISTS(SELECT 1 FROM pg_catalog.pg_roles
          WHERE rolname='scanipy_accepted_owner' AND NOT rolcanlogin AND NOT rolinherit
            AND NOT rolsuper AND NOT rolcreatedb AND NOT rolcreaterole
            AND NOT rolreplication AND NOT rolbypassrls)
      THEN RAISE EXCEPTION 'execution reader predecessor identity mismatch'; END IF;
    """  # noqa: S608 -- literal revision and schema only
    if forward:
        steps = f"""
          IF EXISTS(SELECT 1 FROM pg_catalog.pg_roles WHERE rolname='{ROLE}') THEN
            RAISE EXCEPTION 'execution reader role collision'; END IF;
          {_objects(remember=True)}
          EXECUTE 'CREATE ROLE {ROLE} NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB
            NOCREATEROLE NOREPLICATION NOBYPASSRLS CONNECTION LIMIT -1 PASSWORD NULL';
          SELECT oid INTO role_oid FROM pg_catalog.pg_roles WHERE rolname='{ROLE}';
          IF role_oid IS NULL THEN RAISE EXCEPTION 'execution reader role missing'; END IF;
          {_privileges(grant=True)}
          {_role_guard(granted=True)}
          {_objects(remember=False)}
        """  # noqa: S608 -- frozen migration statements only
    else:
        steps = f"""
          SELECT oid INTO role_oid FROM pg_catalog.pg_roles WHERE rolname='{ROLE}';
          IF role_oid IS NULL THEN RAISE EXCEPTION 'execution reader role missing'; END IF;
          {_objects(remember=True)}
          {_role_guard(granted=True)}
          {_privileges(grant=False)}
          {_role_guard(granted=False)}
          EXECUTE 'DROP ROLE {ROLE}';
          IF EXISTS(SELECT 1 FROM pg_catalog.pg_roles WHERE rolname='{ROLE}') THEN
            RAISE EXCEPTION 'execution reader role removal failed'; END IF;
          {_objects(remember=False)}
        """  # noqa: S608 -- frozen migration statements only
    return f"""DO $execution_reader_migration$
      DECLARE f pg_catalog.pg_proc%ROWTYPE; v_n pg_catalog.pg_namespace%ROWTYPE; reader record;
        database_oid pg_catalog.oid; accepted_schema_oid pg_catalog.oid;
        execution_schema_oid pg_catalog.oid; role_oid pg_catalog.oid;
        target_oids pg_catalog.oid[]:='{{}}';
        before_objects pg_catalog.jsonb:='[]'; after_objects pg_catalog.jsonb:='[]';
        prior_search_path pg_catalog.text:=pg_catalog.current_setting('search_path');
        dependency_count bigint; dependencies_owned boolean;
        entry_count bigint; object_count bigint; entries_owned boolean;
      BEGIN
        PERFORM pg_catalog.set_config('search_path','pg_catalog,pg_temp',true);
        {preflight}
        {steps}
        IF after_objects IS DISTINCT FROM before_objects THEN
          RAISE EXCEPTION 'execution reader original objects changed'; END IF;
        PERFORM pg_catalog.set_config('search_path',prior_search_path,true);
      END $execution_reader_migration$;"""


def _execute_literal(statement: str) -> None:
    # Same accepted Alembic colon escaping; the dialect owns percent escaping.
    op.execute(statement.replace(":", r"\:"))


def upgrade() -> None:
    _execute_literal(_migration_sql(forward=True))


def downgrade() -> None:
    _execute_literal(_migration_sql(forward=False))
