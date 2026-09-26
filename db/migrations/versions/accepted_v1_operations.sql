-- Seven public mutation routes plus private composition helpers. SQL validates
-- bytes, committed relationships and time; no signature/provider is fabricated.
CREATE FUNCTION scanipy_accepted_inputs.v1_namespace(p_namespace uuid) RETURNS jsonb
LANGUAGE plpgsql SET search_path=pg_catalog,scanipy_accepted_inputs,pg_temp SET bytea_output='hex' AS $$
DECLARE selected_namespace text; selected_org text; row record;
BEGIN
  selected_namespace:=current_setting('scanipy.accepted_namespace_id',true);
  selected_org:=current_setting('app.org_id',true);
  PERFORM scanipy_accepted_inputs.v1_require(p_namespace IS NOT NULL
    AND selected_namespace=p_namespace::text AND selected_org IS NOT NULL
    AND (selected_org='' OR selected_org ~ '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'),
    'scope-mismatch');
  PERFORM scanipy_accepted_inputs.v1_control(4096);
  SELECT id,registry_id,scope,org_id,deployment_id,administrator_actor_id,root_spki_sha256,
    policy_event_id,policy_digest,policy_revision,admission_event_id,checkpoint_digest,
    checkpoint_generation,admission_epoch,coordination_revision INTO row
    FROM scanipy_accepted_inputs.registry_namespaces WHERE id=p_namespace FOR UPDATE;
  PERFORM scanipy_accepted_inputs.v1_require(FOUND,'scope-mismatch');
  RETURN jsonb_build_object('namespace_id',row.id,'registry_id',row.registry_id,'scope',row.scope,'org_id',row.org_id,
    'deployment_id',row.deployment_id,'administrator_actor_id',row.administrator_actor_id,
    'root_spki_sha256',encode(row.root_spki_sha256,'hex'),'policy_event_id',row.policy_event_id,
    'policy_digest',encode(row.policy_digest,'hex'),'policy_revision',row.policy_revision,
    'admission_event_id',row.admission_event_id,'checkpoint_digest',encode(row.checkpoint_digest,'hex'),
    'checkpoint_generation',row.checkpoint_generation,'admission_epoch',row.admission_epoch,
    'coordination_revision',row.coordination_revision);
END $$;

CREATE FUNCTION scanipy_accepted_inputs.v1_same_namespace(document jsonb, namespace jsonb) RETURNS void
LANGUAGE plpgsql IMMUTABLE SET search_path=pg_catalog,scanipy_accepted_inputs,pg_temp AS $$
BEGIN
  PERFORM scanipy_accepted_inputs.v1_require(document->'registry_id'=namespace->'registry_id'
    AND document->'scope'=namespace->'scope' AND document->'org_id'=namespace->'org_id','scope-mismatch');
END $$;

CREATE FUNCTION scanipy_accepted_inputs.v1_replay(command jsonb, data bytea, parts bytea[])
RETURNS TABLE(record_bytes bytea,replayed boolean)
LANGUAGE plpgsql SET search_path=pg_catalog,scanipy_accepted_inputs,pg_temp SET bytea_output='hex' AS $$
DECLARE e record; b record; original record; total bigint; output_limit integer;
  schema_name text; document jsonb; frame bytea[];
BEGIN
  PERFORM scanipy_accepted_inputs.v1_control(4096);
  SELECT id,action,record_schema,record_digest,publication_receipt_digest,command_length,command_part_lengths,
    CASE WHEN kind='approval' THEN publication_receipt_length ELSE record_length END AS result_length
    INTO e FROM scanipy_accepted_inputs.authority_events
    WHERE namespace_id=(command->>'namespace_id')::uuid AND operation_key=(command->>'operation_key')::uuid;
  SELECT request_id,command_length,command_part_lengths,sealed_length,sealed_sha256 INTO b
    FROM scanipy_accepted_inputs.request_bundle_bindings
    WHERE namespace_id=(command->>'namespace_id')::uuid AND operation_key=(command->>'operation_key')::uuid;
  PERFORM scanipy_accepted_inputs.v1_require(e.id IS NULL OR b.request_id IS NULL,'ledger-mismatch');
  IF e.id IS NULL AND b.request_id IS NULL THEN RETURN; END IF;
  output_limit:=CASE command->>'action' WHEN 'install-policy' THEN 131072
    WHEN 'create-bound-request' THEN 1048576 ELSE 65536 END;
  IF e.id IS NOT NULL THEN
    PERFORM scanipy_accepted_inputs.v1_require(e.action=command->>'action'
      AND e.command_length=octet_length(data) AND e.command_part_lengths=scanipy_accepted_inputs.v1_lengths(parts)
      AND e.result_length BETWEEN 1 AND output_limit,'ledger-mismatch');
    total:=e.command_length+(SELECT coalesce(sum(n),0) FROM unnest(e.command_part_lengths) n)+e.result_length;
    PERFORM scanipy_accepted_inputs.v1_fetch(total);
    SELECT command_bytes,command_parts,CASE WHEN kind='approval' THEN publication_receipt_bytes ELSE authority_events.record_bytes END AS result
      INTO original FROM scanipy_accepted_inputs.authority_events
      WHERE namespace_id=(command->>'namespace_id')::uuid AND id=e.id;
  ELSE
    PERFORM scanipy_accepted_inputs.v1_require(command->>'action'='create-bound-request'
      AND b.command_length=octet_length(data) AND b.command_part_lengths=scanipy_accepted_inputs.v1_lengths(parts)
      AND b.sealed_length BETWEEN 1 AND output_limit,'ledger-mismatch');
    total:=b.command_length+(SELECT coalesce(sum(n),0) FROM unnest(b.command_part_lengths) n)+b.sealed_length;
    PERFORM scanipy_accepted_inputs.v1_fetch(total);
    SELECT command_bytes,command_parts,sealed_bytes AS result INTO original
      FROM scanipy_accepted_inputs.request_bundle_bindings
      WHERE namespace_id=(command->>'namespace_id')::uuid AND request_id=b.request_id;
  END IF;
  PERFORM scanipy_accepted_inputs.v1_require(original.command_bytes=data AND original.command_parts=parts
    AND octet_length(original.result)<=output_limit,'ledger-mismatch');
  -- Validate original result integrity only. Historical replay does not fetch
  -- current heads, re-evaluate grants, renew leases or adopt a lower operation.
  IF b.request_id IS NOT NULL THEN
    frame:=scanipy_accepted_inputs.v1_stored_frame(original.result,'scanipy-sealed-acceptance/1');
    document:=scanipy_accepted_inputs.v1_stored_document(frame[1],'scanipy-sealed-acceptance/1');
    PERFORM scanipy_accepted_inputs.v1_require(document->>'request_id'=b.request_id::text
      AND scanipy_accepted_inputs.v1_hash(original.result)=b.sealed_sha256,'content-mismatch');
  ELSE
    schema_name:=CASE WHEN e.action='publish-builtin' THEN 'scanipy-accepted-publication/1' ELSE e.record_schema END;
    document:=scanipy_accepted_inputs.v1_stored_document(original.result,schema_name);
    PERFORM scanipy_accepted_inputs.v1_require(scanipy_accepted_inputs.v1_hash(original.result,schema_name)=
      CASE WHEN e.action='publish-builtin' THEN e.publication_receipt_digest ELSE e.record_digest END,'content-mismatch');
    IF e.action='publish-builtin' THEN
      frame:=scanipy_accepted_inputs.v1_frame(parts[1],'scanipy-publication-input/1');
      PERFORM scanipy_accepted_inputs.v1_publication_links(
        scanipy_accepted_inputs.v1_document(frame[2],'scanipy-accepted-approval/1'),
        scanipy_accepted_inputs.v1_hash(frame[2],'scanipy-accepted-approval/1'),document);
    ELSE
      PERFORM scanipy_accepted_inputs.v1_require(document->>'event_id'=e.id::text,'content-mismatch');
      IF e.action IN ('install-policy','record-admission') THEN
        PERFORM scanipy_accepted_inputs.v1_require(original.result=parts[1],'content-mismatch');
      ELSE
        PERFORM scanipy_accepted_inputs.v1_require(document->'operation_key'=command->'operation_key','content-mismatch');
      END IF;
    END IF;
  END IF;
  record_bytes:=original.result; replayed:=true; RETURN NEXT;
END $$;

CREATE FUNCTION scanipy_accepted_inputs.v1_fresh_command(command jsonb, namespace jsonb) RETURNS void
LANGUAGE plpgsql SET search_path=pg_catalog,scanipy_accepted_inputs,pg_temp AS $$
DECLARE meter jsonb; direct_limit bigint;
BEGIN
  PERFORM scanipy_accepted_inputs.v1_require(command->'expected_coordination_revision'=namespace->'coordination_revision',
    'ledger-mismatch');
  direct_limit:=CASE command->>'action' WHEN 'install-policy' THEN 131456 WHEN 'record-admission' THEN 197376
    WHEN 'publish-builtin' THEN 2424832 WHEN 'create-bound-request' THEN 2424832
    WHEN 'seal-bound-capture' THEN 3407872 WHEN 'authorize-detector' THEN 5636096 WHEN 'renew-detector' THEN 5636096 END;
  PERFORM scanipy_accepted_inputs.v1_require(direct_limit IS NOT NULL);
  meter:=current_setting('scanipy.accepted_work')::jsonb;
  PERFORM scanipy_accepted_inputs.v1_require((meter->'used'->>8)::bigint=0);
  meter:=jsonb_set(meter,ARRAY['caps','8'],to_jsonb(direct_limit));
  PERFORM set_config('scanipy.accepted_work',meter::text,true);
END $$;

CREATE FUNCTION scanipy_accepted_inputs.initialize_registry_namespace_v1(p_namespace uuid,installation_bytes bytea)
RETURNS TABLE(namespace_id uuid,replayed boolean)
LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog,scanipy_accepted_inputs,pg_temp SET bytea_output='hex' AS $$
DECLARE document jsonb; old record; existing bytea; selected text;
BEGIN
  PERFORM scanipy_accepted_inputs.v1_work_begin(4096);
  document:=scanipy_accepted_inputs.v1_document(installation_bytes,'scanipy-registry-installed-trust/1');
  PERFORM scanipy_accepted_inputs.v1_require(p_namespace IS NOT NULL,'invalid-input');
  selected:=current_setting('scanipy.accepted_namespace_id',true);
  PERFORM scanipy_accepted_inputs.v1_require(selected=p_namespace::text
    AND current_setting('app.org_id',true)=coalesce(document->>'org_id',''),'scope-mismatch');
  SELECT id,installation_length INTO old FROM scanipy_accepted_inputs.registry_namespaces
    WHERE id=p_namespace OR (registry_id=(document->>'registry_id')::uuid
      AND scope=document->>'scope' AND org_id IS NOT DISTINCT FROM (document->>'org_id')::uuid)
    ORDER BY id FOR UPDATE;
  IF FOUND THEN
    PERFORM scanipy_accepted_inputs.v1_require(old.id=p_namespace AND old.installation_length=octet_length(installation_bytes),'ledger-mismatch');
    PERFORM scanipy_accepted_inputs.v1_fetch(old.installation_length);
    SELECT n.installation_bytes INTO existing FROM scanipy_accepted_inputs.registry_namespaces n WHERE id=p_namespace;
    PERFORM scanipy_accepted_inputs.v1_require(existing=installation_bytes,'ledger-mismatch');
    namespace_id:=p_namespace; replayed:=true; RETURN NEXT; RETURN;
  END IF;
  INSERT INTO scanipy_accepted_inputs.registry_namespaces(id,registry_id,scope,org_id,installation_bytes,
    installation_sha256,deployment_id,administrator_actor_id,root_spki_sha256)
    VALUES(p_namespace,(document->>'registry_id')::uuid,document->>'scope',(document->>'org_id')::uuid,
      installation_bytes,NULL,NULL,NULL,NULL);
  namespace_id:=p_namespace; replayed:=false; RETURN NEXT;
EXCEPTION WHEN unique_violation THEN RAISE EXCEPTION 'ledger-mismatch' USING ERRCODE='P0001';
END $$;

CREATE FUNCTION scanipy_accepted_inputs.v1_policy_evolution(old_policy jsonb,new_policy jsonb) RETURNS void
LANGUAGE plpgsql IMMUTABLE SET search_path=pg_catalog,scanipy_accepted_inputs,pg_temp AS $$
DECLARE grant_row record; successor jsonb; old_grant jsonb;
BEGIN
  IF old_policy IS NOT NULL THEN
    FOR grant_row IN SELECT value FROM jsonb_array_elements(old_policy->'grants') LOOP
      SELECT value INTO successor FROM jsonb_array_elements(new_policy->'grants')
        WHERE value->'grant_id'=grant_row.value->'grant_id';
      PERFORM scanipy_accepted_inputs.v1_require(FOUND AND
        successor-ARRAY['status','status_changed_at']=grant_row.value-ARRAY['status','status_changed_at'],'grant-denied');
      PERFORM scanipy_accepted_inputs.v1_require(CASE grant_row.value->>'status'
        WHEN 'active' THEN successor->>'status' IN ('active','retired','revoked')
        WHEN 'retired' THEN successor->>'status' IN ('retired','revoked')
        ELSE successor->>'status'='revoked' END,'grant-denied');
      IF successor->'status'=grant_row.value->'status' THEN
        PERFORM scanipy_accepted_inputs.v1_require(successor->'status_changed_at'=grant_row.value->'status_changed_at','grant-denied');
      ELSIF grant_row.value->>'status_changed_at' IS NOT NULL THEN
        PERFORM scanipy_accepted_inputs.v1_require((successor->>'status_changed_at')::timestamptz>=
          (grant_row.value->>'status_changed_at')::timestamptz,'grant-denied');
      END IF;
    END LOOP;
  END IF;
  FOR grant_row IN SELECT value FROM jsonb_array_elements(new_policy->'grants') LOOP
    old_grant:=NULL;
    IF old_policy IS NOT NULL THEN
      SELECT value INTO old_grant FROM jsonb_array_elements(old_policy->'grants')
        WHERE value->'grant_id'=grant_row.value->'grant_id';
    END IF;
    IF old_grant IS NULL THEN
      PERFORM scanipy_accepted_inputs.v1_require((new_policy->>'valid_from')::timestamptz<=
        (grant_row.value->>'not_before')::timestamptz AND (grant_row.value->>'not_after')::timestamptz<=
        (new_policy->>'expires_at')::timestamptz,'grant-denied');
    END IF;
  END LOOP;
END $$;

CREATE FUNCTION scanipy_accepted_inputs.install_policy_v1(command_bytes bytea,parts bytea[])
RETURNS TABLE(record_bytes bytea,replayed boolean)
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,scanipy_accepted_inputs,pg_temp SET bytea_output='hex' AS $$
DECLARE command jsonb; namespace jsonb; document jsonb; prior jsonb; old record; replay record;
  digest bytea; previous bytea; recorded timestamptz; ns uuid;
