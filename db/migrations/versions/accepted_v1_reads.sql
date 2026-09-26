-- Exact immutable reads and locked current reads. No provider, external trust,
-- latest-bundle discovery or read-side authorization event is created here.
CREATE FUNCTION scanipy_accepted_inputs.v1_stored_document(data bytea,schema_name text)
RETURNS jsonb LANGUAGE plpgsql IMMUTABLE SET search_path=pg_catalog,scanipy_accepted_inputs,pg_temp AS $$
DECLARE message text; detail text;
BEGIN
  RETURN scanipy_accepted_inputs.v1_document(data,schema_name);
EXCEPTION WHEN SQLSTATE 'P0001' THEN
  GET STACKED DIAGNOSTICS message=MESSAGE_TEXT,detail=PG_EXCEPTION_DETAIL;
  IF message='invalid-input' AND detail IS DISTINCT FROM 'accepted-work-limit' THEN
    RAISE EXCEPTION 'content-mismatch' USING ERRCODE='P0001';
  END IF;
  RAISE;
END $$;

-- Explicit stored provenance at each caller, not an authority bit or an input
-- validator mode. Delegate once, retain one shared no-refund accounting meter,
-- and leave timeouts, locks, unknown errors and marked limit failures intact.
CREATE FUNCTION scanipy_accepted_inputs.v1_stored_frame(data bytea,schema_name text)
RETURNS bytea[] LANGUAGE plpgsql SET search_path=pg_catalog,scanipy_accepted_inputs,pg_temp AS $$
DECLARE message text; detail text;
BEGIN
  RETURN scanipy_accepted_inputs.v1_frame(data,schema_name);
EXCEPTION WHEN SQLSTATE 'P0001' THEN
  GET STACKED DIAGNOSTICS message=MESSAGE_TEXT,detail=PG_EXCEPTION_DETAIL;
  IF message='invalid-input' AND detail IS DISTINCT FROM 'accepted-work-limit' THEN
    RAISE EXCEPTION 'content-mismatch' USING ERRCODE='P0001';
  END IF;
  RAISE;
END $$;

CREATE FUNCTION scanipy_accepted_inputs.v1_stored_occurrence(data bytea,schema_name text)
RETURNS jsonb LANGUAGE plpgsql IMMUTABLE SET search_path=pg_catalog,scanipy_accepted_inputs,pg_temp AS $$
DECLARE message text; detail text;
BEGIN
  RETURN scanipy_accepted_inputs.v1_occurrence(data,schema_name);
EXCEPTION WHEN SQLSTATE 'P0001' THEN
  GET STACKED DIAGNOSTICS message=MESSAGE_TEXT,detail=PG_EXCEPTION_DETAIL;
  IF message='invalid-input' AND detail IS DISTINCT FROM 'accepted-work-limit' THEN
    RAISE EXCEPTION 'content-mismatch' USING ERRCODE='P0001';
  END IF;
  RAISE;
END $$;

CREATE FUNCTION scanipy_accepted_inputs.v1_stored_bundle(spec bytea,detectors bytea[],rules bytea[])
RETURNS TABLE(manifest jsonb,model_blobs bytea[],content_bytes bytea,content_digest bytea)
LANGUAGE plpgsql SET search_path=pg_catalog,scanipy_accepted_inputs,pg_temp AS $$
DECLARE message text; detail text;
BEGIN
  RETURN QUERY SELECT * FROM scanipy_accepted_inputs.v1_bundle(spec,detectors,rules);
EXCEPTION WHEN SQLSTATE 'P0001' THEN
  GET STACKED DIAGNOSTICS message=MESSAGE_TEXT,detail=PG_EXCEPTION_DETAIL;
  IF message='invalid-input' AND detail IS DISTINCT FROM 'accepted-work-limit' THEN
    RAISE EXCEPTION 'content-mismatch' USING ERRCODE='P0001';
  END IF;
  RAISE;
END $$;

