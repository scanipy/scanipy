-- All v1_* helpers are private. Narrow *_v1 wrappers are granted in migration B.
CREATE FUNCTION scanipy_execution.v1_insert_work(
  p_org uuid,p_codebase uuid,p_request uuid,p_kind text,p_occurrence uuid,p_capture uuid,
  retry jsonb,policy jsonb) RETURNS uuid
LANGUAGE plpgsql SET search_path=pg_catalog,scanipy_execution,pg_temp AS $$
DECLARE payload bytea; result uuid;
BEGIN
  payload:=scanipy_execution.v1_bytes(jsonb_build_object('schema','scanipy-execution/work-payload/1',
    'request_id',p_request,'kind',p_kind,'occurrence_id',p_occurrence,'policy',policy));
  PERFORM scanipy_execution.v1_envelope('work-payload',payload,scanipy_execution.v1_digest('work-payload',payload));
  INSERT INTO scanipy_execution.work_items(org_id,codebase_id,request_id,kind,occurrence_id,capture_id,
    idempotency_key,payload_schema,payload_bytes,payload_digest,retry_policy_bytes,
    max_attempts,lease_seconds,initial_backoff_seconds,max_backoff_seconds)
  VALUES(p_org,p_codebase,p_request,p_kind,p_occurrence,p_capture,p_kind||':'||coalesce(p_occurrence,p_request)::text,
    'scanipy-execution/work-payload/1',payload,scanipy_execution.v1_digest('work-payload',payload),
    scanipy_execution.v1_bytes(retry),(retry->>'max_attempts')::int,(retry->>'lease_seconds')::int,
    (retry->>'initial_backoff_seconds')::int,(retry->>'max_backoff_seconds')::int) RETURNING id INTO result;
  RETURN result;
END $$;

CREATE FUNCTION scanipy_execution.cancel_request_v1(p_org uuid,p_request uuid,p_revision bigint,data bytea,digest bytea)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,scanipy_execution,pg_temp AS $$
DECLARE v jsonb; r scanipy_execution.scan_requests%ROWTYPE; moment timestamptz; a record;
BEGIN
  PERFORM scanipy_execution.v1_org(p_org); v:=scanipy_execution.v1_envelope('cancellation',data,digest);
  PERFORM scanipy_execution.v1_require((v->>'request_id')::uuid=p_request,'cancellation scope mismatch');
  SELECT * INTO r FROM scanipy_execution.scan_requests WHERE org_id=p_org AND id=p_request FOR UPDATE;
  PERFORM scanipy_execution.v1_require(r.id IS NOT NULL,'request not found');
  IF r.cancellation_bytes IS NOT NULL THEN
    PERFORM scanipy_execution.v1_require(r.cancellation_bytes=data,'cancellation replay conflict');
    RETURN jsonb_build_object('request_id',r.id,'revision',r.revision,'replayed',true);
  END IF;
  PERFORM scanipy_execution.v1_require(r.revision=p_revision,'request revision conflict');
  PERFORM id FROM scanipy_execution.source_captures WHERE owner_request_id=p_request FOR UPDATE;
  -- Lock every item before any attempt, and every attempt before any run.
  PERFORM id FROM scanipy_execution.work_items WHERE request_id=p_request ORDER BY id FOR UPDATE;
  PERFORM id FROM scanipy_execution.work_attempts WHERE request_id=p_request ORDER BY id FOR UPDATE;
  PERFORM id FROM scanipy_execution.detector_runs WHERE request_id=p_request ORDER BY id FOR UPDATE;
  moment:=pg_catalog.clock_timestamp();
  FOR a IN SELECT id,fencing_token FROM scanipy_execution.work_attempts WHERE request_id=p_request AND state='running' LOOP
    PERFORM scanipy_execution.v1_release_all(a.id,a.fencing_token,'request-cancelled',moment);
  END LOOP;
  UPDATE scanipy_execution.detector_runs SET state='interrupted',terminal_at=moment,result_schema=v->>'schema',result_bytes=data,result_digest=digest
    WHERE request_id=p_request AND state IN ('pending','running');
  UPDATE scanipy_execution.work_attempts SET state='cancelled',terminal_at=moment,result_schema=v->>'schema',result_bytes=data,result_digest=digest
    WHERE request_id=p_request AND state='running';
  UPDATE scanipy_execution.work_items SET state='cancelled',active_attempt_id=NULL,revision=revision+1,terminal_bytes=data,terminal_digest=digest
    WHERE request_id=p_request AND state IN ('pending','running');
  UPDATE scanipy_execution.scan_requests SET revision=revision+1,cancellation_bytes=data WHERE id=p_request;
  PERFORM scanipy_execution.v1_stages(p_request);
  SELECT * INTO STRICT r FROM scanipy_execution.scan_requests WHERE id=p_request;
  RETURN jsonb_build_object('request_id',r.id,'revision',r.revision,'replayed',false);
END $$;

CREATE FUNCTION scanipy_execution.claim_retirement_v1(p_org uuid,p_capture uuid,p_revision bigint)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,scanipy_execution,pg_temp AS $$
DECLARE c scanipy_execution.source_captures%ROWTYPE; moment timestamptz;
BEGIN
  PERFORM scanipy_execution.v1_org(p_org);
  SELECT * INTO c FROM scanipy_execution.source_captures WHERE org_id=p_org AND id=p_capture;
  PERFORM scanipy_execution.v1_require(c.id IS NOT NULL,'capture not found');
  PERFORM id FROM scanipy_execution.scan_requests WHERE id=c.owner_request_id FOR UPDATE;
  SELECT * INTO STRICT c FROM scanipy_execution.source_captures WHERE org_id=p_org AND id=p_capture FOR UPDATE;
  moment:=pg_catalog.clock_timestamp();
  PERFORM scanipy_execution.v1_require(c.revision=p_revision AND c.retention_state<>'retired','capture revision/state conflict');
  IF c.retention_state='active' THEN
    PERFORM scanipy_execution.v1_require(c.retain_until<=moment,'capture retention has not elapsed');
    PERFORM scanipy_execution.v1_require(NOT EXISTS(SELECT 1 FROM scanipy_execution.capture_leases WHERE capture_id=p_capture AND released_at IS NULL AND expires_at>moment),'capture has live consumer');
    PERFORM scanipy_execution.v1_require(NOT EXISTS(SELECT 1 FROM scanipy_execution.work_items WHERE request_id=c.owner_request_id AND state IN ('pending','running')),'capture has nonterminal work');
  ELSE
    PERFORM scanipy_execution.v1_require(c.cleanup_expires_at<=moment,'cleanup claim is still live');
  END IF;
  UPDATE scanipy_execution.source_captures SET retention_state='retiring',cleanup_token=cleanup_token+1,
    cleanup_expires_at=moment+interval '300 seconds',revision=revision+1 WHERE id=p_capture RETURNING * INTO c;
  RETURN jsonb_build_object('capture_id',c.id,'storage_object_id',c.storage_object_id,'storage_reference',c.storage_reference,
    'fencing_token',c.cleanup_token,'revision',c.revision,'lease_expires_at',c.cleanup_expires_at);
END $$;

