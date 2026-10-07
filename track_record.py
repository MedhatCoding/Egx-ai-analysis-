"""سجل التوصيات الفعلية: نسجّل كل توصية شراء ونتابع نتيجتها بنفس قواعد المحاكاة."""
from __future__ import annotations

import numpy as np
import pandas as pd

from .backtest import _stats
from .config import SIGNALS
from .sim import simulate_trade

HISTORY = SIGNALS / "history.csv"
COMPONENTS = ["comp_trend", "comp_momentum", "comp_rs", "comp_volume", "comp_setup"]
COMPONENTS_AR = {
    "comp_trend": "الاتجاه", "comp_momentum": "الزخم", "comp_rs": "القوة النسبية",
    "comp_volume": "الحجم والتجميع", "comp_setup": "جودة النموذج",
}
MIN_TRADES_FOR_COMPONENT_STATS = 20
COLS = [
    "signal_date", "code", "name", "score", *COMPONENTS, "setup", "regime",
    "entry_ref", "stop", "t1", "t2",
    "status", "entry", "exit", "exit_date", "reason", "r_net", "ret_pct", "days", "last_close",
]


def load_history() -> pd.DataFrame:
    if HISTORY.exists():
        df = pd.read_csv(HISTORY)
        for c in COLS:
            if c not in df.columns:
                df[c] = np.nan
        return df[COLS].astype(object)
    return pd.DataFrame(columns=COLS, dtype=object)


def save_history(df: pd.DataFrame) -> None:
    HISTORY.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(HISTORY, index=False)


def log_signals(hist: pd.DataFrame, picks: list[dict], data_date: str, regime_label: str) -> pd.DataFrame:
    rows = []
    have = set(zip(hist["signal_date"], hist["code"]))
    active = set(hist.loc[hist["status"].isin(["pending", "open"]), "code"])
    for p in picks:
        if (data_date, p["code"]) in have or p["code"] in active:
            continue
        rows.append(
            {
                "signal_date": data_date, "code": p["code"], "name": p["name"], "score": p["score"],
                **{c: p.get(c) for c in COMPONENTS},
                "setup": p["setup"], "regime": regime_label, "entry_ref": p["close"],
                "stop": p["stop"], "t1": p["t1"], "t2": p["t2"], "status": "pending",
            }
        )
    if rows:
        hist = pd.concat([hist.astype(object), pd.DataFrame(rows).astype(object)], ignore_index=True)[COLS]
    return hist


def update_history(hist: pd.DataFrame, prices: dict[str, pd.DataFrame], cfg: dict) -> pd.DataFrame:
    rk = cfg["risk"]
    hist = hist.copy().astype(object)
    for i, row in hist.iterrows():
        if row["status"] not in ("pending", "open"):
            continue
        df = prices.get(row["code"])
        if df is None:
            continue
        ts = pd.Timestamp(row["signal_date"])
        sig_i = int(df.index.searchsorted(ts, side="right")) - 1
        if sig_i < 0:
            continue
        res = simulate_trade(
            df["open"].to_numpy(float), df["high"].to_numpy(float), df["low"].to_numpy(float),
            df["close"].to_numpy(float), sig_i, float(row["stop"]), float(row["t1"]),
            rk["max_hold_days"], rk["round_trip_cost_pct"],
        )
        st = res["status"]
        hist.at[i, "status"] = st
        hist.at[i, "last_close"] = float(df["close"].iloc[-1])
        if st in ("closed", "open"):
            hist.at[i, "entry"] = res["entry"]
            hist.at[i, "exit"] = res["exit"]
            hist.at[i, "exit_date"] = df.index[res["exit_idx"]].date().isoformat() if st == "closed" else np.nan
            hist.at[i, "reason"] = res["reason"]
            hist.at[i, "r_net"] = res["r_net"]
            hist.at[i, "ret_pct"] = res["ret_pct"]
            hist.at[i, "days"] = res["days"]
    return hist


def component_stats(closed: pd.DataFrame) -> dict | None:
    """يقارن متوسط نتيجة الصفقات (R) بين النصف الأعلى والأدنى من كل مكوّن نقاط وقت الإشارة.
    الهدف معرفة أي مكوّن فعليًا بيفرق في النتيجة مع الوقت، عشان نراجع أوزان scoring.weights لاحقًا.
    محتاج عدد كافٍ من الصفقات المغلقة، وإلا الفرق قد يكون محض صدفة."""
    if len(closed) < MIN_TRADES_FOR_COMPONENT_STATS:
        return None
    r = closed["r_net"].astype(float)
    out = {}
    for comp in COMPONENTS:
        if comp not in closed.columns or closed[comp].isna().all():
            continue
        v = closed[comp].astype(float)
        med = v.median()
        hi, lo = r[v >= med], r[v < med]
        if len(hi) < 5 or len(lo) < 5:
            continue
        out[comp] = {
            "label": COMPONENTS_AR[comp],
            "high_avg_r": round(float(hi.mean()), 2), "high_n": int(len(hi)),
            "low_avg_r": round(float(lo.mean()), 2), "low_n": int(len(lo)),
        }
    return out or None


def summarize(hist: pd.DataFrame) -> dict:
    closed = hist[hist["status"] == "closed"].copy()
    open_ = hist[hist["status"] == "open"]
    return {
        "recommendations": int(len(hist)),
        "closed": int(len(closed)),
        "open": int(len(open_)),
        "pending": int((hist["status"] == "pending").sum()),
        "skipped": int((hist["status"] == "skipped").sum()),
        "open_avg_r": None if open_.empty else round(float(open_["r_net"].astype(float).mean()), 2),
        "stats": _stats(closed.assign(
            r_net=closed["r_net"].astype(float), ret_pct=closed["ret_pct"].astype(float),
            days=closed["days"].astype(float),
        )) if len(closed) else {"trades": 0},
        "component_stats": component_stats(closed),
        "component_stats_min_trades": MIN_TRADES_FOR_COMPONENT_STATS,
    }