CREATE FUNCTION scanipy_accepted_inputs.v1_fetch_bundle(p_namespace uuid,p_bundle uuid,p_digest bytea)
RETURNS TABLE(spec_bytes bytea,detector_blobs bytea[],rule_blobs bytea[],manifest jsonb,
  model_blobs bytea[],accepted_content_bytes bytea,content_digest bytea)
LANGUAGE plpgsql SET search_path=pg_catalog,scanipy_accepted_inputs,pg_temp SET bytea_output='hex' AS $$
DECLARE meta record; row record; member record; validated record; actual_length bigint; i integer;
  reference uuid; refs uuid[]; kind_name text; descriptor jsonb; scalar_length integer; blob bytea;
BEGIN
  PERFORM scanipy_accepted_inputs.v1_require(p_namespace IS NOT NULL AND p_bundle IS NOT NULL
    AND p_digest IS NOT NULL AND octet_length(p_digest)=32);
  PERFORM scanipy_accepted_inputs.v1_control(128);
  SELECT spec_length,content_length,detector_count,rule_count,model_count INTO meta
    FROM scanipy_accepted_inputs.bundle_versions WHERE namespace_id=p_namespace AND id=p_bundle
      AND accepted_content_digest=p_digest;
  PERFORM scanipy_accepted_inputs.v1_require(FOUND,'ledger-mismatch');
  PERFORM scanipy_accepted_inputs.v1_control(16::bigint*(meta.detector_count+meta.rule_count+meta.model_count)+128);
  PERFORM scanipy_accepted_inputs.v1_fetch(meta.content_length);
  SELECT b.spec_bytes,b.detector_ids,b.rule_ids,b.model_ids,b.s_version INTO row
    FROM scanipy_accepted_inputs.bundle_versions b WHERE namespace_id=p_namespace AND id=p_bundle;
  spec_bytes:=row.spec_bytes; actual_length:=octet_length(spec_bytes);
  PERFORM scanipy_accepted_inputs.v1_require(actual_length=meta.spec_length AND actual_length<=meta.content_length
    AND cardinality(row.detector_ids)=meta.detector_count AND cardinality(row.rule_ids)=meta.rule_count
    AND cardinality(row.model_ids)=meta.model_count,'content-mismatch');
  detector_blobs:=ARRAY[]::bytea[]; rule_blobs:=ARRAY[]::bytea[];
  FOREACH kind_name IN ARRAY ARRAY['detector','rule-set'] LOOP
    refs:=CASE WHEN kind_name='detector' THEN row.detector_ids ELSE row.rule_ids END;
    FOREACH reference IN ARRAY refs LOOP
      PERFORM scanipy_accepted_inputs.v1_control(16);
      SELECT raw_length,metadata_length INTO member FROM scanipy_accepted_inputs.artifact_versions
        WHERE namespace_id=p_namespace AND id=reference AND kind=kind_name;
      PERFORM scanipy_accepted_inputs.v1_require(FOUND,'content-mismatch');
      actual_length:=actual_length+member.raw_length;
      PERFORM scanipy_accepted_inputs.v1_require(actual_length<=meta.content_length,'content-mismatch');
      SELECT raw_bytes INTO blob FROM scanipy_accepted_inputs.artifact_versions
        WHERE namespace_id=p_namespace AND id=reference AND kind=kind_name;
      PERFORM scanipy_accepted_inputs.v1_require(octet_length(blob)=member.raw_length,'content-mismatch');
      IF kind_name='detector' THEN detector_blobs:=array_append(detector_blobs,blob);
      ELSE rule_blobs:=array_append(rule_blobs,blob); END IF;
    END LOOP;
  END LOOP;
  PERFORM scanipy_accepted_inputs.v1_require(actual_length=meta.content_length,'content-mismatch');
  SELECT * INTO validated FROM scanipy_accepted_inputs.v1_stored_bundle(spec_bytes,detector_blobs,rule_blobs);
  manifest:=validated.manifest; model_blobs:=validated.model_blobs; accepted_content_bytes:=validated.content_bytes;
  content_digest:=validated.content_digest;
  PERFORM scanipy_accepted_inputs.v1_require(validated.content_digest=p_digest
    AND manifest->>'bundle_id'=p_bundle::text AND manifest->>'S_version'=row.s_version,'content-mismatch');
  -- Verify every ordered artifact-row identity without refetching model bytes:
  -- models already occur in the charged exact framed S.
  FOREACH kind_name IN ARRAY ARRAY['detector','rule-set','operation-model'] LOOP
    refs:=CASE kind_name WHEN 'detector' THEN row.detector_ids WHEN 'rule-set' THEN row.rule_ids ELSE row.model_ids END;
    i:=0;
    FOREACH reference IN ARRAY refs LOOP
      i:=i+1;
      PERFORM scanipy_accepted_inputs.v1_control(16);
      SELECT metadata_length INTO scalar_length FROM scanipy_accepted_inputs.artifact_versions
        WHERE namespace_id=p_namespace AND id=reference AND kind=kind_name;
      PERFORM scanipy_accepted_inputs.v1_require(FOUND,'content-mismatch');
      PERFORM scanipy_accepted_inputs.v1_control(scalar_length);
      SELECT artifact_id,version,artifact_schema,raw_length,raw_sha256 INTO member
        FROM scanipy_accepted_inputs.artifact_versions WHERE namespace_id=p_namespace AND id=reference AND kind=kind_name;
      IF kind_name='detector' THEN
        descriptor:=manifest->'detectors'->(i-1);
        PERFORM scanipy_accepted_inputs.v1_require(member.artifact_id=descriptor->>'detector_id'
          AND member.version=descriptor->>'detector_version' AND member.artifact_schema=descriptor->>'detector_schema'
          AND member.raw_sha256=decode(descriptor->>'detector_sha256','hex'),'content-mismatch');
      ELSIF kind_name='rule-set' THEN
        SELECT rule INTO descriptor FROM jsonb_array_elements(manifest->'detectors') WITH ORDINALITY d(detector,dn)
          CROSS JOIN LATERAL jsonb_array_elements(detector->'rules') WITH ORDINALITY r(rule,rn)
          ORDER BY dn,rn OFFSET i-1 LIMIT 1;
        PERFORM scanipy_accepted_inputs.v1_require(member.artifact_id=descriptor->>'artifact_id'
          AND member.version=descriptor->>'version' AND member.artifact_schema=descriptor->>'schema'
          AND member.raw_sha256=decode(descriptor->>'raw_sha256','hex'),'content-mismatch');
      ELSE
        descriptor:=manifest->'models'->(i-1);
        PERFORM scanipy_accepted_inputs.v1_require(member.artifact_id=descriptor->>'artifact_id'
          AND member.version=descriptor->>'version' AND member.artifact_schema=descriptor->>'schema'
          AND member.raw_sha256=decode(descriptor->>'raw_sha256','hex')
          AND member.raw_length=octet_length(model_blobs[i]),'content-mismatch');
      END IF;
    END LOOP;
  END LOOP;
  RETURN NEXT;
