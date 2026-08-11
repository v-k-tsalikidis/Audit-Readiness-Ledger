"""So `python -m audit_readiness_ledger` works when the entry point is not on PATH."""

from .cli import main

raise SystemExit(main())
