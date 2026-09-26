-- Frozen AL-03 wire primitives. These are private implementation functions,
-- not additional runtime entrypoints and not signature/admission verifiers.
CREATE FUNCTION scanipy_accepted_inputs.v1_require(ok boolean, code text DEFAULT 'invalid-input')
RETURNS void LANGUAGE plpgsql SET search_path=pg_catalog,scanipy_accepted_inputs,pg_temp AS $$
BEGIN
  IF ok IS DISTINCT FROM TRUE THEN
    IF code='scope-mismatch' THEN RAISE EXCEPTION 'scope-mismatch' USING ERRCODE='42501'; END IF;
    IF code NOT IN ('invalid-input','content-mismatch','ledger-mismatch','policy-stale',
      'policy-expired','checkpoint-denied','grant-denied','fence-stale') THEN code:='invalid-input'; END IF;
    RAISE EXCEPTION '%',code USING ERRCODE='P0001';
  END IF;
END $$;

-- A public entrypoint initializes this backend-local, transaction-local meter.
-- Private functions never accept a caller's budget or refund a reservation.
-- Its value is accounting only: it supplies no namespace, role or authority.
CREATE FUNCTION scanipy_accepted_inputs.v1_work_begin(fetch_limit bigint, control_limit bigint DEFAULT 65536,
  relational_limit bigint DEFAULT 2097184)
RETURNS void LANGUAGE plpgsql SET search_path=pg_catalog,scanipy_accepted_inputs,pg_temp AS $$
BEGIN
  PERFORM scanipy_accepted_inputs.v1_require(fetch_limit BETWEEN 0 AND 150994944
    AND control_limit BETWEEN 0 AND 167772160 AND relational_limit BETWEEN 0 AND 2097184);
  PERFORM pg_catalog.set_config('scanipy.accepted_work',
    pg_catalog.jsonb_build_object('used',pg_catalog.jsonb_build_array(0,0,0,0,0,0,0,0,0),
      'caps',pg_catalog.jsonb_build_array(100000,134217728,fetch_limit,
        control_limit,536870912,relational_limit,2147483648,65536,fetch_limit))::text,true);
END $$;

CREATE FUNCTION scanipy_accepted_inputs.v1_lengths(parts bytea[]) RETURNS integer[]
LANGUAGE sql IMMUTABLE SET search_path=pg_catalog,scanipy_accepted_inputs,pg_temp AS $$
  SELECT coalesce(array_agg(octet_length(value) ORDER BY ordinal),ARRAY[]::integer[])
    FROM unnest(parts) WITH ORDINALITY AS p(value,ordinal)
$$;

CREATE FUNCTION scanipy_accepted_inputs.v1_charge(bucket integer, amount bigint)
RETURNS void LANGUAGE plpgsql SET search_path=pg_catalog,scanipy_accepted_inputs,pg_temp AS $$
DECLARE meter jsonb; used bigint; ceiling bigint;
BEGIN
  PERFORM scanipy_accepted_inputs.v1_require(bucket BETWEEN 0 AND 8 AND amount>=0);
  meter:=NULLIF(pg_catalog.current_setting('scanipy.accepted_work',true),'')::jsonb;
  PERFORM scanipy_accepted_inputs.v1_require(meter IS NOT NULL);
  used:=(meter->'used'->>bucket)::bigint; ceiling:=(meter->'caps'->>bucket)::bigint;
  PERFORM scanipy_accepted_inputs.v1_require(used>=0 AND ceiling>=0);
  IF amount>ceiling-used THEN
    -- Private diagnostic distinction only. Public code/message stay exactly
    -- P0001/invalid-input, including inside a stored-only decoding wrapper.
    RAISE EXCEPTION 'invalid-input' USING ERRCODE='P0001',DETAIL='accepted-work-limit';
  END IF;
  meter:=pg_catalog.jsonb_set(meter,ARRAY['used',bucket::text],pg_catalog.to_jsonb(used+amount));
  PERFORM pg_catalog.set_config('scanipy.accepted_work',meter::text,true);
END $$;

CREATE FUNCTION scanipy_accepted_inputs.v1_control(amount bigint) RETURNS void
LANGUAGE plpgsql SET search_path=pg_catalog,scanipy_accepted_inputs,pg_temp AS $$
BEGIN
  PERFORM scanipy_accepted_inputs.v1_charge(7,amount);
  PERFORM scanipy_accepted_inputs.v1_charge(3,amount);
END $$;

CREATE FUNCTION scanipy_accepted_inputs.v1_fetch(amount bigint) RETURNS void
LANGUAGE plpgsql SET search_path=pg_catalog,scanipy_accepted_inputs,pg_temp AS $$
BEGIN
  PERFORM scanipy_accepted_inputs.v1_charge(8,amount);
  PERFORM scanipy_accepted_inputs.v1_charge(2,amount);
END $$;

CREATE FUNCTION scanipy_accepted_inputs.v1_hash(data bytea, domain_name text DEFAULT NULL)
RETURNS bytea LANGUAGE plpgsql SET search_path=pg_catalog,scanipy_accepted_inputs,pg_temp AS $$
DECLARE prefix bytea:=''::bytea;
BEGIN
  PERFORM scanipy_accepted_inputs.v1_require(data IS NOT NULL);
  IF domain_name IS NOT NULL THEN
    PERFORM scanipy_accepted_inputs.v1_require(octet_length(domain_name) BETWEEN 1 AND 128
      AND domain_name ~ '^[A-Za-z0-9._:/-]+$');
    prefix:=pg_catalog.convert_to(domain_name||chr(10),'UTF8');
  END IF;
  PERFORM scanipy_accepted_inputs.v1_charge(0,1);
  PERFORM scanipy_accepted_inputs.v1_charge(1,octet_length(data)::bigint+octet_length(prefix));
  RETURN pg_catalog.sha256(prefix||data);
END $$;

CREATE FUNCTION scanipy_accepted_inputs.v1_byte_array(parts bytea[], maximum integer DEFAULT 20000)
RETURNS bigint LANGUAGE plpgsql IMMUTABLE SET search_path=pg_catalog,scanipy_accepted_inputs,pg_temp AS $$
DECLARE item bytea; total bigint:=0;
BEGIN
  PERFORM scanipy_accepted_inputs.v1_require(parts IS NOT NULL AND maximum BETWEEN 0 AND 20000
    AND cardinality(parts)<=maximum AND
    (cardinality(parts)=0 OR (array_ndims(parts)=1 AND array_lower(parts,1)=1)));
  FOREACH item IN ARRAY parts LOOP
    PERFORM scanipy_accepted_inputs.v1_require(item IS NOT NULL AND octet_length(item)<=1048576);
    total:=total+octet_length(item);
    PERFORM scanipy_accepted_inputs.v1_require(total<=3145728);
  END LOOP;
  RETURN total;
END $$;

-- Linear lexical admission occurs before PostgreSQL allocates a JSON tree.
-- max_values/max_string are explicit because original occurrence envelopes
-- retain their own domain (no newly imposed accepted-input 20,000-value cap).
CREATE FUNCTION scanipy_accepted_inputs.v1_lexical(data bytea, maximum integer,
  max_values integer DEFAULT 20000, max_string integer DEFAULT 16384, max_depth integer DEFAULT 32)
RETURNS integer LANGUAGE plpgsql IMMUTABLE SET search_path=pg_catalog,scanipy_accepted_inputs,pg_temp AS $$
DECLARE pos integer:=0; size integer; b integer; depth integer:=0; values_seen integer:=0;
  quoted boolean:=false; escaped boolean:=false; extent integer:=0; first integer; token text;
