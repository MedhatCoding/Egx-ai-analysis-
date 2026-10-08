"""نظام النقاط (0-100) + مستويات الدخول والوقف والأهداف. كله متجه على الزمن كاملًا،
فنفس الكود يُستخدم للتوصية الحالية وللـ backtest (عشان النتائج تكون قابلة للمقارنة)."""
from __future__ import annotations

import numpy as np
import pandas as pd


def _interp(s: pd.Series, xs, ys, neutral: float) -> pd.Series:
    return pd.Series(np.interp(s.fillna(neutral).to_numpy(dtype=float), xs, ys), index=s.index)


def compute_scores(
    ind: pd.DataFrame,
    rs_rank: pd.Series | None,
    bench_ret60: pd.Series | None,
    cfg: dict,
) -> pd.DataFrame:
    sc, rk, fl = cfg["scoring"], cfg["risk"], cfg["filters"]
    w = sc["weights"]
    c, atr = ind["close"], ind["atr14"]
    sma200_nan = ind["sma200"].isna()

    # ---------------------------------------------------------- الاتجاه
    above50 = (c > ind["sma50"]).astype(float)
    ma_stack = pd.Series(np.where(sma200_nan, 0.5, (ind["sma50"] > ind["sma200"]).astype(float)), index=ind.index)
    ma_short = (ind["sma20"] > ind["sma50"]).astype(float)
    slope_up = (ind["sma50_slope"] > 0).astype(float)
    comp_trend = 0.3 * above50 + 0.3 * ma_stack + 0.2 * ma_short + 0.2 * slope_up

    # ---------------------------------------------------------- الزخم
    rsi_c = _interp(
        ind["rsi14"], [0, 30, 40, 50, 60, 68, 75, 85, 100], [0.0, 0.15, 0.35, 0.6, 1.0, 0.9, 0.55, 0.25, 0.1], 50.0
    )
    hist = ind["macd_hist"]
    macd_c = 0.5 * (hist > 0).astype(float) + 0.3 * (hist > hist.shift(1)).astype(float) + 0.2 * (ind["macd"] > 0).astype(float)
    comp_mom = 0.5 * rsi_c + 0.5 * macd_c

    # ---------------------------------------------------------- القوة النسبية
    rs_r = rs_rank.reindex(ind.index) if rs_rank is not None else pd.Series(np.nan, index=ind.index)
    if bench_ret60 is not None:
        b = bench_ret60.reindex(ind.index)
        beat = pd.Series(np.where(b.isna(), 0.5, (ind["ret60"] > b).astype(float)), index=ind.index)
    else:
        beat = pd.Series(0.5, index=ind.index)
    comp_rs = 0.7 * rs_r.fillna(0.5) + 0.3 * beat

    # ---------------------------------------------------------- الحجم والتجميع
    ud_c = _interp(ind["updown_vol"], [0, 0.6, 1.0, 1.5, 2.5, 5], [0.0, 0.2, 0.5, 0.85, 1.0, 1.0], 1.0)
    comp_vol = 0.7 * ud_c + 0.3 * ind["obv_rising"].fillna(0.5)

    # ---------------------------------------------------------- جودة الفرصة
    trend_ok = (c > ind["sma50"]) & (ind["sma50_slope"] > 0) & (sma200_nan | (ind["sma50"] > ind["sma200"]))
    extended = ((c - ind["sma50"]) / atr) > sc["extended_atr_mult"]
    breakout = (c > ind["high20"]) & (ind["vol_ratio"] > 1.2) & trend_ok
    pullback = (
        trend_ok
        & (c <= ind["sma20"] + 0.75 * atr)
        & (c >= ind["sma20"] - 1.0 * atr)
        & (ind["rsi14"] < 62)
    )
    near_high = trend_ok & (ind["dist_high252"] > -0.05)
    conds = [extended, breakout, pullback, near_high, trend_ok]
    comp_setup = pd.Series(np.select(conds, [0.1, 1.0, 0.85, 0.7, 0.5], default=0.2), index=ind.index)
    setup = pd.Series(
        np.select(conds, ["extended", "breakout", "pullback", "near_high", "trend"], default="none"),
        index=ind.index,
    )

    total_w = float(sum(w.values()))
    score = 100.0 * (
        w["trend"] * comp_trend
        + w["momentum"] * comp_mom
        + w["relative_strength"] * comp_rs
        + w["volume"] * comp_vol
        + w["setup"] * comp_setup
    ) / total_w

    # ---------------------------------------------------------- المستويات
    swing = ind["low10"] - 0.1 * atr
    stop = np.minimum(np.maximum(swing, c - rk["stop_max_atr"] * atr), c - rk["stop_min_atr"] * atr)
    risk = c - stop
    t1 = c + rk["target_r"][0] * risk
    t2 = c + rk["target_r"][1] * risk
    room_r = (ind["high60"] - c) / risk

    liquid = ind["value_sma20"] >= fl["min_avg_value_egp"]
    lim = fl["price_limit_pct"] - 0.5
    limit_up = ind["ret1"] >= lim
    limit_down = ind["ret1"] <= -lim
    # قريب من حد التداول اليومي (صعودًا أو هبوطًا) حتى لو لسه ماوصلش الحد بالظبط:
    # التنفيذ عند هذه المستويات غير موثوق (فجوات، أوامر معلّقة) فبنحذّر منه بشكل عام
    near_limit = ind["ret1"].abs() >= (lim - 2.0)
    room_ok = (setup == "breakout") | (room_r >= sc["min_room_r"])

    buy_raw = (
        (score >= sc["buy_score"])
        & trend_ok
        & liquid
        & ~extended
        & (ind["rsi14"] < sc["rsi_max_for_buy"])
        & ~limit_up
        & ~limit_down          # قفل الحد الأدنى: تجنّب الشراء وقت الذعر حتى لو تحسّنت المؤشرات لحظيًا
        & room_ok
        & atr.notna()
    )

    out = ind.copy()
    out["score"] = score
    out["comp_trend"] = comp_trend
    out["comp_momentum"] = comp_mom
    out["comp_rs"] = comp_rs
    out["comp_volume"] = comp_vol
    out["comp_setup"] = comp_setup
    out["rs_rank"] = rs_r
    out["setup"] = setup
    out["trend_ok"] = trend_ok
    out["extended"] = extended
    out["liquid"] = liquid
    out["limit_up"] = limit_up
    out["limit_down"] = limit_down
    out["near_limit"] = near_limit
    out["stop"] = stop
    out["risk"] = risk
    out["t1"] = t1
    out["t2"] = t2
    out["room_r"] = room_r
    out["buy_raw"] = buy_raw
    return out