CREATE FUNCTION scanipy_execution.finish_retirement_v1(p_org uuid,p_capture uuid,p_revision bigint,data bytea,digest bytea)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,scanipy_execution,pg_temp AS $$
DECLARE c scanipy_execution.source_captures%ROWTYPE; v jsonb; moment timestamptz;
BEGIN
  PERFORM scanipy_execution.v1_org(p_org); v:=scanipy_execution.v1_envelope('retirement',data,digest);
  SELECT * INTO c FROM scanipy_execution.source_captures WHERE org_id=p_org AND id=p_capture;
  PERFORM scanipy_execution.v1_require(c.id IS NOT NULL,'capture not found');
  PERFORM id FROM scanipy_execution.scan_requests WHERE id=c.owner_request_id FOR UPDATE;
  SELECT * INTO STRICT c FROM scanipy_execution.source_captures WHERE org_id=p_org AND id=p_capture FOR UPDATE;
  PERFORM scanipy_execution.v1_require((v->>'capture_id')::uuid=c.id AND (v->>'storage_object_id')::uuid=c.storage_object_id,'retirement object mismatch');
  IF c.retention_state='retired' THEN
    PERFORM scanipy_execution.v1_require(c.retirement_bytes=data AND c.retirement_digest=digest,'retirement replay conflict');
    RETURN jsonb_build_object('capture_id',c.id,'revision',c.revision,'replayed',true);
  END IF;
  moment:=pg_catalog.clock_timestamp();
  PERFORM scanipy_execution.v1_require(c.retention_state='retiring' AND c.revision=p_revision AND c.cleanup_token=(v->>'token')::bigint
    AND c.cleanup_expires_at>moment,'stale cleanup claim');
  UPDATE scanipy_execution.source_captures SET retention_state='retired',cleanup_expires_at=NULL,retirement_bytes=data,retirement_digest=digest,revision=revision+1
    WHERE id=p_capture RETURNING * INTO c;
  RETURN jsonb_build_object('capture_id',c.id,'revision',c.revision,'replayed',false);
END $$;

CREATE FUNCTION scanipy_execution.v1_release_all(p_attempt uuid,p_token bigint,reason text,moment timestamptz) RETURNS void
LANGUAGE plpgsql SET search_path=pg_catalog,scanipy_execution,pg_temp AS $$
DECLARE data bytea;
BEGIN
  data:=scanipy_execution.v1_bytes(jsonb_build_object('schema','scanipy-execution/lease-release/1','attempt_id',p_attempt,'token',p_token,'reason',reason));
  UPDATE scanipy_execution.capture_leases SET released_at=moment,release_bytes=data,
    release_digest=scanipy_execution.v1_digest('lease-release',data) WHERE work_attempt_id=p_attempt AND released_at IS NULL;
END $$;

CREATE FUNCTION scanipy_execution.v1_stages(p_request uuid) RETURNS void
LANGUAGE plpgsql SET search_path=pg_catalog,scanipy_execution,pg_temp AS $$
DECLARE detect text; captured text; ident text; total bigint; remaining bigint;
  failed bigint; cancelled bigint; running bigint; unsuperseded boolean;
BEGIN
  SELECT state INTO detect FROM scanipy_execution.work_items WHERE request_id=p_request AND kind='capture_detection';
  captured:=CASE WHEN EXISTS(SELECT 1 FROM scanipy_execution.scan_seals WHERE request_id=p_request)
    THEN 'completed' ELSE detect END;
  -- Only an explicit chain ending in a completed replacement can supersede a
  -- zero-occurrence failure. Starting another run does not erase that failure.
  WITH RECURSIVE covered(id,supersedes_run_id) AS (
    SELECT id,supersedes_run_id FROM scanipy_execution.detector_runs WHERE request_id=p_request AND state='completed'
    UNION
    SELECT d.id,d.supersedes_run_id FROM scanipy_execution.detector_runs d JOIN covered c ON c.supersedes_run_id=d.id
      WHERE d.request_id=p_request AND d.result_count=0
  ) SELECT EXISTS(SELECT 1 FROM scanipy_execution.detector_runs d WHERE d.request_id=p_request
    AND d.state IN ('failed','interrupted')
    AND d.result_schema IS DISTINCT FROM 'scanipy-execution/cancellation/1'
    AND NOT EXISTS(SELECT 1 FROM covered c WHERE c.id=d.id)) INTO unsuperseded;
  IF unsuperseded THEN detect:='failed'; END IF;
  SELECT count(*),count(*) FILTER(WHERE state='pending'),count(*) FILTER(WHERE state='failed'),
    count(*) FILTER(WHERE state='cancelled'),count(*) FILTER(WHERE state='running')
    INTO total,remaining,failed,cancelled,running FROM scanipy_execution.work_items WHERE request_id=p_request AND kind='identity';
  ident:=CASE WHEN failed>0 THEN 'failed' WHEN cancelled>0 THEN 'cancelled'
    WHEN running>0 THEN 'running' WHEN remaining>0 THEN 'pending'
    WHEN total>0 OR detect='completed' THEN 'completed'
    WHEN EXISTS(SELECT 1 FROM scanipy_execution.scan_requests WHERE id=p_request AND cancellation_bytes IS NOT NULL)
      THEN 'cancelled' ELSE 'pending' END;
  UPDATE scanipy_execution.scan_requests SET revision=revision+1,detection_state=detect,identity_state=ident,
    capture_state=captured WHERE id=p_request;
END $$;

CREATE FUNCTION scanipy_execution.v1_finish(p_org uuid,p_kind text,p_work uuid,p_attempt uuid,p_token bigint,p_revision bigint,data bytea,digest bytea,p_expire boolean)
RETURNS jsonb LANGUAGE plpgsql SET search_path=pg_catalog,scanipy_execution,pg_temp AS $$
DECLARE v jsonb; s jsonb; a scanipy_execution.work_attempts%ROWTYPE; w scanipy_execution.work_items%ROWTYPE;
  sealed scanipy_execution.scan_seals%ROWTYPE; expected jsonb; actual jsonb; policy jsonb; runner jsonb;
  moment timestamptz; retry_allowed boolean; partial_retained boolean; new_state text; delay integer;