BEGIN
  PERFORM scanipy_accepted_inputs.v1_require(data IS NOT NULL AND maximum BETWEEN 1 AND 1048576
    AND max_values BETWEEN 1 AND 1048576 AND max_string BETWEEN 1 AND 1048576 AND max_depth BETWEEN 1 AND 32);
  size:=octet_length(data);
  PERFORM scanipy_accepted_inputs.v1_require(size BETWEEN 1 AND maximum);
  WHILE pos<size LOOP
    b:=get_byte(data,pos);
    IF quoted THEN
      extent:=extent+1;
      PERFORM scanipy_accepted_inputs.v1_require(extent<=6::bigint*max_string+1);
      IF escaped THEN escaped:=false;
      ELSIF b=92 THEN escaped:=true;
      ELSIF b=34 THEN quoted:=false;
      ELSE PERFORM scanipy_accepted_inputs.v1_require(b>=32); END IF;
      pos:=pos+1; CONTINUE;
    END IF;
    IF b IN (9,10,13,32,44,58) THEN pos:=pos+1; CONTINUE; END IF;
    IF b=34 THEN quoted:=true; extent:=0; values_seen:=values_seen+1;
    ELSIF b IN (91,123) THEN depth:=depth+1; values_seen:=values_seen+1;
      PERFORM scanipy_accepted_inputs.v1_require(depth<=max_depth);
    ELSIF b IN (93,125) THEN depth:=depth-1;
      PERFORM scanipy_accepted_inputs.v1_require(depth>=0);
    ELSE
      first:=pos;
      WHILE pos<size AND get_byte(data,pos) NOT IN (9,10,13,32,44,58,91,93,123,125,34) LOOP
        pos:=pos+1;
        PERFORM scanipy_accepted_inputs.v1_require(pos-first<=20);
      END LOOP;
      token:=pg_catalog.convert_from(substring(data FROM first+1 FOR pos-first),'UTF8');
      IF token NOT IN ('true','false','null') THEN
        PERFORM scanipy_accepted_inputs.v1_require(token ~ '^-?(0|[1-9][0-9]*)$');
        -- The cast enforces the signed 64-bit domain before generic parsing.
        PERFORM token::bigint;
      END IF;
      values_seen:=values_seen+1;
      PERFORM scanipy_accepted_inputs.v1_require(values_seen<=max_values);
      CONTINUE;
    END IF;
    PERFORM scanipy_accepted_inputs.v1_require(values_seen<=max_values);
    pos:=pos+1;
  END LOOP;
  PERFORM scanipy_accepted_inputs.v1_require(NOT quoted AND depth=0);
  RETURN values_seen;
EXCEPTION WHEN numeric_value_out_of_range OR character_not_in_repertoire OR untranslatable_character THEN
  RAISE EXCEPTION 'invalid-input' USING ERRCODE='P0001';
END $$;

CREATE FUNCTION scanipy_accepted_inputs.v1_canonical(v json, depth integer DEFAULT 0,
  max_string integer DEFAULT 16384) RETURNS text
LANGUAGE plpgsql IMMUTABLE SET search_path=pg_catalog,scanipy_accepted_inputs,pg_temp AS $$
DECLARE kind text; item record; prior text; pieces text[]:=ARRAY[]::text[]; result text; token text;
BEGIN
  PERFORM scanipy_accepted_inputs.v1_require(v IS NOT NULL AND depth<=32);
  kind:=pg_catalog.json_typeof(v);
  IF kind='object' THEN
    FOR item IN SELECT key,value FROM pg_catalog.json_each(v) ORDER BY key COLLATE "C" LOOP
      PERFORM scanipy_accepted_inputs.v1_require(prior IS NULL OR prior<>item.key);
      PERFORM scanipy_accepted_inputs.v1_require(octet_length(item.key)<=max_string);
      prior:=item.key;
      pieces:=array_append(pieces,pg_catalog.to_json(item.key)::text||':'||
        scanipy_accepted_inputs.v1_canonical(item.value,depth+1,max_string));
    END LOOP;
    result:='{'||array_to_string(pieces,',')||'}';
  ELSIF kind='array' THEN
    FOR item IN SELECT value FROM pg_catalog.json_array_elements(v) LOOP
      pieces:=array_append(pieces,scanipy_accepted_inputs.v1_canonical(item.value,depth+1,max_string));
    END LOOP;
    result:='['||array_to_string(pieces,',')||']';
  ELSIF kind='string' THEN
    token:=v#>>'{}';
    PERFORM scanipy_accepted_inputs.v1_require(octet_length(token)<=max_string);
    result:=pg_catalog.to_json(token)::text;
  ELSIF kind='number' THEN
    token:=v::text;
    PERFORM scanipy_accepted_inputs.v1_require(length(token)<=20 AND token ~ '^-?(0|[1-9][0-9]*)$');
    result:=(token::bigint)::text;
  ELSIF kind IN ('boolean','null') THEN result:=v::text;
  ELSE PERFORM scanipy_accepted_inputs.v1_require(false); END IF;
  PERFORM scanipy_accepted_inputs.v1_require(octet_length(result)<=1048576);
  RETURN result;
END $$;

CREATE FUNCTION scanipy_accepted_inputs.v1_json(data bytea, maximum integer DEFAULT 65536,
  canonical boolean DEFAULT true, max_values integer DEFAULT 20000, max_depth integer DEFAULT 32) RETURNS jsonb
LANGUAGE plpgsql IMMUTABLE SET search_path=pg_catalog,scanipy_accepted_inputs,pg_temp AS $$
DECLARE original json; encoded bytea;
BEGIN
  PERFORM scanipy_accepted_inputs.v1_lexical(data,maximum,max_values,16384,max_depth);
  original:=pg_catalog.convert_from(data,'UTF8')::json;
  -- Duplicate and portable-string validation happens on preserved json first.
  encoded:=pg_catalog.convert_to(scanipy_accepted_inputs.v1_canonical(original),'UTF8');
  PERFORM scanipy_accepted_inputs.v1_require(octet_length(encoded)<=maximum
    AND (NOT canonical OR encoded=data));
  RETURN original::jsonb;
EXCEPTION WHEN invalid_text_representation OR numeric_value_out_of_range OR
  character_not_in_repertoire OR untranslatable_character THEN
  RAISE EXCEPTION 'invalid-input' USING ERRCODE='P0001';
END $$;

CREATE FUNCTION scanipy_accepted_inputs.v1_bytes(v jsonb, maximum integer DEFAULT 65536)
RETURNS bytea LANGUAGE plpgsql IMMUTABLE SET search_path=pg_catalog,scanipy_accepted_inputs,pg_temp AS $$
DECLARE result bytea;
BEGIN
  -- All callers construct from previously bounded private values. Recheck the
  -- resulting representation, including value/key, decoded-string and byte caps.
  result:=pg_catalog.convert_to(scanipy_accepted_inputs.v1_canonical(v::json),'UTF8');
  PERFORM scanipy_accepted_inputs.v1_lexical(result,maximum);
  RETURN result;
END $$;

CREATE FUNCTION scanipy_accepted_inputs.v1_shape(v jsonb, expected jsonb)
RETURNS void LANGUAGE plpgsql IMMUTABLE SET search_path=pg_catalog,scanipy_accepted_inputs,pg_temp AS $$
DECLARE item record; spec text; token text; maximum integer; count_values integer; ok boolean:=false;
  instant timestamptz; pattern text;
