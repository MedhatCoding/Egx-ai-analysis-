"""Persistent portfolio loader.
The deployed app can import/export this JSON. Daily Actions reads the committed file.
"""
from __future__ import annotations
import json, os
from pathlib import Path

PATH = Path(os.environ.get("PORTFOLIO_FILE", "data/portfolio.json"))

def load_for_daily() -> list[dict]:
    if not PATH.exists():
        return []
    try:
        obj=json.loads(PATH.read_text(encoding="utf-8"))
        return obj if isinstance(obj,list) else []
    except Exception:
        return []