BEGIN
  v:=scanipy_execution.v1_envelope('attempt-result',data,digest);
  s:=scanipy_execution.v1_lock(p_org,p_work,p_kind,p_attempt,p_token,p_revision,false);
  SELECT * INTO STRICT a FROM scanipy_execution.work_attempts WHERE id=p_attempt;
  SELECT * INTO STRICT w FROM scanipy_execution.work_items WHERE id=p_work;
  IF a.state<>'running' THEN
    PERFORM scanipy_execution.v1_require(a.result_bytes=data AND a.result_digest=digest AND
      a.state=CASE WHEN p_expire THEN 'interrupted' ELSE v->>'status' END,'terminal attempt replay conflict');
    RETURN jsonb_build_object('attempt_id',a.id,'attempt_state',a.state,'work_state',w.state,'revision',w.revision,'replayed',true);
  END IF;
  IF p_expire THEN
    moment:=(s->>'now')::timestamptz;
    PERFORM scanipy_execution.v1_require(w.state='running' AND w.active_attempt_id=a.id AND w.fencing_token=p_token AND w.revision=p_revision
      AND a.lease_expires_at<=moment AND v->>'status'='failed','attempt is not expired/current');
  ELSE
    s:=scanipy_execution.v1_lock(p_org,p_work,p_kind,p_attempt,p_token,p_revision,true);
    moment:=(s->>'now')::timestamptz;
  END IF;
  IF p_kind='capture_detection' THEN
    PERFORM scanipy_execution.v1_require(v->'identity'='null'::jsonb,'detection attempt cannot claim identity result');
  ELSE
    PERFORM scanipy_execution.v1_require(jsonb_array_length(v->'completed_run_ids')=0,'identity cannot complete detector runs');
  END IF;
  IF v->>'status'='completed' THEN
    PERFORM scanipy_execution.v1_require(v->>'actual_code_digest' IS NOT NULL AND v->>'actual_env_digest' IS NOT NULL,'completion requires actual execution evidence');
    SELECT (convert_from(planned_policy_bytes,'UTF8')::jsonb)->(p_kind||'_runner') INTO runner
      FROM scanipy_execution.scan_requests WHERE id=w.request_id;
    PERFORM scanipy_execution.v1_require(v->>'actual_code_digest'=runner->>'expected_code_digest'
      AND v->>'actual_env_digest'=runner->>'expected_image_digest','missing or mismatched actual runner artifact pins');
    IF p_kind='capture_detection' THEN
      PERFORM scanipy_execution.v1_require(v->'identity'='null'::jsonb,'detection completion cannot claim identity result');
      SELECT * INTO sealed FROM scanipy_execution.scan_seals WHERE request_id=w.request_id;
      PERFORM scanipy_execution.v1_require(sealed.id IS NOT NULL,'detection completion requires seal');
      SELECT coalesce(jsonb_agg(value->'key' ORDER BY value->>'key' COLLATE "C"),'[]'::jsonb) INTO expected
        FROM jsonb_array_elements(convert_from(sealed.seal_bytes,'UTF8')::jsonb->'bindings');
      SELECT coalesce(jsonb_agg(detector_binding_key ORDER BY detector_binding_key COLLATE "C"),'[]'::jsonb) INTO actual
        FROM scanipy_execution.detector_runs WHERE request_id=w.request_id AND state='completed';
      PERFORM scanipy_execution.v1_require(actual=expected,'planned detector inventory incomplete');
      SELECT coalesce(jsonb_agg(id),'[]'::jsonb) INTO actual FROM scanipy_execution.detector_runs WHERE request_id=w.request_id AND state='completed';
      PERFORM scanipy_execution.v1_require(actual @> (v->'completed_run_ids') AND (v->'completed_run_ids') @> actual,'completed run acknowledgement mismatch');
      PERFORM scanipy_execution.v1_require(NOT EXISTS(SELECT 1 FROM scanipy_execution.detector_runs WHERE request_id=w.request_id AND state IN ('pending','running')),'unsettled detector run');
      PERFORM scanipy_execution.v1_require(NOT EXISTS(SELECT 1 FROM scanipy_execution.detector_runs d JOIN scanipy_execution.detection_occurrences o ON o.detector_run_id=d.id
        WHERE d.request_id=w.request_id AND d.state<>'completed'),'partial retained run prevents complete inventory');
    ELSE
      PERFORM scanipy_execution.v1_require(jsonb_array_length(v->'completed_run_ids')=0,'identity cannot complete detector runs');
      policy:=(convert_from(w.payload_bytes,'UTF8')::jsonb)->'policy';
      PERFORM scanipy_execution.v1_require(v->'identity'<>'null'::jsonb,'identity completion requires descriptors');
      IF policy->>'mode'='required' THEN
        PERFORM scanipy_execution.v1_require(v->'identity'->'cpg_order'->>'status'='completed' AND v->'identity'->'slice'->>'status'='completed','required identity incomplete');
      ELSE
        PERFORM scanipy_execution.v1_require(v->'identity'->'cpg_order'->>'status'='not-applicable' AND v->'identity'->'slice'->>'status'='not-applicable'
          AND v->>'identity_policy_reason'=policy->>'reason','not-applicable identity policy mismatch');
      END IF;
    END IF;
  END IF;
  IF p_kind='capture_detection' AND v->>'status'='failed' THEN
    UPDATE scanipy_execution.detector_runs SET state='interrupted',terminal_at=moment,result_schema=v->>'schema',result_bytes=data,result_digest=digest
      WHERE work_attempt_id=p_attempt AND state IN ('pending','running');
  END IF;
  SELECT EXISTS(SELECT 1 FROM scanipy_execution.detector_runs d JOIN scanipy_execution.detection_occurrences o ON o.detector_run_id=d.id
    WHERE d.request_id=w.request_id AND d.state<>'completed') INTO partial_retained;
  retry_allowed:=v->>'status'='failed' AND (v->>'retryable')::boolean AND a.attempt_number<w.max_attempts
    AND NOT(p_kind='capture_detection' AND partial_retained);
  new_state:=CASE WHEN retry_allowed THEN 'pending' ELSE v->>'status' END;
  delay:=least(w.max_backoff_seconds,w.initial_backoff_seconds*(2^(a.attempt_number-1))::int);
  UPDATE scanipy_execution.work_attempts SET state=CASE WHEN p_expire THEN 'interrupted' ELSE v->>'status' END,
    terminal_at=moment,result_schema=v->>'schema',result_bytes=data,result_digest=digest WHERE id=p_attempt RETURNING * INTO a;
  PERFORM scanipy_execution.v1_release_all(p_attempt,p_token,CASE WHEN p_expire THEN 'attempt-expired' ELSE 'attempt-'||a.state END,moment);
  UPDATE scanipy_execution.work_items SET state=new_state,active_attempt_id=NULL,revision=revision+1,
    next_attempt_at=CASE WHEN retry_allowed THEN moment+make_interval(secs=>delay) ELSE next_attempt_at END,
    terminal_bytes=CASE WHEN retry_allowed THEN NULL ELSE data END,terminal_digest=CASE WHEN retry_allowed THEN NULL ELSE digest END
    WHERE id=p_work RETURNING * INTO w;
  PERFORM scanipy_execution.v1_stages(w.request_id);
  IF p_kind='capture_detection' AND v->>'status'='completed' THEN
    PERFORM scanipy_execution.v1_require((SELECT detection_state='completed'
      FROM scanipy_execution.scan_requests WHERE id=w.request_id),
      'unsuperseded detector failure prevents completion');
  END IF;
  RETURN jsonb_build_object('attempt_id',a.id,'attempt_state',a.state,'work_state',w.state,'revision',w.revision,'replayed',false);
END $$;

CREATE FUNCTION scanipy_execution.v1_renew(p_org uuid,p_kind text,p_work uuid,p_attempt uuid,p_token bigint,p_revision bigint)
RETURNS jsonb LANGUAGE plpgsql SET search_path=pg_catalog,scanipy_execution,pg_temp AS $$
DECLARE s jsonb; expiry timestamptz; result_revision bigint;
BEGIN
  s:=scanipy_execution.v1_lock(p_org,p_work,p_kind,p_attempt,p_token,p_revision,true);
  expiry:=(s->>'now')::timestamptz+make_interval(secs=>(s->'work'->>'lease_seconds')::int);
  UPDATE scanipy_execution.work_attempts SET lease_expires_at=expiry WHERE id=p_attempt;
  UPDATE scanipy_execution.capture_leases SET expires_at=expiry WHERE work_attempt_id=p_attempt AND released_at IS NULL;
  UPDATE scanipy_execution.work_items SET revision=revision+1 WHERE id=p_work RETURNING revision INTO result_revision;
  RETURN jsonb_build_object('attempt_id',p_attempt,'revision',result_revision,'lease_expires_at',expiry);
END $$;

