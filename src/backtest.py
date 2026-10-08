"""اختبار القواعد على التاريخ. نفس قواعد التوصية الحالية ونفس محاكاة الصفقة.

تحذيرات مهمة (تظهر أيضًا في التطبيق):
- القائمة الحالية للأسهم = تحيّز البقاء (الأسهم اللي اختفت أو اتوقفت مش موجودة).
- لا نحاكي الانزلاق السعري في الأسهم قليلة السيولة، لذلك التكلفة الفعلية قد تكون أعلى.
- النتائج السابقة لا تضمن المستقبل.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .sim import simulate_trade


def _stats(trades: pd.DataFrame) -> dict:
    if trades.empty:
        return {"trades": 0}
    r = trades["r_net"].to_numpy()
    wins, losses = r[r > 0], r[r <= 0]
    pf = float(wins.sum() / abs(losses.sum())) if losses.sum() != 0 else None
    # أطول سلسلة خسائر متتالية
    streak = best = 0
    for x in trades.sort_values("exit_date")["r_net"]:
        streak = streak + 1 if x <= 0 else 0
        best = max(best, streak)
    eq = trades.sort_values("exit_date")["r_net"].cumsum()
    dd = float((eq - eq.cummax()).min())
    return {
        "trades": int(len(trades)),
        "win_rate": round(float((r > 0).mean() * 100), 1),
        "avg_r": round(float(r.mean()), 3),
        "median_r": round(float(np.median(r)), 3),
        "profit_factor": None if pf is None else round(pf, 2),
        "avg_ret_pct": round(float(trades["ret_pct"].mean()), 2),
        "avg_days": round(float(trades["days"].mean()), 1),
        "max_losing_streak": int(best),
        "max_drawdown_r": round(dd, 2),
        "pct_target": round(float((trades["reason"] == "target").mean() * 100), 1),
        "pct_stop": round(float((trades["reason"] == "stop").mean() * 100), 1),
        "pct_time": round(float((trades["reason"] == "time").mean() * 100), 1),
    }


def _run_symbol(code: str, f: pd.DataFrame, mask: np.ndarray, cfg: dict, step: int = 1) -> list[dict]:
    o, h, l, c = (f[k].to_numpy(dtype=float) for k in ("open", "high", "low", "close"))
    stop, t1 = f["stop"].to_numpy(dtype=float), f["t1"].to_numpy(dtype=float)
    dates = f.index
    rk = cfg["risk"]
    out = []
    i, n = 0, len(f)
    while i < n - 1:
        if mask[i] and np.isfinite(stop[i]):
            res = simulate_trade(o, h, l, c, i, stop[i], t1[i], rk["max_hold_days"], rk["round_trip_cost_pct"])
            if res["status"] == "closed":
                out.append(
                    {
                        "code": code,
                        "signal_date": dates[i].date().isoformat(),
                        "entry_date": dates[res["entry_idx"]].date().isoformat(),
                        "exit_date": dates[res["exit_idx"]].date().isoformat(),
                        "entry": res["entry"],
                        "exit": res["exit"],
                        "reason": res["reason"],
                        "r_net": res["r_net"],
                        "ret_pct": res["ret_pct"],
                        "days": res["days"],
                        "score": float(f["score"].iloc[i]),
                    }
                )
                i = res["exit_idx"] + 1      # لا نفتح صفقة جديدة في نفس السهم قبل خروج القديمة
                continue
            # skipped/open/pending: نكمل
        i += step
    return out


def run_backtest(frames: dict[str, pd.DataFrame], cfg: dict) -> tuple[dict, pd.DataFrame, pd.DataFrame]:
    """يرجع (ملخص، صفقات الاستراتيجية، صفقات خط الأساس)."""
    strat, base = [], []
    step = cfg["backtest"]["baseline_every_n_bars"]
    for code, f in frames.items():
        if len(f) < 260:
            continue
        valid = f["stop"].notna() & f["liquid"]
        strat += _run_symbol(code, f, (f["buy_raw"] & f["regime_ok"]).to_numpy(), cfg)
        base += _run_symbol(code, f, valid.to_numpy(), cfg, step=step)

    st = pd.DataFrame(strat)
    bs = pd.DataFrame(base)
    summary = {
        "strategy": _stats(st),
        "baseline": _stats(bs),
        "period": {
            "from": min(f.index[0] for f in frames.values()).date().isoformat(),
            "to": max(f.index[-1] for f in frames.values()).date().isoformat(),
        },
        "assumptions": {
            "entry": "افتتاح الجلسة التالية",
            "max_hold_days": cfg["risk"]["max_hold_days"],
            "round_trip_cost_pct": cfg["risk"]["round_trip_cost_pct"],
            "target_r": cfg["risk"]["target_r"][0],
        },
    }
    return summary, st, bs
