-- Unconditional history protection also applies to the table owner. No no-op
-- UPDATE exception exists for the four immutable history tables.
CREATE FUNCTION scanipy_accepted_inputs.v1_immutable_history() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog,scanipy_accepted_inputs,pg_temp AS $$
BEGIN
  RAISE EXCEPTION 'immutable accepted history' USING ERRCODE='P0001';
END $$;

CREATE FUNCTION scanipy_accepted_inputs.v1_namespace_guard() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog,scanipy_accepted_inputs,pg_temp AS $$
DECLARE document jsonb; policy record; admission record;
BEGIN
  IF TG_OP='INSERT' THEN
    document:=scanipy_accepted_inputs.v1_document(NEW.installation_bytes,'scanipy-registry-installed-trust/1');
    PERFORM scanipy_accepted_inputs.v1_require((document->>'registry_id')::uuid=NEW.registry_id
      AND document->>'scope'=NEW.scope AND (document->>'org_id')::uuid IS NOT DISTINCT FROM NEW.org_id,
      'scope-mismatch');
    NEW.installation_sha256:=scanipy_accepted_inputs.v1_hash(NEW.installation_bytes);
    NEW.deployment_id:=(document->>'deployment_id')::uuid;
    NEW.administrator_actor_id:=(document->>'administrator_actor_id')::uuid;
    NEW.root_spki_sha256:=decode(document->>'root_spki_sha256','hex');
    PERFORM scanipy_accepted_inputs.v1_require(NEW.policy_event_id IS NULL AND NEW.policy_digest IS NULL
      AND NEW.policy_revision=0 AND NEW.admission_event_id IS NULL AND NEW.checkpoint_digest IS NULL
      AND NEW.checkpoint_generation=0 AND NEW.admission_epoch IS NULL AND NEW.coordination_revision=0);
    RETURN NEW;
  END IF;
  PERFORM scanipy_accepted_inputs.v1_require(NEW.id=OLD.id AND NEW.registry_id=OLD.registry_id
    AND NEW.scope=OLD.scope AND NEW.org_id IS NOT DISTINCT FROM OLD.org_id
    AND NEW.installation_bytes=OLD.installation_bytes AND NEW.installation_sha256=OLD.installation_sha256
    AND NEW.deployment_id=OLD.deployment_id AND NEW.administrator_actor_id=OLD.administrator_actor_id
    AND NEW.root_spki_sha256=OLD.root_spki_sha256
    AND NEW.created_at=OLD.created_at,'ledger-mismatch');
  PERFORM scanipy_accepted_inputs.v1_require(OLD.coordination_revision<9223372036854775807
    AND NEW.coordination_revision=OLD.coordination_revision+1 AND NEW.updated_at>=OLD.updated_at,'ledger-mismatch');
  -- Exactly one head changes in one operation, never a combined rebase/reset.
  IF NEW.policy_event_id IS DISTINCT FROM OLD.policy_event_id THEN
    PERFORM scanipy_accepted_inputs.v1_require(NEW.admission_event_id IS NOT DISTINCT FROM OLD.admission_event_id
      AND NEW.checkpoint_digest IS NOT DISTINCT FROM OLD.checkpoint_digest
      AND NEW.checkpoint_generation=OLD.checkpoint_generation
      AND NEW.admission_epoch IS NOT DISTINCT FROM OLD.admission_epoch
      AND OLD.policy_revision<9223372036854775807 AND NEW.policy_revision=OLD.policy_revision+1,'ledger-mismatch');
    SELECT record_digest,policy_revision,previous_event_digest INTO policy
      FROM scanipy_accepted_inputs.authority_events
      WHERE namespace_id=NEW.id AND kind='policy' AND id=NEW.policy_event_id;
    PERFORM scanipy_accepted_inputs.v1_require(FOUND AND policy.record_digest=NEW.policy_digest
      AND policy.policy_revision=NEW.policy_revision
      AND policy.previous_event_digest IS NOT DISTINCT FROM OLD.policy_digest,'ledger-mismatch');
  ELSE
    PERFORM scanipy_accepted_inputs.v1_require(NEW.policy_digest IS NOT DISTINCT FROM OLD.policy_digest
      AND NEW.policy_revision=OLD.policy_revision AND NEW.admission_event_id IS DISTINCT FROM OLD.admission_event_id
      AND OLD.checkpoint_generation<9223372036854775807
      AND NEW.checkpoint_generation=OLD.checkpoint_generation+1,'ledger-mismatch');
    SELECT record_digest,checkpoint_generation,admission_epoch,previous_event_digest INTO admission
      FROM scanipy_accepted_inputs.authority_events
      WHERE namespace_id=NEW.id AND kind='admission' AND id=NEW.admission_event_id;
    PERFORM scanipy_accepted_inputs.v1_require(FOUND AND admission.record_digest=NEW.checkpoint_digest
      AND admission.checkpoint_generation=NEW.checkpoint_generation AND admission.admission_epoch=NEW.admission_epoch
      AND admission.previous_event_digest IS NOT DISTINCT FROM OLD.checkpoint_digest,'ledger-mismatch');
  END IF;
  RETURN NEW;
