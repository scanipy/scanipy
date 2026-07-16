"""Direct unit coverage for ``services/scan/http/serde.py``'s JSON-decode
boundary — narrower and faster than driving the same failure mode through the
full FastAPI app (see ``tests/unit/test_deploy19_http_adapter.py``'s
``test_deeply_nested_json_callback_body_400_not_500`` for the end-to-end leg).
"""

from __future__ import annotations

import sys

import pytest

from services.scan.api import InvalidInputError
from services.scan.http.serde import parse_job_status_report, parse_scan_request


@pytest.mark.unit
def test_deeply_nested_json_raises_invalid_input_not_recursion_error() -> None:
    """A pathologically deep JSON document must surface as
    :class:`InvalidInputError` (-> 400 invalid_input), never let a raw
    ``RecursionError`` escape ``_load_json_object``'s contract of "ANY
    malformation -> InvalidInputError"."""
    depth = sys.getrecursionlimit() + 500
    deeply_nested = (b"[" * depth) + (b"]" * depth)

    with pytest.raises(InvalidInputError):
        parse_job_status_report(deeply_nested)

    with pytest.raises(InvalidInputError):
        parse_scan_request(deeply_nested)


@pytest.mark.unit
def test_ordinary_malformed_json_still_raises_invalid_input() -> None:
    """Non-regression: the pre-existing ``ValueError``/``UnicodeDecodeError``
    malformation paths are unaffected by the added ``RecursionError`` catch."""
    with pytest.raises(InvalidInputError):
        parse_job_status_report(b"{not valid json")

    with pytest.raises(InvalidInputError):
        parse_job_status_report(b"\x80\x81\x82 not valid utf-8")