CREATE FUNCTION scanipy_execution.v1_capture_lease(p_org uuid,p_kind text,p_work uuid,p_attempt uuid,p_token bigint,p_revision bigint,action text,data bytea,digest bytea)
RETURNS jsonb LANGUAGE plpgsql SET search_path=pg_catalog,scanipy_execution,pg_temp AS $$
DECLARE s jsonb; consumer scanipy_execution.capture_leases%ROWTYPE; v jsonb; result_revision bigint;
BEGIN
  s:=scanipy_execution.v1_lock(p_org,p_work,p_kind,p_attempt,p_token,p_revision,false);
  SELECT * INTO consumer FROM scanipy_execution.capture_leases WHERE work_attempt_id=p_attempt;
  IF action='release' THEN
    v:=scanipy_execution.v1_envelope('lease-release',data,digest);
    PERFORM scanipy_execution.v1_require((v->>'attempt_id')::uuid=p_attempt AND (v->>'token')::bigint=p_token,'release consumer mismatch');
    IF consumer.released_at IS NOT NULL THEN
      PERFORM scanipy_execution.v1_require(consumer.release_bytes=data AND consumer.release_digest=digest,'release replay conflict');
      RETURN jsonb_build_object('lease_id',consumer.id,'replayed',true,'revision',(s->'work'->>'revision')::bigint);
    END IF;
  END IF;
  s:=scanipy_execution.v1_lock(p_org,p_work,p_kind,p_attempt,p_token,p_revision,true);
  PERFORM scanipy_execution.v1_require(consumer.id IS NOT NULL,'capture has not been registered');
  IF action='acquire' THEN
    RETURN jsonb_build_object('lease_id',consumer.id,'replayed',true,'revision',p_revision);
  ELSIF action='renew' THEN
    UPDATE scanipy_execution.capture_leases SET expires_at=(s->'attempt'->>'lease_expires_at')::timestamptz WHERE id=consumer.id;
  ELSIF action='release' THEN
    UPDATE scanipy_execution.capture_leases SET released_at=(s->>'now')::timestamptz,release_bytes=data,release_digest=digest WHERE id=consumer.id;
  ELSE RAISE EXCEPTION 'unknown private lease action'; END IF;
  UPDATE scanipy_execution.work_items SET revision=revision+1 WHERE id=p_work RETURNING revision INTO result_revision;
  RETURN jsonb_build_object('lease_id',consumer.id,'replayed',false,'revision',result_revision);
END $$;

CREATE FUNCTION scanipy_execution.create_request_v1(p_org uuid,p_codebase uuid,data bytea,digest bytea,policy_bytes bytea,policy_digest bytea)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,scanipy_execution,pg_temp AS $$
DECLARE v jsonb; policy jsonb; r scanipy_execution.scan_requests%ROWTYPE; wid uuid;
BEGIN
  PERFORM scanipy_execution.v1_org(p_org);
  v:=scanipy_execution.v1_envelope('request',data,digest);
  policy:=scanipy_execution.v1_envelope('planned-policy',policy_bytes,policy_digest);
  PERFORM scanipy_execution.v1_require(v->>'requested_policy_digest'=encode(policy_digest,'hex')
    AND v->'identity_policy'=policy->'identity_policy','requested policy binding mismatch');
  PERFORM scanipy_execution.v1_require((v->>'org_id')::uuid=p_org AND (v->>'codebase_id')::uuid=p_codebase,'typed request scope mismatch');
  INSERT INTO scanipy_execution.scan_requests(org_id,codebase_id,lineage_id,predecessor_request_id,
    idempotency_key,request_schema,request_bytes,request_digest,planned_policy_schema,planned_policy_bytes,planned_policy_digest)
  VALUES(p_org,p_codebase,(v->>'lineage_id')::uuid,(v->>'predecessor_request_id')::uuid,
    v->>'idempotency_key',v->>'schema',data,digest,policy->>'schema',policy_bytes,policy_digest)
  ON CONFLICT(org_id,idempotency_key) DO NOTHING RETURNING * INTO r;
  IF r.id IS NULL THEN
    SELECT * INTO STRICT r FROM scanipy_execution.scan_requests WHERE org_id=p_org AND idempotency_key=v->>'idempotency_key' FOR UPDATE;
    PERFORM scanipy_execution.v1_require(r.codebase_id=p_codebase AND r.request_bytes=data AND r.request_digest=digest
      AND r.planned_policy_bytes=policy_bytes AND r.planned_policy_digest=policy_digest,'idempotency conflict');
    RETURN jsonb_build_object('request_id',r.id,'work_item_id',r.active_detection_work_id,'revision',r.revision,'replayed',true);
  END IF;
  wid:=scanipy_execution.v1_insert_work(p_org,p_codebase,r.id,'capture_detection',NULL,NULL,v->'retry_policy',v->'identity_policy');
  UPDATE scanipy_execution.scan_requests SET active_detection_work_id=wid,revision=revision+1 WHERE id=r.id RETURNING * INTO r;
  RETURN jsonb_build_object('request_id',r.id,'work_item_id',wid,'revision',r.revision,'replayed',false);
END $$;

CREATE FUNCTION scanipy_execution.v1_lock(
  p_org uuid,p_work uuid,p_kind text,p_attempt uuid,p_token bigint,p_revision bigint,p_live boolean)
RETURNS jsonb LANGUAGE plpgsql SET search_path=pg_catalog,scanipy_execution,pg_temp AS $$
DECLARE w scanipy_execution.work_items%ROWTYPE; r scanipy_execution.scan_requests%ROWTYPE;
  c scanipy_execution.source_captures%ROWTYPE; a scanipy_execution.work_attempts%ROWTYPE;
  moment timestamptz; consumer scanipy_execution.capture_leases%ROWTYPE;
BEGIN
  PERFORM scanipy_execution.v1_org(p_org);
  SELECT * INTO w FROM scanipy_execution.work_items WHERE org_id=p_org AND id=p_work;
  PERFORM scanipy_execution.v1_require(w.id IS NOT NULL AND w.kind=p_kind,'work not found or wrong kind');
  SELECT * INTO STRICT r FROM scanipy_execution.scan_requests WHERE org_id=p_org AND id=w.request_id FOR UPDATE;
  SELECT * INTO c FROM scanipy_execution.source_captures WHERE org_id=p_org AND owner_request_id=r.id FOR UPDATE;
  SELECT * INTO STRICT w FROM scanipy_execution.work_items WHERE org_id=p_org AND id=p_work FOR UPDATE;
  IF p_attempt IS NOT NULL THEN
    SELECT * INTO a FROM scanipy_execution.work_attempts WHERE org_id=p_org AND work_item_id=w.id AND id=p_attempt FOR UPDATE;
    PERFORM scanipy_execution.v1_require(a.id IS NOT NULL AND a.kind=p_kind AND a.fencing_token=p_token,'attempt scope or token mismatch');
    PERFORM id FROM scanipy_execution.detector_runs WHERE org_id=p_org AND work_attempt_id=a.id ORDER BY id FOR UPDATE;
  END IF;
  moment:=pg_catalog.clock_timestamp();
  IF p_live THEN
    PERFORM scanipy_execution.v1_require(w.state='running' AND w.active_attempt_id=a.id AND w.fencing_token=p_token
      AND w.revision=p_revision AND a.state='running' AND a.lease_expires_at>moment AND r.cancellation_bytes IS NULL,'stale or expired attempt');
    IF c.id IS NOT NULL THEN
      SELECT * INTO consumer FROM scanipy_execution.capture_leases WHERE org_id=p_org AND work_attempt_id=a.id;
      PERFORM scanipy_execution.v1_require(c.retention_state='active' AND consumer.capture_id=c.id
        AND consumer.fencing_token=p_token AND consumer.released_at IS NULL AND consumer.expires_at>moment,'missing or expired capture consumer');
    ELSE
      PERFORM scanipy_execution.v1_require(p_kind='capture_detection','identity requires capture');
    END IF;
  END IF;
  RETURN jsonb_build_object('work',to_jsonb(w),'request',to_jsonb(r),'capture',CASE WHEN c.id IS NULL THEN NULL ELSE to_jsonb(c) END,
    'attempt',CASE WHEN a.id IS NULL THEN NULL ELSE to_jsonb(a) END,'now',moment);