BEGIN
  PERFORM scanipy_accepted_inputs.v1_work_begin(328064,167772160);
  command:=scanipy_accepted_inputs.v1_command(command_bytes,parts,'install-policy'); ns:=(command->>'namespace_id')::uuid;
  namespace:=scanipy_accepted_inputs.v1_namespace(ns);
  SELECT * INTO replay FROM scanipy_accepted_inputs.v1_replay(command,command_bytes,parts);
  IF FOUND THEN record_bytes:=replay.record_bytes; replayed:=true; RETURN NEXT; RETURN; END IF;
  PERFORM scanipy_accepted_inputs.v1_fresh_command(command,namespace);
  document:=scanipy_accepted_inputs.v1_document(parts[1],'scanipy-accepted-trust-policy/1');
  PERFORM scanipy_accepted_inputs.v1_same_namespace(document,namespace);
  PERFORM scanipy_accepted_inputs.v1_require((namespace->>'policy_revision')::bigint<9223372036854775807
    AND (document->>'revision')::bigint=(namespace->>'policy_revision')::bigint+1
    AND document->'previous_policy_digest'=namespace->'policy_digest'
    AND command->'body'->'predecessor_policy_digest'=namespace->'policy_digest','policy-stale');
  previous:=decode(namespace->>'policy_digest','hex');
  IF namespace->>'policy_event_id' IS NOT NULL THEN
    SELECT record_length INTO old FROM scanipy_accepted_inputs.authority_events
      WHERE namespace_id=ns AND kind='policy' AND id=(namespace->>'policy_event_id')::uuid;
    PERFORM scanipy_accepted_inputs.v1_require(FOUND AND old.record_length<=131072,'ledger-mismatch');
    PERFORM scanipy_accepted_inputs.v1_fetch(old.record_length+384);
    SELECT e.record_bytes,e.signature_bytes INTO old FROM scanipy_accepted_inputs.authority_events e
      WHERE namespace_id=ns AND kind='policy' AND id=(namespace->>'policy_event_id')::uuid;
    prior:=scanipy_accepted_inputs.v1_stored_document(old.record_bytes,'scanipy-accepted-trust-policy/1');
    PERFORM scanipy_accepted_inputs.v1_require(octet_length(old.signature_bytes)=384
      AND scanipy_accepted_inputs.v1_hash(old.record_bytes,'scanipy-accepted-trust-policy/1')=previous,'content-mismatch');
  END IF;
  PERFORM scanipy_accepted_inputs.v1_policy_evolution(prior,document);
  digest:=scanipy_accepted_inputs.v1_hash(parts[1],'scanipy-accepted-trust-policy/1'); recorded:=clock_timestamp();
  INSERT INTO scanipy_accepted_inputs.authority_events(id,namespace_id,kind,record_schema,record_bytes,record_digest,
    recorded_at,operation_key,action,command_bytes,command_digest,command_parts,registry_id,scope,org_id,
    policy_revision,previous_event_digest,signature_bytes)
    VALUES((document->>'event_id')::uuid,ns,'policy','scanipy-accepted-trust-policy/1',parts[1],digest,recorded,
      (command->>'operation_key')::uuid,'install-policy',command_bytes,
      scanipy_accepted_inputs.v1_hash(command_bytes,'scanipy-accepted-ledger-command/1'),parts,
      (namespace->>'registry_id')::uuid,namespace->>'scope',(namespace->>'org_id')::uuid,
      (document->>'revision')::bigint,previous,parts[2]);
  UPDATE scanipy_accepted_inputs.registry_namespaces SET policy_event_id=(document->>'event_id')::uuid,
    policy_digest=digest,policy_revision=(document->>'revision')::bigint,
    coordination_revision=coordination_revision+1,updated_at=recorded WHERE id=ns;
  record_bytes:=parts[1]; replayed:=false; RETURN NEXT;
EXCEPTION WHEN unique_violation THEN RAISE EXCEPTION 'ledger-mismatch' USING ERRCODE='P0001';
END $$;

CREATE FUNCTION scanipy_accepted_inputs.record_admission_v1(command_bytes bytea,parts bytea[])
RETURNS TABLE(record_bytes bytea,replayed boolean)
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,scanipy_accepted_inputs,pg_temp SET bytea_output='hex' AS $$
DECLARE command jsonb; namespace jsonb; document jsonb; old record; replay record;
  digest bytea; previous bytea; recorded timestamptz; ns uuid; policy jsonb; prior jsonb;
BEGIN
  PERFORM scanipy_accepted_inputs.v1_work_begin(197376,167772160);
  command:=scanipy_accepted_inputs.v1_command(command_bytes,parts,'record-admission'); ns:=(command->>'namespace_id')::uuid;
  namespace:=scanipy_accepted_inputs.v1_namespace(ns);
  SELECT * INTO replay FROM scanipy_accepted_inputs.v1_replay(command,command_bytes,parts);
  IF FOUND THEN record_bytes:=replay.record_bytes; replayed:=true; RETURN NEXT; RETURN; END IF;
  PERFORM scanipy_accepted_inputs.v1_fresh_command(command,namespace);
  document:=scanipy_accepted_inputs.v1_document(parts[1],'scanipy-registry-admission/1');
  PERFORM scanipy_accepted_inputs.v1_same_namespace(document,namespace);
  PERFORM scanipy_accepted_inputs.v1_require((namespace->>'checkpoint_generation')::bigint<9223372036854775807
    AND (document->>'generation')::bigint=(namespace->>'checkpoint_generation')::bigint+1
    AND document->'previous_checkpoint_digest'=namespace->'checkpoint_digest'
    AND command->'body'->'predecessor_checkpoint_digest'=namespace->'checkpoint_digest'
    AND document->'deployment_id'=namespace->'deployment_id'
    AND document->'administrator_actor_id'=namespace->'administrator_actor_id'
    AND document->'policy_digest'=namespace->'policy_digest'
    AND document->'policy_revision'=namespace->'policy_revision','checkpoint-denied');
  SELECT record_length INTO old FROM scanipy_accepted_inputs.authority_events
    WHERE namespace_id=ns AND kind='policy' AND id=(namespace->>'policy_event_id')::uuid;
  PERFORM scanipy_accepted_inputs.v1_require(FOUND AND old.record_length<=131072,'ledger-mismatch');
  PERFORM scanipy_accepted_inputs.v1_fetch(old.record_length+384);
  SELECT e.record_bytes,e.signature_bytes INTO old FROM scanipy_accepted_inputs.authority_events e
    WHERE namespace_id=ns AND kind='policy' AND id=(namespace->>'policy_event_id')::uuid;
  policy:=scanipy_accepted_inputs.v1_stored_document(old.record_bytes,'scanipy-accepted-trust-policy/1');
  PERFORM scanipy_accepted_inputs.v1_require(scanipy_accepted_inputs.v1_hash(old.record_bytes,'scanipy-accepted-trust-policy/1')=
    decode(namespace->>'policy_digest','hex') AND octet_length(old.signature_bytes)=384,'content-mismatch');
  previous:=decode(namespace->>'checkpoint_digest','hex');
  IF namespace->>'admission_event_id' IS NOT NULL THEN
    SELECT record_length INTO old FROM scanipy_accepted_inputs.authority_events
      WHERE namespace_id=ns AND kind='admission' AND id=(namespace->>'admission_event_id')::uuid;
    PERFORM scanipy_accepted_inputs.v1_require(FOUND AND old.record_length<=65536,'ledger-mismatch');
    PERFORM scanipy_accepted_inputs.v1_fetch(old.record_length+384);
    SELECT e.record_bytes,e.signature_bytes INTO old FROM scanipy_accepted_inputs.authority_events e
      WHERE namespace_id=ns AND kind='admission' AND id=(namespace->>'admission_event_id')::uuid;
    prior:=scanipy_accepted_inputs.v1_stored_document(old.record_bytes,'scanipy-registry-admission/1');
    PERFORM scanipy_accepted_inputs.v1_require(octet_length(old.signature_bytes)=384 AND
      scanipy_accepted_inputs.v1_hash(old.record_bytes,'scanipy-registry-admission/1')=previous,'content-mismatch');
  END IF;
  digest:=scanipy_accepted_inputs.v1_hash(parts[1],'scanipy-registry-admission/1'); recorded:=clock_timestamp();
  INSERT INTO scanipy_accepted_inputs.authority_events(id,namespace_id,kind,record_schema,record_bytes,record_digest,
    recorded_at,operation_key,action,command_bytes,command_digest,command_parts,registry_id,scope,org_id,
    policy_event_id,policy_digest,policy_revision,checkpoint_generation,admission_epoch,previous_event_digest,signature_bytes)
    VALUES((document->>'event_id')::uuid,ns,'admission','scanipy-registry-admission/1',parts[1],digest,recorded,
      (command->>'operation_key')::uuid,'record-admission',command_bytes,
      scanipy_accepted_inputs.v1_hash(command_bytes,'scanipy-accepted-ledger-command/1'),parts,
      (namespace->>'registry_id')::uuid,namespace->>'scope',(namespace->>'org_id')::uuid,
      (namespace->>'policy_event_id')::uuid,decode(namespace->>'policy_digest','hex'),(namespace->>'policy_revision')::bigint,
      (document->>'generation')::bigint,(document->>'admission_epoch')::uuid,previous,parts[2]);
  UPDATE scanipy_accepted_inputs.registry_namespaces SET admission_event_id=(document->>'event_id')::uuid,
    checkpoint_digest=digest,checkpoint_generation=(document->>'generation')::bigint,
    admission_epoch=(document->>'admission_epoch')::uuid,
    coordination_revision=coordination_revision+1,updated_at=recorded WHERE id=ns;
  record_bytes:=parts[1]; replayed:=false; RETURN NEXT;
EXCEPTION WHEN unique_violation THEN RAISE EXCEPTION 'ledger-mismatch' USING ERRCODE='P0001';
END $$;

CREATE FUNCTION scanipy_accepted_inputs.v1_live(namespace jsonb,expected jsonb)
RETURNS TABLE(live_bytes bytea,policy jsonb,checkpoint jsonb,objects bytea[])
LANGUAGE plpgsql SET search_path=pg_catalog,scanipy_accepted_inputs,pg_temp SET bytea_output='hex' AS $$
DECLARE p record; a record; actual jsonb; ns uuid;
BEGIN
  PERFORM scanipy_accepted_inputs.v1_shape(expected,scanipy_accepted_inputs.v1_shapes()->'records'->'ADMISSION_EXPECTATION');
  ns:=(namespace->>'namespace_id')::uuid;
  PERFORM scanipy_accepted_inputs.v1_require(namespace->>'policy_event_id' IS NOT NULL
    AND namespace->>'admission_event_id' IS NOT NULL,'checkpoint-denied');
  actual:=jsonb_build_object('policy_digest',namespace->'policy_digest','policy_revision',namespace->'policy_revision',
    'checkpoint_digest',namespace->'checkpoint_digest','checkpoint_generation',namespace->'checkpoint_generation',
    'admission_epoch',namespace->'admission_epoch');
  PERFORM scanipy_accepted_inputs.v1_require(expected=actual,'policy-stale');
  PERFORM scanipy_accepted_inputs.v1_control(1024);
  SELECT record_length INTO p FROM scanipy_accepted_inputs.authority_events
    WHERE namespace_id=ns AND kind='policy' AND id=(namespace->>'policy_event_id')::uuid;
  PERFORM scanipy_accepted_inputs.v1_require(FOUND AND p.record_length<=131072,'ledger-mismatch');
  SELECT record_length INTO a FROM scanipy_accepted_inputs.authority_events
    WHERE namespace_id=ns AND kind='admission' AND id=(namespace->>'admission_event_id')::uuid;
  PERFORM scanipy_accepted_inputs.v1_require(FOUND AND a.record_length<=65536,'ledger-mismatch');
  PERFORM scanipy_accepted_inputs.v1_fetch(p.record_length+a.record_length+768);
  SELECT record_bytes,signature_bytes INTO p FROM scanipy_accepted_inputs.authority_events
    WHERE namespace_id=ns AND kind='policy' AND id=(namespace->>'policy_event_id')::uuid;
  SELECT record_bytes,signature_bytes INTO a FROM scanipy_accepted_inputs.authority_events
    WHERE namespace_id=ns AND kind='admission' AND id=(namespace->>'admission_event_id')::uuid;
  policy:=scanipy_accepted_inputs.v1_stored_document(p.record_bytes,'scanipy-accepted-trust-policy/1');
  checkpoint:=scanipy_accepted_inputs.v1_stored_document(a.record_bytes,'scanipy-registry-admission/1');
  PERFORM scanipy_accepted_inputs.v1_same_namespace(policy,namespace);
  PERFORM scanipy_accepted_inputs.v1_same_namespace(checkpoint,namespace);
  PERFORM scanipy_accepted_inputs.v1_require(policy->'event_id'=namespace->'policy_event_id'
    AND checkpoint->'event_id'=namespace->'admission_event_id'
    AND policy->'revision'=actual->'policy_revision' AND checkpoint->'policy_revision'=actual->'policy_revision'
    AND checkpoint->'policy_digest'=actual->'policy_digest' AND checkpoint->'generation'=actual->'checkpoint_generation'
    AND checkpoint->'admission_epoch'=actual->'admission_epoch'
    AND checkpoint->'deployment_id'=namespace->'deployment_id'
    AND checkpoint->'administrator_actor_id'=namespace->'administrator_actor_id'
    AND scanipy_accepted_inputs.v1_hash(p.record_bytes,'scanipy-accepted-trust-policy/1')=decode(actual->>'policy_digest','hex')
    AND scanipy_accepted_inputs.v1_hash(a.record_bytes,'scanipy-registry-admission/1')=decode(actual->>'checkpoint_digest','hex'),
    'content-mismatch');
  objects:=ARRAY[p.record_bytes,p.signature_bytes,a.record_bytes,a.signature_bytes];
  live_bytes:=scanipy_accepted_inputs.v1_encode_frame('scanipy-registry-current-authority/1',actual||
    jsonb_build_object('registry_id',namespace->'registry_id','scope',namespace->'scope','org_id',namespace->'org_id'),objects);
  RETURN NEXT;
END $$;

CREATE FUNCTION scanipy_accepted_inputs.v1_policy_time(policy jsonb,checkpoint jsonb,moment timestamptz)
RETURNS void LANGUAGE plpgsql IMMUTABLE SET search_path=pg_catalog,scanipy_accepted_inputs,pg_temp AS $$
BEGIN
  PERFORM scanipy_accepted_inputs.v1_require(moment IS NOT NULL AND (policy->>'valid_from')::timestamptz<=moment
    AND moment<(policy->>'expires_at')::timestamptz,'policy-expired');
  PERFORM scanipy_accepted_inputs.v1_require(checkpoint->>'action'='admit'
    AND (checkpoint->>'issued_at')::timestamptz<=moment AND moment<(checkpoint->>'expires_at')::timestamptz,'checkpoint-denied');
END $$;

CREATE FUNCTION scanipy_accepted_inputs.v1_grant(policy jsonb,approval jsonb) RETURNS jsonb
LANGUAGE plpgsql IMMUTABLE SET search_path=pg_catalog,scanipy_accepted_inputs,pg_temp AS $$
DECLARE result jsonb; key text;
BEGIN
  SELECT value INTO result FROM jsonb_array_elements(policy->'grants') WHERE value->'grant_id'=approval->'grant_id';
  PERFORM scanipy_accepted_inputs.v1_require(FOUND,'grant-denied');
  FOREACH key IN ARRAY ARRAY['key_id','key_version','spki_sha256','signature_profile','issuer_actor_id','scope','org_id'] LOOP
    PERFORM scanipy_accepted_inputs.v1_require(result->key=approval->key,'grant-denied');
  END LOOP;
  RETURN result;