END $$;

CREATE FUNCTION scanipy_accepted_inputs.read_exact_bundle_v1(p_namespace uuid,p_bundle_id uuid,p_content_digest bytea)
RETURNS TABLE(spec_bytes bytea,detector_blobs bytea[],rule_blobs bytea[])
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,scanipy_accepted_inputs,pg_temp SET bytea_output='hex' AS $$
DECLARE namespace jsonb; bundle record;
BEGIN
  PERFORM scanipy_accepted_inputs.v1_work_begin(1048576);
  namespace:=scanipy_accepted_inputs.v1_namespace(p_namespace);
  SELECT * INTO bundle FROM scanipy_accepted_inputs.v1_fetch_bundle(p_namespace,p_bundle_id,p_content_digest);
  PERFORM scanipy_accepted_inputs.v1_same_namespace(bundle.manifest,namespace);
  spec_bytes:=bundle.spec_bytes; detector_blobs:=bundle.detector_blobs; rule_blobs:=bundle.rule_blobs;
  RETURN NEXT;
END $$;

CREATE FUNCTION scanipy_accepted_inputs.v1_publication_links(approval jsonb,approval_digest bytea,receipt jsonb)
RETURNS void LANGUAGE plpgsql IMMUTABLE SET search_path=pg_catalog,scanipy_accepted_inputs,pg_temp AS $$
DECLARE key text;
BEGIN
  FOREACH key IN ARRAY ARRAY['registry_id','scope','org_id','publication_key','bundle_id','accepted_content_digest','evidence_inventory_digest'] LOOP
    PERFORM scanipy_accepted_inputs.v1_require(receipt->key=approval->key,'ledger-mismatch');
  END LOOP;
  PERFORM scanipy_accepted_inputs.v1_require(receipt->'approval_event_id'=approval->'event_id'
    AND receipt->'publisher_actor_id'=approval->'issuer_actor_id'
    AND receipt->>'approval_statement_digest'=encode(approval_digest,'hex'),'ledger-mismatch');