BEGIN
  PERFORM scanipy_accepted_inputs.v1_require(v IS NOT NULL AND expected IS NOT NULL);
  IF jsonb_typeof(expected)='object' THEN
    IF expected ? '$nullable' THEN
      IF v<>'null'::jsonb THEN PERFORM scanipy_accepted_inputs.v1_shape(v,expected->'$nullable'); END IF;
    ELSIF expected ? '$enum' THEN
      PERFORM scanipy_accepted_inputs.v1_require(EXISTS(
        SELECT 1 FROM jsonb_array_elements(expected->'$enum') e WHERE e=v AND jsonb_typeof(e)=jsonb_typeof(v)));
    ELSIF expected ? '$array' THEN
      PERFORM scanipy_accepted_inputs.v1_require(jsonb_typeof(v)='array');
      count_values:=jsonb_array_length(v);
      PERFORM scanipy_accepted_inputs.v1_require(count_values BETWEEN
        (expected->>'$min')::integer AND (expected->>'$max')::integer);
      FOR item IN SELECT value FROM jsonb_array_elements(v) LOOP
        PERFORM scanipy_accepted_inputs.v1_shape(item.value,expected->'$array');
      END LOOP;
    ELSE
      PERFORM scanipy_accepted_inputs.v1_require(jsonb_typeof(v)='object' AND
        (SELECT array_agg(key ORDER BY key COLLATE "C") FROM jsonb_object_keys(v) key)
          IS NOT DISTINCT FROM
        (SELECT array_agg(key ORDER BY key COLLATE "C") FROM jsonb_object_keys(expected) key));
      FOR item IN SELECT key,value FROM jsonb_each(expected) LOOP
        PERFORM scanipy_accepted_inputs.v1_shape(v->item.key,item.value);
      END LOOP;
    END IF;
    RETURN;
  END IF;
  spec:=expected#>>'{}'; token:=v#>>'{}';
  IF spec IN ('count','positive') THEN
    PERFORM scanipy_accepted_inputs.v1_require(jsonb_typeof(v)='number'
      AND token ~ '^(0|[1-9][0-9]*)$' AND length(token)<=19);
    PERFORM scanipy_accepted_inputs.v1_require(token::bigint>=CASE WHEN spec='positive' THEN 1 ELSE 0 END);
    RETURN;
  END IF;
  PERFORM scanipy_accepted_inputs.v1_require(jsonb_typeof(v)='string');
  maximum:=CASE spec WHEN 'digest' THEN 64 WHEN 'uuid' THEN 36 WHEN 'version' THEN 32
    WHEN 'token' THEN 128 WHEN 'id' THEN 128 WHEN 'cwe' THEN 11 WHEN 'path' THEN 4096
    WHEN 'reason' THEN 4096 WHEN 'second' THEN 20 WHEN 'instant' THEN 27 ELSE 16384 END;
  PERFORM scanipy_accepted_inputs.v1_require(octet_length(token)<=maximum);
  CASE spec
    WHEN 'digest' THEN ok:=token ~ '^[0-9a-f]{64}$';
    WHEN 'uuid' THEN ok:=token ~ '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$';
    WHEN 'token' THEN ok:=token ~ '^[A-Za-z0-9][A-Za-z0-9._:-]*$';
    WHEN 'id' THEN ok:=token ~ '^[A-Za-z][A-Za-z0-9_.:/-]{0,127}$';
    WHEN 'cwe' THEN ok:=token ~ '^CWE-[1-9][0-9]{0,6}$';
    WHEN 'version' THEN
      ok:=token ~ '^(0|[1-9][0-9]{0,9})\.(0|[1-9][0-9]{0,9})\.(0|[1-9][0-9]{0,9})$';
      IF ok THEN ok:=split_part(token,'.',1)::bigint<=2147483647
        AND split_part(token,'.',2)::bigint<=2147483647 AND split_part(token,'.',3)::bigint<=2147483647; END IF;
    WHEN 'text' THEN ok:=true;
    WHEN 'reason' THEN ok:=token<>'';
    WHEN 'path' THEN
      ok:=left(token,1)='/' AND token<>'/' AND position(chr(92) IN token)=0
        AND NOT EXISTS(SELECT 1 FROM unnest(string_to_array(substring(token FROM 2),'/')) p WHERE p IN ('','.','..'))
        AND NOT EXISTS(SELECT 1 FROM generate_series(1,length(token)) i
          WHERE ascii(substring(token FROM i FOR 1))<32 OR ascii(substring(token FROM i FOR 1)) BETWEEN 127 AND 159);
    WHEN 'second','instant' THEN
      pattern:='^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}'||
        CASE WHEN spec='instant' THEN '\.[0-9]{6}Z$' ELSE 'Z$' END;
      ok:=token ~ pattern AND substring(token FROM 1 FOR 4)<>'0000';
      IF ok THEN
        instant:=token::timestamptz;
        ok:=to_char(instant AT TIME ZONE 'UTC',CASE WHEN spec='instant'
          THEN 'YYYY-MM-DD"T"HH24:MI:SS.US"Z"' ELSE 'YYYY-MM-DD"T"HH24:MI:SS"Z"' END)=token;
      END IF;
    ELSE ok:=false;
  END CASE;
  PERFORM scanipy_accepted_inputs.v1_require(ok);
EXCEPTION WHEN invalid_text_representation OR numeric_value_out_of_range OR
  datetime_field_overflow OR invalid_datetime_format THEN
  RAISE EXCEPTION 'invalid-input' USING ERRCODE='P0001';
END $$;

CREATE FUNCTION scanipy_accepted_inputs.v1_unique(v jsonb) RETURNS void
LANGUAGE plpgsql IMMUTABLE SET search_path=pg_catalog,scanipy_accepted_inputs,pg_temp AS $$
BEGIN
  PERFORM scanipy_accepted_inputs.v1_require(jsonb_typeof(v)='array'
    AND jsonb_array_length(v)=(SELECT count(DISTINCT value) FROM jsonb_array_elements(v)));
END $$;

CREATE FUNCTION scanipy_accepted_inputs.v1_scoped(v jsonb) RETURNS void
LANGUAGE plpgsql IMMUTABLE SET search_path=pg_catalog,scanipy_accepted_inputs,pg_temp AS $$
BEGIN
  IF v ? 'scope' THEN
    PERFORM scanipy_accepted_inputs.v1_require((v->>'scope'='global')=(v->'org_id'='null'::jsonb),'scope-mismatch');
  END IF;
END $$;

CREATE FUNCTION scanipy_accepted_inputs.v1_document(data bytea, schema_name text,
  canonical boolean DEFAULT true) RETURNS jsonb
LANGUAGE plpgsql IMMUTABLE SET search_path=pg_catalog,scanipy_accepted_inputs,pg_temp AS $$
DECLARE v jsonb; expected jsonb; item record; rule record; members jsonb; used jsonb;
  maximum integer; keys text[]; name text; detector boolean; seconds double precision;