END $$;

CREATE FUNCTION scanipy_accepted_inputs.v1_grant_use(grant_row jsonb,moment timestamptz,
  published timestamptz,publication boolean DEFAULT false) RETURNS void
LANGUAGE plpgsql IMMUTABLE SET search_path=pg_catalog,scanipy_accepted_inputs,pg_temp AS $$
BEGIN
  PERFORM scanipy_accepted_inputs.v1_require(moment IS NOT NULL AND published IS NOT NULL
    AND (grant_row->>'not_before')::timestamptz<=moment AND moment<(grant_row->>'not_after')::timestamptz,'grant-denied');
  IF publication THEN
    PERFORM scanipy_accepted_inputs.v1_require(grant_row->>'status'='active','grant-denied');
  ELSE
    PERFORM scanipy_accepted_inputs.v1_require(grant_row->>'status' IN ('active','retired'),'grant-denied');
    IF grant_row->>'status'='retired' THEN
      PERFORM scanipy_accepted_inputs.v1_require(published<(grant_row->>'status_changed_at')::timestamptz
        AND (grant_row->>'status_changed_at')::timestamptz<=moment,'grant-denied');
    END IF;
  END IF;
END $$;

CREATE FUNCTION scanipy_accepted_inputs.v1_approval_material(frame bytea[],expected jsonb,
  namespace jsonb,policy jsonb,policy_bytes bytea,moment timestamptz) RETURNS jsonb
LANGUAGE plpgsql SET search_path=pg_catalog,scanipy_accepted_inputs,pg_temp AS $$
DECLARE approval jsonb; inventory jsonb; adoption jsonb; grant_row jsonb; key text; issued timestamptz;
BEGIN
  PERFORM scanipy_accepted_inputs.v1_byte_array(frame,16);
  PERFORM scanipy_accepted_inputs.v1_require(cardinality(frame)=11);
  approval:=scanipy_accepted_inputs.v1_document(frame[2],'scanipy-accepted-approval/1');
  inventory:=scanipy_accepted_inputs.v1_document(frame[8],'scanipy-accepted-evidence-inventory/1');
  adoption:=scanipy_accepted_inputs.v1_document(frame[9],'scanipy-operator-adoption/1');
  PERFORM scanipy_accepted_inputs.v1_same_namespace(approval,namespace);
  PERFORM scanipy_accepted_inputs.v1_same_namespace(adoption,namespace);
  FOREACH key IN ARRAY ARRAY['bundle_id','S_version','accepted_content_digest'] LOOP
    PERFORM scanipy_accepted_inputs.v1_require(approval->key=expected->key,'content-mismatch');
  END LOOP;
  PERFORM scanipy_accepted_inputs.v1_require(adoption->'bundle_id'=approval->'bundle_id'
    AND adoption->'accepted_content_digest'=approval->'accepted_content_digest'
    AND adoption->'actor_id'=approval->'issuer_actor_id'
    AND approval->>'trust_policy_digest'=encode(scanipy_accepted_inputs.v1_hash(policy_bytes,'scanipy-accepted-trust-policy/1'),'hex')
    AND approval->>'evidence_inventory_digest'=encode(scanipy_accepted_inputs.v1_hash(frame[8],'scanipy-accepted-evidence-inventory/1'),'hex')
    AND approval->>'spki_sha256'=encode(scanipy_accepted_inputs.v1_hash(frame[4]),'hex')
    AND namespace->>'root_spki_sha256'=encode(scanipy_accepted_inputs.v1_hash(frame[7]),'hex')
    AND inventory->'objects'->0->>'raw_sha256'=encode(scanipy_accepted_inputs.v1_hash(frame[9]),'hex')
    AND (inventory->'objects'->0->>'length')::bigint=octet_length(frame[9]),'content-mismatch');
  issued:=(approval->>'issued_at')::timestamptz;
  PERFORM scanipy_accepted_inputs.v1_require(issued BETWEEN moment-interval '300 seconds' AND moment+interval '30 seconds'
    AND (adoption->>'decided_at')::timestamptz BETWEEN issued-interval '300 seconds' AND issued,'grant-denied');
  grant_row:=scanipy_accepted_inputs.v1_grant(policy,approval);
  PERFORM scanipy_accepted_inputs.v1_grant_use(grant_row,moment,moment,true);
  RETURN approval;
END $$;

-- Historical publication checks use its recorded time and original policy,
-- never the current head. This does not repeat an external signature check.
CREATE FUNCTION scanipy_accepted_inputs.v1_publication_material(frame bytea[],receipt jsonb,
  namespace jsonb,expected jsonb) RETURNS jsonb
LANGUAGE plpgsql SET search_path=pg_catalog,scanipy_accepted_inputs,pg_temp AS $$
DECLARE policy jsonb; checkpoint jsonb; approval jsonb; moment timestamptz;
BEGIN
  PERFORM scanipy_accepted_inputs.v1_require(cardinality(frame)=11);
  policy:=scanipy_accepted_inputs.v1_document(frame[5],'scanipy-accepted-trust-policy/1');
  checkpoint:=scanipy_accepted_inputs.v1_document(frame[10],'scanipy-registry-admission/1');
  PERFORM scanipy_accepted_inputs.v1_same_namespace(policy,namespace);
  PERFORM scanipy_accepted_inputs.v1_same_namespace(checkpoint,namespace);
  moment:=(receipt->>'published_at')::timestamptz;
  PERFORM scanipy_accepted_inputs.v1_policy_time(policy,checkpoint,moment);
  approval:=scanipy_accepted_inputs.v1_approval_material(frame,expected,namespace,policy,frame[5],moment);
  PERFORM scanipy_accepted_inputs.v1_publication_links(approval,
    scanipy_accepted_inputs.v1_hash(frame[2],'scanipy-accepted-approval/1'),receipt);
  PERFORM scanipy_accepted_inputs.v1_require(receipt->>'approval_signature_sha256'=
    encode(scanipy_accepted_inputs.v1_hash(frame[3]),'hex')
    AND receipt->>'policy_digest'=encode(scanipy_accepted_inputs.v1_hash(frame[5],'scanipy-accepted-trust-policy/1'),'hex')
    AND receipt->'policy_revision'=policy->'revision' AND checkpoint->'policy_digest'=receipt->'policy_digest'
    AND checkpoint->'policy_revision'=receipt->'policy_revision'
    AND receipt->>'checkpoint_digest'=encode(scanipy_accepted_inputs.v1_hash(frame[10],'scanipy-registry-admission/1'),'hex')
    AND receipt->'checkpoint_generation'=checkpoint->'generation' AND receipt->'admission_epoch'=checkpoint->'admission_epoch'
    AND checkpoint->'deployment_id'=namespace->'deployment_id'
    AND checkpoint->'administrator_actor_id'=namespace->'administrator_actor_id','content-mismatch');
  RETURN approval;
END $$;

CREATE FUNCTION scanipy_accepted_inputs.v1_publication_record(frame bytea[],receipt jsonb,
  namespace jsonb,expected jsonb) RETURNS jsonb
LANGUAGE plpgsql SET search_path=pg_catalog,scanipy_accepted_inputs,pg_temp AS $$
DECLARE manifest jsonb; key text;
BEGIN
  manifest:=scanipy_accepted_inputs.v1_document(frame[1],'scanipy-publication-input/1');
  FOREACH key IN ARRAY ARRAY['registry_id','scope','org_id','bundle_id','S_version','accepted_content_digest'] LOOP
    PERFORM scanipy_accepted_inputs.v1_require(manifest->key=expected->key,'content-mismatch');
  END LOOP;
  RETURN scanipy_accepted_inputs.v1_publication_material(frame,receipt,namespace,expected);
END $$;

CREATE FUNCTION scanipy_accepted_inputs.v1_sealed_material(frame bytea[],namespace jsonb) RETURNS jsonb
LANGUAGE plpgsql SET search_path=pg_catalog,scanipy_accepted_inputs,pg_temp AS $$
DECLARE manifest jsonb; approval jsonb; receipt jsonb; expected jsonb; current_policy jsonb;
  checkpoint jsonb; published timestamptz; resolved timestamptz; publication_parts bytea[];
BEGIN
  PERFORM scanipy_accepted_inputs.v1_require(cardinality(frame)=16);
  manifest:=scanipy_accepted_inputs.v1_document(frame[1],'scanipy-sealed-acceptance/1');
  approval:=scanipy_accepted_inputs.v1_document(frame[2],'scanipy-accepted-approval/1');
  expected:=jsonb_build_object('registry_id',namespace->'registry_id','scope',namespace->'scope','org_id',namespace->'org_id',
    'bundle_id',approval->'bundle_id','S_version',approval->'S_version','accepted_content_digest',approval->'accepted_content_digest');
  receipt:=scanipy_accepted_inputs.v1_document(frame[5],'scanipy-accepted-publication/1');
  -- Reorder only the already retained original objects for the private common
  -- material validator. Slot 1 remains the actual SEALED header; no invented
  -- PUBLICATION_INPUT bytes or claim that such a frame was retained is made.
  publication_parts:=ARRAY[frame[1],frame[2],frame[3],frame[4],frame[6],frame[7],frame[12],frame[13],frame[14],frame[8],frame[9]];
  PERFORM scanipy_accepted_inputs.v1_publication_material(publication_parts,receipt,namespace,expected);
  published:=(receipt->>'published_at')::timestamptz; resolved:=(manifest->>'resolved_at')::timestamptz;
  current_policy:=scanipy_accepted_inputs.v1_document(frame[10],'scanipy-accepted-trust-policy/1');
  checkpoint:=scanipy_accepted_inputs.v1_document(frame[15],'scanipy-registry-admission/1');
  PERFORM scanipy_accepted_inputs.v1_same_namespace(current_policy,namespace);
  PERFORM scanipy_accepted_inputs.v1_same_namespace(checkpoint,namespace);
  PERFORM scanipy_accepted_inputs.v1_require(namespace->>'scope'='customer'
    AND manifest->'registry_id'=expected->'registry_id' AND manifest->'org_id'=expected->'org_id'
    AND manifest->'bundle_id'=expected->'bundle_id' AND manifest->'accepted_content_digest'=expected->'accepted_content_digest'
    AND manifest->'approval_event_id'=approval->'event_id' AND published<=resolved
    AND manifest->'publication_policy_digest'=receipt->'policy_digest'
    AND manifest->>'current_policy_digest'=encode(scanipy_accepted_inputs.v1_hash(frame[10],'scanipy-accepted-trust-policy/1'),'hex')
    AND manifest->'current_policy_revision'=current_policy->'revision'
    AND manifest->>'checkpoint_digest'=encode(scanipy_accepted_inputs.v1_hash(frame[15],'scanipy-registry-admission/1'),'hex')
    AND manifest->'checkpoint_generation'=checkpoint->'generation' AND manifest->'admission_epoch'=checkpoint->'admission_epoch'
    AND checkpoint->'policy_digest'=manifest->'current_policy_digest' AND checkpoint->'policy_revision'=manifest->'current_policy_revision'
    AND checkpoint->'deployment_id'=namespace->'deployment_id'
    AND checkpoint->'administrator_actor_id'=namespace->'administrator_actor_id','content-mismatch');
  PERFORM scanipy_accepted_inputs.v1_policy_time(current_policy,checkpoint,resolved);
  PERFORM scanipy_accepted_inputs.v1_grant_use(scanipy_accepted_inputs.v1_grant(current_policy,approval),resolved,published);
  RETURN expected;
END $$;

CREATE FUNCTION scanipy_accepted_inputs.v1_retain_artifact(p_namespace uuid,p_kind text,
  p_id text,p_version text,p_schema text,data bytea,digest bytea) RETURNS uuid
LANGUAGE plpgsql SET search_path=pg_catalog,scanipy_accepted_inputs,pg_temp SET bytea_output='hex' AS $$
DECLARE row record; existing bytea; result uuid;
BEGIN
  -- Namespace lock belongs to the composing writer; this has no public grant.
  PERFORM scanipy_accepted_inputs.v1_control(64);
  SELECT id,raw_length,raw_sha256 INTO row FROM scanipy_accepted_inputs.artifact_versions
    WHERE namespace_id=p_namespace AND kind=p_kind AND artifact_id=p_id AND version=p_version;
  IF FOUND THEN
    PERFORM scanipy_accepted_inputs.v1_require(row.raw_length=octet_length(data)
      AND row.raw_sha256=digest,'content-mismatch');
    PERFORM scanipy_accepted_inputs.v1_fetch(row.raw_length);
    SELECT raw_bytes INTO existing FROM scanipy_accepted_inputs.artifact_versions
      WHERE namespace_id=p_namespace AND id=row.id;
    PERFORM scanipy_accepted_inputs.v1_require(existing=data
      AND scanipy_accepted_inputs.v1_hash(existing)=digest,'content-mismatch');
    RETURN row.id;
  END IF;
  INSERT INTO scanipy_accepted_inputs.artifact_versions(namespace_id,kind,artifact_id,version,artifact_schema,
    raw_bytes,raw_length,raw_sha256) VALUES(p_namespace,p_kind,p_id,p_version,p_schema,data,octet_length(data),digest)
    RETURNING id INTO result;
  RETURN result;
END $$;

CREATE FUNCTION scanipy_accepted_inputs.publish_builtin_bundle_v1(command_bytes bytea,parts bytea[])
RETURNS TABLE(record_bytes bytea,replayed boolean)
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,scanipy_accepted_inputs,pg_temp SET bytea_output='hex' AS $$
DECLARE command jsonb; namespace jsonb; expected jsonb; ns uuid; replay record; live record; bundle record;
  frame bytea[]; manifest jsonb; approval jsonb; receipt jsonb; digest bytea; receipt_digest bytea;
  detectors bytea[]; rules bytea[]; detector_ids uuid[]:=ARRAY[]::uuid[]; rule_ids uuid[]:=ARRAY[]::uuid[];
  model_ids uuid[]:=ARRAY[]::uuid[]; existing record; selected record; item record; rule record;
  d integer; r integer; moment timestamptz; key text; total bigint;