END $$;

CREATE FUNCTION scanipy_execution.v1_claim(p_org uuid,p_kind text,p_work uuid,data bytea,digest bytea)
RETURNS jsonb LANGUAGE plpgsql SET search_path=pg_catalog,scanipy_execution,pg_temp AS $$
DECLARE v jsonb; candidate record; locked_request uuid; s jsonb; w scanipy_execution.work_items%ROWTYPE;
  a scanipy_execution.work_attempts%ROWTYPE; cap uuid; moment timestamptz; runner jsonb;
BEGIN
  PERFORM scanipy_execution.v1_org(p_org); v:=scanipy_execution.v1_envelope('attempt-policy',data,digest);
  FOR candidate IN SELECT id,request_id FROM scanipy_execution.work_items
    WHERE org_id=p_org AND kind=p_kind AND state='pending' AND next_attempt_at<=pg_catalog.clock_timestamp()
      AND (p_work IS NULL OR id=p_work) ORDER BY created_at,id LOOP
    locked_request:=NULL;
    SELECT id INTO locked_request FROM scanipy_execution.scan_requests WHERE org_id=p_org AND id=candidate.request_id FOR UPDATE SKIP LOCKED;
    IF locked_request IS NULL THEN CONTINUE; END IF;
    s:=scanipy_execution.v1_lock(p_org,candidate.id,p_kind,NULL,NULL,NULL,false);
    SELECT * INTO STRICT w FROM scanipy_execution.work_items WHERE id=candidate.id;
    moment:=(s->>'now')::timestamptz; cap:=(s->'capture'->>'id')::uuid;
    IF w.state<>'pending' OR w.next_attempt_at>moment THEN CONTINUE; END IF;
    PERFORM scanipy_execution.v1_require(s->'request'->>'cancellation_bytes' IS NULL,'request cancelled');
    PERFORM scanipy_execution.v1_require(w.lease_seconds=(v->>'lease_seconds')::int,'lease policy mismatch');
    SELECT (convert_from(planned_policy_bytes,'UTF8')::jsonb)->(p_kind||'_runner') INTO runner
      FROM scanipy_execution.scan_requests WHERE id=w.request_id;
    PERFORM scanipy_execution.v1_require(runner->>'code_policy_digest'=v->>'code_policy_digest'
      AND runner->>'environment_policy_digest'=v->>'environment_policy_digest','runner policy binding mismatch');
    PERFORM scanipy_execution.v1_require(w.fencing_token<w.max_attempts,'attempt budget exhausted');
    IF cap IS NOT NULL THEN
      PERFORM scanipy_execution.v1_require(s->'capture'->>'retention_state'='active','capture not active');
    END IF;
    INSERT INTO scanipy_execution.work_attempts(org_id,codebase_id,request_id,work_item_id,kind,
      attempt_number,fencing_token,assignment_id,policy_schema,policy_bytes,policy_digest,started_at,lease_expires_at)
    VALUES(p_org,w.codebase_id,w.request_id,w.id,p_kind,w.fencing_token+1,w.fencing_token+1,
      v->>'assignment_id',v->>'schema',data,digest,moment,moment+make_interval(secs=>w.lease_seconds)) RETURNING * INTO a;
    UPDATE scanipy_execution.work_items SET state='running',active_attempt_id=a.id,fencing_token=a.fencing_token,revision=revision+1
      WHERE id=w.id RETURNING * INTO w;
    IF cap IS NOT NULL THEN
      INSERT INTO scanipy_execution.capture_leases(org_id,codebase_id,request_id,capture_id,work_item_id,work_attempt_id,fencing_token,acquired_at,expires_at)
      VALUES(p_org,w.codebase_id,w.request_id,cap,w.id,a.id,a.fencing_token,moment,a.lease_expires_at);
    END IF;
    PERFORM scanipy_execution.v1_stages(w.request_id);
    RETURN jsonb_build_object('work_item_id',w.id,'request_id',w.request_id,'kind',p_kind,'occurrence_id',w.occurrence_id,
      'attempt_id',a.id,'attempt_number',a.attempt_number,'fencing_token',a.fencing_token,'revision',w.revision,
      'lease_expires_at',a.lease_expires_at,'capture_id',cap,'payload',convert_from(w.payload_bytes,'UTF8')::jsonb);
  END LOOP;
  RETURN NULL;
END $$;

CREATE FUNCTION scanipy_execution.register_capture_and_seal_v1(
  p_org uuid,p_work uuid,p_attempt uuid,p_token bigint,p_revision bigint,
  data bytea,digest bytea,inventory bytea,inventory_digest bytea,content bytea,content_digest bytea,
  spec bytea,detectors bytea[],rules bytea[],authority_evidence bytea)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,scanipy_execution,pg_temp AS $$
DECLARE s jsonb; v jsonb; inv jsonb; accepted jsonb; old scanipy_execution.scan_seals%ROWTYPE;
  c scanipy_execution.source_captures%ROWTYPE; binding record; rule record; idx integer:=0; total bigint;
  cap uuid; sid uuid; moment timestamptz; v_request_id uuid; v_codebase_id uuid; lease_end timestamptz; requested jsonb; plan jsonb; plan_digest bytea;