BEGIN
  expected:=scanipy_accepted_inputs.v1_shapes()->'documents'->schema_name;
  PERFORM scanipy_accepted_inputs.v1_require(expected IS NOT NULL);
  maximum:=CASE schema_name WHEN 'scanipy-accepted-trust-policy/1' THEN 131072
    WHEN 'scanipy-registry-installed-trust/1' THEN 4096
    WHEN 'scanipy-accepted-s-manifest/1' THEN 1048576 ELSE 65536 END;
  v:=scanipy_accepted_inputs.v1_json(data,maximum,canonical);
  PERFORM scanipy_accepted_inputs.v1_shape(v,expected);
  PERFORM scanipy_accepted_inputs.v1_scoped(v);
  CASE schema_name
    WHEN 'scanipy-accepted-trust-policy/1' THEN
      PERFORM scanipy_accepted_inputs.v1_require(((v->>'revision')::bigint=1)=(v->'previous_policy_digest'='null'::jsonb)
        AND (v->>'valid_from')::timestamptz<(v->>'expires_at')::timestamptz);
      PERFORM scanipy_accepted_inputs.v1_unique((SELECT coalesce(jsonb_agg(value->'grant_id'),'[]') FROM jsonb_array_elements(v->'grants')));
      PERFORM scanipy_accepted_inputs.v1_unique((SELECT coalesce(jsonb_agg(jsonb_build_array(value->'key_id',value->'key_version')),'[]') FROM jsonb_array_elements(v->'grants')));
      FOR item IN SELECT value FROM jsonb_array_elements(v->'grants') LOOP
        PERFORM scanipy_accepted_inputs.v1_scoped(item.value);
        PERFORM scanipy_accepted_inputs.v1_require(item.value->'scope'=v->'scope' AND item.value->'org_id'=v->'org_id','scope-mismatch');
        PERFORM scanipy_accepted_inputs.v1_require((item.value->>'not_before')::timestamptz<(item.value->>'not_after')::timestamptz
          AND (item.value->>'status'='active')=(item.value->'status_changed_at'='null'::jsonb));
      END LOOP;
    WHEN 'scanipy-registry-admission/1' THEN
      seconds:=extract(epoch FROM (v->>'expires_at')::timestamptz-(v->>'issued_at')::timestamptz);
      PERFORM scanipy_accepted_inputs.v1_require(((v->>'generation')::bigint=1)=(v->'previous_checkpoint_digest'='null'::jsonb)
        AND seconds>0 AND seconds<=604800);
    WHEN 'scanipy-accepted-detector/1' THEN
      FOREACH name IN ARRAY ARRAY['cwes','languages','frameworks','rule_ids'] LOOP
        PERFORM scanipy_accepted_inputs.v1_unique(v->name);
      END LOOP;
      PERFORM scanipy_accepted_inputs.v1_require((SELECT jsonb_agg(value->'language') FROM jsonb_array_elements(v->'profiles'))=v->'languages');
    WHEN 'scanipy-accepted-s-manifest/1' THEN
      PERFORM scanipy_accepted_inputs.v1_unique((SELECT jsonb_agg(value->'detector_id') FROM jsonb_array_elements(v->'detectors')));
      FOR item IN SELECT value FROM jsonb_array_elements(v->'detectors') LOOP
        PERFORM scanipy_accepted_inputs.v1_unique((SELECT jsonb_agg(value->'language') FROM jsonb_array_elements(item.value->'language_profiles')));
        PERFORM scanipy_accepted_inputs.v1_unique((SELECT jsonb_agg(value->'rule_id') FROM jsonb_array_elements(item.value->'rules')));
        PERFORM scanipy_accepted_inputs.v1_unique((SELECT jsonb_agg(value->'artifact_id') FROM jsonb_array_elements(item.value->'rules')));
      END LOOP;
      PERFORM scanipy_accepted_inputs.v1_unique((SELECT jsonb_agg(jsonb_build_array(value->'artifact_id',value->'version')) FROM jsonb_array_elements(v->'models')));
      PERFORM scanipy_accepted_inputs.v1_unique((SELECT jsonb_agg(value->'raw_sha256') FROM jsonb_array_elements(v->'models')));
      SELECT jsonb_agg(key ORDER BY key) INTO members FROM
        (SELECT jsonb_build_array(value->'artifact_id',value->'raw_sha256') key FROM jsonb_array_elements(v->'models')) x;
      SELECT jsonb_agg(key ORDER BY key) INTO used FROM
        (SELECT DISTINCT jsonb_build_array(r->'model_artifact_id',r->'model_raw_sha256') key
          FROM jsonb_array_elements(v->'detectors') d CROSS JOIN LATERAL jsonb_array_elements(d->'rules') r) x;
      PERFORM scanipy_accepted_inputs.v1_require(members=used,'content-mismatch');
    WHEN 'scanipy-accepted-evidence-inventory/1' THEN
      PERFORM scanipy_accepted_inputs.v1_require(v->'objects'->0->>'role'='operator-adoption'
        AND v->'objects'->0->>'schema'='scanipy-operator-adoption/1');
    WHEN 'scanipy-capture-seal-authorization/1','scanipy-execution-authorization/1','scanipy-execution-denial/1' THEN
      IF schema_name='scanipy-capture-seal-authorization/1' THEN
        PERFORM scanipy_accepted_inputs.v1_require(v->>'work_kind'='capture_detection');
      ELSE
        detector:=v->>'purpose'='detector-run';
        PERFORM scanipy_accepted_inputs.v1_require((v->>'work_kind'='capture_detection')=detector
          AND (v->'detector_run_id'<>'null'::jsonb)=detector AND (v->'run_input_digest'<>'null'::jsonb)=detector
          AND (v->'occurrence_id'='null'::jsonb)=detector);
        IF schema_name='scanipy-execution-authorization/1' THEN
          PERFORM scanipy_accepted_inputs.v1_require((v->>'action'='initial')=(v->'previous_authorization_id'='null'::jsonb));
        END IF;
      END IF;
      IF schema_name<>'scanipy-execution-denial/1' THEN
        PERFORM scanipy_accepted_inputs.v1_require((v->>'authorized_at')::timestamptz<(v->>'lease_expires_at')::timestamptz
          AND (v->>'authorized_at')::timestamptz<(v->>'capture_lease_expires_at')::timestamptz);
      END IF;
    ELSE NULL;
  END CASE;
  IF scanipy_accepted_inputs.v1_shapes()->'frames' ? schema_name THEN
    PERFORM scanipy_accepted_inputs.v1_require((SELECT jsonb_agg(jsonb_build_array(value->'role',value->'schema'))
      FROM jsonb_array_elements(v->'objects'))=scanipy_accepted_inputs.v1_shapes()->'frames'->schema_name);
  END IF;
  RETURN v;
END $$;

CREATE FUNCTION scanipy_accepted_inputs.v1_record(data bytea, record_name text) RETURNS jsonb
LANGUAGE plpgsql IMMUTABLE SET search_path=pg_catalog,scanipy_accepted_inputs,pg_temp AS $$
DECLARE v jsonb;
BEGIN
  v:=scanipy_accepted_inputs.v1_json(data);
  PERFORM scanipy_accepted_inputs.v1_shape(v,scanipy_accepted_inputs.v1_shapes()->'records'->record_name);
  PERFORM scanipy_accepted_inputs.v1_scoped(v);
  IF record_name='LEDGER_EXPECTATION' THEN
    PERFORM scanipy_accepted_inputs.v1_require((v->'binding'='null'::jsonb)=(v->'execution_authorization_digest'='null'::jsonb)
      AND (v->'binding'='null'::jsonb)=(v->'policy_event_id'='null'::jsonb)
      AND (v->'binding'='null'::jsonb)=(v->'admission_event_id'='null'::jsonb));
  END IF;
  RETURN v;
END $$;

CREATE FUNCTION scanipy_accepted_inputs.v1_frame_parts(data bytea, frame_schema text,
  maximum integer) RETURNS bytea[]
LANGUAGE plpgsql IMMUTABLE SET search_path=pg_catalog,scanipy_accepted_inputs,pg_temp AS $$
DECLARE prefix bytea; offset_at integer; size integer; part_size bigint; i integer;
  result bytea[]:=ARRAY[]::bytea[];
BEGIN
  prefix:=convert_to(frame_schema||chr(10),'UTF8'); size:=octet_length(data); offset_at:=octet_length(prefix);
  PERFORM scanipy_accepted_inputs.v1_require(data IS NOT NULL AND size<=maximum AND
    substring(data FROM 1 FOR offset_at)=prefix);
  WHILE offset_at<size LOOP
    PERFORM scanipy_accepted_inputs.v1_require(size-offset_at>=8 AND cardinality(result)<20001);
    -- Reject lengths above our finite cap without signed-bigint overflow.
    part_size:=0;
    FOR i IN 0..7 LOOP
      part_size:=part_size*256+get_byte(data,offset_at+i);
      PERFORM scanipy_accepted_inputs.v1_require(part_size<=maximum);
    END LOOP;
    offset_at:=offset_at+8;
    PERFORM scanipy_accepted_inputs.v1_require(part_size<=size-offset_at);
    result:=array_append(result,substring(data FROM offset_at+1 FOR part_size::integer));
    offset_at:=offset_at+part_size::integer;
  END LOOP;
  PERFORM scanipy_accepted_inputs.v1_require(offset_at=size AND cardinality(result)>0);
  RETURN result;
END $$;

CREATE FUNCTION scanipy_accepted_inputs.v1_frame(data bytea, frame_schema text)
RETURNS bytea[] LANGUAGE plpgsql SET search_path=pg_catalog,scanipy_accepted_inputs,pg_temp AS $$
DECLARE parts bytea[]; manifest jsonb; item record; schema_name text; maximum integer;
  values_seen integer; raw bytea;
BEGIN
  PERFORM scanipy_accepted_inputs.v1_require(scanipy_accepted_inputs.v1_shapes()->'frames' ? frame_schema);
  parts:=scanipy_accepted_inputs.v1_frame_parts(data,frame_schema,
    CASE WHEN frame_schema='scanipy-registry-current-authority/1' THEN 262144 ELSE 1048576 END);
  manifest:=scanipy_accepted_inputs.v1_document(parts[1],frame_schema);
  PERFORM scanipy_accepted_inputs.v1_require(cardinality(parts)=jsonb_array_length(manifest->'objects')+1);
  values_seen:=scanipy_accepted_inputs.v1_lexical(parts[1],65536);
  FOR item IN SELECT value,ordinality FROM jsonb_array_elements(manifest->'objects') WITH ORDINALITY LOOP
    raw:=parts[item.ordinality::integer+1]; schema_name:=item.value->>'schema';
    maximum:=CASE WHEN schema_name='scanipy-accepted-trust-policy/1' THEN 131072
      WHEN schema_name IS NULL THEN 4096 ELSE 65536 END;
    PERFORM scanipy_accepted_inputs.v1_require(octet_length(raw)<=maximum
      AND octet_length(raw)=(item.value->>'length')::bigint);
    PERFORM scanipy_accepted_inputs.v1_require(scanipy_accepted_inputs.v1_hash(raw)=decode(item.value->>'raw_sha256','hex'),'content-mismatch');
    IF schema_name IS NOT NULL THEN
      PERFORM scanipy_accepted_inputs.v1_document(raw,schema_name);
      values_seen:=values_seen+scanipy_accepted_inputs.v1_lexical(raw,maximum);
      PERFORM scanipy_accepted_inputs.v1_require(values_seen<=20000);
    ELSIF right(item.value->>'role',10)='-signature' THEN
      PERFORM scanipy_accepted_inputs.v1_require(octet_length(raw)=384);
    ELSE PERFORM scanipy_accepted_inputs.v1_require(octet_length(raw)>0); END IF;
  END LOOP;
  RETURN parts;
