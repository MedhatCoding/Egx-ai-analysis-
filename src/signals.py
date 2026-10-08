"""تشغيل التحليل على كل الأسهم: المؤشرات، الترتيب النسبي، حالة السوق، التصنيف والتوصيات."""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

from .indicators import compute_indicators
from .regime import REGIME_AR, compute_regime
from .scoring import compute_scores
from .ml_model import train_predict

SETUP_AR = {
    "breakout": "اختراق",
    "pullback": "تصحيح داخل اتجاه",
    "near_high": "قرب القمة",
    "trend": "استمرار اتجاه",
    "extended": "متمدد",
    "none": "لا نموذج",
}
SIGNAL_AR = {
    "BUY": "شراء",
    "WATCH": "مراقبة",
    "NEUTRAL": "محايد",
    "AVOID": "تجنب",
    "ILLIQUID": "سيولة ضعيفة",
    "STALE": "بيانات قديمة",
}


def clean(x):
    """تحويل أنواع numpy لأنواع بايثون قابلة للتحويل JSON."""
    if isinstance(x, (np.floating, float)):
        return None if (x is None or not math.isfinite(float(x))) else round(float(x), 4)
    if isinstance(x, (np.integer,)):
        return int(x)
    if isinstance(x, (np.bool_,)):
        return bool(x)
    if isinstance(x, pd.Timestamp):
        return x.date().isoformat()
    return x


# --------------------------------------------------------------------------- التحليل
def analyze(prices: dict[str, pd.DataFrame], bench_df: pd.DataFrame | None, cfg: dict):
    inds = {code: compute_indicators(df) for code, df in prices.items()}
    close_panel = pd.DataFrame({c: i["close"] for c, i in inds.items()}).sort_index()

    bench_close = bench_df["close"] if bench_df is not None and len(bench_df) else None
    regime_df = compute_regime(bench_close, close_panel, cfg)

    r60 = (close_panel / close_panel.shift(60) - 1.0).rank(axis=1, pct=True)
    r120 = (close_panel / close_panel.shift(120) - 1.0).rank(axis=1, pct=True)
    rs_rank = 0.6 * r60 + 0.4 * r120.fillna(r60)

    regime_ok = regime_df["regime_score"] >= cfg["risk"]["regime_min_score"]
    frames: dict[str, pd.DataFrame] = {}
    for code, ind in inds.items():
        f = compute_scores(ind, rs_rank[code], regime_df["bench_ret60"], cfg)
        f["regime_ok"] = regime_ok.reindex(f.index).fillna(False)
        frames[code] = f
    ml_probs, ml_meta = train_predict(frames, cfg)
    regime_df.attrs["ml_probs"] = ml_probs
    regime_df.attrs["ml_meta"] = ml_meta
    return frames, regime_df, close_panel