BEGIN
  v:=scanipy_execution.v1_envelope('seal',data,digest);
  inv:=scanipy_execution.v1_envelope('source-inventory',inventory,inventory_digest);
  accepted:=scanipy_execution.v1_envelope('accepted-content',content,content_digest);
  PERFORM scanipy_execution.v1_require(spec IS NOT NULL AND detectors IS NOT NULL AND rules IS NOT NULL AND authority_evidence IS NOT NULL,'missing accepted bytes');
  PERFORM scanipy_execution.v1_byte_array(detectors);
  PERFORM scanipy_execution.v1_byte_array(rules);
  SELECT octet_length(spec)+coalesce(sum(octet_length(x)),0) INTO total FROM unnest(detectors||rules) x;
  PERFORM scanipy_execution.v1_require(total<=1048576 AND octet_length(authority_evidence)<=1048576,'accepted bytes size limit');
  PERFORM scanipy_execution.v1_require(NOT EXISTS(SELECT 1 FROM unnest(detectors||rules) x WHERE x IS NULL),'null accepted content');
  PERFORM scanipy_execution.v1_require(accepted->>'spec_sha256'=encode(sha256(spec),'hex') AND
    v->>'accepted_content_digest'=encode(content_digest,'hex') AND v->>'inventory_digest'=encode(inventory_digest,'hex') AND
    v->>'acceptance_evidence_digest'=encode(sha256(authority_evidence),'hex'),'accepted/inventory digest mismatch');
  PERFORM scanipy_execution.v1_require(cardinality(detectors)=jsonb_array_length(v->'bindings') AND
    cardinality(detectors)=jsonb_array_length(accepted->'detector_sha256s') AND cardinality(rules)=jsonb_array_length(accepted->'rule_sha256s'),'accepted content inventory mismatch');
  FOR binding IN SELECT value,ordinality FROM jsonb_array_elements(v->'bindings') WITH ORDINALITY LOOP
    PERFORM scanipy_execution.v1_require(binding.value->>'detector_content_digest'=encode(sha256(detectors[binding.ordinality]),'hex')
      AND accepted->'detector_sha256s'->>(binding.ordinality::int-1)=binding.value->>'detector_content_digest','detector bytes mismatch');
    FOR rule IN SELECT value FROM jsonb_array_elements(binding.value->'rules') LOOP
      idx:=idx+1;
      PERFORM scanipy_execution.v1_require(rule.value->>'content_digest'=encode(sha256(rules[idx]),'hex')
        AND accepted->'rule_sha256s'->>(idx-1)=rule.value->>'content_digest','rule bytes mismatch');
    END LOOP;
  END LOOP;
  PERFORM scanipy_execution.v1_require(idx=cardinality(rules),'extra rule content');
  PERFORM scanipy_execution.v1_require(NOT EXISTS(SELECT 1 FROM jsonb_array_elements_text(v->'intended_files') p
    WHERE NOT EXISTS(SELECT 1 FROM jsonb_array_elements(inv->'files') f WHERE f->>'path'=p)),'intended file outside capture inventory');
  s:=scanipy_execution.v1_lock(p_org,p_work,'capture_detection',p_attempt,p_token,p_revision,true);
  v_request_id:=(s->'work'->>'request_id')::uuid; v_codebase_id:=(s->'work'->>'codebase_id')::uuid;
  PERFORM scanipy_execution.v1_require((v->>'request_id')::uuid=v_request_id,'seal request mismatch');
  SELECT convert_from(r.request_bytes,'UTF8')::jsonb,convert_from(r.planned_policy_bytes,'UTF8')::jsonb,r.planned_policy_digest
    INTO requested,plan,plan_digest FROM scanipy_execution.scan_requests r WHERE r.id=v_request_id;
  PERFORM scanipy_execution.v1_require(v->>'s_version'=requested->>'requested_s_version','requested S_version mismatch');
  PERFORM scanipy_execution.v1_require(v->>'planned_policy_digest'=encode(plan_digest,'hex') AND v->'bindings'=plan->'bindings','sealed planned-policy mismatch');
  SELECT * INTO old FROM scanipy_execution.scan_seals WHERE org_id=p_org AND scan_seals.request_id=v_request_id;
  IF old.id IS NOT NULL THEN
    PERFORM scanipy_execution.v1_require(old.seal_bytes=data AND old.seal_digest=digest AND old.accepted_content_bytes=content
      AND old.accepted_spec_bytes=spec AND old.accepted_detector_bytes=detectors AND old.accepted_rule_bytes=rules
      AND old.acceptance_evidence_bytes=authority_evidence,'conflicting seal replay');
    RETURN jsonb_build_object('capture_id',old.capture_id,'seal_id',old.id,'replayed',true);
  END IF;
  moment:=(s->>'now')::timestamptz; lease_end:=(s->'attempt'->>'lease_expires_at')::timestamptz;
  INSERT INTO scanipy_execution.source_captures(org_id,codebase_id,owner_request_id,resolved_commit,commit_algorithm,
    tree_algorithm,tree_digest,inventory_schema,inventory_bytes,inventory_digest,storage_object_id,storage_reference,
    created_at,retain_seconds,retain_until)
  VALUES(p_org,v_codebase_id,v_request_id,v->>'resolved_commit',v->>'commit_algorithm',v->>'tree_algorithm',decode(v->>'tree_digest','hex'),
    inv->>'schema',inventory,inventory_digest,(v->>'storage_object_id')::uuid,v->>'storage_reference',moment,
    (v->>'retain_seconds')::int,moment+make_interval(secs=>(v->>'retain_seconds')::int)) RETURNING id INTO cap;
  INSERT INTO scanipy_execution.scan_seals(org_id,codebase_id,request_id,capture_id,seal_schema,seal_bytes,seal_digest,s_version,
    accepted_content_bytes,accepted_content_digest,accepted_spec_bytes,accepted_detector_bytes,accepted_rule_bytes,
    acceptance_evidence_bytes,acceptance_evidence_digest,created_at)
  VALUES(p_org,v_codebase_id,v_request_id,cap,v->>'schema',data,digest,v->>'s_version',content,content_digest,spec,detectors,rules,
    authority_evidence,sha256(authority_evidence),moment) RETURNING id INTO sid;
  INSERT INTO scanipy_execution.capture_leases(org_id,codebase_id,request_id,capture_id,work_item_id,work_attempt_id,fencing_token,acquired_at,expires_at)
  VALUES(p_org,v_codebase_id,v_request_id,cap,p_work,p_attempt,p_token,moment,lease_end);
  UPDATE scanipy_execution.scan_requests SET capture_state='completed',revision=revision+1 WHERE id=v_request_id;
  RETURN jsonb_build_object('capture_id',cap,'seal_id',sid,'replayed',false);
END $$;

CREATE FUNCTION scanipy_execution.retain_detection_batch_v1(
  p_org uuid,p_work uuid,p_attempt uuid,p_token bigint,p_revision bigint,p_run uuid,
  data bytea,digest bytea,p_stdout bytea,p_stderr bytea,raw_results bytea[],witnesses bytea[])
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,scanipy_execution,pg_temp AS $$
DECLARE v jsonb; s jsonb; run scanipy_execution.detector_runs%ROWTYPE; sealed scanipy_execution.scan_seals%ROWTYPE;
  binding jsonb; rule jsonb; requested jsonb; item record; idx integer; bytes_total bigint; oid uuid;
  ids jsonb:='[]'; ids_work jsonb:='[]'; wid uuid; part text; names jsonb; planned jsonb; moment timestamptz;