END $$;

CREATE FUNCTION scanipy_accepted_inputs.v1_encode_frame(schema_name text, manifest jsonb, objects bytea[])
RETURNS bytea LANGUAGE plpgsql SET search_path=pg_catalog,scanipy_accepted_inputs,pg_temp AS $$
DECLARE data bytea; item bytea; all_parts bytea[]; total bigint; descriptors jsonb:='[]'; i integer;
  roles jsonb;
BEGIN
  total:=scanipy_accepted_inputs.v1_byte_array(objects,15); roles:=scanipy_accepted_inputs.v1_shapes()->'frames'->schema_name;
  PERFORM scanipy_accepted_inputs.v1_require(roles IS NOT NULL AND cardinality(objects)=jsonb_array_length(roles));
  FOR i IN 1..cardinality(objects) LOOP
    descriptors:=descriptors||jsonb_build_array(jsonb_build_object('role',roles->(i-1)->0,
      'schema',roles->(i-1)->1,'length',octet_length(objects[i]),
      'raw_sha256',encode(scanipy_accepted_inputs.v1_hash(objects[i]),'hex')));
  END LOOP;
  manifest:=manifest||jsonb_build_object('schema',schema_name,'objects',descriptors);
  all_parts:=array_prepend(scanipy_accepted_inputs.v1_bytes(manifest),objects);
  total:=total+octet_length(all_parts[1])+8*cardinality(all_parts)+octet_length(schema_name)+1;
  PERFORM scanipy_accepted_inputs.v1_require(total<=CASE WHEN schema_name='scanipy-registry-current-authority/1' THEN 262144 ELSE 1048576 END);
  data:=convert_to(schema_name||chr(10),'UTF8');
  FOREACH item IN ARRAY all_parts LOOP data:=data||int8send(octet_length(item)::bigint)||item; END LOOP;
  PERFORM scanipy_accepted_inputs.v1_frame(data,schema_name);
  RETURN data;
END $$;

CREATE FUNCTION scanipy_accepted_inputs.v1_command(data bytea, parts bytea[], wanted text)
RETURNS jsonb LANGUAGE plpgsql SET search_path=pg_catalog,scanipy_accepted_inputs,pg_temp AS $$
DECLARE v jsonb; expected jsonb; item record; roles text[]; role_name text; last_role text;
  total bigint; cap bigint; detectors integer:=0; rules integer:=0; ordinal integer;
BEGIN
  cap:=CASE wanted WHEN 'install-policy' THEN 196992 WHEN 'record-admission' THEN 131456
    WHEN 'publish-builtin' THEN 2162688 WHEN 'create-bound-request' THEN 2162688
    WHEN 'seal-bound-capture' THEN 3211264 WHEN 'authorize-detector' THEN 1114112
    WHEN 'renew-detector' THEN 65536 ELSE NULL END;
  PERFORM scanipy_accepted_inputs.v1_require(cap IS NOT NULL AND data IS NOT NULL AND octet_length(data) BETWEEN 1 AND 65536);
  total:=scanipy_accepted_inputs.v1_byte_array(parts)+octet_length(data);
  PERFORM scanipy_accepted_inputs.v1_require(total<=cap);
  expected:=jsonb_build_object('schema',jsonb_build_object('$enum',jsonb_build_array('scanipy-accepted-ledger-command/1')),
    'action',jsonb_build_object('$enum',jsonb_build_array(wanted)),
    'operation_key','uuid','namespace_id','uuid','expected_coordination_revision','count',
    'body',scanipy_accepted_inputs.v1_shapes()->'commands'->wanted,
    'objects',jsonb_build_object('$array',jsonb_build_object('role','token','ordinal','count','length','count','raw_sha256','digest'),
      '$min',0,'$max',20000));
  v:=scanipy_accepted_inputs.v1_json(data);
  PERFORM scanipy_accepted_inputs.v1_shape(v,expected);
  PERFORM scanipy_accepted_inputs.v1_require(jsonb_array_length(v->'objects')=cardinality(parts));
  IF v->'body' ? 'bundle' THEN PERFORM scanipy_accepted_inputs.v1_scoped(v->'body'->'bundle'); END IF;
  roles:=CASE wanted WHEN 'install-policy' THEN ARRAY['policy','root-signature']
    WHEN 'record-admission' THEN ARRAY['checkpoint','root-signature']
    WHEN 'create-bound-request' THEN ARRAY['request','planned-policy']
    WHEN 'seal-bound-capture' THEN ARRAY['seal','source-inventory','accepted-content']
    WHEN 'authorize-detector' THEN ARRAY['run-input'] WHEN 'renew-detector' THEN ARRAY[]::text[] ELSE NULL END;
  IF wanted='publish-builtin' THEN
    PERFORM scanipy_accepted_inputs.v1_require(cardinality(parts)>=4 AND octet_length(parts[1])<=1048576
      AND total-octet_length(data)-octet_length(parts[1])<=1048576);
  ELSE PERFORM scanipy_accepted_inputs.v1_require(cardinality(parts)=cardinality(roles)); END IF;
  last_role:='detector';
  FOR item IN SELECT value,ordinality FROM jsonb_array_elements(v->'objects') WITH ORDINALITY LOOP
    role_name:=item.value->>'role'; ordinal:=0;
    IF wanted='publish-builtin' THEN
      IF item.ordinality=1 THEN PERFORM scanipy_accepted_inputs.v1_require(role_name='publication-input');
      ELSIF item.ordinality=2 THEN PERFORM scanipy_accepted_inputs.v1_require(role_name='accepted-spec');
      ELSE
        IF role_name='rule' THEN last_role:='rule'; END IF;
        PERFORM scanipy_accepted_inputs.v1_require(role_name=last_role);
        IF last_role='detector' THEN ordinal:=detectors; detectors:=detectors+1;
        ELSE ordinal:=rules; rules:=rules+1; END IF;
      END IF;
    ELSE PERFORM scanipy_accepted_inputs.v1_require(role_name=roles[item.ordinality::integer]); END IF;
    PERFORM scanipy_accepted_inputs.v1_require((item.value->>'ordinal')::bigint=ordinal
      AND (item.value->>'length')::bigint=octet_length(parts[item.ordinality::integer]));
  END LOOP;
  IF wanted='publish-builtin' THEN PERFORM scanipy_accepted_inputs.v1_require(detectors>0 AND rules>0);
  ELSIF wanted IN ('install-policy','record-admission') THEN
    PERFORM scanipy_accepted_inputs.v1_require(octet_length(parts[2])=384 AND octet_length(parts[1])<=
      CASE WHEN wanted='install-policy' THEN 131072 ELSE 65536 END);
  END IF;
  -- The complete shape/count/length admission above precedes every input hash.
  FOR item IN SELECT value,ordinality FROM jsonb_array_elements(v->'objects') WITH ORDINALITY LOOP
    PERFORM scanipy_accepted_inputs.v1_require(scanipy_accepted_inputs.v1_hash(parts[item.ordinality::integer])=
      decode(item.value->>'raw_sha256','hex'),'content-mismatch');
  END LOOP;
  RETURN v;
END $$;

CREATE FUNCTION scanipy_accepted_inputs.v1_concat_reserve(n bigint, values_seen bigint, copies integer DEFAULT 1)
RETURNS void LANGUAGE plpgsql SET search_path=pg_catalog,scanipy_accepted_inputs,pg_temp AS $$
DECLARE cost bigint;
BEGIN
  PERFORM scanipy_accepted_inputs.v1_require(n BETWEEN 0 AND 1049088
    AND values_seen BETWEEN 0 AND 1048640 AND copies BETWEEN 1 AND 3);
  cost:=8*(n+1)*(values_seen+1)+16*n+4096;
  PERFORM scanipy_accepted_inputs.v1_require(cost<=2147483648/copies);
  PERFORM scanipy_accepted_inputs.v1_charge(6,cost*copies);
END $$;

CREATE FUNCTION scanipy_accepted_inputs.v1_lower_reserve(helper text, payloads bytea[],
  detector_count integer DEFAULT 0, rule_count integer DEFAULT 0)