# --------------------------------------------------------------------------- آخر شمعة لكل سهم
def latest_table(frames: dict[str, pd.DataFrame], names: dict[str, str], cfg: dict, ml_probs: dict[str, float] | None = None) -> pd.DataFrame:
    market_last = max(f.index[-1] for f in frames.values())
    ml_probs = ml_probs or {}
    ml_weight = float(cfg.get("ml", {}).get("score_weight", 0.20))
    rows = []
    for code, f in frames.items():
        r = f.iloc[-1]
        d = f.index[-1]
        rows.append(
            {
                "code": code,
                "name": names.get(code, code),
                "date": d,
                "stale": (market_last - d).days > cfg["data"]["max_stale_days"],
                "close": r["close"],
                "technical_score": r["score"],
                "ml_prob": ml_probs.get(code, 0.5),
                "score": (1.0 - ml_weight) * r["score"] + ml_weight * (ml_probs.get(code, 0.5) * 100.0),
                "comp_trend": r["comp_trend"],
                "comp_momentum": r["comp_momentum"],
                "comp_rs": r["comp_rs"],
                "comp_volume": r["comp_volume"],
                "comp_setup": r["comp_setup"],
                "setup": r["setup"],
                "trend_ok": bool(r["trend_ok"]),
                "extended": bool(r["extended"]),
                "liquid": bool(r["liquid"]),
                "limit_up": bool(r["limit_up"]),
                "limit_down": bool(r["limit_down"]),
                "near_limit": bool(r["near_limit"]),
                "buy_raw": bool(r["buy_raw"]),
                "rsi": r["rsi14"],
                "macd_hist": r["macd_hist"],
                "atr": r["atr14"],
                "atr_pct": r["atr_pct"],
                "ret1": r["ret1"],
                "ret5": r["ret5"],
                "ret20": r["ret20"],
                "ret60": r["ret60"],
                "vol_ratio": r["vol_ratio"],
                "updown_vol": r["updown_vol"],
                "avg_value_m": r["value_sma20"] / 1e6 if pd.notna(r["value_sma20"]) else np.nan,
                "rs_pct": r["rs_rank"] * 100 if pd.notna(r["rs_rank"]) else np.nan,
                "sma20": r["sma20"],
                "sma50": r["sma50"],
                "sma200": r["sma200"],
                "dist_high252": r["dist_high252"] * 100 if pd.notna(r["dist_high252"]) else np.nan,
                "stop": r["stop"],
                "risk": r["risk"],
                "t1": r["t1"],
                "t2": r["t2"],
                "room_r": r["room_r"],
            }
        )
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------- التصنيف
def why_not_buy(r: pd.Series, regime_label: str, max_buys: int, cfg: dict) -> list[str]:
    sc = cfg["scoring"]
    out = []
    if r["score"] < sc["buy_score"]:
        out.append(f"النقاط {r['score']:.0f} أقل من حد الشراء {sc['buy_score']}")
    if not r["trend_ok"]:
        out.append("الاتجاه غير مكتمل (تحت المتوسط 50 أو المتوسط 50 هابط)")
    if r["extended"]:
        out.append("السهم متمدد بعيدًا عن متوسطه")
    if r["rsi"] >= sc["rsi_max_for_buy"]:
        out.append(f"RSI مرتفع ({r['rsi']:.0f})")
    if r["limit_up"]:
        out.append("ارتفع بالحد الأقصى في آخر جلسة (لا شراء عند حد التداول)")
    if r["limit_down"]:
        out.append("هبط بالحد الأقصى في آخر جلسة (تجنّب حتى الاستقرار)")
    if r["setup"] != "breakout" and pd.notna(r["room_r"]) and r["room_r"] < sc["min_room_r"]:
        out.append("المقاومة قريبة من السعر")
    if max_buys == 0:
        out.append("السوق هابط: لا توصيات شراء اليوم")
    return out


def classify(latest: pd.DataFrame, regime_label: str, regime_score: float, cfg: dict) -> pd.DataFrame:
    df = latest.copy()
    sc, rk = cfg["scoring"], cfg["risk"]
    max_buys = rk["max_buys_by_regime"][regime_label]
    if regime_score < rk["regime_min_score"]:
        max_buys = 0

    df["signal"] = "NEUTRAL"
    trend_down = (df["close"] < df["sma50"]) & (df["sma50"] < df["sma200"])
    df.loc[(df["score"] < sc["avoid_score"]) | trend_down, "signal"] = "AVOID"
    df.loc[(df["score"] >= sc["watch_score"]) & ~trend_down, "signal"] = "WATCH"

    cand = df[df["buy_raw"] & ~df["stale"] & df["liquid"]].sort_values(["score", "rs_pct"], ascending=False)
    buy_idx = list(cand.index[:max_buys])
    df.loc[cand.index, "signal"] = "WATCH"      # المتبقي بعد الحد الأقصى يبقى مراقبة
    df.loc[buy_idx, "signal"] = "BUY"
    df.loc[~df["liquid"], "signal"] = "ILLIQUID"
    df.loc[df["stale"], "signal"] = "STALE"
    # هبوط بالحد الأدنى في آخر جلسة: تسعير غير موثوق، فنتجنبه بغض النظر عن أي تصنيف سابق
    # (إلا لو أقل سيولة أو بيانات قديمة أصلاً، وده أهم)
    df.loc[df["limit_down"] & df["signal"].isin(["BUY", "WATCH", "NEUTRAL"]), "signal"] = "AVOID"

    df["why_not_buy"] = [
        why_not_buy(r, regime_label, max_buys, cfg) if s == "WATCH" else []
        for (_, r), s in zip(df.iterrows(), df["signal"])
    ]
    df["rank"] = df["score"].rank(ascending=False, method="first").astype(int)
    return df.sort_values("score", ascending=False).reset_index(drop=True)