BEGIN
  PERFORM scanipy_accepted_inputs.v1_work_begin(2424832,167772160);
  command:=scanipy_accepted_inputs.v1_command(command_bytes,parts,'publish-builtin');
  ns:=(command->>'namespace_id')::uuid; namespace:=scanipy_accepted_inputs.v1_namespace(ns);
  SELECT * INTO replay FROM scanipy_accepted_inputs.v1_replay(command,command_bytes,parts);
  IF FOUND THEN record_bytes:=replay.record_bytes; replayed:=true; RETURN NEXT; RETURN; END IF;
  PERFORM scanipy_accepted_inputs.v1_fresh_command(command,namespace);
  expected:=command->'body'->'bundle'; PERFORM scanipy_accepted_inputs.v1_same_namespace(expected,namespace);
  frame:=scanipy_accepted_inputs.v1_frame(parts[1],'scanipy-publication-input/1');
  manifest:=scanipy_accepted_inputs.v1_document(frame[1],'scanipy-publication-input/1');
  FOREACH key IN ARRAY ARRAY['registry_id','scope','org_id','bundle_id','S_version','accepted_content_digest'] LOOP
    PERFORM scanipy_accepted_inputs.v1_require(manifest->key=expected->key,'content-mismatch');
  END LOOP;
  SELECT * INTO live FROM scanipy_accepted_inputs.v1_live(namespace,command->'body'->'admission');
  PERFORM scanipy_accepted_inputs.v1_require(frame[5]=live.objects[1] AND frame[6]=live.objects[2]
    AND frame[10]=live.objects[3] AND frame[11]=live.objects[4],'policy-stale');
  SELECT count(*)::integer INTO d FROM jsonb_array_elements(command->'objects') WHERE value->>'role'='detector';
  detectors:=parts[3:2+d]; rules:=parts[3+d:cardinality(parts)];
  SELECT * INTO bundle FROM scanipy_accepted_inputs.v1_bundle(parts[2],detectors,rules);
  FOREACH key IN ARRAY ARRAY['registry_id','scope','org_id','bundle_id','S_version'] LOOP
    PERFORM scanipy_accepted_inputs.v1_require(bundle.manifest->key=expected->key,'content-mismatch');
  END LOOP;
  PERFORM scanipy_accepted_inputs.v1_require(bundle.content_digest=decode(expected->>'accepted_content_digest','hex'),'content-mismatch');
  PERFORM scanipy_accepted_inputs.v1_control(512);
  SELECT id,s_version,accepted_content_digest INTO existing FROM scanipy_accepted_inputs.bundle_versions
    WHERE namespace_id=ns AND (id=(expected->>'bundle_id')::uuid OR s_version=expected->>'S_version');
  IF FOUND THEN
    PERFORM scanipy_accepted_inputs.v1_require(existing.id=(expected->>'bundle_id')::uuid
      AND existing.s_version=expected->>'S_version' AND existing.accepted_content_digest=bundle.content_digest,'content-mismatch');
    -- Existing bundle costs its complete T once; do not also select each model
    -- artifact raw value a second time in the fresh-artifact branch below.
    SELECT * INTO selected FROM scanipy_accepted_inputs.v1_fetch_bundle(ns,existing.id,bundle.content_digest);
    PERFORM scanipy_accepted_inputs.v1_require(selected.spec_bytes=parts[2]
      AND selected.detector_blobs=detectors AND selected.rule_blobs=rules,'content-mismatch');
  ELSE
    FOR item IN SELECT value,ordinality FROM jsonb_array_elements(bundle.manifest->'models') WITH ORDINALITY LOOP
      model_ids:=array_append(model_ids,scanipy_accepted_inputs.v1_retain_artifact(ns,'operation-model',
        item.value->>'artifact_id',item.value->>'version',item.value->>'schema',bundle.model_blobs[item.ordinality::integer],
        decode(item.value->>'raw_sha256','hex')));
    END LOOP;
    d:=0; r:=0;
    FOR item IN SELECT value FROM jsonb_array_elements(bundle.manifest->'detectors') LOOP
      d:=d+1;
      detector_ids:=array_append(detector_ids,scanipy_accepted_inputs.v1_retain_artifact(ns,'detector',
        item.value->>'detector_id',item.value->>'detector_version',item.value->>'detector_schema',detectors[d],
        decode(item.value->>'detector_sha256','hex')));
      FOR rule IN SELECT value FROM jsonb_array_elements(item.value->'rules') LOOP
        r:=r+1;
        rule_ids:=array_append(rule_ids,scanipy_accepted_inputs.v1_retain_artifact(ns,'rule-set',
          rule.value->>'artifact_id',rule.value->>'version',rule.value->>'schema',rules[r],
          decode(rule.value->>'raw_sha256','hex')));
      END LOOP;
    END LOOP;
    total:=octet_length(parts[2])::bigint+scanipy_accepted_inputs.v1_byte_array(detectors)+scanipy_accepted_inputs.v1_byte_array(rules);
    INSERT INTO scanipy_accepted_inputs.bundle_versions(id,namespace_id,s_version,spec_bytes,accepted_content_bytes,
      accepted_content_digest,detector_ids,rule_ids,model_ids,content_length)
      VALUES((expected->>'bundle_id')::uuid,ns,expected->>'S_version',parts[2],bundle.content_bytes,bundle.content_digest,
        detector_ids,rule_ids,model_ids,total);
  END IF;
  -- The current heads remain locked, but expensive decoding can cross expiry.
  -- Sample the actual DB clock only after that work and check all fresh uses.
  moment:=clock_timestamp();
  PERFORM scanipy_accepted_inputs.v1_policy_time(live.policy,live.checkpoint,moment);
  approval:=scanipy_accepted_inputs.v1_approval_material(frame,expected,namespace,live.policy,live.objects[1],moment);
  digest:=scanipy_accepted_inputs.v1_hash(frame[2],'scanipy-accepted-approval/1');
  receipt:=jsonb_build_object('schema','scanipy-accepted-publication/1',
    'registry_id',namespace->'registry_id','scope',namespace->'scope','org_id',namespace->'org_id',
    'publication_key',approval->'publication_key','bundle_id',expected->'bundle_id',
    'accepted_content_digest',expected->'accepted_content_digest','approval_event_id',approval->'event_id',
    'approval_statement_digest',encode(digest,'hex'),
    'approval_signature_sha256',encode(scanipy_accepted_inputs.v1_hash(frame[3]),'hex'),
    'evidence_inventory_digest',approval->'evidence_inventory_digest',
    'policy_digest',namespace->'policy_digest','policy_revision',namespace->'policy_revision',
    'checkpoint_digest',namespace->'checkpoint_digest','checkpoint_generation',namespace->'checkpoint_generation',
    'admission_epoch',namespace->'admission_epoch','published_at',to_char(moment AT TIME ZONE 'UTC','YYYY-MM-DD"T"HH24:MI:SS.US"Z"'),
    'publisher_actor_id',approval->'issuer_actor_id','publisher_artifact_digest',command->'body'->'publisher_artifact_digest');
  record_bytes:=scanipy_accepted_inputs.v1_bytes(receipt);
  PERFORM scanipy_accepted_inputs.v1_document(record_bytes,'scanipy-accepted-publication/1');
  PERFORM scanipy_accepted_inputs.v1_publication_record(frame,receipt,namespace,expected);
  receipt_digest:=scanipy_accepted_inputs.v1_hash(record_bytes,'scanipy-accepted-publication/1');
  INSERT INTO scanipy_accepted_inputs.authority_events(id,namespace_id,kind,record_schema,record_bytes,record_digest,
    recorded_at,operation_key,action,command_bytes,command_digest,command_parts,registry_id,scope,org_id,
    bundle_id,accepted_content_digest,publication_key,publication_receipt_bytes,publication_receipt_digest,
    publication_input_bytes,policy_event_id,policy_digest,policy_revision,admission_event_id,checkpoint_digest,
    checkpoint_generation,admission_epoch)
    VALUES((approval->>'event_id')::uuid,ns,'approval','scanipy-accepted-approval/1',frame[2],digest,moment,
      (command->>'operation_key')::uuid,'publish-builtin',command_bytes,
      scanipy_accepted_inputs.v1_hash(command_bytes,'scanipy-accepted-ledger-command/1'),parts,
      (namespace->>'registry_id')::uuid,namespace->>'scope',(namespace->>'org_id')::uuid,
      (expected->>'bundle_id')::uuid,bundle.content_digest,(approval->>'publication_key')::uuid,record_bytes,receipt_digest,
      parts[1],(namespace->>'policy_event_id')::uuid,decode(namespace->>'policy_digest','hex'),(namespace->>'policy_revision')::bigint,
      (namespace->>'admission_event_id')::uuid,decode(namespace->>'checkpoint_digest','hex'),
      (namespace->>'checkpoint_generation')::bigint,(namespace->>'admission_epoch')::uuid);
  replayed:=false; RETURN NEXT;
EXCEPTION WHEN unique_violation THEN RAISE EXCEPTION 'ledger-mismatch' USING ERRCODE='P0001';
END $$;

-- Original occurrence JSON retains its own portable scalar/depth/byte domain;
-- the fixed execution entrypoint still performs its complete owning shape and
-- relational validation. Never apply the accepted 20,000-value/16-KiB rule.
CREATE FUNCTION scanipy_accepted_inputs.v1_occurrence(data bytea,schema_name text) RETURNS jsonb
LANGUAGE plpgsql IMMUTABLE SET search_path=pg_catalog,scanipy_accepted_inputs,pg_temp AS $$
DECLARE preserved json; document jsonb; canonical bytea;
BEGIN
  PERFORM scanipy_accepted_inputs.v1_lexical(data,1048576,1048576,1048576);
  preserved:=convert_from(data,'UTF8')::json;
  canonical:=convert_to(scanipy_accepted_inputs.v1_canonical(preserved,0,1048576),'UTF8');
  PERFORM scanipy_accepted_inputs.v1_require(canonical=data);
  document:=preserved::jsonb;
  PERFORM scanipy_accepted_inputs.v1_require(jsonb_typeof(document)='object' AND document->>'schema'=schema_name);
  RETURN document;
EXCEPTION WHEN data_exception THEN RAISE EXCEPTION 'invalid-input' USING ERRCODE='P0001';
END $$;

CREATE FUNCTION scanipy_accepted_inputs.v1_planned_projection(manifest jsonb,policy jsonb) RETURNS void
LANGUAGE plpgsql IMMUTABLE SET search_path=pg_catalog,scanipy_accepted_inputs,pg_temp AS $$
DECLARE item record; binding jsonb; profile jsonb; expected_rules jsonb; key text;
BEGIN
  PERFORM scanipy_accepted_inputs.v1_require(policy->>'schema'='scanipy-execution/planned-policy/1'
    AND jsonb_typeof(policy->'bindings')='array');
  PERFORM scanipy_accepted_inputs.v1_require(jsonb_array_length(policy->'bindings')=jsonb_array_length(manifest->'detectors'));
  FOR item IN SELECT value,ordinality FROM jsonb_array_elements(manifest->'detectors') WITH ORDINALITY LOOP
    binding:=policy->'bindings'->(item.ordinality::integer-1);
    PERFORM scanipy_accepted_inputs.v1_require(jsonb_typeof(binding)='object'
      AND binding->'detector_id'=item.value->'detector_id' AND binding->'class_id'=item.value->'class_id'
      AND binding->'detector_content_digest'=item.value->'detector_sha256'
      AND binding->'engines'='["ifds"]'::jsonb,'content-mismatch');
    SELECT value INTO profile FROM jsonb_array_elements(item.value->'language_profiles')
      WHERE value->'language'=binding->'language';
    PERFORM scanipy_accepted_inputs.v1_require(FOUND,'content-mismatch');
    key:='accepted-detector/'||(item.ordinality-1)::text||'/'||(profile->>'language')||'/'||
      (profile->>'projection_profile')||'/'||(profile->>'source_syntax_schema');
    SELECT jsonb_agg(jsonb_build_object('rule_id',value->'rule_id','content_digest',value->'raw_sha256',
      'semantic_digest',value->'semantic_descriptor_digest') ORDER BY ordinality) INTO expected_rules
      FROM jsonb_array_elements(item.value->'rules') WITH ORDINALITY;
    PERFORM scanipy_accepted_inputs.v1_require(binding->>'key'=key AND binding->'rules'=expected_rules,'content-mismatch');
  END LOOP;
END $$;

CREATE FUNCTION scanipy_accepted_inputs.v1_planned_pins_present(policy jsonb) RETURNS boolean
LANGUAGE plpgsql IMMUTABLE SET search_path=pg_catalog,scanipy_accepted_inputs,pg_temp AS $$
DECLARE binding jsonb; field text; runner text;
BEGIN
  -- Owning schema validation must precede this predicate. A missing key or wrong
  -- type is a command failure, not the eligible schema-valid null-pin denial.
  PERFORM scanipy_accepted_inputs.v1_require(jsonb_typeof(policy->'bindings')='array');
  FOR binding IN SELECT value FROM jsonb_array_elements(policy->'bindings') LOOP
    FOREACH field IN ARRAY ARRAY['expected_tool_digest','expected_code_digest','expected_image_digest'] LOOP
      PERFORM scanipy_accepted_inputs.v1_require(binding ? field AND jsonb_typeof(binding->field) IN ('string','null'));
    END LOOP;
  END LOOP;
  FOREACH runner IN ARRAY ARRAY['capture_detection_runner','identity_runner'] LOOP
    PERFORM scanipy_accepted_inputs.v1_require(jsonb_typeof(policy->runner)='object');
    FOREACH field IN ARRAY ARRAY['expected_code_digest','expected_image_digest'] LOOP
      PERFORM scanipy_accepted_inputs.v1_require((policy->runner) ? field
        AND jsonb_typeof(policy->runner->field) IN ('string','null'));
    END LOOP;
  END LOOP;
  FOR binding IN SELECT value FROM jsonb_array_elements(policy->'bindings') LOOP
    IF binding->'expected_tool_digest'='null'::jsonb OR binding->'expected_code_digest'='null'::jsonb
      OR binding->'expected_image_digest'='null'::jsonb THEN RETURN false; END IF;
  END LOOP;
  FOREACH runner IN ARRAY ARRAY['capture_detection_runner','identity_runner'] LOOP
    IF policy->runner->'expected_code_digest'='null'::jsonb
      OR policy->runner->'expected_image_digest'='null'::jsonb THEN RETURN false; END IF;
  END LOOP;
  RETURN true;
END $$;

CREATE FUNCTION scanipy_accepted_inputs.v1_fetch_publication(namespace jsonb,p_approval uuid,expected jsonb)
RETURNS TABLE(frame bytea[],receipt_bytes bytea,receipt jsonb,approval jsonb)
LANGUAGE plpgsql SET search_path=pg_catalog,scanipy_accepted_inputs,pg_temp SET bytea_output='hex' AS $$
DECLARE row record; ns uuid;
BEGIN
  ns:=(namespace->>'namespace_id')::uuid;
  PERFORM scanipy_accepted_inputs.v1_control(1024);
  SELECT publication_input_length,publication_receipt_length INTO row
    FROM scanipy_accepted_inputs.authority_events WHERE namespace_id=ns AND kind='approval' AND id=p_approval;
  PERFORM scanipy_accepted_inputs.v1_require(FOUND AND row.publication_input_length BETWEEN 1 AND 1048576
    AND row.publication_receipt_length BETWEEN 1 AND 65536,'ledger-mismatch');
  PERFORM scanipy_accepted_inputs.v1_fetch(row.publication_input_length+row.publication_receipt_length);
  SELECT publication_input_bytes,publication_receipt_bytes,publication_receipt_digest,record_digest,
    bundle_id,accepted_content_digest INTO row FROM scanipy_accepted_inputs.authority_events
    WHERE namespace_id=ns AND kind='approval' AND id=p_approval;
  frame:=scanipy_accepted_inputs.v1_stored_frame(row.publication_input_bytes,'scanipy-publication-input/1');
  receipt_bytes:=row.publication_receipt_bytes;
  receipt:=scanipy_accepted_inputs.v1_stored_document(receipt_bytes,'scanipy-accepted-publication/1');
  approval:=scanipy_accepted_inputs.v1_publication_record(frame,receipt,namespace,expected);
  PERFORM scanipy_accepted_inputs.v1_require(approval->>'event_id'=p_approval::text
    AND row.bundle_id=(expected->>'bundle_id')::uuid
    AND row.accepted_content_digest=decode(expected->>'accepted_content_digest','hex')
    AND row.record_digest=scanipy_accepted_inputs.v1_hash(frame[2],'scanipy-accepted-approval/1')
    AND row.publication_receipt_digest=scanipy_accepted_inputs.v1_hash(receipt_bytes,'scanipy-accepted-publication/1'),
    'content-mismatch');
  RETURN NEXT;
