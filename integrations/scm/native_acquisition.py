"""Explicit native Git unavailability until bounded source acquisition exists.

Contract: docs/bhmea/GIT-SOURCE-ACQUISITION.md. Trusted injected Python runners
are test/application collaborators, not a sanctioned production safety profile.
"""

from typing import NoReturn

from integrations.scm.base import SCMError

NATIVE_GIT_UNAVAILABLE_REASON = (
    "Native Git acquisition is unavailable; a separately reviewed bounded "
    "source-capture producer is required"
)


class NativeGitAcquisitionUnavailable(SCMError):  # noqa: N818 -- explicit unavailability category
    """The unsafe default acquisition route is disabled, not retryable I/O."""


def refuse_native_git_acquisition() -> NoReturn:
    """Refuse without inspecting or disclosing any source/credential input."""
    raise NativeGitAcquisitionUnavailable(NATIVE_GIT_UNAVAILABLE_REASON)