RETURNS void LANGUAGE plpgsql SET search_path=pg_catalog,scanipy_accepted_inputs,pg_temp AS $$
DECLARE a CONSTANT bigint:=1048576; o CONSTANT bigint:=65536; h CONSTANT bigint:=16384;
  f bigint; scalar_bytes bigint; images bigint; hashes bigint; hashed_bytes bigint;
  tickets integer;
BEGIN
  PERFORM scanipy_accepted_inputs.v1_byte_array(payloads,3);
  PERFORM scanipy_accepted_inputs.v1_require(detector_count BETWEEN 0 AND 20000 AND rule_count BETWEEN 0 AND 20000);
  CASE helper
    WHEN 'create' THEN
      PERFORM scanipy_accepted_inputs.v1_require(cardinality(payloads)=2);
      f:=8*a; scalar_bytes:=4*a+4*h; images:=40*a+4*h; hashes:=5; hashed_bytes:=5*a+162; tickets:=1;
    WHEN 'register' THEN
      PERFORM scanipy_accepted_inputs.v1_require(cardinality(payloads)=3);
      f:=14*a; scalar_bytes:=4*a+8*h; images:=84*a+11*h; hashes:=6+detector_count+rule_count; hashed_bytes:=6*a+99; tickets:=2;
    WHEN 'begin' THEN
      PERFORM scanipy_accepted_inputs.v1_require(cardinality(payloads)=1);
      f:=78*a+o; scalar_bytes:=5*a+8*h; images:=61*a+9*h; hashes:=1; hashed_bytes:=octet_length(payloads[1])+30; tickets:=5;
    WHEN 'renew' THEN
      PERFORM scanipy_accepted_inputs.v1_require(cardinality(payloads)=0);
      f:=14*a; scalar_bytes:=5*a+12*h; images:=108*a+21*h; hashes:=0; hashed_bytes:=0; tickets:=3;
    WHEN 'fail' THEN
      PERFORM scanipy_accepted_inputs.v1_require(cardinality(payloads)=1 AND octet_length(payloads[1])<=o);
      f:=23*a+o; scalar_bytes:=11*a+17*h; images:=192*a+4*o+26*h; hashes:=3;
      hashed_bytes:=octet_length(payloads[1])+32; tickets:=6;
    WHEN 'finish' THEN
      PERFORM scanipy_accepted_inputs.v1_require(cardinality(payloads)=1 AND octet_length(payloads[1])<=o);
      f:=32*a+4*o+4096; scalar_bytes:=12*a+24*h; images:=208*a+8*o+16384+34*h;
      hashes:=2; hashed_bytes:=octet_length(payloads[1])+4096+69; tickets:=8;
    ELSE PERFORM scanipy_accepted_inputs.v1_require(false);
  END CASE;
  -- Fixed branch-complete maxima cover rejected replay paths and legacy guards.
  -- These reservations never represent executor probes, RSS or physical I/O.
  PERFORM scanipy_accepted_inputs.v1_charge(2,f);
  PERFORM scanipy_accepted_inputs.v1_charge(3,scalar_bytes+64::bigint*tickets*65537);
  PERFORM scanipy_accepted_inputs.v1_charge(4,images);
  PERFORM scanipy_accepted_inputs.v1_charge(5,tickets::bigint*65537);
  PERFORM scanipy_accepted_inputs.v1_charge(0,hashes);
  PERFORM scanipy_accepted_inputs.v1_charge(1,hashed_bytes);
END $$;

-- K must precede parsing a seal's request locator. Exact detector/rule counts
-- are available only after its scoped bundle is fetched; row/hash reservations
-- above therefore form a separate mandatory pre-delegate step. No refund.
CREATE FUNCTION scanipy_accepted_inputs.v1_lower_preflight(helper text,payloads bytea[])
RETURNS void LANGUAGE plpgsql SET search_path=pg_catalog,scanipy_accepted_inputs,pg_temp AS $$
DECLARE n bigint; v bigint; i integer; expected_count integer;
BEGIN
  expected_count:=CASE helper WHEN 'create' THEN 2 WHEN 'register' THEN 3
    WHEN 'begin' THEN 1 WHEN 'renew' THEN 0 WHEN 'fail' THEN 1 WHEN 'finish' THEN 1 END;
  PERFORM scanipy_accepted_inputs.v1_require(expected_count IS NOT NULL);
  PERFORM scanipy_accepted_inputs.v1_byte_array(payloads,3);
  PERFORM scanipy_accepted_inputs.v1_require(cardinality(payloads)=expected_count);
  FOR i IN 1..cardinality(payloads) LOOP
    n:=octet_length(payloads[i]);
    v:=scanipy_accepted_inputs.v1_lexical(payloads[i],1048576,1048576,1048576);
    IF helper IN ('fail','finish') THEN
      PERFORM scanipy_accepted_inputs.v1_require(n<=65536 AND v<=64);
    END IF;
    PERFORM scanipy_accepted_inputs.v1_concat_reserve(n,v);
    IF helper='create' AND i=1 THEN
      PERFORM scanipy_accepted_inputs.v1_concat_reserve(n+512,v+64,3);
    END IF;
  END LOOP;
  IF helper='finish' THEN PERFORM scanipy_accepted_inputs.v1_concat_reserve(4096,16); END IF;
END $$;

-- Frozen rows from the actual bound_rules owner. SQL performs independent
-- structural validation; accepting one of these rows is not model authority.
CREATE FUNCTION scanipy_accepted_inputs.v1_initial_models() RETURNS jsonb
LANGUAGE sql IMMUTABLE SET search_path=pg_catalog,scanipy_accepted_inputs,pg_temp AS $$
SELECT $models${"java.jdbc-execute-query/1":{"exceptional":{"continuation":"exit-unknown-exception","effects":["unknown-external-effect"],"result":"absent"},"kind":"external-call","language":"java","model_id":"java.jdbc-execute-query/1","normal":{"effects":["external-io","unknown-external-effect"],"result":"defined"},"operation":"external-api","preconditions":[{"evidence_kind":"checked","id":"java-declared-statement-receiver/1"},{"evidence_kind":"checked","id":"java-string-argument/1"},{"evidence_kind":"assumed","id":"java21-jdbc-contract/1"},{"evidence_kind":"checked","id":"terminal-selected-entry-call/1"}],"signature":{"parameters":["java.lang.String"],"receiver":"java.sql.Statement","result":"java.sql.ResultSet"},"symbol":{"member":"executeQuery","owner":"java.sql.Statement"},"target_platform_profile":"scanipy-target-java21-jdbc/1","transfer_authorization":{"propagation":[],"sanitization":[],"sink_inputs":[{"class_id":"injection","context_id":"sql-query-text","position":{"index":0,"kind":"argument"}}]}},"java.string-concat/1":{"exceptional":{"continuation":"exit-unknown-exception","effects":["resource-failure"],"result":"absent"},"kind":"builtin-operator","language":"java","model_id":"java.string-concat/1","normal":{"effects":["allocation"],"result":"defined"},"operation":"string-concat","preconditions":[{"evidence_kind":"assumed","id":"java-standard-string-semantics/1"},{"evidence_kind":"checked","id":"java-string-operands/1"}],"signature":{"parameters":["java.lang.String","java.lang.String"],"receiver":null,"result":"java.lang.String"},"symbol":null,"target_platform_profile":"scanipy-target-java21-jdbc/1","transfer_authorization":{"propagation":[{"from":{"index":0,"kind":"argument"},"to":{"index":0,"kind":"result"}},{"from":{"index":1,"kind":"argument"},"to":{"index":0,"kind":"result"}}],"sanitization":[],"sink_inputs":[]}},"python.os-system/1":{"exceptional":{"continuation":"exit-unknown-exception","effects":["unknown-external-effect"],"result":"absent"},"kind":"external-call","language":"python","model_id":"python.os-system/1","normal":{"effects":["external-io","external-process"],"result":"defined"},"operation":"external-api","preconditions":[{"evidence_kind":"checked","id":"python-direct-os-import/1"},{"evidence_kind":"checked","id":"python-exact-str-argument/1"},{"evidence_kind":"assumed","id":"python-no-external-binding-mutation/1"},{"evidence_kind":"checked","id":"python-no-local-binding-mutation/1"},{"evidence_kind":"assumed","id":"python-standard-os-implementation/1"},{"evidence_kind":"checked","id":"terminal-selected-entry-call/1"}],"signature":{"parameters":["python.exact-str"],"receiver":null,"result":"python.int"},"symbol":{"member":"system","owner":"os"},"target_platform_profile":"scanipy-target-cpython311-posix/1","transfer_authorization":{"propagation":[],"sanitization":[],"sink_inputs":[{"class_id":"injection","context_id":"posix-shell-command","position":{"index":0,"kind":"argument"}}]}},"python.string-concat/1":{"exceptional":{"continuation":"exit-unknown-exception","effects":["resource-failure"],"result":"absent"},"kind":"builtin-operator","language":"python","model_id":"python.string-concat/1","normal":{"effects":["allocation"],"result":"defined"},"operation":"string-concat","preconditions":[{"evidence_kind":"checked","id":"python-exact-str-operands/1"}],"signature":{"parameters":["python.exact-str","python.exact-str"],"receiver":null,"result":"python.exact-str"},"symbol":null,"target_platform_profile":"scanipy-target-cpython311-posix/1","transfer_authorization":{"propagation":[{"from":{"index":0,"kind":"argument"},"to":{"index":0,"kind":"result"}},{"from":{"index":1,"kind":"argument"},"to":{"index":0,"kind":"result"}}],"sanitization":[],"sink_inputs":[]}}}$models$::jsonb
$$;