END $$;

CREATE FUNCTION scanipy_accepted_inputs.read_publication_receipt_v1(p_namespace uuid,p_publication_key uuid,p_approval_event_id uuid)
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
END $$;

CREATE FUNCTION scanipy_accepted_inputs.read_authority_event_v1(p_namespace uuid,p_kind text,p_event_id uuid,p_record_digest bytea)
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
END $$;

CREATE FUNCTION scanipy_accepted_inputs.read_request_binding_v1(p_namespace uuid,p_org uuid,p_codebase uuid,p_request uuid)
RETURNS TABLE(sealed_bytes bytea)
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,scanipy_accepted_inputs,pg_temp SET bytea_output='hex' AS $$
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
END $$;

CREATE FUNCTION scanipy_accepted_inputs.v1_read_bridge_reserve() RETURNS void
LANGUAGE plpgsql SET search_path=pg_catalog,scanipy_accepted_inputs,pg_temp AS $$
BEGIN
  -- Appendix J: census AND independently ordered run-ID lock pass, plus the
  -- closed fixed scalar/result representations. No raw/hash/legacy K credit.
  PERFORM scanipy_accepted_inputs.v1_charge(3,8454272);
  PERFORM scanipy_accepted_inputs.v1_charge(5,131106);
END $$;

CREATE FUNCTION scanipy_accepted_inputs.v1_read_inputs(binding_bytes bytea,admission_bytes bytea)
RETURNS TABLE(binding jsonb,admission jsonb)
LANGUAGE plpgsql IMMUTABLE SET search_path=pg_catalog,scanipy_accepted_inputs,pg_temp AS $$
BEGIN
  binding:=scanipy_accepted_inputs.v1_json(binding_bytes,65536);
  admission:=scanipy_accepted_inputs.v1_json(admission_bytes,65536);
  PERFORM scanipy_accepted_inputs.v1_shape(binding,scanipy_accepted_inputs.v1_shapes()->'records'->'EXECUTION_BINDING');
  PERFORM scanipy_accepted_inputs.v1_shape(admission,scanipy_accepted_inputs.v1_shapes()->'records'->'ADMISSION_EXPECTATION');
  RETURN NEXT;
END $$;

-- Shared private body: no meter initialization, no call to a public read, one
-- actual detector bridge. R6's prior validation shares this same no-refund work.
CREATE FUNCTION scanipy_accepted_inputs.v1_read_current(p_namespace uuid,binding jsonb,admission jsonb)
RETURNS TABLE(ledger_bytes bytea,live_bytes bytea,reference_time text)
LANGUAGE plpgsql SET search_path=pg_catalog,scanipy_accepted_inputs,pg_temp SET bytea_output='hex' AS $$
DECLARE namespace jsonb; live record; current_execution record; sealed record; request_binding record; bundle record;
  context jsonb; fence jsonb; key text; source_name text; approval jsonb; receipt jsonb; grant_row jsonb;
  moment timestamptz; issued timestamptz; ledger jsonb;