END $$;

CREATE FUNCTION scanipy_accepted_inputs.v1_event_projection(v jsonb) RETURNS jsonb
LANGUAGE plpgsql IMMUTABLE SET search_path=pg_catalog,scanipy_accepted_inputs,pg_temp AS $$
DECLARE result jsonb; name text;
BEGIN
  result:='{}';
  FOREACH name IN ARRAY ARRAY['registry_id','scope','org_id','bundle_id','accepted_content_digest',
    'approval_event_id','publication_key','policy_event_id','policy_digest','policy_revision',
    'admission_event_id','checkpoint_digest','checkpoint_generation','admission_epoch',
    'codebase_id','request_id','request_binding_digest','work_item_id','work_attempt_id',
    'fencing_token','work_revision','capture_id','seal_id','capture_lease_id','requested_policy_digest',
    'attempt_policy_digest','lease_expires_at','capture_lease_expires_at','detector_run_id',
    'run_input_digest','occurrence_id','previous_authorization_id','purpose','resolver_artifact_digest',
    'authorized_at','observed_at'] LOOP
    result:=result||jsonb_build_object(name,coalesce(v->name,'null'));
  END LOOP;
  result:=result||jsonb_build_object('execution_action',CASE WHEN v->>'schema'='scanipy-execution-authorization/1' THEN v->'action' ELSE 'null'::jsonb END,
    'denial_reason',CASE WHEN v->>'schema'='scanipy-execution-denial/1' THEN v->'reason' ELSE 'null'::jsonb END,
    'previous_event_digest',CASE v->>'schema' WHEN 'scanipy-accepted-trust-policy/1' THEN v->'previous_policy_digest'
      WHEN 'scanipy-registry-admission/1' THEN v->'previous_checkpoint_digest' ELSE 'null'::jsonb END);
  IF v->>'schema'='scanipy-accepted-trust-policy/1' THEN
    result:=result||jsonb_build_object('policy_revision',v->'revision');
  ELSIF v->>'schema'='scanipy-registry-admission/1' THEN
    result:=result||jsonb_build_object('checkpoint_generation',v->'generation');
  END IF;
  RETURN result;
END $$;

CREATE FUNCTION scanipy_accepted_inputs.v1_event_guard() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog,scanipy_accepted_inputs,pg_temp AS $$
DECLARE document jsonb; expected jsonb; actual jsonb; namespace record; receipt jsonb;
  frame bytea[]; policy jsonb; admission jsonb; selected record;
