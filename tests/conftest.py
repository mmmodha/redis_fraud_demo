"""Pytest configuration: make the repo root importable so ``backend.app.*`` and
``data.*`` resolve without installing the project, and put ``backend/`` on the
path too so the in-package ``from app.* import ...`` style used by the backend
modules (which run inside Docker with cwd=backend/) keeps working under
pytest."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))