END $$;

CREATE FUNCTION scanipy_accepted_inputs.create_bound_request_v1(command_bytes bytea,parts bytea[])
RETURNS TABLE(record_bytes bytea,replayed boolean)
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,scanipy_accepted_inputs,pg_temp SET bytea_output='hex' AS $$
DECLARE command jsonb; namespace jsonb; expected jsonb; ns uuid; replay record; live record; bundle record;
  publication record; request jsonb; policy jsonb; request_digest bytea; policy_digest bytea;
  lower_result jsonb; moment timestamptz; manifest jsonb; key text; seal_digest bytea; objects bytea[];
BEGIN
  PERFORM scanipy_accepted_inputs.v1_work_begin(10813440,167772160);
  command:=scanipy_accepted_inputs.v1_command(command_bytes,parts,'create-bound-request');
  ns:=(command->>'namespace_id')::uuid; namespace:=scanipy_accepted_inputs.v1_namespace(ns);
  SELECT * INTO replay FROM scanipy_accepted_inputs.v1_replay(command,command_bytes,parts);
  IF FOUND THEN record_bytes:=replay.record_bytes; replayed:=true; RETURN NEXT; RETURN; END IF;
  PERFORM scanipy_accepted_inputs.v1_fresh_command(command,namespace);
  expected:=command->'body'->'bundle'; PERFORM scanipy_accepted_inputs.v1_same_namespace(expected,namespace);
  PERFORM scanipy_accepted_inputs.v1_require(namespace->>'scope'='customer','scope-mismatch');
  SELECT * INTO live FROM scanipy_accepted_inputs.v1_live(namespace,command->'body'->'admission');
  SELECT * INTO publication FROM scanipy_accepted_inputs.v1_fetch_publication(namespace,
    (command->'body'->>'approval_event_id')::uuid,expected);
  SELECT * INTO bundle FROM scanipy_accepted_inputs.v1_fetch_bundle(ns,(expected->>'bundle_id')::uuid,
    decode(expected->>'accepted_content_digest','hex'));
  FOREACH key IN ARRAY ARRAY['registry_id','scope','org_id','bundle_id','S_version'] LOOP
    PERFORM scanipy_accepted_inputs.v1_require(bundle.manifest->key=expected->key,'content-mismatch');
  END LOOP;
  -- Reserve legacy concatenation work before any new occurrence JSON tree;
  -- its owner still validates the full shape in the actual call below.
  PERFORM scanipy_accepted_inputs.v1_lower_preflight('create',parts);
  PERFORM scanipy_accepted_inputs.v1_lower_reserve('create',parts);
  request:=scanipy_accepted_inputs.v1_occurrence(parts[1],'scanipy-execution/request/1');
  policy:=scanipy_accepted_inputs.v1_occurrence(parts[2],'scanipy-execution/planned-policy/1');
  request_digest:=scanipy_accepted_inputs.v1_hash(parts[1],'scanipy-execution/request/1');
  policy_digest:=scanipy_accepted_inputs.v1_hash(parts[2],'scanipy-execution/planned-policy/1');
  PERFORM scanipy_accepted_inputs.v1_require(request->'org_id'=expected->'org_id','scope-mismatch');
  PERFORM scanipy_accepted_inputs.v1_require(request->'requested_s_version'=expected->'S_version'
    AND request->>'requested_policy_digest'=encode(policy_digest,'hex')
    AND request->'identity_policy'=policy->'identity_policy','content-mismatch');
  PERFORM scanipy_accepted_inputs.v1_planned_projection(bundle.manifest,policy);
  PERFORM scanipy_accepted_inputs.v1_relational_reserve(5);
  lower_result:=scanipy_execution.create_request_v1((expected->>'org_id')::uuid,(request->>'codebase_id')::uuid,
    parts[1],request_digest,parts[2],policy_digest);
  PERFORM scanipy_accepted_inputs.v1_keys(lower_result,ARRAY['request_id','work_item_id','revision','replayed']);
  PERFORM scanipy_accepted_inputs.v1_require(lower_result->'replayed'='false'::jsonb,'ledger-mismatch');
  PERFORM scanipy_accepted_inputs.v1_shape(lower_result->'request_id','"uuid"');
  PERFORM scanipy_accepted_inputs.v1_shape(lower_result->'work_item_id','"uuid"');
  PERFORM scanipy_accepted_inputs.v1_shape(lower_result->'revision','"count"');
  moment:=clock_timestamp();
  PERFORM scanipy_accepted_inputs.v1_policy_time(live.policy,live.checkpoint,moment);
  PERFORM scanipy_accepted_inputs.v1_grant_use(scanipy_accepted_inputs.v1_grant(live.policy,publication.approval),
    moment,(publication.receipt->>'published_at')::timestamptz);
  PERFORM scanipy_accepted_inputs.v1_require((publication.receipt->>'published_at')::timestamptz<=moment,'ledger-mismatch');
  manifest:=jsonb_build_object('registry_id',namespace->'registry_id','bundle_id',expected->'bundle_id',
    'org_id',expected->'org_id','codebase_id',request->'codebase_id','request_id',lower_result->'request_id',
    'accepted_content_digest',expected->'accepted_content_digest','approval_event_id',publication.approval->'event_id',
    'publication_policy_digest',publication.receipt->'policy_digest',
    'current_policy_digest',namespace->'policy_digest','current_policy_revision',namespace->'policy_revision',
    'checkpoint_digest',namespace->'checkpoint_digest','checkpoint_generation',namespace->'checkpoint_generation',
    'admission_epoch',namespace->'admission_epoch',
    'resolved_at',to_char(moment AT TIME ZONE 'UTC','YYYY-MM-DD"T"HH24:MI:SS.US"Z"'),
    'verifier_artifact_digest',command->'body'->'verifier_artifact_digest');
  objects:=ARRAY[publication.frame[2],publication.frame[3],publication.frame[4],publication.receipt_bytes,
    publication.frame[5],publication.frame[6],publication.frame[10],publication.frame[11],
    live.objects[1],live.objects[2],publication.frame[7],publication.frame[8],publication.frame[9],live.objects[3],live.objects[4]];
  record_bytes:=scanipy_accepted_inputs.v1_encode_frame('scanipy-sealed-acceptance/1',manifest,objects);
  seal_digest:=scanipy_accepted_inputs.v1_hash(record_bytes);
  INSERT INTO scanipy_accepted_inputs.request_bundle_bindings(namespace_id,org_id,codebase_id,request_id,
    registry_id,bundle_id,approval_event_id,policy_event_id,admission_event_id,accepted_content_digest,
    requested_policy_digest,sealed_bytes,sealed_sha256,resolved_at,operation_key,command_bytes,command_digest,command_parts)
    VALUES(ns,(expected->>'org_id')::uuid,(request->>'codebase_id')::uuid,(lower_result->>'request_id')::uuid,
      (namespace->>'registry_id')::uuid,(expected->>'bundle_id')::uuid,(publication.approval->>'event_id')::uuid,
      (namespace->>'policy_event_id')::uuid,(namespace->>'admission_event_id')::uuid,bundle.content_digest,
      policy_digest,record_bytes,seal_digest,moment,(command->>'operation_key')::uuid,command_bytes,
      scanipy_accepted_inputs.v1_hash(command_bytes,'scanipy-accepted-ledger-command/1'),parts);
  replayed:=false; RETURN NEXT;
EXCEPTION WHEN unique_violation THEN RAISE EXCEPTION 'ledger-mismatch' USING ERRCODE='P0001';
END $$;

CREATE FUNCTION scanipy_accepted_inputs.v1_relational_reserve(tickets integer) RETURNS void
LANGUAGE plpgsql SET search_path=pg_catalog,scanipy_accepted_inputs,pg_temp AS $$
BEGIN
  PERFORM scanipy_accepted_inputs.v1_require(tickets BETWEEN 1 AND 5);
  PERFORM scanipy_accepted_inputs.v1_charge(5,tickets::bigint*65537);
  PERFORM scanipy_accepted_inputs.v1_charge(3,64::bigint*tickets*65537);
END $$;

CREATE FUNCTION scanipy_accepted_inputs.v1_fetch_binding(namespace jsonb,p_request uuid)
RETURNS TABLE(sealed_bytes bytea,sealed_digest bytea,frame bytea[],manifest jsonb,expected jsonb,
  planned_bytes bytea,planned jsonb,requested_policy_digest bytea)
LANGUAGE plpgsql SET search_path=pg_catalog,scanipy_accepted_inputs,pg_temp SET bytea_output='hex' AS $$
DECLARE meta record; row record; ns uuid;
BEGIN
  ns:=(namespace->>'namespace_id')::uuid;
  PERFORM scanipy_accepted_inputs.v1_require(namespace->>'scope'='customer' AND p_request IS NOT NULL,'scope-mismatch');
  PERFORM scanipy_accepted_inputs.v1_control(1024);
  SELECT sealed_length,command_part_lengths INTO meta FROM scanipy_accepted_inputs.request_bundle_bindings
    WHERE namespace_id=ns AND org_id=(namespace->>'org_id')::uuid AND request_id=p_request;
  PERFORM scanipy_accepted_inputs.v1_require(FOUND AND meta.sealed_length BETWEEN 1 AND 1048576
    AND cardinality(meta.command_part_lengths)=2 AND meta.command_part_lengths[2] BETWEEN 1 AND 1048576,'ledger-mismatch');
  PERFORM scanipy_accepted_inputs.v1_fetch(meta.sealed_length+meta.command_part_lengths[2]);
  SELECT b.sealed_bytes,b.sealed_sha256,b.command_parts[2] AS planned_bytes,b.requested_policy_digest,
    b.codebase_id,b.bundle_id,b.approval_event_id,b.policy_event_id,b.admission_event_id,b.accepted_content_digest,b.resolved_at
    INTO row FROM scanipy_accepted_inputs.request_bundle_bindings b
    WHERE namespace_id=ns AND org_id=(namespace->>'org_id')::uuid AND request_id=p_request;
  sealed_bytes:=row.sealed_bytes; sealed_digest:=row.sealed_sha256; planned_bytes:=row.planned_bytes;
  requested_policy_digest:=row.requested_policy_digest;
  PERFORM scanipy_accepted_inputs.v1_require(octet_length(sealed_bytes)=meta.sealed_length
    AND octet_length(planned_bytes)=meta.command_part_lengths[2]
    AND scanipy_accepted_inputs.v1_hash(sealed_bytes)=sealed_digest
    AND scanipy_accepted_inputs.v1_hash(planned_bytes,'scanipy-execution/planned-policy/1')=requested_policy_digest,
    'content-mismatch');
  frame:=scanipy_accepted_inputs.v1_stored_frame(sealed_bytes,'scanipy-sealed-acceptance/1');
  expected:=scanipy_accepted_inputs.v1_sealed_material(frame,namespace);
  manifest:=scanipy_accepted_inputs.v1_stored_document(frame[1],'scanipy-sealed-acceptance/1');
  PERFORM scanipy_accepted_inputs.v1_require(manifest->>'request_id'=p_request::text
    AND manifest->>'codebase_id'=row.codebase_id::text AND manifest->>'bundle_id'=row.bundle_id::text
    AND manifest->>'approval_event_id'=row.approval_event_id::text
    AND manifest->>'accepted_content_digest'=encode(row.accepted_content_digest,'hex')
    AND (manifest->>'resolved_at')::timestamptz=row.resolved_at
    AND convert_from(frame[10],'UTF8')::jsonb->>'event_id'=row.policy_event_id::text
    AND convert_from(frame[15],'UTF8')::jsonb->>'event_id'=row.admission_event_id::text,'content-mismatch');
  planned:=scanipy_accepted_inputs.v1_stored_occurrence(planned_bytes,'scanipy-execution/planned-policy/1');
  RETURN NEXT;
END $$;

CREATE FUNCTION scanipy_accepted_inputs.v1_context_check(context jsonb,namespace jsonb,fence jsonb) RETURNS void
LANGUAGE plpgsql IMMUTABLE SET search_path=pg_catalog,scanipy_accepted_inputs,pg_temp AS $$
DECLARE key text; extra text[]; captured boolean;
BEGIN
  extra:=CASE WHEN context ? 'detector_run_id' THEN ARRAY['detector_run_id','run_input_digest','run_state'] ELSE ARRAY[]::text[] END;
  PERFORM scanipy_accepted_inputs.v1_keys(context,ARRAY['org_id','codebase_id','request_id','work_item_id',
    'work_attempt_id','fencing_token','work_revision','requested_policy_digest','attempt_policy_digest','lease_expires_at',
    'capture_id','seal_id','capture_lease_id','capture_lease_expires_at','accepted_content_digest','acceptance_evidence_digest','db_now']||extra);
  PERFORM scanipy_accepted_inputs.v1_require(context->'org_id'=namespace->'org_id','scope-mismatch');
  FOREACH key IN ARRAY ARRAY['work_item_id','work_attempt_id','fencing_token','work_revision'] LOOP
    PERFORM scanipy_accepted_inputs.v1_require(context->key=fence->key,'fence-stale');
  END LOOP;
  FOREACH key IN ARRAY ARRAY['org_id','codebase_id','request_id','work_item_id','work_attempt_id'] LOOP
    PERFORM scanipy_accepted_inputs.v1_shape(context->key,'"uuid"');
  END LOOP;
  FOREACH key IN ARRAY ARRAY['requested_policy_digest','attempt_policy_digest'] LOOP
    PERFORM scanipy_accepted_inputs.v1_shape(context->key,'"digest"');
  END LOOP;
  PERFORM scanipy_accepted_inputs.v1_shape(context->'lease_expires_at','"instant"');
  PERFORM scanipy_accepted_inputs.v1_shape(context->'db_now','"instant"');
  captured:=context->'capture_id'<>'null'::jsonb;
  FOREACH key IN ARRAY ARRAY['capture_id','seal_id','capture_lease_id','capture_lease_expires_at',
    'accepted_content_digest','acceptance_evidence_digest'] LOOP
    PERFORM scanipy_accepted_inputs.v1_require((context->key<>'null'::jsonb)=captured,'ledger-mismatch');
    IF captured THEN
      PERFORM scanipy_accepted_inputs.v1_shape(context->key,to_jsonb(CASE WHEN key IN ('accepted_content_digest','acceptance_evidence_digest')
        THEN 'digest' WHEN key='capture_lease_expires_at' THEN 'instant' ELSE 'uuid' END));
    END IF;
  END LOOP;
  IF cardinality(extra)>0 THEN
    PERFORM scanipy_accepted_inputs.v1_require(captured AND context->>'run_state' IN ('pending','running'),'fence-stale');
    PERFORM scanipy_accepted_inputs.v1_shape(context->'detector_run_id','"uuid"');
    PERFORM scanipy_accepted_inputs.v1_shape(context->'run_input_digest','"digest"');
  END IF;
END $$;

CREATE FUNCTION scanipy_accepted_inputs.v1_common_observation(command jsonb,namespace jsonb,
  expected jsonb,binding_digest bytea,context jsonb) RETURNS jsonb