BEGIN
  SELECT registry_id,scope,org_id INTO namespace FROM scanipy_accepted_inputs.registry_namespaces
    WHERE id=NEW.namespace_id FOR UPDATE;
  PERFORM scanipy_accepted_inputs.v1_require(FOUND AND NEW.registry_id=namespace.registry_id
    AND NEW.scope=namespace.scope AND NEW.org_id IS NOT DISTINCT FROM namespace.org_id,'scope-mismatch');
  document:=scanipy_accepted_inputs.v1_document(NEW.record_bytes,NEW.record_schema);
  PERFORM scanipy_accepted_inputs.v1_require((document->>'event_id')::uuid=NEW.id
    AND scanipy_accepted_inputs.v1_hash(NEW.record_bytes,NEW.record_schema)=NEW.record_digest,'content-mismatch');
  expected:=scanipy_accepted_inputs.v1_event_projection(document);
  -- These three contextual columns do not invent new wire fields: admission
  -- identifies its actual policy row, while publication retains the exact
  -- policy/checkpoint rows present in its original owning frame and receipt.
  IF NEW.kind='admission' THEN
    SELECT record_digest,policy_revision INTO selected FROM scanipy_accepted_inputs.authority_events
      WHERE namespace_id=NEW.namespace_id AND kind='policy' AND id=NEW.policy_event_id;
    PERFORM scanipy_accepted_inputs.v1_require(FOUND AND selected.record_digest=NEW.policy_digest
      AND selected.policy_revision=NEW.policy_revision,'ledger-mismatch');
    expected:=expected||jsonb_build_object('policy_event_id',NEW.policy_event_id);
  ELSIF NEW.kind='approval' THEN
    frame:=scanipy_accepted_inputs.v1_frame(NEW.publication_input_bytes,'scanipy-publication-input/1');
    PERFORM scanipy_accepted_inputs.v1_require(frame[2]=NEW.record_bytes,'content-mismatch');
    receipt:=scanipy_accepted_inputs.v1_document(NEW.publication_receipt_bytes,'scanipy-accepted-publication/1');
    policy:=scanipy_accepted_inputs.v1_document(frame[5],'scanipy-accepted-trust-policy/1');
    admission:=scanipy_accepted_inputs.v1_document(frame[10],'scanipy-registry-admission/1');
    PERFORM scanipy_accepted_inputs.v1_require(receipt->'registry_id'=document->'registry_id'
      AND receipt->'scope'=document->'scope' AND receipt->'org_id'=document->'org_id'
      AND receipt->'bundle_id'=document->'bundle_id' AND receipt->'accepted_content_digest'=document->'accepted_content_digest'
      AND receipt->'policy_revision'=policy->'revision' AND admission->'policy_digest'=receipt->'policy_digest'
      AND admission->'policy_revision'=receipt->'policy_revision'
      AND receipt->'checkpoint_generation'=admission->'generation' AND receipt->'admission_epoch'=admission->'admission_epoch'
      AND receipt->>'policy_digest'=encode(scanipy_accepted_inputs.v1_hash(frame[5],'scanipy-accepted-trust-policy/1'),'hex')
      AND receipt->>'checkpoint_digest'=encode(scanipy_accepted_inputs.v1_hash(frame[10],'scanipy-registry-admission/1'),'hex'),
      'content-mismatch');
    PERFORM scanipy_accepted_inputs.v1_require(scanipy_accepted_inputs.v1_hash(NEW.publication_receipt_bytes,
      'scanipy-accepted-publication/1')=NEW.publication_receipt_digest,'content-mismatch');
    PERFORM scanipy_accepted_inputs.v1_require(receipt->>'approval_event_id'=document->>'event_id'
      AND receipt->>'publication_key'=document->>'publication_key'
      AND receipt->>'approval_statement_digest'=encode(NEW.record_digest,'hex')
      AND receipt->>'approval_signature_sha256'=encode(scanipy_accepted_inputs.v1_hash(frame[3]),'hex')
      AND receipt->>'evidence_inventory_digest'=document->>'evidence_inventory_digest'
      AND receipt->>'publisher_actor_id'=document->>'issuer_actor_id','ledger-mismatch');
    expected:=expected||jsonb_build_object('policy_event_id',policy->'event_id',
      'policy_digest',receipt->'policy_digest','policy_revision',receipt->'policy_revision',
      'admission_event_id',admission->'event_id','checkpoint_digest',receipt->'checkpoint_digest',
      'checkpoint_generation',receipt->'checkpoint_generation','admission_epoch',receipt->'admission_epoch');
  END IF;
  -- Never to_jsonb(NEW): that would duplicate every raw command/part payload.
  actual:=jsonb_build_object('registry_id',NEW.registry_id,'scope',NEW.scope,'org_id',NEW.org_id,
    'bundle_id',NEW.bundle_id,'accepted_content_digest',encode(NEW.accepted_content_digest,'hex'),
    'approval_event_id',NEW.approval_event_id,'publication_key',NEW.publication_key,
    'policy_event_id',NEW.policy_event_id,'policy_digest',encode(NEW.policy_digest,'hex'),'policy_revision',NEW.policy_revision,
    'admission_event_id',NEW.admission_event_id,'checkpoint_digest',encode(NEW.checkpoint_digest,'hex'),
    'checkpoint_generation',NEW.checkpoint_generation,'admission_epoch',NEW.admission_epoch,
    'codebase_id',NEW.codebase_id,'request_id',NEW.request_id,'request_binding_digest',encode(NEW.request_binding_digest,'hex'),
    'work_item_id',NEW.work_item_id,'work_attempt_id',NEW.work_attempt_id,'fencing_token',NEW.fencing_token,
    'work_revision',NEW.work_revision,'capture_id',NEW.capture_id,'seal_id',NEW.seal_id,'capture_lease_id',NEW.capture_lease_id,
    'requested_policy_digest',encode(NEW.requested_policy_digest,'hex'),'attempt_policy_digest',encode(NEW.attempt_policy_digest,'hex'),
    'lease_expires_at',to_char(NEW.lease_expires_at AT TIME ZONE 'UTC','YYYY-MM-DD"T"HH24:MI:SS.US"Z"'),
    'capture_lease_expires_at',to_char(NEW.capture_lease_expires_at AT TIME ZONE 'UTC','YYYY-MM-DD"T"HH24:MI:SS.US"Z"'),
    'detector_run_id',NEW.detector_run_id,'run_input_digest',encode(NEW.run_input_digest,'hex'),
    'occurrence_id',NEW.occurrence_id,'previous_authorization_id',NEW.previous_authorization_id,
    'purpose',NEW.purpose,'resolver_artifact_digest',encode(NEW.resolver_artifact_digest,'hex'),
    'authorized_at',to_char(NEW.authorized_at AT TIME ZONE 'UTC','YYYY-MM-DD"T"HH24:MI:SS.US"Z"'),
    'observed_at',to_char(NEW.observed_at AT TIME ZONE 'UTC','YYYY-MM-DD"T"HH24:MI:SS.US"Z"'),
    'execution_action',NEW.execution_action,'denial_reason',NEW.denial_reason,
    'previous_event_digest',encode(NEW.previous_event_digest,'hex'));
  PERFORM scanipy_accepted_inputs.v1_require(actual=expected,'content-mismatch');
  IF document ? 'operation_key' THEN
    PERFORM scanipy_accepted_inputs.v1_require((document->>'operation_key')::uuid=NEW.operation_key,'ledger-mismatch');
  END IF;
  PERFORM scanipy_accepted_inputs.v1_require(scanipy_accepted_inputs.v1_hash(NEW.command_bytes,
    'scanipy-accepted-ledger-command/1')=NEW.command_digest,'content-mismatch');
  RETURN NEW;