BEGIN
  v:=scanipy_execution.v1_envelope('detection-batch',data,digest);
  PERFORM scanipy_execution.v1_require((v->>'run_id')::uuid=p_run,'typed run mismatch');
  PERFORM scanipy_execution.v1_require(p_stdout IS NOT NULL AND p_stderr IS NOT NULL AND raw_results IS NOT NULL AND witnesses IS NOT NULL,'missing raw evidence parameters');
  PERFORM scanipy_execution.v1_byte_array(raw_results);
  PERFORM scanipy_execution.v1_byte_array(witnesses);
  PERFORM scanipy_execution.v1_require(cardinality(raw_results)=jsonb_array_length(v->'occurrences') AND cardinality(witnesses)=cardinality(raw_results),'raw occurrence inventory mismatch');
  SELECT octet_length(p_stdout)::bigint+octet_length(p_stderr)+coalesce(sum(octet_length(x)),0) INTO bytes_total FROM unnest(raw_results||witnesses) x;
  PERFORM scanipy_execution.v1_require(bytes_total<=67108864,'batch raw byte limit');
  PERFORM scanipy_execution.v1_require(v->>'stdout_sha256'=encode(sha256(p_stdout),'hex') AND v->>'stderr_sha256'=encode(sha256(p_stderr),'hex'),'raw stream digest mismatch');
  FOR item IN SELECT value,ordinality FROM jsonb_array_elements(v->'occurrences') WITH ORDINALITY LOOP
    idx:=item.ordinality;
    PERFORM scanipy_execution.v1_require(raw_results[idx] IS NOT NULL AND octet_length(raw_results[idx])+coalesce(octet_length(witnesses[idx]),0)<=16777216,'occurrence raw byte limit');
    PERFORM scanipy_execution.v1_require(item.value->>'raw_sha256'=encode(sha256(raw_results[idx]),'hex') AND
      (item.value->>'witness_sha256') IS NOT DISTINCT FROM encode(sha256(witnesses[idx]),'hex'),'occurrence raw digest mismatch');
  END LOOP;
  s:=scanipy_execution.v1_lock(p_org,p_work,'capture_detection',p_attempt,p_token,p_revision,false);
  SELECT * INTO run FROM scanipy_execution.detector_runs WHERE org_id=p_org AND id=p_run AND work_item_id=p_work AND work_attempt_id=p_attempt;
  PERFORM scanipy_execution.v1_require(run.id IS NOT NULL,'detector run scope mismatch');
  requested:=convert_from(run.input_bytes,'UTF8')::jsonb;
  PERFORM scanipy_execution.v1_require(v->'actual_invocation'=jsonb_build_object(
    'argv',requested->'argv','cwd',requested->'cwd'),'actual invocation differs from immutable run input');
  IF run.state NOT IN ('pending','running') THEN
    PERFORM scanipy_execution.v1_require(run.result_schema=v->>'schema' AND run.result_bytes=data AND run.result_digest=digest
      AND run.stdout=p_stdout AND run.stderr=p_stderr,'terminal batch replay conflict');
    FOR item IN SELECT * FROM scanipy_execution.detection_occurrences WHERE detector_run_id=p_run ORDER BY tool_ordinal LOOP
      idx:=item.tool_ordinal+1;
      PERFORM scanipy_execution.v1_require(item.raw_result_bytes=raw_results[idx] AND item.witness_bytes IS NOT DISTINCT FROM witnesses[idx],'raw batch replay conflict');
      ids:=ids||jsonb_build_array(item.id);
      SELECT id INTO STRICT wid FROM scanipy_execution.work_items WHERE occurrence_id=item.id;
      ids_work:=ids_work||jsonb_build_array(wid);
    END LOOP;
    RETURN jsonb_build_object('run_id',p_run,'occurrence_ids',ids,'identity_work_ids',ids_work,'replayed',true);
  END IF;
  s:=scanipy_execution.v1_lock(p_org,p_work,'capture_detection',p_attempt,p_token,p_revision,true);
  moment:=(s->>'now')::timestamptz;
  SELECT * INTO STRICT sealed FROM scanipy_execution.scan_seals WHERE id=run.seal_id;
  SELECT value INTO STRICT binding FROM jsonb_array_elements(convert_from(sealed.seal_bytes,'UTF8')::jsonb->'bindings') WHERE value->>'key'=run.detector_binding_key;
  PERFORM scanipy_execution.v1_require(v->'tool_identity'->>'policy_digest'=binding->>'tool_policy_digest'
    AND v->'code_identity'->>'policy_digest'=binding->>'code_policy_digest','observed tool/code policy mismatch');
  PERFORM scanipy_execution.v1_require(v->'tool_identity'->>'artifact_digest'=binding->>'expected_tool_digest'
    AND v->'code_identity'->>'artifact_digest'=binding->>'expected_code_digest'
    AND v->>'detector_env_digest'=binding->>'expected_image_digest','missing or mismatched actual detector artifact pins');
  IF v->>'status'='completed' THEN
    planned:=(convert_from(sealed.seal_bytes,'UTF8')::jsonb)->'intended_files';
    PERFORM scanipy_execution.v1_require((v->'coverage'->'files') @> planned AND planned @> (v->'coverage'->'files'),'incomplete intended file coverage');
    SELECT jsonb_agg(value->'rule_id') INTO names FROM jsonb_array_elements(binding->'rules');
    PERFORM scanipy_execution.v1_require(v->'coverage'->'rules' @> names AND names @> (v->'coverage'->'rules'),'incomplete intended rule coverage');
  END IF;
  SELECT convert_from(request_bytes,'UTF8')::jsonb INTO STRICT requested FROM scanipy_execution.scan_requests WHERE id=run.request_id;
  -- Validate every binding before the first INSERT, not merely on its turn.
  FOR item IN SELECT value FROM jsonb_array_elements(v->'occurrences') LOOP
    PERFORM scanipy_execution.v1_require(binding->'engines' @> jsonb_build_array(item.value->'engine'),'unsealed child engine');
    PERFORM scanipy_execution.v1_require(EXISTS(SELECT 1 FROM jsonb_array_elements(binding->'rules') x WHERE x->>'rule_id'=item.value->>'rule_id'),'unsealed rule');
  END LOOP;
  FOR item IN SELECT value,ordinality FROM jsonb_array_elements(v->'occurrences') WITH ORDINALITY LOOP
    idx:=item.ordinality;
    SELECT value INTO STRICT rule FROM jsonb_array_elements(binding->'rules') WHERE value->>'rule_id'=item.value->>'rule_id';
    part:=CASE WHEN item.value->>'engine' IN ('ifds','ide') THEN 'deterministic-core' ELSE 'oracle-passthrough' END;
    INSERT INTO scanipy_execution.detection_occurrences(org_id,codebase_id,request_id,capture_id,detector_run_id,
      adapter_result_key,duplicate_ordinal,tool_ordinal,raw_result_bytes,raw_result_digest,witness_bytes,witness_digest,
      engine,origin,determinism_partition,detector_id,class_id,language,rule_id,rule_semantic_digest,s_version,env_digest,full_env_digest,
      cwe,severity,message,physical_location,metadata_bytes,created_at)
    VALUES(p_org,run.codebase_id,run.request_id,run.capture_id,run.id,item.value->>'result_key',(item.value->>'duplicate_ordinal')::bigint,
      (item.value->>'tool_ordinal')::bigint,raw_results[idx],sha256(raw_results[idx]),witnesses[idx],sha256(witnesses[idx]),item.value->>'engine',part,part,
      binding->>'detector_id',binding->>'class_id',binding->>'language',item.value->>'rule_id',decode(rule->>'semantic_digest','hex'),sealed.s_version,
      v->>'detector_env_digest',v->>'full_env_digest',item.value->>'cwe',item.value->>'severity',item.value->>'message',item.value->'location',
      scanipy_execution.v1_bytes(item.value),moment) RETURNING id INTO oid;
    wid:=scanipy_execution.v1_insert_work(p_org,run.codebase_id,run.request_id,'identity',oid,run.capture_id,requested->'retry_policy',requested->'identity_policy');
    ids:=ids||jsonb_build_array(oid); ids_work:=ids_work||jsonb_build_array(wid);
  END LOOP;
  UPDATE scanipy_execution.detector_runs SET state=v->>'status',terminal_at=moment,result_schema=v->>'schema',result_bytes=data,result_digest=digest,
    stdout=p_stdout,stderr=p_stderr,result_count=cardinality(raw_results),inventory_digest=decode(v->>'inventory_digest','hex') WHERE id=p_run;
  PERFORM scanipy_execution.v1_stages(run.request_id);
  RETURN jsonb_build_object('run_id',p_run,'occurrence_ids',ids,'identity_work_ids',ids_work,'replayed',false);
END $$;