LANGUAGE plpgsql VOLATILE SET search_path=pg_catalog,scanipy_accepted_inputs,pg_temp AS $$
DECLARE result jsonb; key text;
BEGIN
  result:=jsonb_build_object('event_id',gen_random_uuid(),'operation_key',command->'operation_key',
    'registry_id',namespace->'registry_id','scope',namespace->'scope','org_id',namespace->'org_id',
    'bundle_id',expected->'bundle_id','request_binding_digest',encode(binding_digest,'hex'),
    'accepted_content_digest',expected->'accepted_content_digest',
    'policy_event_id',namespace->'policy_event_id','policy_digest',namespace->'policy_digest','policy_revision',namespace->'policy_revision',
    'admission_event_id',namespace->'admission_event_id','checkpoint_digest',namespace->'checkpoint_digest',
    'checkpoint_generation',namespace->'checkpoint_generation','admission_epoch',namespace->'admission_epoch',
    'work_kind','capture_detection','resolver_artifact_digest',command->'body'->'resolver_artifact_digest');
  FOREACH key IN ARRAY ARRAY['codebase_id','request_id','work_item_id','work_attempt_id','fencing_token','work_revision',
    'capture_id','seal_id','capture_lease_id','requested_policy_digest','attempt_policy_digest','lease_expires_at','capture_lease_expires_at'] LOOP
    result:=result||jsonb_build_object(key,context->key);
  END LOOP;
  RETURN result;
END $$;

CREATE FUNCTION scanipy_accepted_inputs.v1_emit_observation(command jsonb,raw_command bytea,parts bytea[],document jsonb)
RETURNS bytea LANGUAGE plpgsql SET search_path=pg_catalog,scanipy_accepted_inputs,pg_temp SET bytea_output='hex' AS $$
DECLARE raw bytea; kind_name text; schema_name text;
BEGIN
  schema_name:=document->>'schema';
  kind_name:=CASE schema_name WHEN 'scanipy-capture-seal-authorization/1' THEN 'seal-authorization'
    WHEN 'scanipy-execution-authorization/1' THEN 'execution-authorization'
    WHEN 'scanipy-execution-denial/1' THEN 'execution-denial' END;
  PERFORM scanipy_accepted_inputs.v1_require(kind_name IS NOT NULL);
  raw:=scanipy_accepted_inputs.v1_bytes(document);
  PERFORM scanipy_accepted_inputs.v1_document(raw,schema_name);
  INSERT INTO scanipy_accepted_inputs.authority_events(id,namespace_id,kind,record_schema,record_bytes,record_digest,
    recorded_at,operation_key,action,command_bytes,command_digest,command_parts,registry_id,scope,org_id,
    bundle_id,accepted_content_digest,approval_event_id,policy_event_id,policy_digest,policy_revision,
    admission_event_id,checkpoint_digest,checkpoint_generation,admission_epoch,codebase_id,request_id,
    request_binding_digest,work_item_id,work_attempt_id,fencing_token,work_revision,capture_id,seal_id,capture_lease_id,
    requested_policy_digest,attempt_policy_digest,lease_expires_at,capture_lease_expires_at,
    detector_run_id,run_input_digest,occurrence_id,previous_authorization_id,purpose,execution_action,
    resolver_artifact_digest,authorized_at,observed_at,denial_reason)
    VALUES((document->>'event_id')::uuid,(command->>'namespace_id')::uuid,kind_name,schema_name,raw,
      scanipy_accepted_inputs.v1_hash(raw,schema_name),coalesce(document->>'authorized_at',document->>'observed_at')::timestamptz,
      (command->>'operation_key')::uuid,command->>'action',raw_command,
      scanipy_accepted_inputs.v1_hash(raw_command,'scanipy-accepted-ledger-command/1'),parts,
      (document->>'registry_id')::uuid,document->>'scope',(document->>'org_id')::uuid,
      (document->>'bundle_id')::uuid,decode(document->>'accepted_content_digest','hex'),(document->>'approval_event_id')::uuid,
      (document->>'policy_event_id')::uuid,decode(document->>'policy_digest','hex'),(document->>'policy_revision')::bigint,
      (document->>'admission_event_id')::uuid,decode(document->>'checkpoint_digest','hex'),
      (document->>'checkpoint_generation')::bigint,(document->>'admission_epoch')::uuid,
      (document->>'codebase_id')::uuid,(document->>'request_id')::uuid,decode(document->>'request_binding_digest','hex'),
      (document->>'work_item_id')::uuid,(document->>'work_attempt_id')::uuid,(document->>'fencing_token')::bigint,
      (document->>'work_revision')::bigint,(document->>'capture_id')::uuid,(document->>'seal_id')::uuid,(document->>'capture_lease_id')::uuid,
      decode(document->>'requested_policy_digest','hex'),decode(document->>'attempt_policy_digest','hex'),
      (document->>'lease_expires_at')::timestamptz,(document->>'capture_lease_expires_at')::timestamptz,
      (document->>'detector_run_id')::uuid,decode(document->>'run_input_digest','hex'),(document->>'occurrence_id')::uuid,
      (document->>'previous_authorization_id')::uuid,document->>'purpose',document->>'action',
      decode(document->>'resolver_artifact_digest','hex'),(document->>'authorized_at')::timestamptz,
      (document->>'observed_at')::timestamptz,document->>'reason');
  RETURN raw;
END $$;

CREATE FUNCTION scanipy_accepted_inputs.seal_bound_capture_v1(command_bytes bytea,parts bytea[])
RETURNS TABLE(record_bytes bytea,replayed boolean)
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,scanipy_accepted_inputs,pg_temp SET bytea_output='hex' AS $$
DECLARE command jsonb; namespace jsonb; ns uuid; replay record; live record; binding record; bundle record;
  seal jsonb; context jsonb; fence jsonb; lower_result jsonb; document jsonb; moment timestamptz;
  seal_digest bytea; inventory_digest bytea; content_digest bytea; approval jsonb; receipt jsonb;
  first_observed_at timestamptz;
BEGIN
  PERFORM scanipy_accepted_inputs.v1_work_begin(18087936,167772160);
  command:=scanipy_accepted_inputs.v1_command(command_bytes,parts,'seal-bound-capture');
  ns:=(command->>'namespace_id')::uuid; namespace:=scanipy_accepted_inputs.v1_namespace(ns);
  SELECT * INTO replay FROM scanipy_accepted_inputs.v1_replay(command,command_bytes,parts);
  IF FOUND THEN record_bytes:=replay.record_bytes; replayed:=true; RETURN NEXT; RETURN; END IF;
  PERFORM scanipy_accepted_inputs.v1_fresh_command(command,namespace);
  PERFORM scanipy_accepted_inputs.v1_require(namespace->>'scope'='customer','scope-mismatch');
  PERFORM scanipy_accepted_inputs.v1_lower_preflight('register',parts);
  seal:=scanipy_accepted_inputs.v1_occurrence(parts[1],'scanipy-execution/seal/1');
  PERFORM scanipy_accepted_inputs.v1_shape(seal->'request_id','"uuid"');
  SELECT * INTO live FROM scanipy_accepted_inputs.v1_live(namespace,command->'body'->'admission');
  SELECT * INTO binding FROM scanipy_accepted_inputs.v1_fetch_binding(namespace,(seal->>'request_id')::uuid);
  SELECT * INTO bundle FROM scanipy_accepted_inputs.v1_fetch_bundle(ns,(binding.expected->>'bundle_id')::uuid,
    decode(binding.expected->>'accepted_content_digest','hex'));
  PERFORM scanipy_accepted_inputs.v1_planned_projection(bundle.manifest,binding.planned);
  PERFORM scanipy_accepted_inputs.v1_require(seal->'bindings'=binding.planned->'bindings'
    AND seal->'s_version'=binding.expected->'S_version'
    AND seal->>'planned_policy_digest'=encode(binding.requested_policy_digest,'hex')
    AND seal->>'acceptance_evidence_digest'=encode(binding.sealed_digest,'hex')
    AND parts[3]=bundle.accepted_content_bytes,'content-mismatch');
  fence:=command->'body'->'fence';
  PERFORM scanipy_accepted_inputs.v1_relational_reserve(5);
  PERFORM scanipy_accepted_inputs.v1_relational_reserve(2);
  context:=scanipy_execution.lock_accepted_capture_context_v1((namespace->>'org_id')::uuid,
    (fence->>'work_item_id')::uuid,(fence->>'work_attempt_id')::uuid,(fence->>'fencing_token')::bigint,(fence->>'work_revision')::bigint);
  PERFORM scanipy_accepted_inputs.v1_context_check(context,namespace,fence);
  first_observed_at:=(context->>'db_now')::timestamptz;
  PERFORM scanipy_accepted_inputs.v1_require(first_observed_at>=(binding.manifest->>'resolved_at')::timestamptz,'fence-stale');
  PERFORM scanipy_accepted_inputs.v1_require(context->'request_id'=seal->'request_id'
    AND context->'codebase_id'=binding.manifest->'codebase_id'
    AND context->>'requested_policy_digest'=encode(binding.requested_policy_digest,'hex')
    AND context->'capture_id'='null'::jsonb,'ledger-mismatch');
  PERFORM scanipy_accepted_inputs.v1_lower_reserve('register',parts,cardinality(bundle.detector_blobs),cardinality(bundle.rule_blobs));
  seal_digest:=scanipy_accepted_inputs.v1_hash(parts[1],'scanipy-execution/seal/1');
  inventory_digest:=scanipy_accepted_inputs.v1_hash(parts[2],'scanipy-execution/source-inventory/1');
  content_digest:=scanipy_accepted_inputs.v1_hash(parts[3],'scanipy-execution/accepted-content/1');
  lower_result:=scanipy_execution.register_capture_and_seal_v1((namespace->>'org_id')::uuid,
    (fence->>'work_item_id')::uuid,(fence->>'work_attempt_id')::uuid,(fence->>'fencing_token')::bigint,(fence->>'work_revision')::bigint,
    parts[1],seal_digest,parts[2],inventory_digest,parts[3],content_digest,
    bundle.spec_bytes,bundle.detector_blobs,bundle.rule_blobs,binding.sealed_bytes);
  PERFORM scanipy_accepted_inputs.v1_keys(lower_result,ARRAY['capture_id','seal_id','replayed']);
  PERFORM scanipy_accepted_inputs.v1_require(lower_result->'replayed'='false'::jsonb,'ledger-mismatch');
  PERFORM scanipy_accepted_inputs.v1_relational_reserve(2);
  context:=scanipy_execution.lock_accepted_capture_context_v1((namespace->>'org_id')::uuid,
    (fence->>'work_item_id')::uuid,(fence->>'work_attempt_id')::uuid,(fence->>'fencing_token')::bigint,(fence->>'work_revision')::bigint);
  PERFORM scanipy_accepted_inputs.v1_context_check(context,namespace,fence);
  PERFORM scanipy_accepted_inputs.v1_require(context->'capture_id'=lower_result->'capture_id'
    AND context->'seal_id'=lower_result->'seal_id' AND context->'request_id'=seal->'request_id'
    AND context->>'accepted_content_digest'=encode(bundle.content_digest,'hex')
    AND context->>'acceptance_evidence_digest'=encode(binding.sealed_digest,'hex'),'content-mismatch');
  moment:=clock_timestamp();
  PERFORM scanipy_accepted_inputs.v1_require((context->>'db_now')::timestamptz>=first_observed_at
    AND moment>=(context->>'db_now')::timestamptz
    AND (binding.manifest->>'resolved_at')::timestamptz<=moment
    AND moment<(context->>'lease_expires_at')::timestamptz
    AND moment<(context->>'capture_lease_expires_at')::timestamptz,'fence-stale');
  PERFORM scanipy_accepted_inputs.v1_policy_time(live.policy,live.checkpoint,moment);
  approval:=scanipy_accepted_inputs.v1_stored_document(binding.frame[2],'scanipy-accepted-approval/1');
  receipt:=scanipy_accepted_inputs.v1_stored_document(binding.frame[5],'scanipy-accepted-publication/1');
  PERFORM scanipy_accepted_inputs.v1_grant_use(scanipy_accepted_inputs.v1_grant(live.policy,approval),moment,(receipt->>'published_at')::timestamptz);
  document:=scanipy_accepted_inputs.v1_common_observation(command,namespace,binding.expected,binding.sealed_digest,context)||
    jsonb_build_object('schema','scanipy-capture-seal-authorization/1','approval_event_id',approval->'event_id',
      'authorized_at',to_char(moment AT TIME ZONE 'UTC','YYYY-MM-DD"T"HH24:MI:SS.US"Z"'));
  record_bytes:=scanipy_accepted_inputs.v1_emit_observation(command,command_bytes,parts,document);
  replayed:=false; RETURN NEXT;
EXCEPTION WHEN unique_violation THEN RAISE EXCEPTION 'ledger-mismatch' USING ERRCODE='P0001';
END $$;

-- Immutable AL rows are read under the held namespace lock before the occurrence lock
-- hierarchy. These fixed private helpers add no execution-side selector.
CREATE FUNCTION scanipy_accepted_inputs.v1_fetch_seal(namespace jsonb,p_work uuid)
RETURNS TABLE(document jsonb,seal_bytes bytea,seal jsonb)
LANGUAGE plpgsql SET search_path=pg_catalog,scanipy_accepted_inputs,pg_temp SET bytea_output='hex' AS $$
DECLARE meta record; row record; ns uuid;
BEGIN
  ns:=(namespace->>'namespace_id')::uuid;
  PERFORM scanipy_accepted_inputs.v1_control(1024);
  SELECT id,record_length,command_part_lengths INTO meta FROM scanipy_accepted_inputs.authority_events
    WHERE namespace_id=ns AND kind='seal-authorization' AND work_item_id=p_work;
  PERFORM scanipy_accepted_inputs.v1_require(FOUND AND meta.record_length<=65536
    AND cardinality(meta.command_part_lengths)=3 AND meta.command_part_lengths[1] BETWEEN 1 AND 1048576,'ledger-mismatch');
  PERFORM scanipy_accepted_inputs.v1_fetch(meta.record_length+meta.command_part_lengths[1]);
  SELECT record_bytes,record_digest,command_parts[1] AS seal_bytes,request_id,seal_id,capture_id,
    request_binding_digest,accepted_content_digest INTO row FROM scanipy_accepted_inputs.authority_events
    WHERE namespace_id=ns AND id=meta.id;
  document:=scanipy_accepted_inputs.v1_stored_document(row.record_bytes,'scanipy-capture-seal-authorization/1');
  PERFORM scanipy_accepted_inputs.v1_same_namespace(document,namespace);
  PERFORM scanipy_accepted_inputs.v1_require(document->>'event_id'=meta.id::text
    AND document->>'work_item_id'=p_work::text AND document->>'request_id'=row.request_id::text
    AND document->>'seal_id'=row.seal_id::text AND document->>'capture_id'=row.capture_id::text
    AND document->>'request_binding_digest'=encode(row.request_binding_digest,'hex')
    AND document->>'accepted_content_digest'=encode(row.accepted_content_digest,'hex')
    AND scanipy_accepted_inputs.v1_hash(row.record_bytes,'scanipy-capture-seal-authorization/1')=row.record_digest,'content-mismatch');
  seal_bytes:=row.seal_bytes; seal:=scanipy_accepted_inputs.v1_stored_occurrence(seal_bytes,'scanipy-execution/seal/1');
  PERFORM scanipy_accepted_inputs.v1_require(seal->'request_id'=document->'request_id'
    AND seal->'planned_policy_digest'=document->'requested_policy_digest'
    AND seal->'acceptance_evidence_digest'=document->'request_binding_digest','content-mismatch');
  RETURN NEXT;
