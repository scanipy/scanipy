"""Controlled codec checks; no fixture establishes accepted model authority."""

import hashlib
import json
from dataclasses import FrozenInstanceError, asdict, fields, replace
from pathlib import Path

import pytest

from analysis.ifds.bound_rules import (
    BoundRule,
    BoundRuleError,
    QualifiedRuleKey,
    ScalarLimits,
    checked_limits,
    decode_bound_rule,
    decode_bounded_json,
    decode_qualified_rule_key,
    encode_qualified_rule_key,
)

pytestmark = pytest.mark.unit


@pytest.fixture
def rule_key():
    return QualifiedRuleKey(
        registry_id="11111111-1111-4111-8111-111111111111",
        bundle_id="22222222-2222-4222-8222-222222222222",
        scope="global",
        org_id=None,
        S_version="1.0.0",
        accepted_content_digest="a" * 64,
        detector_id="controlled-detector",
        detector_version="1.0.0",
        detector_raw_sha256="b" * 64,
        rule_id="controlled-rule",
        rule_artifact_id="controlled-rule-artifact",
        rule_artifact_version="1.0.0",
        rule_raw_sha256="c" * 64,
        model_artifact_id="controlled-model-artifact",
        model_artifact_version="1.0.0",
        model_raw_sha256="d" * 64,
        semantic_descriptor_digest="e" * 64,
    )