BEGIN
  namespace:=scanipy_accepted_inputs.v1_namespace(p_namespace);
  PERFORM scanipy_accepted_inputs.v1_require(namespace->>'scope'='customer'
    AND namespace->'org_id'=binding->'org_id','scope-mismatch');
  SELECT * INTO live FROM scanipy_accepted_inputs.v1_live(namespace,admission);
  SELECT * INTO current_execution FROM scanipy_accepted_inputs.v1_fetch_execution(namespace,
    (binding->>'work_attempt_id')::uuid,(binding->>'detector_run_id')::uuid,(binding->>'authorization_event_id')::uuid);
  PERFORM scanipy_accepted_inputs.v1_require(binding->>'authorization_digest'=encode(current_execution.record_digest,'hex'),'ledger-mismatch');
  FOR key IN SELECT jsonb_object_keys(scanipy_accepted_inputs.v1_shapes()->'records'->'EXECUTION_BINDING') LOOP
    IF key='authorization_digest' THEN CONTINUE; END IF;
    source_name:=CASE WHEN key='authorization_event_id' THEN 'event_id' ELSE key END;
    PERFORM scanipy_accepted_inputs.v1_require(binding->key=current_execution.document->source_name,'fence-stale');
  END LOOP;
  SELECT * INTO sealed FROM scanipy_accepted_inputs.v1_fetch_seal(namespace,(binding->>'work_item_id')::uuid);
  SELECT * INTO request_binding FROM scanipy_accepted_inputs.v1_fetch_binding(namespace,(binding->>'request_id')::uuid);
  SELECT * INTO bundle FROM scanipy_accepted_inputs.v1_fetch_bundle(p_namespace,(request_binding.expected->>'bundle_id')::uuid,
    decode(request_binding.expected->>'accepted_content_digest','hex'));
  PERFORM scanipy_accepted_inputs.v1_planned_projection(bundle.manifest,request_binding.planned);
  PERFORM scanipy_accepted_inputs.v1_require(scanipy_accepted_inputs.v1_planned_pins_present(request_binding.planned),'grant-denied');
  PERFORM scanipy_accepted_inputs.v1_execution_material(namespace,request_binding.expected,request_binding.sealed_digest,
    request_binding.manifest,request_binding.planned,sealed.document,sealed.seal,current_execution.run_input);
  FOREACH key IN ARRAY ARRAY['policy_event_id','admission_event_id','policy_digest','policy_revision',
    'checkpoint_digest','checkpoint_generation','admission_epoch'] LOOP
    PERFORM scanipy_accepted_inputs.v1_require(current_execution.document->key=namespace->key,'policy-stale');
  END LOOP;
  fence:=jsonb_build_object('work_item_id',binding->'work_item_id','work_attempt_id',binding->'work_attempt_id',
    'fencing_token',binding->'fencing_token','work_revision',binding->'work_revision');
  PERFORM scanipy_accepted_inputs.v1_read_bridge_reserve();
  context:=scanipy_execution.lock_accepted_detector_context_v1((binding->>'org_id')::uuid,
    (binding->>'work_item_id')::uuid,(binding->>'work_attempt_id')::uuid,(binding->>'fencing_token')::bigint,
    (binding->>'work_revision')::bigint,(binding->>'detector_run_id')::uuid,(binding->>'capture_lease_id')::uuid);
  PERFORM scanipy_accepted_inputs.v1_context_check(context,namespace,fence);
  PERFORM scanipy_accepted_inputs.v1_context_material(context,sealed.document,request_binding.manifest,
    request_binding.sealed_digest,request_binding.requested_policy_digest,decode(binding->>'run_input_digest','hex'));
  PERFORM scanipy_accepted_inputs.v1_previous_context(current_execution.document,context,
    request_binding.manifest,request_binding.sealed_digest);
  -- Fresh after the final lock wait, not a caller echo or pre-lock timestamp.
  moment:=clock_timestamp(); issued:=(current_execution.document->>'authorized_at')::timestamptz;
  PERFORM scanipy_accepted_inputs.v1_require((request_binding.manifest->>'resolved_at')::timestamptz<=issued
    AND issued<=(context->>'db_now')::timestamptz AND moment>=(context->>'db_now')::timestamptz
    AND issued<=moment AND moment<(context->>'lease_expires_at')::timestamptz
    AND moment<(context->>'capture_lease_expires_at')::timestamptz,'fence-stale');
  approval:=scanipy_accepted_inputs.v1_stored_document(request_binding.frame[2],'scanipy-accepted-approval/1');
  receipt:=scanipy_accepted_inputs.v1_stored_document(request_binding.frame[5],'scanipy-accepted-publication/1');
  grant_row:=scanipy_accepted_inputs.v1_grant(live.policy,approval);
  PERFORM scanipy_accepted_inputs.v1_policy_time(live.policy,live.checkpoint,issued);
  PERFORM scanipy_accepted_inputs.v1_policy_time(live.policy,live.checkpoint,moment);
  PERFORM scanipy_accepted_inputs.v1_grant_use(grant_row,issued,(receipt->>'published_at')::timestamptz);
  PERFORM scanipy_accepted_inputs.v1_grant_use(grant_row,moment,(receipt->>'published_at')::timestamptz);
  ledger:=jsonb_build_object('binding',binding,'execution_authorization_digest',binding->'authorization_digest',
    'policy_event_id',namespace->'policy_event_id','admission_event_id',namespace->'admission_event_id',
    'request_binding_digest',encode(request_binding.sealed_digest,'hex'),
    'publication_receipt_digest',encode(scanipy_accepted_inputs.v1_hash(request_binding.frame[5],
      'scanipy-accepted-publication/1'),'hex'));
  PERFORM scanipy_accepted_inputs.v1_shape(ledger,scanipy_accepted_inputs.v1_shapes()->'records'->'LEDGER_EXPECTATION');
  ledger_bytes:=scanipy_accepted_inputs.v1_bytes(ledger); live_bytes:=live.live_bytes;
  reference_time:=to_char(moment AT TIME ZONE 'UTC','YYYY-MM-DD"T"HH24:MI:SS.US"Z"');
  PERFORM scanipy_accepted_inputs.v1_require(octet_length(ledger_bytes)<=65536 AND octet_length(live_bytes)<=262144
    AND octet_length(reference_time)=27);
  RETURN NEXT;
END $$;

CREATE FUNCTION scanipy_accepted_inputs.read_execution_authority_v1(p_namespace uuid,binding_bytes bytea,admission_bytes bytea)
RETURNS TABLE(ledger_bytes bytea,live_bytes bytea,reference_time text)
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,scanipy_accepted_inputs,pg_temp SET bytea_output='hex' AS $$
DECLARE input record;
BEGIN
  PERFORM scanipy_accepted_inputs.v1_work_begin(5701632,8519808,131106);
  SELECT * INTO input FROM scanipy_accepted_inputs.v1_read_inputs(binding_bytes,admission_bytes);
  RETURN QUERY SELECT * FROM scanipy_accepted_inputs.v1_read_current(p_namespace,input.binding,input.admission);
END $$;

CREATE FUNCTION scanipy_accepted_inputs.recheck_execution_authority_v1(p_namespace uuid,binding_bytes bytea,admission_bytes bytea,
  prior_ledger_bytes bytea,prior_live_bytes bytea,prior_reference_time text)
RETURNS void LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,scanipy_accepted_inputs,pg_temp SET bytea_output='hex' AS $$
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
END $$;
