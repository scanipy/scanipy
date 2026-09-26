-- The migration renders this fixed body exactly twice. IS_DETECTOR is a literal
-- chosen by the migration, never a caller argument or a third generic bridge.
-- Narrow control columns only; no SELECT *, row-to-JSON, raw payload or hash.
CREATE FUNCTION scanipy_execution.__BRIDGE_NAME__(p_org uuid,p_work uuid,p_attempt uuid,
  p_token bigint,p_revision bigint__TARGET_PARAMETERS__) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER
SET search_path=pg_catalog,scanipy_execution,pg_temp SET bytea_output='hex' AS $$
DECLARE r record; w record; a record; c record; s record; l record; d record;
  request_key uuid; capture_key uuid; run_key uuid; active_ids uuid[];
  now_at timestamptz; result jsonb; seen bigint; returned bigint; planned integer;
  sealed boolean; is_detector CONSTANT boolean:=__IS_DETECTOR__;
BEGIN
  PERFORM scanipy_execution.v1_org(p_org);
  IF p_work IS NULL OR p_attempt IS NULL OR p_token IS NULL OR p_token<1
     OR p_revision IS NULL OR p_revision<0 THEN
    RAISE EXCEPTION 'invalid-input' USING ERRCODE='P0001';
  END IF;
  SELECT request_id INTO request_key FROM scanipy_execution.work_items
    WHERE org_id=p_org AND id=p_work;
  IF NOT FOUND THEN RAISE EXCEPTION 'fence-stale' USING ERRCODE='P0001'; END IF;
  SELECT id,org_id,codebase_id,planned_policy_digest,active_detection_work_id,
      cancellation_bytes IS NOT NULL AS cancelled,error_reference IS NOT NULL AS has_error
    INTO r FROM scanipy_execution.scan_requests
    WHERE org_id=p_org AND id=request_key FOR UPDATE;
  IF NOT FOUND OR r.cancelled OR r.has_error OR r.active_detection_work_id IS DISTINCT FROM p_work THEN
    RAISE EXCEPTION 'fence-stale' USING ERRCODE='P0001';
  END IF;

  -- The request lock stabilizes ordinary owner-function history. Four bounded
  -- id-only queries share ONE N+1 ticket including the server-derived planned
  -- row. No caller count, whole-history array or unbounded COUNT is admitted.
  SELECT id INTO capture_key FROM scanipy_execution.source_captures
    WHERE org_id=p_org AND codebase_id=r.codebase_id AND owner_request_id=request_key;
  SELECT id,capture_id,accepted_content_digest,acceptance_evidence_digest INTO s
    FROM scanipy_execution.scan_seals
    WHERE org_id=p_org AND codebase_id=r.codebase_id AND request_id=request_key;
  sealed:=FOUND;
  planned:=CASE WHEN NOT is_detector AND sealed THEN 1 ELSE 0 END;
  seen:=planned;
  SELECT count(*) INTO returned FROM (SELECT id FROM scanipy_execution.work_items
    WHERE org_id=p_org AND request_id=request_key LIMIT (65536-seen+1)) q;
  seen:=seen+returned;
  IF seen>65536 THEN RAISE EXCEPTION 'invalid-input' USING ERRCODE='P0001'; END IF;
  SELECT count(*) INTO returned FROM (SELECT id FROM scanipy_execution.work_attempts
    WHERE org_id=p_org AND request_id=request_key LIMIT (65536-seen+1)) q;
  seen:=seen+returned;
  IF seen>65536 THEN RAISE EXCEPTION 'invalid-input' USING ERRCODE='P0001'; END IF;
  SELECT count(*) INTO returned FROM (SELECT id FROM scanipy_execution.detector_runs
    WHERE org_id=p_org AND request_id=request_key LIMIT (65536-seen+1)) q;
  seen:=seen+returned;
  IF seen>65536 THEN RAISE EXCEPTION 'invalid-input' USING ERRCODE='P0001'; END IF;
  SELECT count(*) INTO returned FROM (SELECT id FROM scanipy_execution.detection_occurrences
    WHERE org_id=p_org AND request_id=request_key LIMIT (65536-seen+1)) q;
  seen:=seen+returned;
  IF seen>65536 THEN RAISE EXCEPTION 'invalid-input' USING ERRCODE='P0001'; END IF;

  IF capture_key IS NOT NULL THEN
    SELECT id,org_id,codebase_id,owner_request_id,retention_state INTO c
      FROM scanipy_execution.source_captures
      WHERE org_id=p_org AND id=capture_key FOR UPDATE;
    IF NOT FOUND OR c.retention_state<>'active' OR c.owner_request_id<>request_key
      OR c.codebase_id<>r.codebase_id THEN
      RAISE EXCEPTION 'fence-stale' USING ERRCODE='P0001';
    END IF;
  END IF;
  SELECT id,org_id,codebase_id,request_id,kind,state,active_attempt_id,fencing_token,revision INTO w
    FROM scanipy_execution.work_items WHERE org_id=p_org AND id=p_work FOR UPDATE;
  SELECT id,org_id,codebase_id,request_id,work_item_id,kind,state,fencing_token,
      policy_digest,lease_expires_at INTO a
    FROM scanipy_execution.work_attempts WHERE org_id=p_org AND id=p_attempt FOR UPDATE;
  IF NOT FOUND OR w.id IS NULL OR w.request_id<>request_key OR w.codebase_id<>r.codebase_id
    OR w.kind<>'capture_detection' OR w.state<>'running' OR w.active_attempt_id IS DISTINCT FROM p_attempt
    OR w.fencing_token<>p_token OR w.revision<>p_revision OR a.work_item_id<>p_work
    OR a.request_id<>request_key OR a.codebase_id<>r.codebase_id
    OR a.kind<>'capture_detection' OR a.state<>'running' OR a.fencing_token<>p_token THEN
    RAISE EXCEPTION 'fence-stale' USING ERRCODE='P0001';
  END IF;
  FOR run_key IN SELECT id FROM scanipy_execution.detector_runs
    WHERE org_id=p_org AND work_attempt_id=p_attempt ORDER BY id FOR UPDATE LOOP NULL; END LOOP;
  SELECT coalesce(array_agg(id ORDER BY id),ARRAY[]::uuid[]) INTO active_ids
    FROM (SELECT id FROM scanipy_execution.detector_runs
      WHERE org_id=p_org AND work_attempt_id=p_attempt AND state IN ('pending','running')
      ORDER BY id LIMIT 2) q;
  __TARGET_CHECK__

  IF sealed IS DISTINCT FROM (capture_key IS NOT NULL) OR (sealed AND s.capture_id<>capture_key) THEN
    RAISE EXCEPTION 'ledger-mismatch' USING ERRCODE='P0001';
  END IF;
  SELECT id,org_id,codebase_id,request_id,capture_id,work_item_id,work_attempt_id,
    fencing_token,expires_at,released_at INTO l FROM scanipy_execution.capture_leases
    WHERE sealed AND org_id=p_org AND work_attempt_id=p_attempt FOR UPDATE;
  IF sealed THEN
    IF NOT FOUND OR l.codebase_id<>r.codebase_id OR l.request_id<>request_key OR l.capture_id<>capture_key
      OR l.work_item_id<>p_work OR l.fencing_token<>p_token OR l.released_at IS NOT NULL THEN
      RAISE EXCEPTION 'fence-stale' USING ERRCODE='P0001';
    END IF;
    __CONSUMER_CHECK__
  ELSIF is_detector THEN RAISE EXCEPTION 'ledger-mismatch' USING ERRCODE='P0001';
  END IF;
  now_at:=clock_timestamp();
  IF a.lease_expires_at<=now_at OR (sealed AND l.expires_at<=now_at) THEN
    RAISE EXCEPTION 'fence-stale' USING ERRCODE='P0001';
  END IF;
  result:=jsonb_build_object('org_id',r.org_id,'codebase_id',r.codebase_id,'request_id',r.id,
    'work_item_id',w.id,'work_attempt_id',a.id,'fencing_token',w.fencing_token,'work_revision',w.revision,
    'requested_policy_digest',encode(r.planned_policy_digest,'hex'),
    'attempt_policy_digest',encode(a.policy_digest,'hex'),
    'lease_expires_at',to_char(a.lease_expires_at AT TIME ZONE 'UTC','YYYY-MM-DD"T"HH24:MI:SS.US"Z"'),
    'capture_id',capture_key,'seal_id',CASE WHEN sealed THEN s.id ELSE NULL END,
    'capture_lease_id',CASE WHEN sealed THEN l.id ELSE NULL END,
    'capture_lease_expires_at',CASE WHEN sealed THEN to_char(l.expires_at AT TIME ZONE 'UTC','YYYY-MM-DD"T"HH24:MI:SS.US"Z"') ELSE NULL END,
    'accepted_content_digest',CASE WHEN sealed THEN encode(s.accepted_content_digest,'hex') ELSE NULL END,
    'acceptance_evidence_digest',CASE WHEN sealed THEN encode(s.acceptance_evidence_digest,'hex') ELSE NULL END,
    'db_now',to_char(now_at AT TIME ZONE 'UTC','YYYY-MM-DD"T"HH24:MI:SS.US"Z"'));
  __TARGET_RESULT__
  RETURN result;
END $$;