# --------------------------------------------------------------------------- الشرح
def explain(r: pd.Series) -> tuple[list[str], list[str]]:
    why, warn = [], []
    if r["trend_ok"]:
        if pd.notna(r["sma200"]):
            why.append("اتجاه صاعد: السعر فوق المتوسط 50 والمتوسط 50 فوق 200")
        else:
            why.append("اتجاه صاعد: السعر فوق المتوسط 50 والمتوسط صاعد")
    mom = f"RSI {r['rsi']:.0f}"
    if r["macd_hist"] > 0:
        mom += " وMACD إيجابي"
    why.append(mom)
    if pd.notna(r["rs_pct"]) and r["rs_pct"] >= 70:
        why.append(f"قوة نسبية أعلى من {r['rs_pct']:.0f}% من الأسهم المحللة")
    if pd.notna(r["vol_ratio"]) and r["vol_ratio"] >= 1.3:
        why.append(f"حجم التداول {r['vol_ratio']:.1f} ضعف المتوسط")
    if pd.notna(r["updown_vol"]) and r["updown_vol"] >= 1.5:
        why.append("أحجام أيام الصعود أكبر من أيام الهبوط (تجميع)")
    why.append(
        {
            "breakout": "اختراق أعلى 20 يوم بحجم مؤكد",
            "pullback": "تصحيح نحو المتوسط 20 داخل اتجاه صاعد",
            "near_high": "قريب من أعلى 52 أسبوع",
            "trend": "استمرار الاتجاه الصاعد",
        }.get(r["setup"], "")
    )
    why = [w for w in why if w]

    if r.get("near_limit"):
        kind = "الحد الأقصى" if r["ret1"] > 0 else "الحد الأدنى"
        warn.append(f"قريب من {kind} المسموح للتداول اليومي؛ التنفيذ عند هذا المستوى أقل ضمانًا")
    if r["rsi"] >= 70:
        warn.append(f"RSI مرتفع ({r['rsi']:.0f}) وقد يحدث تهدئة")
    if pd.notna(r["atr_pct"]) and r["atr_pct"] >= 5:
        warn.append(f"تذبذب يومي مرتفع (متوسط المدى {r['atr_pct']:.1f}% من السعر)")
    if r["setup"] != "breakout" and pd.notna(r["room_r"]) and r["room_r"] < 1.5:
        warn.append("المقاومة قريبة نسبيًا من السعر")
    if pd.notna(r["avg_value_m"]) and r["avg_value_m"] < 3:
        warn.append(f"السيولة متوسطة ({r['avg_value_m']:.1f} مليون ج.م يوميًا): انتبه لفرق السعر عند التنفيذ")
    if pd.notna(r["ret5"]) and r["ret5"] > 15:
        warn.append(f"صعد {r['ret5']:.0f}% في 5 جلسات")
    return why, warn


def pick_dict(r: pd.Series, cfg: dict) -> dict:
    rk = cfg["risk"]
    why, warn = explain(r)
    risk_frac = r["risk"] / r["close"] if r["close"] else np.nan
    pos = min(rk["max_position_pct"], rk["risk_per_trade_pct"] / risk_frac) if risk_frac and risk_frac > 0 else np.nan
    atr = r["atr"]
    d = {
        "code": r["code"],
        "name": r["name"],
        "signal": r["signal"],
        "score": r["score"],
        "technical_score": r.get("technical_score", r["score"]),
        "ml_prob": r.get("ml_prob", 0.5),
        "comp_trend": r["comp_trend"],
        "comp_momentum": r["comp_momentum"],
        "comp_rs": r["comp_rs"],
        "comp_volume": r["comp_volume"],
        "comp_setup": r["comp_setup"],
        "setup": r["setup"],
        "setup_ar": SETUP_AR.get(r["setup"], r["setup"]),
        "close": r["close"],
        "entry_low": r["close"] - 0.5 * atr,
        "entry_high": r["close"] + 0.25 * atr,
        "stop": r["stop"],
        "t1": r["t1"],
        "t2": r["t2"],
        "risk_pct": risk_frac * 100 if pd.notna(risk_frac) else None,
        "position_pct": pos,
        "rsi": r["rsi"],
        "ret5": r["ret5"],
        "ret20": r["ret20"],
        "vol_ratio": r["vol_ratio"],
        "rs_pct": r["rs_pct"],
        "avg_value_m": r["avg_value_m"],
        "why": why,
        "cautions": warn,
        "why_not_buy": r.get("why_not_buy", []),
    }
    return {k: (clean(v) if not isinstance(v, list) else v) for k, v in d.items()}