CREATE FUNCTION scanipy_accepted_inputs.v1_keys(v jsonb, names text[]) RETURNS void
LANGUAGE plpgsql IMMUTABLE SET search_path=pg_catalog,scanipy_accepted_inputs,pg_temp AS $$
BEGIN
  PERFORM scanipy_accepted_inputs.v1_require(jsonb_typeof(v)='object' AND
    (SELECT array_agg(key ORDER BY key COLLATE "C") FROM jsonb_object_keys(v) key)=
    (SELECT array_agg(name ORDER BY name COLLATE "C") FROM unnest(names) name));
END $$;

CREATE FUNCTION scanipy_accepted_inputs.v1_position(v jsonb, is_result boolean) RETURNS void
LANGUAGE plpgsql IMMUTABLE SET search_path=pg_catalog,scanipy_accepted_inputs,pg_temp AS $$
BEGIN
  PERFORM scanipy_accepted_inputs.v1_keys(v,ARRAY['kind','index']);
  PERFORM scanipy_accepted_inputs.v1_shape(v->'index','"count"');
  PERFORM scanipy_accepted_inputs.v1_require(v->>'kind'=CASE WHEN is_result THEN 'result' ELSE 'argument' END
    AND (v->>'index')::bigint<=CASE WHEN is_result THEN 0 ELSE 255 END);
END $$;

CREATE FUNCTION scanipy_accepted_inputs.v1_bound_rule(rule_raw bytea,model_raw bytea,
  member jsonb,detector jsonb) RETURNS void
LANGUAGE plpgsql SET search_path=pg_catalog,scanipy_accepted_inputs,pg_temp AS $$
DECLARE rule jsonb; models jsonb; catalog jsonb; row record; clause record; selector jsonb;
  model jsonb; previous text; profiles jsonb; language text; selected_language text; primitive text;
  source_counts jsonb:='{"python":0,"java":0}'; sink_counts jsonb:='{"python":0,"java":0}';
  path text; parameter jsonb; requested jsonb; allowed jsonb;
