"""حالة السوق: اتجاه المؤشر + اتساع السوق (نسبة الأسهم فوق متوسطاتها)."""
from __future__ import annotations

import numpy as np
import pandas as pd

from .indicators import sma

REGIME_AR = {
    "strong_up": "صاعد بقوة",
    "up": "صاعد",
    "neutral": "محايد",
    "weak": "ضعيف",
    "down": "هابط",
}


def internal_index(close_panel: pd.DataFrame) -> pd.Series:
    """مؤشر داخلي متساوي الأوزان من الأسهم المحللة (بديل لو تعذر EGX30)."""
    rets = close_panel / close_panel.shift(1) - 1.0
    idx = (1.0 + rets.mean(axis=1).fillna(0.0)).cumprod() * 100.0
    return idx


def label_from_score(score: float, cfg: dict) -> str:
    r = cfg["regime"]
    if score >= r["strong_up"]:
        return "strong_up"
    if score >= r["up"]:
        return "up"
    if score >= r["neutral"]:
        return "neutral"
    if score >= r["weak"]:
        return "weak"
    return "down"


def compute_regime(bench_close: pd.Series | None, close_panel: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    idx = close_panel.index
    if bench_close is not None and len(bench_close) > 60:
        bench = bench_close.reindex(idx.union(bench_close.index)).ffill().reindex(idx)
        bench_name = "EGX30"
    else:
        bench = internal_index(close_panel)
        bench_name = "مؤشر داخلي"

    s50 = sma(bench, 50)
    s200 = sma(bench, 200)

    p50 = close_panel.rolling(50, min_periods=50).mean()
    p200 = close_panel.rolling(200, min_periods=200).mean()
    v50, v200 = p50.notna(), p200.notna()
    b50 = ((close_panel > p50) & v50).sum(axis=1) / v50.sum(axis=1).replace(0, np.nan)
    b200 = ((close_panel > p200) & v200).sum(axis=1) / v200.sum(axis=1).replace(0, np.nan)

    w = cfg["regime"]["weights"]
    comp_b50 = (bench > s50).astype(float)
    comp_b200 = pd.Series(np.where(s200.isna(), 0.5, (bench > s200).astype(float)), index=idx)
    comp_slope = (s50 > s50.shift(10)).astype(float)

    score = (
        w["bench_above_sma50"] * comp_b50
        + w["bench_above_sma200"] * comp_b200
        + w["bench_sma50_rising"] * comp_slope
        + w["breadth_above_sma50"] * b50.fillna(0.5)
        + w["breadth_above_sma200"] * b200.fillna(0.5)
    )
    out = pd.DataFrame(
        {
            "bench_close": bench,
            "bench_sma50": s50,
            "bench_sma200": s200,
            "bench_ret60": (bench / bench.shift(60) - 1.0) * 100,
            "breadth50": b50,
            "breadth200": b200,
            "regime_score": score,
        },
        index=idx,
    )
    out["regime"] = [label_from_score(x, cfg) for x in out["regime_score"]]
    out.attrs["bench_name"] = bench_name
    return out