END $$;

CREATE FUNCTION scanipy_accepted_inputs.v1_artifact_guard() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog,scanipy_accepted_inputs,pg_temp AS $$
BEGIN
  PERFORM scanipy_accepted_inputs.v1_shape(to_jsonb(NEW.artifact_id),'"id"'::jsonb);
  PERFORM scanipy_accepted_inputs.v1_shape(to_jsonb(NEW.version),'"version"'::jsonb);
  PERFORM scanipy_accepted_inputs.v1_require(NEW.raw_length=octet_length(NEW.raw_bytes)
    AND scanipy_accepted_inputs.v1_hash(NEW.raw_bytes)=NEW.raw_sha256,'content-mismatch');
  RETURN NEW;
END $$;

CREATE FUNCTION scanipy_accepted_inputs.v1_binding_guard() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog,scanipy_accepted_inputs,pg_temp AS $$
DECLARE parts bytea[]; manifest jsonb; current_policy jsonb; checkpoint jsonb;
BEGIN
  parts:=scanipy_accepted_inputs.v1_frame(NEW.sealed_bytes,'scanipy-sealed-acceptance/1');
  manifest:=scanipy_accepted_inputs.v1_document(parts[1],'scanipy-sealed-acceptance/1');
  current_policy:=scanipy_accepted_inputs.v1_document(parts[10],'scanipy-accepted-trust-policy/1');
  checkpoint:=scanipy_accepted_inputs.v1_document(parts[15],'scanipy-registry-admission/1');
  PERFORM scanipy_accepted_inputs.v1_require(manifest->>'registry_id'=NEW.registry_id::text
    AND manifest->>'org_id'=NEW.org_id::text AND manifest->>'codebase_id'=NEW.codebase_id::text
    AND manifest->>'request_id'=NEW.request_id::text AND manifest->>'bundle_id'=NEW.bundle_id::text
    AND manifest->>'approval_event_id'=NEW.approval_event_id::text
    AND manifest->>'accepted_content_digest'=encode(NEW.accepted_content_digest,'hex')
    AND (manifest->>'resolved_at')::timestamptz=NEW.resolved_at
    AND current_policy->>'event_id'=NEW.policy_event_id::text
    AND checkpoint->>'event_id'=NEW.admission_event_id::text,'content-mismatch');
  PERFORM scanipy_accepted_inputs.v1_require(scanipy_accepted_inputs.v1_hash(NEW.sealed_bytes)=NEW.sealed_sha256
    AND scanipy_accepted_inputs.v1_hash(NEW.command_bytes,'scanipy-accepted-ledger-command/1')=NEW.command_digest,
    'content-mismatch');
  RETURN NEW;
