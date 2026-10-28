"""Fail-closed rules for market-data freshness."""
from __future__ import annotations

from datetime import date
import pandas as pd


def apply_market_freshness_gate(classified: pd.DataFrame, data_date: str | date, expected_date: date) -> tuple[pd.DataFrame, bool]:
    """Demote every BUY if the latest overall market date misses expected session.

    This is a conservative portfolio-wide gate: it does not claim a holiday or
    provider delay can be inferred. Correct the maintained holiday calendar or
    restore data freshness before BUY signals can resume.
    """
    actual = date.fromisoformat(str(data_date)[:10]) if not isinstance(data_date, date) else data_date
    if actual >= expected_date:
        return classified, False
    out = classified.copy()
    mask = out["signal"].astype(str).eq("BUY")
    if not mask.any():
        return out, True
    out.loc[mask, "signal"] = "WATCH"
    for idx in out.index[mask]:
        reasons = out.at[idx, "why_not_buy"]
        reasons = list(reasons) if isinstance(reasons, (list, tuple)) else []
        reasons.append(f"توقف آمن: بيانات السوق العامة قديمة ({actual}؛ المتوقع {expected_date})؛ لا شراء قبل تحديثها")
        out.at[idx, "why_not_buy"] = reasons
    return out, True
