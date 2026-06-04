"""CLI entrypoint: ``python -m services.staging`` regenerates the staging table.

Writes ``docs/cross-cutting/DOC-STAGING-STATUS.md`` from the current machine
verdicts (CMP-CI-01 / WBS §21-L9). Kept separate from ``status_table`` so the
``-m`` invocation does not double-import the module (the ``runpy`` warning that
``python -m services.staging.status_table`` triggers via the package re-exports).
"""

from __future__ import annotations

from services.staging.status_table import main

if __name__ == "__main__":
    main()