BEGIN
  PERFORM scanipy_accepted_inputs.v1_require(rule_raw IS NOT NULL AND model_raw IS NOT NULL
    AND octet_length(rule_raw)<=262144 AND octet_length(model_raw)<=524288
    AND octet_length(rule_raw)+octet_length(model_raw)<=1048576);
  rule:=scanipy_accepted_inputs.v1_json(rule_raw,262144,false,50000,24);
  models:=scanipy_accepted_inputs.v1_json(model_raw,524288,false,50000,24);
  PERFORM scanipy_accepted_inputs.v1_keys(models,ARRAY['schema','target_platform_profiles','models']);
  PERFORM scanipy_accepted_inputs.v1_require(models->>'schema'='scanipy-operation-models/1'
    AND jsonb_typeof(models->'models')='array' AND jsonb_array_length(models->'models') BETWEEN 1 AND 128
    AND jsonb_typeof(models->'target_platform_profiles')='array'
    AND jsonb_array_length(models->'target_platform_profiles') BETWEEN 1 AND 2);
  catalog:=scanipy_accepted_inputs.v1_initial_models();
  FOR row IN SELECT value FROM jsonb_array_elements(models->'models') LOOP
    PERFORM scanipy_accepted_inputs.v1_require(jsonb_typeof(row.value)='object'
      AND jsonb_typeof(row.value->'model_id')='string' AND catalog ? (row.value->>'model_id')
      AND row.value=catalog->(row.value->>'model_id')
      AND (previous IS NULL OR (row.value->>'model_id') COLLATE "C">previous COLLATE "C"));
    previous:=row.value->>'model_id';
  END LOOP;
  SELECT jsonb_agg(value ORDER BY value) INTO profiles FROM
    (SELECT DISTINCT value->'target_platform_profile' AS value FROM jsonb_array_elements(models->'models')) q;
  PERFORM scanipy_accepted_inputs.v1_require(models->'target_platform_profiles'=profiles);
  PERFORM scanipy_accepted_inputs.v1_keys(rule,ARRAY['schema','semantics','spec_id','class_id','engine',
    'languages','projection_profile','model_artifact_digest','clauses']);
  PERFORM scanipy_accepted_inputs.v1_require(rule->>'schema'='scanipy-bound-rule-set/1'
    AND rule->>'semantics'='scanipy-scalar-ifds/1' AND rule->>'engine'='ifds'
    AND rule->>'projection_profile'='scanipy-java-python-scalar-flow/1'
    AND rule->'spec_id'=member->'rule_id' AND rule->'model_artifact_digest'=member->'model_raw_sha256'
    AND rule->'class_id'=detector->'class_id' AND rule->>'class_id'='injection'
    AND rule->'languages'=detector->'languages' AND jsonb_typeof(rule->'clauses')='array'
    AND jsonb_array_length(rule->'clauses') BETWEEN 1 AND 256,'content-mismatch');
  FOR clause IN SELECT value FROM jsonb_array_elements(rule->'clauses') LOOP
    primitive:=clause.value->>'primitive'; selector:=clause.value->'selector';
    PERFORM scanipy_accepted_inputs.v1_require(primitive IN ('source','sink','propagate','sanitize'));
    selected_language:=selector->>'language';
    PERFORM scanipy_accepted_inputs.v1_require(selected_language IN ('python','java')
      AND rule->'languages' ? selected_language);
    IF primitive='source' THEN
      PERFORM scanipy_accepted_inputs.v1_keys(clause.value,ARRAY['primitive','selector']);
      PERFORM scanipy_accepted_inputs.v1_keys(selector,ARRAY['kind','language','source_file','declaration','formal_index','parameter_types']);
      PERFORM scanipy_accepted_inputs.v1_require(selector->>'kind'='entry_parameter'
        AND jsonb_typeof(selector->'source_file')='string');
      path:=selector->>'source_file';
      PERFORM scanipy_accepted_inputs.v1_require(path<>'' AND octet_length(path)<=1024
        AND cardinality(string_to_array(path,'/'))<=32 AND position(chr(92) IN path)=0
        AND NOT EXISTS(SELECT 1 FROM unnest(string_to_array(path,'/')) p WHERE p IN ('','.','..'))
        AND NOT EXISTS(SELECT 1 FROM generate_series(1,length(path)) i
          WHERE ascii(substring(path FROM i FOR 1))<32 OR ascii(substring(path FROM i FOR 1)) BETWEEN 127 AND 159));
      PERFORM scanipy_accepted_inputs.v1_shape(selector->'formal_index','"count"');
      PERFORM scanipy_accepted_inputs.v1_require((selector->>'formal_index')::bigint<=255
        AND jsonb_typeof(selector->'declaration')='array' AND jsonb_array_length(selector->'declaration') BETWEEN 1 AND 32);
      FOR parameter IN SELECT value FROM jsonb_array_elements(selector->'declaration') LOOP
        PERFORM scanipy_accepted_inputs.v1_require(jsonb_typeof(parameter)='string'
          AND (parameter#>>'{}') ~ '^[A-Za-z_][A-Za-z0-9_]{0,127}$');
      END LOOP;
      IF selected_language='python' THEN
        PERFORM scanipy_accepted_inputs.v1_require(jsonb_array_length(selector->'declaration')=1
          AND selector->'parameter_types'='null'::jsonb AND right(path,3)='.py');
      ELSE
        PERFORM scanipy_accepted_inputs.v1_require(jsonb_typeof(selector->'parameter_types')='array'
          AND jsonb_array_length(selector->'parameter_types')<=256);
        FOR parameter IN SELECT value FROM jsonb_array_elements(selector->'parameter_types') LOOP
          PERFORM scanipy_accepted_inputs.v1_require(jsonb_typeof(parameter)='string' AND parameter#>>'{}'
            IN ('python.exact-str','python.int','java.lang.String','java.sql.Statement','java.sql.ResultSet'));
        END LOOP;
      END IF;
      source_counts:=jsonb_set(source_counts,ARRAY[selected_language],to_jsonb((source_counts->>selected_language)::integer+1));
    ELSE
      PERFORM scanipy_accepted_inputs.v1_keys(clause.value,CASE WHEN primitive='propagate'
        THEN ARRAY['primitive','selector','from','to'] ELSE ARRAY['primitive','selector','position','context_id'] END);
      PERFORM scanipy_accepted_inputs.v1_keys(selector,ARRAY['kind','language','model_id']);
      PERFORM scanipy_accepted_inputs.v1_require(selector->>'kind'='model' AND jsonb_typeof(selector->'model_id')='string');
      SELECT value INTO model FROM jsonb_array_elements(models->'models') WHERE value->'model_id'=selector->'model_id';
      PERFORM scanipy_accepted_inputs.v1_require(FOUND AND model->>'language'=selected_language);
      IF primitive='propagate' THEN
        PERFORM scanipy_accepted_inputs.v1_position(clause.value->'from',false);
        PERFORM scanipy_accepted_inputs.v1_position(clause.value->'to',true);
        requested:=jsonb_build_object('from',clause.value->'from','to',clause.value->'to');
        allowed:=model->'transfer_authorization'->'propagation';
      ELSE
        PERFORM scanipy_accepted_inputs.v1_position(clause.value->'position',primitive='sanitize');
        PERFORM scanipy_accepted_inputs.v1_require(clause.value->>'context_id'=
          CASE WHEN selected_language='python' THEN 'posix-shell-command' ELSE 'sql-query-text' END);
        requested:=jsonb_build_object('position',clause.value->'position','class_id',rule->'class_id','context_id',clause.value->'context_id');
        allowed:=model->'transfer_authorization'->CASE WHEN primitive='sink' THEN 'sink_inputs' ELSE 'sanitization' END;
        IF primitive='sink' THEN
          sink_counts:=jsonb_set(sink_counts,ARRAY[selected_language],to_jsonb((sink_counts->>selected_language)::integer+1));
        END IF;
      END IF;
      PERFORM scanipy_accepted_inputs.v1_require(EXISTS(SELECT 1 FROM jsonb_array_elements(allowed) value WHERE value=requested));
    END IF;
  END LOOP;
  FOR language IN SELECT jsonb_array_elements_text(rule->'languages') LOOP
    PERFORM scanipy_accepted_inputs.v1_require((source_counts->>language)::integer>0 AND (sink_counts->>language)::integer>0);
  END LOOP;
END $$;

CREATE FUNCTION scanipy_accepted_inputs.v1_bundle(spec bytea,detectors bytea[],rules bytea[])
RETURNS TABLE(manifest jsonb,model_blobs bytea[],content_bytes bytea,content_digest bytea)
LANGUAGE plpgsql SET search_path=pg_catalog,scanipy_accepted_inputs,pg_temp AS $$
DECLARE spec_parts bytea[]; total bigint; item record; rule record; detector jsonb; model_index integer;
  d integer:=0; r integer:=0; model_raw bytea; descriptor_bytes bytea;
  detector_hashes jsonb:='[]'; rule_hashes jsonb:='[]'; actual bytea;
BEGIN
  PERFORM scanipy_accepted_inputs.v1_require(spec IS NOT NULL AND octet_length(spec)<=1048576);
  total:=octet_length(spec)::bigint+scanipy_accepted_inputs.v1_byte_array(detectors)+scanipy_accepted_inputs.v1_byte_array(rules);
  PERFORM scanipy_accepted_inputs.v1_require(total<=1048576 AND cardinality(detectors)>0 AND cardinality(rules)>0);
  spec_parts:=scanipy_accepted_inputs.v1_frame_parts(spec,'scanipy-accepted-spec-set/1',1048576);
  manifest:=scanipy_accepted_inputs.v1_document(spec_parts[1],'scanipy-accepted-s-manifest/1');
  PERFORM scanipy_accepted_inputs.v1_require(cardinality(spec_parts)=jsonb_array_length(manifest->'models')+1
    AND cardinality(detectors)=jsonb_array_length(manifest->'detectors')
    AND cardinality(rules)=(SELECT sum(jsonb_array_length(value->'rules')) FROM jsonb_array_elements(manifest->'detectors')));
  model_blobs:=spec_parts[2:cardinality(spec_parts)];
  FOR item IN SELECT value,ordinality FROM jsonb_array_elements(manifest->'models') WITH ORDINALITY LOOP
    PERFORM scanipy_accepted_inputs.v1_require(scanipy_accepted_inputs.v1_hash(model_blobs[item.ordinality::integer])=
      decode(item.value->>'raw_sha256','hex'),'content-mismatch');
  END LOOP;
  FOR item IN SELECT value FROM jsonb_array_elements(manifest->'detectors') LOOP
    d:=d+1; actual:=scanipy_accepted_inputs.v1_hash(detectors[d]);
    PERFORM scanipy_accepted_inputs.v1_require(actual=decode(item.value->>'detector_sha256','hex'),'content-mismatch');
    detector_hashes:=detector_hashes||jsonb_build_array(encode(actual,'hex'));
    detector:=scanipy_accepted_inputs.v1_document(detectors[d],'scanipy-accepted-detector/1',false);
    PERFORM scanipy_accepted_inputs.v1_require(detector->'id'=item.value->'detector_id'
      AND detector->'version'=item.value->'detector_version' AND detector->'class_id'=item.value->'class_id'
      AND detector->'engine'=item.value->'engine' AND detector->'profiles'=item.value->'language_profiles'
      AND detector->'rule_ids'=(SELECT jsonb_agg(value->'rule_id') FROM jsonb_array_elements(item.value->'rules')),'content-mismatch');
    FOR rule IN SELECT value FROM jsonb_array_elements(item.value->'rules') LOOP
      r:=r+1; actual:=scanipy_accepted_inputs.v1_hash(rules[r]);
      PERFORM scanipy_accepted_inputs.v1_require(actual=decode(rule.value->>'raw_sha256','hex'),'content-mismatch');
      rule_hashes:=rule_hashes||jsonb_build_array(encode(actual,'hex'));
      SELECT ordinality::integer INTO model_index FROM jsonb_array_elements(manifest->'models') WITH ORDINALITY
        WHERE value->'artifact_id'=rule.value->'model_artifact_id' AND value->'raw_sha256'=rule.value->'model_raw_sha256';
      PERFORM scanipy_accepted_inputs.v1_require(FOUND,'content-mismatch');
      model_raw:=model_blobs[model_index];
      descriptor_bytes:=scanipy_accepted_inputs.v1_bytes(jsonb_build_object('schema','scanipy-rule-semantics-binding/1',
        'rule_raw_sha256',rule.value->'raw_sha256','model_raw_sha256',rule.value->'model_raw_sha256',
        'semantics',rule.value->'semantics','projection_profile',rule.value->'projection_profile'));
      PERFORM scanipy_accepted_inputs.v1_require(scanipy_accepted_inputs.v1_hash(descriptor_bytes,'scanipy-rule-semantics-binding/1')=
        decode(rule.value->>'semantic_descriptor_digest','hex'),'content-mismatch');
      PERFORM scanipy_accepted_inputs.v1_bound_rule(rules[r],model_raw,rule.value,detector);
    END LOOP;
  END LOOP;
  content_bytes:=scanipy_accepted_inputs.v1_bytes(jsonb_build_object('schema','scanipy-execution/accepted-content/1',
    'spec_sha256',encode(scanipy_accepted_inputs.v1_hash(spec),'hex'),
    'detector_sha256s',detector_hashes,'rule_sha256s',rule_hashes),1048576);
  content_digest:=scanipy_accepted_inputs.v1_hash(content_bytes,'scanipy-execution/accepted-content/1');
  RETURN NEXT;
END $$;