# --------------------------------------------------------------------------- ملخص السوق
def market_summary(latest: pd.DataFrame, regime_df: pd.DataFrame, cfg: dict) -> dict:
    last = regime_df.iloc[-1]
    prev = regime_df.iloc[-2] if len(regime_df) > 1 else last
    ok = latest[~latest["stale"]]
    liq = ok[ok["liquid"]]
    movers_src = liq if len(liq) >= 6 else ok

    gainers = movers_src.sort_values("ret1", ascending=False).head(3)
    losers = movers_src.sort_values("ret1").head(3)

    def mv(df):
        return [{"code": r.code, "name": r.name, "ret1": clean(r.ret1)} for r in df.itertuples()]

    return {
        "bench_name": regime_df.attrs.get("bench_name", "المؤشر"),
        "bench_close": clean(last["bench_close"]),
        "bench_change_1d": clean((last["bench_close"] / prev["bench_close"] - 1) * 100),
        "bench_ret20": clean((last["bench_close"] / regime_df["bench_close"].iloc[-21] - 1) * 100)
        if len(regime_df) > 21
        else None,
        "seasonality_score": clean(last.get("seasonality_score", np.nan) * 100),
        "seasonality_month_return": clean(last.get("seasonality_month_return", np.nan)),
        "bench_above_sma50": bool(last["bench_close"] > last["bench_sma50"]) if pd.notna(last["bench_sma50"]) else None,
        "bench_above_sma200": bool(last["bench_close"] > last["bench_sma200"]) if pd.notna(last["bench_sma200"]) else None,
        "breadth50": clean(last["breadth50"] * 100) if pd.notna(last["breadth50"]) else None,
        "breadth200": clean(last["breadth200"] * 100) if pd.notna(last["breadth200"]) else None,
        "advancers": int((ok["ret1"] > 0).sum()),
        "decliners": int((ok["ret1"] < 0).sum()),
        "unchanged": int((ok["ret1"] == 0).sum()),
        "median_ret20": clean(ok["ret20"].median()),
        "top_gainers": mv(gainers),
        "top_losers": mv(losers),
    }


def build_result(frames, regime_df, latest_cls: pd.DataFrame, universe_size: int, cfg: dict) -> dict:
    last = regime_df.iloc[-1]
    label = last["regime"]
    max_buys = cfg["risk"]["max_buys_by_regime"][label]
    if last["regime_score"] < cfg["risk"]["regime_min_score"]:
        max_buys = 0
    buys = latest_cls[latest_cls["signal"] == "BUY"]
    watch = latest_cls[latest_cls["signal"] == "WATCH"].head(15)
    data_date = max(f.index[-1] for f in frames.values())
    counts = latest_cls["signal"].value_counts().to_dict()
    return {
        "data_date": data_date.date().isoformat(),
        "universe_size": int(universe_size),
        "analyzed": int(len(latest_cls)),
        "signal_counts": {k: int(v) for k, v in counts.items()},
        "regime": {
            "label": label,
            "label_ar": REGIME_AR[label],
            "score": clean(last["regime_score"] * 100),
            "max_buys": int(max_buys),
            "seasonality_score": clean(last.get("seasonality_score", np.nan) * 100),
            "seasonality_month_return": clean(last.get("seasonality_month_return", np.nan)),
        },
        "market": market_summary(latest_cls, regime_df, cfg),
        "picks": [pick_dict(r, cfg) for _, r in buys.iterrows()],
        "watch": [pick_dict(r, cfg) for _, r in watch.iterrows()],
        "ml": regime_df.attrs.get("ml_meta", {}),
    }
