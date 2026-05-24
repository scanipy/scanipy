"""CMP-SCM-01 — SCM integration package.

Public surface: the provider-neutral `SCMConnector` ABC, its value types, the
error hierarchy, and the conformance suite every concrete connector must pass.
"""

from __future__ import annotations

from integrations.scm.base import (
    CloneMetadata,
    RepoRef,
    SCMAuthError,
    SCMAuthMode,
    SCMConnector,
    SCMCredentials,
    SCMError,
    SCMNotFoundError,
    SCMRateLimitError,
    SCMSignatureMismatch,
    SCMTransientError,
    WebhookSubscription,
)
from integrations.scm.conformance import (
    CONFORMANCE_OPERATIONS,
    ConformanceFailure,
    ConformanceReport,
    run_conformance_suite,
)

__all__ = [
    "CONFORMANCE_OPERATIONS",
    "CloneMetadata",
    "ConformanceFailure",
    "ConformanceReport",
    "RepoRef",
    "SCMAuthError",
    "SCMAuthMode",
    "SCMConnector",
    "SCMCredentials",
    "SCMError",
    "SCMNotFoundError",
    "SCMRateLimitError",
    "SCMSignatureMismatch",
    "SCMTransientError",
    "WebhookSubscription",
    "run_conformance_suite",
]