def test_qualified_key_round_trip_is_exact_canonical(rule_key):
    encoded = encode_qualified_rule_key(rule_key)
    assert decode_qualified_rule_key(encoded) == rule_key
    assert (
        encoded
        == json.dumps(
            asdict(rule_key), sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode()
    )
    assert not encoded.endswith(b"\n")


@pytest.mark.parametrize(
    "change",
    [
        {"scope": "customer"},
        {"org_id": "bad"},
        {"scope": "global", "org_id": "33333333-3333-4333-8333-333333333333"},
        {"registry_id": "11111111111141118111111111111111"},
        {"detector_id": "../model"},
        {"detector_id": "☃"},
        {"rule_id": "a" * 129},
        {"accepted_content_digest": "A" * 64},
        {"model_raw_sha256": "sha256:" + "d" * 64},
        {"schema": "scanipy-qualified-rule/2"},
    ],
)
def test_key_constructor_rejects_ambiguous_or_invalid_identity(rule_key, change):
    with pytest.raises(BoundRuleError):
        replace(rule_key, **change)


@pytest.mark.parametrize(
    "version",
    [
        "1.0",
        "01.0.0",
        "1.0.0-rc1",
        "1.0.0+build",
        "-1.0.0",
        "1.0.2147483648",
        "1.0.true",
        True,
        1,
        "1.0.0\n",
    ],
)
def test_versions_are_exact_bounded_numeric_labels(rule_key, version):
    with pytest.raises(BoundRuleError):
        replace(rule_key, S_version=version)


def test_customer_scope_is_explicit(rule_key):
    customer = replace(rule_key, scope="customer", org_id="33333333-3333-4333-8333-333333333333")
    assert decode_qualified_rule_key(encode_qualified_rule_key(customer)) == customer


@pytest.mark.parametrize(
    "mutation",
    [
        "duplicate",
        "unknown",
        "missing",
        "whitespace",
        "trailing",
        "float",
        "nul",
        "surrogate",
        "depth",
        "large",
        "bytearray",
    ],
)
def test_key_wire_fails_closed(rule_key, mutation):
    raw = encode_qualified_rule_key(rule_key)
    row = asdict(rule_key)
    if mutation == "duplicate":
        raw = b'{"scope":"global",' + raw[1:]
    elif mutation == "unknown":
        row["accepted"] = True
        raw = json.dumps(row).encode()
    elif mutation == "missing":
        del row["schema"]
        raw = json.dumps(row).encode()
    elif mutation == "whitespace":
        raw = json.dumps(row, indent=2).encode()
    elif mutation == "trailing":
        raw += b"\n"
    elif mutation == "float":
        raw = raw.replace(b'"1.0.0"', b"1.0", 1)
    elif mutation == "nul":
        raw = raw.replace(b"controlled-rule", b"controlled\\u0000rule", 1)
    elif mutation == "surrogate":
        raw = raw.replace(b"controlled-rule", b"controlled\\ud800rule", 1)
    elif mutation == "depth":
        raw = b"[" * 5 + b"0" + b"]" * 5
    elif mutation == "large":
        raw += b" " * 16384
    elif mutation == "bytearray":
        raw = bytearray(raw)
    with pytest.raises(BoundRuleError):
        decode_qualified_rule_key(raw)


def test_key_encoder_revalidates_even_frozen_objects(rule_key):
    object.__setattr__(rule_key, "scope", "invalid")
    with pytest.raises(BoundRuleError):
        encode_qualified_rule_key(rule_key)


def test_key_constructor_checks_size_before_encoding(rule_key):
    # Small malformed-Unicode sentinel proves the length guard wins BEFORE
    # encode; no enormous temporary string/allocation is needed for the test.
    with pytest.raises(BoundRuleError, match=r"^string-limit$"):
        replace(rule_key, detector_id="a" * 128 + "\ud800")


def test_key_encoder_checks_size_before_encoding(rule_key):
    object.__setattr__(rule_key, "detector_id", "a" * 128 + "\ud800")
    with pytest.raises(BoundRuleError, match=r"^string-limit$"):
        encode_qualified_rule_key(rule_key)


def test_key_encoder_rejects_subclasses_without_callbacks(rule_key):
    class Impostor:
        def __getattr__(self, name):
            raise AssertionError("must not inspect a foreign object")

    with pytest.raises(BoundRuleError):
        encode_qualified_rule_key(Impostor())


@pytest.mark.parametrize("definition", fields(ScalarLimits))
def test_all_limits_are_lower_only_positive_exact_ints(definition):
    ceilings = ScalarLimits()
    assert replace(ceilings, **{definition.name: 1})
    for value in (0, -1, True, 1.0, definition.default + 1):
        with pytest.raises(BoundRuleError):
            replace(ceilings, **{definition.name: value})


def test_rule_key_identity_does_not_collapse_different_artifacts(rule_key):
    another = replace(rule_key, detector_id="another-detector")
    assert another != rule_key
    assert encode_qualified_rule_key(another) != encode_qualified_rule_key(rule_key)


def test_maximum_version_component_is_accepted(rule_key):
    key = replace(rule_key, S_version="2147483647.2147483647.2147483647")
    assert decode_qualified_rule_key(encode_qualified_rule_key(key)) == key


@pytest.mark.parametrize("raw", [b"[" * 5, b"[0,0,0,0]", b'"' + b"a" * 30])
def test_json_limits_precede_parser_allocation(monkeypatch, raw):
    def forbidden(*args, **kwargs):
        raise AssertionError("parser must not run for preflight-rejected input")

    monkeypatch.setattr("analysis.ifds.bound_rules.json.loads", forbidden)
    with pytest.raises(BoundRuleError):
        decode_bounded_json(raw, max_bytes=128, max_depth=4, max_values=4, max_string_bytes=4)


@pytest.mark.parametrize(
    "raw",
    [
        b"1.0",
        b"NaN",
        b"Infinity",
        b"9223372036854775808",
        b"-9223372036854775809",
        b'{"x":1,"x":2}',
        b'"\\ud800"',
        b'"\\u0000"',
    ],
)
def test_bounded_json_rejects_unsupported_domain(raw):
    with pytest.raises(BoundRuleError):
        decode_bounded_json(raw, max_bytes=128, max_depth=4, max_values=20, max_string_bytes=32)


def test_escaped_string_bound_uses_decoded_utf8_bytes():
    raw = b'"' + b"\\u0061" * 4 + b'"'
    assert (
        decode_bounded_json(raw, max_bytes=64, max_depth=4, max_values=2, max_string_bytes=4)
        == "aaaa"
    )
    with pytest.raises(BoundRuleError):
        decode_bounded_json(raw, max_bytes=64, max_depth=4, max_values=2, max_string_bytes=3)


def test_frozen_limits_are_revalidated():
    limits = ScalarLimits()
    object.__setattr__(limits, "max_files", 17)
    with pytest.raises(BoundRuleError):
        checked_limits(limits)
    with pytest.raises(BoundRuleError):
        checked_limits(None)


_FIXTURE = Path(__file__).parents[1] / "fixtures" / "semantic_g1"


def _documents():
    return (
        json.loads((_FIXTURE / "rules.json").read_bytes()),
        json.loads((_FIXTURE / "operation_models.json").read_bytes()),
    )


def _rebound(key, rule, models):
    model_bytes = json.dumps(models, indent=2).encode()
    model_hash = hashlib.sha256(model_bytes).hexdigest()
    rule["model_artifact_digest"] = model_hash
    rule_bytes = json.dumps(rule, indent=2).encode()
    return (
        rule_bytes,
        model_bytes,
        replace(
            key,
            rule_id=rule["spec_id"],
            rule_raw_sha256=hashlib.sha256(rule_bytes).hexdigest(),
            model_raw_sha256=model_hash,
        ),
    )


def test_bound_rule_preserves_actual_fixture_bytes(rule_key):
    rules = (_FIXTURE / "rules.json").read_bytes()
    models = (_FIXTURE / "operation_models.json").read_bytes()
    key = replace(
        rule_key,
        rule_id="semantic-g1-injection",
        rule_raw_sha256=hashlib.sha256(rules).hexdigest(),
        model_raw_sha256=hashlib.sha256(models).hexdigest(),
    )
    bound = decode_bound_rule(rules, models, key=key, language="python", limits=ScalarLimits())
    assert bound.rule_bytes is rules and bound.model_bytes is models
    assert bound.key == key and bound.language == "python"
    assert bound.rule_document.get("class_id") == "injection"
    assert bound.rule_document.get("languages").values == ("python", "java")
    assert len(bound.rule_document.get("clauses").values) == 4
    assert len(bound.model_document.get("models").values) == 4


@pytest.mark.parametrize(
    "path,value",
    [
        (("schema",), "scanipy-operation-models/2"),
        (("models", 0, "signature", "receiver"), None),
        (("models", 2, "preconditions", 2, "evidence_kind"), "checked"),
        (("models", 2, "normal", "effects"), []),
        (("models", 2, "exceptional", "effects"), []),
        (("models", 2, "symbol", "owner"), "custom.os"),
        (("models", 3, "transfer_authorization", "propagation", 1, "from", "index"), True),
        (("models", 3, "signature", "parameters"), ["python.exact-str"]),
        (("models", 3, "model_id"), "custom.concat/1"),
        (("models", 3, "preconditions"), []),
    ],
)
def test_changed_model_meaning_fails_even_with_rebound_hashes(rule_key, path, value):
    rule, models = _documents()
    target = models
    for component in path[:-1]:
        target = target[component]
    target[path[-1]] = value
    rule_bytes, model_bytes, key = _rebound(rule_key, rule, models)
    with pytest.raises(BoundRuleError):
        decode_bound_rule(
            rule_bytes, model_bytes, key=key, language="python", limits=ScalarLimits()
        )


@pytest.mark.parametrize(
    "mutation",
    [
        "unknown",
        "missing",
        "duplicate-model",
        "model-order",
        "empty-models",
        "unused-profile",
        "clauses-empty",
        "source-missing",
        "sink-missing",
        "source-bool",
        "source-path",
        "source-name",
        "source-parameter-types",
        "model-language",
        "sink-position",
        "sink-bool",
        "sink-context",
        "unknown-primitive",
        "language-missing",
        "duplicate-language",
        "engine",
        "class",
        "unknown-rule-schema",
        "unknown-selector",
    ],
)
def test_closed_rules_and_all_model_members_are_validated(rule_key, mutation):
    rule, models = _documents()
    if mutation == "unknown":
        rule["accepted"] = True
    elif mutation == "missing":
        del rule["semantics"]
    elif mutation == "duplicate-model":
        models["models"].append(models["models"][0])
    elif mutation == "model-order":
        models["models"].reverse()
    elif mutation == "empty-models":
        models["models"] = []
    elif mutation == "unused-profile":
        models["models"] = models["models"][2:]
    elif mutation == "clauses-empty":
        rule["clauses"] = []
    elif mutation == "source-missing":
        rule["clauses"] = rule["clauses"][1:]
    elif mutation == "sink-missing":
        del rule["clauses"][1]
    elif mutation == "source-bool":
        rule["clauses"][0]["selector"]["formal_index"] = True
    elif mutation == "source-path":
        rule["clauses"][0]["selector"]["source_file"] = "../source.py"
    elif mutation == "source-name":
        rule["clauses"][0]["selector"]["declaration"] = ["雪"]
    elif mutation == "source-parameter-types":
        rule["clauses"][0]["selector"]["parameter_types"] = []
    elif mutation == "model-language":
        rule["clauses"][1]["selector"]["language"] = "java"
    elif mutation == "sink-position":
        rule["clauses"][1]["position"]["index"] = 1
    elif mutation == "sink-bool":
        rule["clauses"][1]["position"]["index"] = False
    elif mutation == "sink-context":
        rule["clauses"][1]["context_id"] = "sql-query-text"
    elif mutation == "unknown-primitive":
        rule["clauses"][0]["primitive"] = "execute"
    elif mutation == "language-missing":
        rule["languages"] = ["java"]
    elif mutation == "duplicate-language":
        rule["languages"] = ["python", "python"]
    elif mutation == "engine":
        rule["engine"] = "ide"
    elif mutation == "class":
        rule["class_id"] = "memory-safety"
    elif mutation == "unknown-rule-schema":
        rule["schema"] = "scanipy-bound-rule-set/2"
    elif mutation == "unknown-selector":
        rule["clauses"][0]["selector"]["callback"] = "eval"
    rules, model_bytes, key = _rebound(rule_key, rule, models)
    with pytest.raises(BoundRuleError):
        decode_bound_rule(rules, model_bytes, key=key, language="python", limits=ScalarLimits())


def test_duplicate_source_clauses_preserve_original_ordinals(rule_key):
    rule, models = _documents()
    rule["clauses"].append(rule["clauses"][0])
    rules, model_bytes, key = _rebound(rule_key, rule, models)
    bound = decode_bound_rule(rules, model_bytes, key=key, language="python", limits=ScalarLimits())
    clauses = bound.rule_document.get("clauses").values
    assert len(clauses) == 5 and clauses[0] == clauses[4]


@pytest.mark.parametrize("primitive", ["propagate", "sanitize"])
def test_unauthorized_transfers_fail_without_requiring_a_matching_site(rule_key, primitive):
    rule, models = _documents()
    clause = {
        "primitive": primitive,
        "selector": {"kind": "model", "language": "python", "model_id": "python.os-system/1"},
    }
    if primitive == "propagate":
        clause.update(
            {"from": {"kind": "argument", "index": 0}, "to": {"kind": "result", "index": 0}}
        )
    else:
        clause.update(
            {"position": {"kind": "result", "index": 0}, "context_id": "posix-shell-command"}
        )
    rule["clauses"].append(clause)
    rules, model_bytes, key = _rebound(rule_key, rule, models)
    with pytest.raises(BoundRuleError):
        decode_bound_rule(rules, model_bytes, key=key, language="python", limits=ScalarLimits())


def test_rule_and_model_hashes_bind_actual_raw_bytes(rule_key):
    rule, models = _documents()
    rules, model_bytes, key = _rebound(rule_key, rule, models)
    for altered_rules, altered_models in ((rules + b" ", model_bytes), (rules, model_bytes + b" ")):
        with pytest.raises(BoundRuleError):
            decode_bound_rule(
                altered_rules, altered_models, key=key, language="python", limits=ScalarLimits()
            )


def test_bound_rule_does_not_retain_mutable_input_aliases(rule_key):
    rule, models = _documents()
    rules, model_bytes, key = _rebound(rule_key, rule, models)
    bound = decode_bound_rule(rules, model_bytes, key=key, language="python", limits=ScalarLimits())
    rule["class_id"] = "secrets"
    models["models"].clear()
    assert bound.rule_document.get("class_id") == "injection"
    assert len(bound.model_document.get("models").values) == 4


def test_positional_signatures_and_declaration_components_may_repeat(rule_key):
    rule, models = _documents()
    rule["clauses"][2]["selector"]["declaration"] = ["same", "same", "run"]
    rule["clauses"][2]["selector"]["parameter_types"] = ["java.lang.String"] * 2
    rules, model_bytes, key = _rebound(rule_key, rule, models)
    bound = decode_bound_rule(rules, model_bytes, key=key, language="java", limits=ScalarLimits())
    assert bound.language == "java"  # Decoding is not Java execution permission.
    concat = bound.model_document.get("models").values[3]
    assert concat.get("signature").get("parameters").values == ("python.exact-str",) * 2
    assert bound.rule_document.get("clauses").values[2].get("selector").get(
        "declaration"
    ).values == ("same", "same", "run")


@pytest.mark.parametrize("index", [0, 1])
def test_only_exact_authorized_concat_propagation_decodes(rule_key, index):
    rule, models = _documents()
    rule["clauses"].append(
        {
            "primitive": "propagate",
            "selector": {
                "kind": "model",
                "language": "python",
                "model_id": "python.string-concat/1",
            },
            "from": {"kind": "argument", "index": index},
            "to": {"kind": "result", "index": 0},
        }
    )
    rules, model_bytes, key = _rebound(rule_key, rule, models)
    bound = decode_bound_rule(rules, model_bytes, key=key, language="python", limits=ScalarLimits())
    assert len(bound.rule_document.get("clauses").values) == 5


@pytest.mark.parametrize(
    "limit,value",
    [
        ("max_rule_bytes", 1),
        ("max_model_bytes", 1),
        ("max_accepted_bytes", 1),
        ("max_clauses", 3),
        ("max_models", 3),
        ("max_rule_json_depth", 1),
        ("max_rule_json_values", 5),
        ("max_rule_string_bytes", 8),
        ("max_path_bytes", 4),
    ],
)
def test_decoder_enforces_lowered_trusted_limits(rule_key, limit, value):
    rule, models = _documents()
    rules, model_bytes, key = _rebound(rule_key, rule, models)
    with pytest.raises(BoundRuleError):
        decode_bound_rule(
            rules,
            model_bytes,
            key=key,
            language="python",
            limits=replace(ScalarLimits(), **{limit: value}),
        )


@pytest.mark.parametrize(
    "path",
    [
        "/a.py",
        "a//b.py",
        "./a.py",
        "a/../b.py",
        "a\\b.py",
        "a\tb.py",
        "a\x7fb.py",
        "a\x85b.py",
        "a.py/",
        "a.java",
    ],
)
def test_source_selectors_reject_unsafe_or_non_python_paths(rule_key, path):
    rule, models = _documents()
    rule["clauses"][0]["selector"]["source_file"] = path
    rules, model_bytes, key = _rebound(rule_key, rule, models)
    with pytest.raises(BoundRuleError):
        decode_bound_rule(rules, model_bytes, key=key, language="python", limits=ScalarLimits())


@pytest.mark.parametrize("mutation", ["key", "rule-type", "model-type", "language", "limits"])
def test_bound_rule_constructor_repeats_validation(rule_key, mutation):
    rule, models = _documents()
    rules, model_bytes, key = _rebound(rule_key, rule, models)
    arguments = {
        "key": key,
        "rule_bytes": rules,
        "model_bytes": model_bytes,
        "language": "python",
        "limits": ScalarLimits(),
    }
    if mutation == "key":
        arguments["key"] = replace(key, rule_id="other-rule")
    elif mutation == "rule-type":
        arguments["rule_bytes"] = bytearray(rules)
    elif mutation == "model-type":
        arguments["model_bytes"] = bytearray(model_bytes)
    elif mutation == "language":
        arguments["language"] = "javascript"
    else:
        arguments["limits"] = object()
    with pytest.raises(BoundRuleError):
        BoundRule(**arguments)


def test_qualified_rule_isolation_is_not_collapsed_by_identical_site_and_ordinal(rule_key):
    rule, models = _documents()
    rules, model_bytes, key = _rebound(rule_key, rule, models)
    first = decode_bound_rule(rules, model_bytes, key=key, language="python", limits=ScalarLimits())
    other_key = replace(key, detector_id="different-detector", rule_artifact_id="other-member")
    second = decode_bound_rule(
        rules, model_bytes, key=other_key, language="python", limits=ScalarLimits()
    )
    assert (
        first.rule_document.get("clauses").values[0]
        == second.rule_document.get("clauses").values[0]
    )
    assert first.key != second.key
    assert first != second
    with pytest.raises(FrozenInstanceError):
        first.key = second.key


@pytest.mark.parametrize("artifact", ["rule", "model"])
@pytest.mark.parametrize("malformation", ["duplicate", "unknown", "floating", "trailing"])
def test_actual_artifact_decoder_rejects_malformed_rebound_json(rule_key, artifact, malformation):
    rule, models = _documents()
    rules, model_bytes, key = _rebound(rule_key, rule, models)
    raw = rules if artifact == "rule" else model_bytes
    if malformation == "duplicate":
        raw = b'{"schema":"duplicate",' + raw[1:]
    elif malformation == "unknown":
        raw = b'{"unexpected":null,' + raw[1:]
    elif malformation == "floating":
        raw = b'{"unexpected":1.0,' + raw[1:]
    else:
        raw += b"{}"
    if artifact == "rule":
        rules = raw
        key = replace(key, rule_raw_sha256=hashlib.sha256(raw).hexdigest())
    else:
        model_bytes = raw
        key = replace(key, model_raw_sha256=hashlib.sha256(raw).hexdigest())
    with pytest.raises(BoundRuleError):
        decode_bound_rule(rules, model_bytes, key=key, language="python", limits=ScalarLimits())