END $$;

CREATE TRIGGER accepted_namespace_insert_or_update BEFORE INSERT OR UPDATE
  ON scanipy_accepted_inputs.registry_namespaces FOR EACH ROW
  EXECUTE FUNCTION scanipy_accepted_inputs.v1_namespace_guard();
CREATE TRIGGER accepted_namespace_no_delete BEFORE DELETE
  ON scanipy_accepted_inputs.registry_namespaces FOR EACH ROW
  EXECUTE FUNCTION scanipy_accepted_inputs.v1_immutable_history();
CREATE TRIGGER accepted_namespace_no_truncate BEFORE TRUNCATE
  ON scanipy_accepted_inputs.registry_namespaces FOR EACH STATEMENT
  EXECUTE FUNCTION scanipy_accepted_inputs.v1_immutable_history();
CREATE TRIGGER accepted_artifact_insert BEFORE INSERT ON scanipy_accepted_inputs.artifact_versions
  FOR EACH ROW EXECUTE FUNCTION scanipy_accepted_inputs.v1_artifact_guard();
CREATE TRIGGER accepted_event_insert BEFORE INSERT ON scanipy_accepted_inputs.authority_events
  FOR EACH ROW EXECUTE FUNCTION scanipy_accepted_inputs.v1_event_guard();
CREATE TRIGGER accepted_binding_insert BEFORE INSERT ON scanipy_accepted_inputs.request_bundle_bindings
  FOR EACH ROW EXECUTE FUNCTION scanipy_accepted_inputs.v1_binding_guard();

DO $$ DECLARE table_name text;
BEGIN
  FOREACH table_name IN ARRAY ARRAY['artifact_versions','bundle_versions','authority_events','request_bundle_bindings'] LOOP
    EXECUTE format('CREATE TRIGGER accepted_history_no_change BEFORE UPDATE OR DELETE ON scanipy_accepted_inputs.%I '
      'FOR EACH ROW EXECUTE FUNCTION scanipy_accepted_inputs.v1_immutable_history()',table_name);
    EXECUTE format('CREATE TRIGGER accepted_history_no_truncate BEFORE TRUNCATE ON scanipy_accepted_inputs.%I '
      'FOR EACH STATEMENT EXECUTE FUNCTION scanipy_accepted_inputs.v1_immutable_history()',table_name);
  END LOOP;
END $$;