END $$;

CREATE FUNCTION scanipy_accepted_inputs.v1_fetch_execution(namespace jsonb,p_attempt uuid,p_run uuid,p_previous uuid)
RETURNS TABLE(document jsonb,record_bytes bytea,record_digest bytea,run_bytes bytea,run_input jsonb)
LANGUAGE plpgsql SET search_path=pg_catalog,scanipy_accepted_inputs,pg_temp SET bytea_output='hex' AS $$
DECLARE meta record; row record; initial record; ns uuid; leaf uuid;
BEGIN
  ns:=(namespace->>'namespace_id')::uuid;
  PERFORM scanipy_accepted_inputs.v1_control(1536);
  SELECT id,record_length INTO meta FROM scanipy_accepted_inputs.authority_events
    WHERE namespace_id=ns AND kind='execution-authorization' AND id=p_previous
      AND work_attempt_id=p_attempt AND detector_run_id=p_run;
  PERFORM scanipy_accepted_inputs.v1_require(FOUND AND meta.record_length<=65536,'ledger-mismatch');
  SELECT id INTO leaf FROM scanipy_accepted_inputs.authority_events
    WHERE namespace_id=ns AND kind='execution-authorization' AND work_attempt_id=p_attempt AND detector_run_id=p_run
    ORDER BY work_revision DESC LIMIT 1;
  PERFORM scanipy_accepted_inputs.v1_require(leaf=p_previous,'ledger-mismatch');
  SELECT id,command_part_lengths INTO initial FROM scanipy_accepted_inputs.authority_events
    WHERE namespace_id=ns AND kind='execution-authorization' AND execution_action='initial'
      AND work_attempt_id=p_attempt AND detector_run_id=p_run;
  PERFORM scanipy_accepted_inputs.v1_require(FOUND AND cardinality(initial.command_part_lengths)=1
    AND initial.command_part_lengths[1] BETWEEN 1 AND 1048576,'ledger-mismatch');
  PERFORM scanipy_accepted_inputs.v1_fetch(meta.record_length+initial.command_part_lengths[1]);
  SELECT e.record_bytes,e.record_digest,e.work_revision,e.run_input_digest INTO row
    FROM scanipy_accepted_inputs.authority_events e WHERE namespace_id=ns AND id=p_previous;
  SELECT command_parts[1] INTO run_bytes FROM scanipy_accepted_inputs.authority_events WHERE namespace_id=ns AND id=initial.id;
  record_bytes:=row.record_bytes; record_digest:=row.record_digest;
  document:=scanipy_accepted_inputs.v1_stored_document(record_bytes,'scanipy-execution-authorization/1');
  PERFORM scanipy_accepted_inputs.v1_same_namespace(document,namespace);
  PERFORM scanipy_accepted_inputs.v1_require(document->>'event_id'=p_previous::text
    AND document->>'work_attempt_id'=p_attempt::text AND document->>'detector_run_id'=p_run::text
    AND (document->>'work_revision')::bigint=row.work_revision
    AND document->>'run_input_digest'=encode(row.run_input_digest,'hex')
    AND scanipy_accepted_inputs.v1_hash(record_bytes,'scanipy-execution-authorization/1')=record_digest
    AND scanipy_accepted_inputs.v1_hash(run_bytes,'scanipy-execution/run-input/1')=row.run_input_digest,'content-mismatch');
  run_input:=scanipy_accepted_inputs.v1_stored_occurrence(run_bytes,'scanipy-execution/run-input/1');
  RETURN NEXT;
END $$;

CREATE FUNCTION scanipy_accepted_inputs.v1_execution_material(namespace jsonb,expected jsonb,
  binding_digest bytea,manifest jsonb,planned jsonb,seal_document jsonb,seal jsonb,run_input jsonb)
RETURNS void LANGUAGE plpgsql IMMUTABLE SET search_path=pg_catalog,scanipy_accepted_inputs,pg_temp AS $$
DECLARE key text; selected jsonb;
BEGIN
  FOREACH key IN ARRAY ARRAY['registry_id','org_id','bundle_id','request_id','codebase_id','accepted_content_digest','approval_event_id'] LOOP
    PERFORM scanipy_accepted_inputs.v1_require(seal_document->key=manifest->key,'content-mismatch');
  END LOOP;
  PERFORM scanipy_accepted_inputs.v1_require(seal_document->>'request_binding_digest'=encode(binding_digest,'hex')
    AND seal->'bindings'=planned->'bindings' AND seal->'s_version'=expected->'S_version'
    AND (manifest->>'resolved_at')::timestamptz<=(seal_document->>'authorized_at')::timestamptz,'content-mismatch');
  SELECT value INTO selected FROM jsonb_array_elements(planned->'bindings') WHERE value->'key'=run_input->'binding_key';
  PERFORM scanipy_accepted_inputs.v1_require(FOUND,'content-mismatch');
  FOREACH key IN ARRAY ARRAY['tool_policy_digest','code_policy_digest','environment_policy_digest'] LOOP
    PERFORM scanipy_accepted_inputs.v1_require(selected->key=run_input->key,'content-mismatch');
  END LOOP;
END $$;

CREATE FUNCTION scanipy_accepted_inputs.v1_context_material(context jsonb,seal_document jsonb,
  manifest jsonb,binding_digest bytea,requested_digest bytea,run_digest bytea DEFAULT NULL)
RETURNS void LANGUAGE plpgsql IMMUTABLE SET search_path=pg_catalog,scanipy_accepted_inputs,pg_temp AS $$
DECLARE key text;
BEGIN
  FOREACH key IN ARRAY ARRAY['org_id','codebase_id','request_id','capture_id','seal_id','work_item_id'] LOOP
    PERFORM scanipy_accepted_inputs.v1_require(context->key=seal_document->key,'content-mismatch');
  END LOOP;
  PERFORM scanipy_accepted_inputs.v1_require(context->'request_id'=manifest->'request_id'
    AND context->'codebase_id'=manifest->'codebase_id'
    AND context->'accepted_content_digest'=manifest->'accepted_content_digest'
    AND context->>'acceptance_evidence_digest'=encode(binding_digest,'hex')
    AND context->>'requested_policy_digest'=encode(requested_digest,'hex'),'content-mismatch');
  IF run_digest IS NOT NULL THEN
    PERFORM scanipy_accepted_inputs.v1_require(context->>'run_input_digest'=encode(run_digest,'hex'),'content-mismatch');
  END IF;
END $$;

CREATE FUNCTION scanipy_accepted_inputs.v1_denial_reason(policy jsonb,checkpoint jsonb,
  approval jsonb,receipt jsonb,planned jsonb,moment timestamptz) RETURNS text
LANGUAGE plpgsql IMMUTABLE SET search_path=pg_catalog,scanipy_accepted_inputs,pg_temp AS $$
DECLARE grant_row jsonb; pins boolean; published timestamptz;
BEGIN
  -- Missing/malformed identities/pins are command failures, not a lower-priority
  -- denial. Establish all of them before applying the fixed eligibility order.
  grant_row:=scanipy_accepted_inputs.v1_grant(policy,approval);
  pins:=scanipy_accepted_inputs.v1_planned_pins_present(planned);
  published:=(receipt->>'published_at')::timestamptz;
  PERFORM scanipy_accepted_inputs.v1_require(moment IS NOT NULL AND published<=moment,'ledger-mismatch');
  IF moment<(policy->>'valid_from')::timestamptz OR moment>=(policy->>'expires_at')::timestamptz THEN RETURN 'policy-expired'; END IF;
  IF checkpoint->>'action'<>'admit' OR moment<(checkpoint->>'issued_at')::timestamptz
    OR moment>=(checkpoint->>'expires_at')::timestamptz THEN RETURN 'unsupported-authority'; END IF;
  IF grant_row->>'status'='revoked' THEN RETURN 'grant-revoked'; END IF;
  IF moment<(grant_row->>'not_before')::timestamptz OR moment>=(grant_row->>'not_after')::timestamptz THEN RETURN 'grant-expired'; END IF;
  IF grant_row->>'status' NOT IN ('active','retired') OR (grant_row->>'status'='retired' AND
    (published>=(grant_row->>'status_changed_at')::timestamptz OR moment<(grant_row->>'status_changed_at')::timestamptz))
    THEN RETURN 'unsupported-authority'; END IF;
  IF NOT pins THEN RETURN 'missing-runtime-pin'; END IF;
  RETURN NULL;
END $$;

CREATE FUNCTION scanipy_accepted_inputs.v1_fail_denied(namespace jsonb,context jsonb,reason text)
RETURNS void LANGUAGE plpgsql SET search_path=pg_catalog,scanipy_accepted_inputs,pg_temp SET bytea_output='hex' AS $$
DECLARE failure bytea; terminal bytea; digest bytea; result jsonb; org uuid; work uuid; attempt uuid; token bigint; revision bigint; run uuid;
BEGIN
  PERFORM scanipy_accepted_inputs.v1_require(reason IN ('policy-expired','unsupported-authority','grant-revoked','grant-expired','missing-runtime-pin'));
  org:=(namespace->>'org_id')::uuid; work:=(context->>'work_item_id')::uuid; attempt:=(context->>'work_attempt_id')::uuid;
  token:=(context->>'fencing_token')::bigint; revision:=(context->>'work_revision')::bigint; run:=(context->>'detector_run_id')::uuid;
  -- These three fixed-form upper bounds are paid BEFORE constructing either
  -- generated JSON value. Later length/token checks validate this reservation;
  -- generated paths do not pay K again, refund it, or reset the shared meter.
  PERFORM scanipy_accepted_inputs.v1_concat_reserve(65536,64);
  PERFORM scanipy_accepted_inputs.v1_concat_reserve(65536,64);
  PERFORM scanipy_accepted_inputs.v1_concat_reserve(4096,16);
  failure:=scanipy_accepted_inputs.v1_bytes(jsonb_build_object('schema','scanipy-execution/run-failure/1',
    'code',reason,'message','Accepted execution denied.','prefix_sha256',encode(scanipy_accepted_inputs.v1_hash(''::bytea),'hex'),
    'observed_byte_count',NULL,'truncated',true,'observed_full_sha256',NULL));
  terminal:=scanipy_accepted_inputs.v1_bytes(jsonb_build_object('schema','scanipy-execution/attempt-result/1',
    'status','failed','retryable',false,'error',jsonb_build_object('code',reason,'message','Accepted execution denied.'),
    'actual_code_digest',NULL,'actual_env_digest',NULL,'completed_run_ids','[]'::jsonb,'identity',NULL,'identity_policy_reason',NULL));
  PERFORM scanipy_accepted_inputs.v1_require(octet_length(failure)<=65536 AND octet_length(terminal)<=65536
    AND scanipy_accepted_inputs.v1_lexical(failure,65536)<=64
    AND scanipy_accepted_inputs.v1_lexical(terminal,65536)<=64);
  PERFORM scanipy_accepted_inputs.v1_lower_reserve('fail',ARRAY[failure]);
  digest:=scanipy_accepted_inputs.v1_hash(failure,'scanipy-execution/run-failure/1');
  result:=scanipy_execution.fail_detector_run_v1(org,work,attempt,token,revision,run,failure,digest,''::bytea);
  PERFORM scanipy_accepted_inputs.v1_keys(result,ARRAY['run_id','replayed']);
  PERFORM scanipy_accepted_inputs.v1_require(result->>'run_id'=run::text AND result->'replayed'='false'::jsonb,'ledger-mismatch');
  PERFORM scanipy_accepted_inputs.v1_lower_reserve('finish',ARRAY[terminal]);
  digest:=scanipy_accepted_inputs.v1_hash(terminal,'scanipy-execution/attempt-result/1');
  result:=scanipy_execution.finish_capture_detection_v1(org,work,attempt,token,revision,terminal,digest);
  PERFORM scanipy_accepted_inputs.v1_keys(result,ARRAY['attempt_id','attempt_state','work_state','revision','replayed']);
  PERFORM scanipy_accepted_inputs.v1_require(result->>'attempt_id'=attempt::text AND result->>'attempt_state'='failed'
    AND result->>'work_state'='failed' AND result->'replayed'='false'::jsonb
    AND (result->>'revision')::bigint=revision+1,'ledger-mismatch');
END $$;

CREATE FUNCTION scanipy_accepted_inputs.authorize_detector_run_v1(command_bytes bytea,parts bytea[])
RETURNS TABLE(record_bytes bytea,replayed boolean)
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,scanipy_accepted_inputs,pg_temp SET bytea_output='hex' AS $$
DECLARE command jsonb; namespace jsonb; ns uuid; replay record; live record; binding record; bundle record; sealed record;
  fence jsonb; context jsonb; run_input jsonb; run_digest bytea; result jsonb; document jsonb; moment timestamptz;
  reason text; approval jsonb; receipt jsonb; run uuid; lease uuid; first_observed_at timestamptz;