CREATE FUNCTION scanipy_execution.fail_detector_run_v1(p_org uuid,p_work uuid,p_attempt uuid,p_token bigint,p_revision bigint,p_run uuid,data bytea,digest bytea,prefix bytea)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,scanipy_execution,pg_temp AS $$
DECLARE v jsonb; s jsonb; run scanipy_execution.detector_runs%ROWTYPE;
BEGIN
  v:=scanipy_execution.v1_envelope('run-failure',data,digest);
  PERFORM scanipy_execution.v1_require(prefix IS NOT NULL AND octet_length(prefix)<=65536 AND v->>'prefix_sha256'=encode(sha256(prefix),'hex'),'failed-run prefix bound/digest');
  PERFORM scanipy_execution.v1_require((v->>'observed_byte_count')::bigint IS NULL OR (v->>'observed_byte_count')::bigint>=octet_length(prefix),'observed count below prefix');
  PERFORM scanipy_execution.v1_require(v->'truncated'='true'::jsonb OR (v->>'observed_byte_count')::bigint=octet_length(prefix),'untruncated evidence requires exact count');
  PERFORM scanipy_execution.v1_require(v->>'observed_full_sha256' IS NULL OR v->'truncated'='true'::jsonb OR v->>'observed_full_sha256'=encode(sha256(prefix),'hex'),'full digest mismatch');
  s:=scanipy_execution.v1_lock(p_org,p_work,'capture_detection',p_attempt,p_token,p_revision,false);
  SELECT * INTO run FROM scanipy_execution.detector_runs WHERE org_id=p_org AND id=p_run AND work_item_id=p_work AND work_attempt_id=p_attempt;
  PERFORM scanipy_execution.v1_require(run.id IS NOT NULL,'failed run scope mismatch');
  IF run.state NOT IN ('pending','running') THEN
    PERFORM scanipy_execution.v1_require(run.result_schema=v->>'schema' AND run.result_bytes=data AND run.result_digest=digest AND run.failure_prefix=prefix,'failed-run replay conflict');
    RETURN jsonb_build_object('run_id',run.id,'replayed',true);
  END IF;
  s:=scanipy_execution.v1_lock(p_org,p_work,'capture_detection',p_attempt,p_token,p_revision,true);
  UPDATE scanipy_execution.detector_runs SET state='failed',terminal_at=(s->>'now')::timestamptz,
    result_schema=v->>'schema',result_bytes=data,result_digest=digest,failure_prefix=prefix WHERE id=run.id;
  PERFORM scanipy_execution.v1_stages(run.request_id);
  RETURN jsonb_build_object('run_id',run.id,'replayed',false);
END $$;

CREATE FUNCTION scanipy_execution.begin_detector_run_v1(p_org uuid,p_work uuid,p_attempt uuid,p_token bigint,p_revision bigint,data bytea,digest bytea)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,scanipy_execution,pg_temp AS $$
DECLARE s jsonb; v jsonb; sealed scanipy_execution.scan_seals%ROWTYPE; binding jsonb;
  existing scanipy_execution.detector_runs%ROWTYPE; result uuid; occurrence_ids jsonb;
  superseded uuid; failed_leaves uuid[];
BEGIN
  v:=scanipy_execution.v1_envelope('run-input',data,digest);
  s:=scanipy_execution.v1_lock(p_org,p_work,'capture_detection',p_attempt,p_token,p_revision,true);
  SELECT * INTO sealed FROM scanipy_execution.scan_seals WHERE org_id=p_org AND request_id=(s->'work'->>'request_id')::uuid;
  PERFORM scanipy_execution.v1_require(sealed.id IS NOT NULL,'detector requires immutable seal');
  SELECT value INTO binding FROM jsonb_array_elements(convert_from(sealed.seal_bytes,'UTF8')::jsonb->'bindings') WHERE value->>'key'=v->>'binding_key';
  PERFORM scanipy_execution.v1_require(binding IS NOT NULL AND binding->>'tool_policy_digest'=v->>'tool_policy_digest'
    AND binding->>'code_policy_digest'=v->>'code_policy_digest' AND binding->>'environment_policy_digest'=v->>'environment_policy_digest','sealed execution policy mismatch');
  SELECT * INTO existing FROM scanipy_execution.detector_runs WHERE org_id=p_org AND request_id=sealed.request_id
    AND detector_binding_key=v->>'binding_key' AND state='completed';
  IF existing.id IS NOT NULL THEN
    PERFORM scanipy_execution.v1_require(existing.seal_id=sealed.id AND existing.capture_id=sealed.capture_id,'completed binding scope mismatch');
    SELECT coalesce(jsonb_agg(id ORDER BY tool_ordinal),'[]'::jsonb) INTO occurrence_ids FROM scanipy_execution.detection_occurrences WHERE detector_run_id=existing.id;
    RETURN jsonb_build_object('run_id',existing.id,'completed',true,'occurrence_ids',occurrence_ids,'replayed',true);
  END IF;
  PERFORM scanipy_execution.v1_require(NOT EXISTS(SELECT 1 FROM scanipy_execution.detector_runs d JOIN scanipy_execution.detection_occurrences o ON o.detector_run_id=d.id
    WHERE d.request_id=sealed.request_id AND d.state<>'completed'),'retained partial observations require new request');
  SELECT * INTO existing FROM scanipy_execution.detector_runs WHERE work_attempt_id=p_attempt AND detector_binding_key=v->>'binding_key' AND run_ordinal=(v->>'run_ordinal')::bigint;
  IF existing.id IS NOT NULL THEN
    PERFORM scanipy_execution.v1_require(existing.input_bytes=data AND existing.input_digest=digest,'run invocation replay conflict');
    PERFORM scanipy_execution.v1_require(existing.state IN ('pending','running'),'terminal failed/interrupted run cannot begin again; read retained failure and allocate a new run');
    RETURN jsonb_build_object('run_id',existing.id,'completed',false,'occurrence_ids','[]'::jsonb,'replayed',true);
  END IF;
  PERFORM scanipy_execution.v1_require(NOT EXISTS(SELECT 1 FROM scanipy_execution.detector_runs WHERE request_id=sealed.request_id
    AND detector_binding_key=v->>'binding_key' AND state IN ('pending','running')),'binding already executing');
  SELECT array_agg(d.id) INTO failed_leaves FROM scanipy_execution.detector_runs d WHERE d.request_id=sealed.request_id
    AND d.detector_binding_key=v->>'binding_key' AND d.state IN ('failed','interrupted') AND d.result_count=0
    AND NOT EXISTS(SELECT 1 FROM scanipy_execution.detector_runs child WHERE child.supersedes_run_id=d.id);
  PERFORM scanipy_execution.v1_require(coalesce(cardinality(failed_leaves),0)<=1,'ambiguous failure-chain leaves');
  superseded:=failed_leaves[1];
  INSERT INTO scanipy_execution.detector_runs(org_id,codebase_id,request_id,capture_id,seal_id,work_item_id,work_attempt_id,
    detector_binding_key,run_ordinal,supersedes_run_id,input_schema,input_bytes,input_digest,created_at)
  VALUES(p_org,sealed.codebase_id,sealed.request_id,sealed.capture_id,sealed.id,p_work,p_attempt,v->>'binding_key',
    (v->>'run_ordinal')::bigint,superseded,v->>'schema',data,digest,(s->>'now')::timestamptz) RETURNING id INTO result;
  RETURN jsonb_build_object('run_id',result,'completed',false,'occurrence_ids','[]'::jsonb,'replayed',false);
END $$;
