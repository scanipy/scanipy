"""Backwards-compatibility shim for the v2 GitHub helper. AC-SCM-02c.

`search_repositories` is the v2 public symbol; legacy callers
(`scanipy --query … --run-semgrep`) continue to import it from this path. The
implementation now delegates to `GitHubConnector.list_repos_tiered_star`
(DOC-CMP-SCM-02 §3.5), but the public name, signature shape, and synchronous
return shape are preserved so a v2 caller observes no behavioural difference.

The exact captured v2 parameter list is part of the `CLAR-SCM-01` baseline; the
*existence and shape* contract (a callable at this import path that returns the
tiered-star repository listing) is fully specified by DOC §3.5 and is what
`TST-AC-SCM-02c` exercises. This module threads **no** provenance fields and
emits no findings (it is upstream of the provenance chain; RULE-6 non-touch).
"""

from __future__ import annotations

import asyncio
from collections.abc import Sequence
from typing import TYPE_CHECKING, Any

from integrations.scm.github import GitHubConnector

if TYPE_CHECKING:
    from integrations.scm.base import RepoRef

__all__ = ["GitHubConnector", "search_repositories"]


def search_repositories(
    query: str,
    *,
    connector: GitHubConnector,
    star_tiers: tuple[int, ...] = (1000, 100, 10, 0),
) -> list[RepoRef]:
    """Tiered-star repository search (v2-compatible shim). AC-SCM-02c.

    Caller-transparent re-export delegating to
    `GitHubConnector.list_repos_tiered_star`. Drives the connector's async
    generator to exhaustion and returns the materialised list, preserving the
    v2 synchronous list-return shape.

    Args:
        query: the GitHub search query (the v2 `--query` value).
        connector: an initialised `GitHubConnector` providing the transport.
        star_tiers: descending star bands to walk (DOC §3.3 default).

    Returns:
        The repositories discovered across the star tiers, highest tier first.
    """

    async def _collect() -> list[RepoRef]:
        results: list[RepoRef] = []
        async for ref in connector.list_repos_tiered_star(query=query, star_tiers=star_tiers):
            results.append(ref)
        return results

    return asyncio.run(_collect())


def _v2_argv_shim(argv: Sequence[str]) -> Any:  # noqa: ANN401 — legacy untyped surface
    """Placeholder for the v2 CLI argv adapter (shape pending CLAR-SCM-01).

    The v2 `scanipy --query … --run-semgrep` entrypoint wired argv through to
    `search_repositories`; the precise argv contract is part of the CLAR-SCM-01
    baseline capture. Left unimplemented rather than guessed (RULE-4).
    """
    raise NotImplementedError("v2 argv adapter pending CLAR-SCM-01 baseline capture")