BEGIN
  PERFORM scanipy_accepted_inputs.v1_work_begin(145494016,167772160);
  command:=scanipy_accepted_inputs.v1_command(command_bytes,parts,'authorize-detector');
  ns:=(command->>'namespace_id')::uuid; namespace:=scanipy_accepted_inputs.v1_namespace(ns);
  SELECT * INTO replay FROM scanipy_accepted_inputs.v1_replay(command,command_bytes,parts);
  IF FOUND THEN record_bytes:=replay.record_bytes; replayed:=true; RETURN NEXT; RETURN; END IF;
  PERFORM scanipy_accepted_inputs.v1_fresh_command(command,namespace);
  PERFORM scanipy_accepted_inputs.v1_require(namespace->>'scope'='customer','scope-mismatch');
  fence:=command->'body'->'fence';
  SELECT * INTO live FROM scanipy_accepted_inputs.v1_live(namespace,command->'body'->'admission');
  SELECT * INTO sealed FROM scanipy_accepted_inputs.v1_fetch_seal(namespace,(fence->>'work_item_id')::uuid);
  SELECT * INTO binding FROM scanipy_accepted_inputs.v1_fetch_binding(namespace,(sealed.document->>'request_id')::uuid);
  SELECT * INTO bundle FROM scanipy_accepted_inputs.v1_fetch_bundle(ns,(binding.expected->>'bundle_id')::uuid,
    decode(binding.expected->>'accepted_content_digest','hex'));
  PERFORM scanipy_accepted_inputs.v1_planned_projection(bundle.manifest,binding.planned);
  PERFORM scanipy_accepted_inputs.v1_lower_preflight('begin',parts);
  run_input:=scanipy_accepted_inputs.v1_occurrence(parts[1],'scanipy-execution/run-input/1');
  run_digest:=scanipy_accepted_inputs.v1_hash(parts[1],'scanipy-execution/run-input/1');
  PERFORM scanipy_accepted_inputs.v1_execution_material(namespace,binding.expected,binding.sealed_digest,
    binding.manifest,binding.planned,sealed.document,sealed.seal,run_input);
  PERFORM scanipy_accepted_inputs.v1_relational_reserve(5);
  PERFORM scanipy_accepted_inputs.v1_relational_reserve(2);
  context:=scanipy_execution.lock_accepted_capture_context_v1((namespace->>'org_id')::uuid,
    (fence->>'work_item_id')::uuid,(fence->>'work_attempt_id')::uuid,(fence->>'fencing_token')::bigint,(fence->>'work_revision')::bigint);
  PERFORM scanipy_accepted_inputs.v1_context_check(context,namespace,fence);
  PERFORM scanipy_accepted_inputs.v1_context_material(context,sealed.document,binding.manifest,binding.sealed_digest,binding.requested_policy_digest);
  first_observed_at:=(context->>'db_now')::timestamptz;
  PERFORM scanipy_accepted_inputs.v1_require(first_observed_at>=(binding.manifest->>'resolved_at')::timestamptz
    AND first_observed_at>=(sealed.document->>'authorized_at')::timestamptz,'fence-stale');
  lease:=(context->>'capture_lease_id')::uuid;
  PERFORM scanipy_accepted_inputs.v1_lower_reserve('begin',parts);
  result:=scanipy_execution.begin_detector_run_v1((namespace->>'org_id')::uuid,(fence->>'work_item_id')::uuid,
    (fence->>'work_attempt_id')::uuid,(fence->>'fencing_token')::bigint,(fence->>'work_revision')::bigint,parts[1],run_digest);
  PERFORM scanipy_accepted_inputs.v1_keys(result,ARRAY['run_id','completed','occurrence_ids','replayed']);
  PERFORM scanipy_accepted_inputs.v1_require(result->'completed'='false'::jsonb AND result->'replayed'='false'::jsonb
    AND result->'occurrence_ids'='[]'::jsonb,'ledger-mismatch');
  PERFORM scanipy_accepted_inputs.v1_shape(result->'run_id','"uuid"'); run:=(result->>'run_id')::uuid;
  PERFORM scanipy_accepted_inputs.v1_relational_reserve(2);
  context:=scanipy_execution.lock_accepted_detector_context_v1((namespace->>'org_id')::uuid,
    (fence->>'work_item_id')::uuid,(fence->>'work_attempt_id')::uuid,(fence->>'fencing_token')::bigint,(fence->>'work_revision')::bigint,run,lease);
  PERFORM scanipy_accepted_inputs.v1_context_check(context,namespace,fence);
  PERFORM scanipy_accepted_inputs.v1_context_material(context,sealed.document,binding.manifest,binding.sealed_digest,binding.requested_policy_digest,run_digest);
  PERFORM scanipy_accepted_inputs.v1_require(context->>'run_state'='running','ledger-mismatch');
  moment:=clock_timestamp();
  PERFORM scanipy_accepted_inputs.v1_require((context->>'db_now')::timestamptz>=first_observed_at
    AND moment>=(context->>'db_now')::timestamptz
    AND (binding.manifest->>'resolved_at')::timestamptz<=moment
    AND (sealed.document->>'authorized_at')::timestamptz<=moment
    AND moment<(context->>'lease_expires_at')::timestamptz
    AND moment<(context->>'capture_lease_expires_at')::timestamptz,'fence-stale');
  approval:=scanipy_accepted_inputs.v1_stored_document(binding.frame[2],'scanipy-accepted-approval/1');
  receipt:=scanipy_accepted_inputs.v1_stored_document(binding.frame[5],'scanipy-accepted-publication/1');
  reason:=scanipy_accepted_inputs.v1_denial_reason(live.policy,live.checkpoint,approval,receipt,binding.planned,moment);
  document:=scanipy_accepted_inputs.v1_common_observation(command,namespace,binding.expected,binding.sealed_digest,context)||
    jsonb_build_object('approval_event_id',approval->'event_id','purpose','detector-run','detector_run_id',run,
      'run_input_digest',encode(run_digest,'hex'),'occurrence_id',NULL,'previous_authorization_id',NULL);
  IF reason IS NULL THEN
    document:=document||jsonb_build_object('schema','scanipy-execution-authorization/1','action','initial',
      'authorized_at',to_char(moment AT TIME ZONE 'UTC','YYYY-MM-DD"T"HH24:MI:SS.US"Z"'));
  ELSE
    document:=document||jsonb_build_object('schema','scanipy-execution-denial/1','reason',reason,
      'observed_at',to_char(moment AT TIME ZONE 'UTC','YYYY-MM-DD"T"HH24:MI:SS.US"Z"'));
  END IF;
  record_bytes:=scanipy_accepted_inputs.v1_emit_observation(command,command_bytes,parts,document);
  IF reason IS NOT NULL THEN PERFORM scanipy_accepted_inputs.v1_fail_denied(namespace,context,reason); END IF;
  replayed:=false; RETURN NEXT;
EXCEPTION WHEN unique_violation THEN RAISE EXCEPTION 'ledger-mismatch' USING ERRCODE='P0001';
END $$;

CREATE FUNCTION scanipy_accepted_inputs.v1_previous_context(previous jsonb,context jsonb,
  manifest jsonb,binding_digest bytea) RETURNS void
LANGUAGE plpgsql IMMUTABLE SET search_path=pg_catalog,scanipy_accepted_inputs,pg_temp AS $$
DECLARE key text;
BEGIN
  FOREACH key IN ARRAY ARRAY['org_id','codebase_id','request_id','capture_id','seal_id','work_item_id',
    'work_attempt_id','fencing_token','work_revision','capture_lease_id','requested_policy_digest',
    'attempt_policy_digest','lease_expires_at','capture_lease_expires_at','detector_run_id','run_input_digest'] LOOP
    PERFORM scanipy_accepted_inputs.v1_require(previous->key=context->key,'fence-stale');
  END LOOP;
  PERFORM scanipy_accepted_inputs.v1_require(previous->'bundle_id'=manifest->'bundle_id'
    AND previous->'approval_event_id'=manifest->'approval_event_id'
    AND previous->'accepted_content_digest'=manifest->'accepted_content_digest'
    AND previous->>'request_binding_digest'=encode(binding_digest,'hex')
    AND (manifest->>'resolved_at')::timestamptz<=(previous->>'authorized_at')::timestamptz,'content-mismatch');
END $$;

CREATE FUNCTION scanipy_accepted_inputs.renew_authorized_execution_v1(command_bytes bytea,parts bytea[])
RETURNS TABLE(record_bytes bytea,replayed boolean)
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,scanipy_accepted_inputs,pg_temp SET bytea_output='hex' AS $$
DECLARE command jsonb; namespace jsonb; ns uuid; replay record; live record; binding record; bundle record; sealed record; previous record;
  fence jsonb; renewed_fence jsonb; context jsonb; before_context jsonb; result jsonb; document jsonb; moment timestamptz;
  reason text; approval jsonb; receipt jsonb; run uuid; lease uuid; previous_id uuid; before_moment timestamptz;
BEGIN
  PERFORM scanipy_accepted_inputs.v1_work_begin(63639552,167772160);
  command:=scanipy_accepted_inputs.v1_command(command_bytes,parts,'renew-detector');
  ns:=(command->>'namespace_id')::uuid; namespace:=scanipy_accepted_inputs.v1_namespace(ns);
  SELECT * INTO replay FROM scanipy_accepted_inputs.v1_replay(command,command_bytes,parts);
  IF FOUND THEN record_bytes:=replay.record_bytes; replayed:=true; RETURN NEXT; RETURN; END IF;
  PERFORM scanipy_accepted_inputs.v1_fresh_command(command,namespace);
  PERFORM scanipy_accepted_inputs.v1_require(namespace->>'scope'='customer','scope-mismatch');
  fence:=command->'body'->'fence'; run:=(command->'body'->>'detector_run_id')::uuid;
  previous_id:=(command->'body'->>'previous_authorization_id')::uuid;
  SELECT * INTO live FROM scanipy_accepted_inputs.v1_live(namespace,command->'body'->'admission');
  SELECT * INTO previous FROM scanipy_accepted_inputs.v1_fetch_execution(namespace,(fence->>'work_attempt_id')::uuid,run,previous_id);
  SELECT * INTO sealed FROM scanipy_accepted_inputs.v1_fetch_seal(namespace,(fence->>'work_item_id')::uuid);
  SELECT * INTO binding FROM scanipy_accepted_inputs.v1_fetch_binding(namespace,(sealed.document->>'request_id')::uuid);
  SELECT * INTO bundle FROM scanipy_accepted_inputs.v1_fetch_bundle(ns,(binding.expected->>'bundle_id')::uuid,
    decode(binding.expected->>'accepted_content_digest','hex'));
  PERFORM scanipy_accepted_inputs.v1_planned_projection(bundle.manifest,binding.planned);
  PERFORM scanipy_accepted_inputs.v1_execution_material(namespace,binding.expected,binding.sealed_digest,
    binding.manifest,binding.planned,sealed.document,sealed.seal,previous.run_input);
  lease:=(previous.document->>'capture_lease_id')::uuid;
  PERFORM scanipy_accepted_inputs.v1_relational_reserve(5);
  PERFORM scanipy_accepted_inputs.v1_relational_reserve(2);
  context:=scanipy_execution.lock_accepted_detector_context_v1((namespace->>'org_id')::uuid,
    (fence->>'work_item_id')::uuid,(fence->>'work_attempt_id')::uuid,(fence->>'fencing_token')::bigint,(fence->>'work_revision')::bigint,run,lease);
  PERFORM scanipy_accepted_inputs.v1_context_check(context,namespace,fence);
  PERFORM scanipy_accepted_inputs.v1_context_material(context,sealed.document,binding.manifest,binding.sealed_digest,
    binding.requested_policy_digest,decode(previous.document->>'run_input_digest','hex'));
  PERFORM scanipy_accepted_inputs.v1_previous_context(previous.document,context,binding.manifest,binding.sealed_digest);
  moment:=clock_timestamp();
  PERFORM scanipy_accepted_inputs.v1_require((previous.document->>'authorized_at')::timestamptz<=(context->>'db_now')::timestamptz
    AND (sealed.document->>'authorized_at')::timestamptz<=(context->>'db_now')::timestamptz
    AND (binding.manifest->>'resolved_at')::timestamptz<=moment
    AND moment>=(context->>'db_now')::timestamptz
    AND (previous.document->>'authorized_at')::timestamptz<=moment
    AND moment<(context->>'lease_expires_at')::timestamptz
    AND moment<(context->>'capture_lease_expires_at')::timestamptz,'fence-stale');
  approval:=scanipy_accepted_inputs.v1_stored_document(binding.frame[2],'scanipy-accepted-approval/1');
  receipt:=scanipy_accepted_inputs.v1_stored_document(binding.frame[5],'scanipy-accepted-publication/1');
  reason:=scanipy_accepted_inputs.v1_denial_reason(live.policy,live.checkpoint,approval,receipt,binding.planned,moment);
  IF reason IS NULL THEN
    -- The denial branch never reaches this legacy renewal or extends a lease.
    before_moment:=moment;
    PERFORM scanipy_accepted_inputs.v1_lower_preflight('renew',parts);
    PERFORM scanipy_accepted_inputs.v1_lower_reserve('renew',parts);
    result:=scanipy_execution.renew_capture_detection_v1((namespace->>'org_id')::uuid,
      (fence->>'work_item_id')::uuid,(fence->>'work_attempt_id')::uuid,(fence->>'fencing_token')::bigint,(fence->>'work_revision')::bigint);
    PERFORM scanipy_accepted_inputs.v1_keys(result,ARRAY['attempt_id','revision','lease_expires_at']);
    PERFORM scanipy_accepted_inputs.v1_require(result->'attempt_id'=fence->'work_attempt_id'
      AND (result->>'revision')::bigint=(fence->>'work_revision')::bigint+1,'ledger-mismatch');
    renewed_fence:=fence||jsonb_build_object('work_revision',result->'revision'); before_context:=context;
    PERFORM scanipy_accepted_inputs.v1_relational_reserve(2);
    context:=scanipy_execution.lock_accepted_detector_context_v1((namespace->>'org_id')::uuid,
      (fence->>'work_item_id')::uuid,(fence->>'work_attempt_id')::uuid,(fence->>'fencing_token')::bigint,(result->>'revision')::bigint,run,lease);
    PERFORM scanipy_accepted_inputs.v1_context_check(context,namespace,renewed_fence);
    PERFORM scanipy_accepted_inputs.v1_context_material(context,sealed.document,binding.manifest,binding.sealed_digest,
      binding.requested_policy_digest,decode(previous.document->>'run_input_digest','hex'));
    PERFORM scanipy_accepted_inputs.v1_require((context->>'lease_expires_at')::timestamptz=(result->>'lease_expires_at')::timestamptz
      AND context->'lease_expires_at'=context->'capture_lease_expires_at'
      AND (context->>'lease_expires_at')::timestamptz>(before_context->>'lease_expires_at')::timestamptz
      AND context->'attempt_policy_digest'=before_context->'attempt_policy_digest','content-mismatch');
    moment:=clock_timestamp();
    PERFORM scanipy_accepted_inputs.v1_require((context->>'db_now')::timestamptz>=(before_context->>'db_now')::timestamptz
      AND (context->>'db_now')::timestamptz>=before_moment
      AND moment>=(context->>'db_now')::timestamptz
      AND (binding.manifest->>'resolved_at')::timestamptz<=moment
      AND (sealed.document->>'authorized_at')::timestamptz<=moment
      AND (previous.document->>'authorized_at')::timestamptz<=moment
      AND moment<(context->>'lease_expires_at')::timestamptz
      AND moment<(context->>'capture_lease_expires_at')::timestamptz,'fence-stale');
    PERFORM scanipy_accepted_inputs.v1_policy_time(live.policy,live.checkpoint,moment);
    PERFORM scanipy_accepted_inputs.v1_grant_use(scanipy_accepted_inputs.v1_grant(live.policy,approval),moment,(receipt->>'published_at')::timestamptz);
  END IF;
  document:=scanipy_accepted_inputs.v1_common_observation(command,namespace,binding.expected,binding.sealed_digest,context)||
    jsonb_build_object('approval_event_id',approval->'event_id','purpose','detector-run','detector_run_id',run,
      'run_input_digest',previous.document->'run_input_digest','occurrence_id',NULL,'previous_authorization_id',previous_id);
  IF reason IS NULL THEN
    document:=document||jsonb_build_object('schema','scanipy-execution-authorization/1','action','renew',
      'authorized_at',to_char(moment AT TIME ZONE 'UTC','YYYY-MM-DD"T"HH24:MI:SS.US"Z"'));
  ELSE
    document:=document||jsonb_build_object('schema','scanipy-execution-denial/1','reason',reason,
      'observed_at',to_char(moment AT TIME ZONE 'UTC','YYYY-MM-DD"T"HH24:MI:SS.US"Z"'));
  END IF;
  record_bytes:=scanipy_accepted_inputs.v1_emit_observation(command,command_bytes,parts,document);
  IF reason IS NOT NULL THEN PERFORM scanipy_accepted_inputs.v1_fail_denied(namespace,context,reason); END IF;
  replayed:=false; RETURN NEXT;
EXCEPTION WHEN unique_violation THEN RAISE EXCEPTION 'ledger-mismatch' USING ERRCODE='P0001';
END $$;
