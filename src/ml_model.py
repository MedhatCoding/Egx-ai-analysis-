"""تعلم آلي + شبكة عصبية متعددة الطبقات للتنبؤ الاحتمالي بفرص 10 جلسات قادمة.
الهدف ليس استبدال التحليل الفني، بل إضافة طبقة تعلم من سجل الأسعار التاريخي.
"""
from __future__ import annotations

import warnings
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.neural_network import MLPClassifier
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import roc_auc_score, brier_score_loss

FEATURES = [
    "score", "rsi14", "macd_hist", "atr_pct", "ret1", "ret5", "ret20", "ret60",
    "vol_ratio", "updown_vol", "rs_rank", "dist_high252", "sma50_slope",
]

def _dataset(frames: dict[str, pd.DataFrame], horizon: int, threshold: float) -> pd.DataFrame:
    rows = []
    for code, f in frames.items():
        x = f.copy()
        cols = [c for c in FEATURES if c in x.columns]
        if len(cols) < 8:
            continue
        future = x["close"].shift(-horizon) / x["close"] - 1.0
        z = x[cols].replace([np.inf, -np.inf], np.nan).copy()
        z["target"] = (future >= threshold).astype(float)
        z["code"] = code
        z["date"] = x.index
        z = z.loc[future.notna()].dropna()
        if len(z):
            rows.append(z)
    return pd.concat(rows, ignore_index=True).sort_values("date").reset_index(drop=True) if rows else pd.DataFrame()

def train_predict(frames: dict[str, pd.DataFrame], cfg: dict) -> tuple[dict[str, float], dict]:
    mcfg = cfg.get("ml", {})
    if not mcfg.get("enabled", True):
        return {}, {"enabled": False, "samples": 0, "auc": None}

    horizon = int(mcfg.get("horizon_days", 10))
    # Target is defined on net return: require the desired net gain PLUS round-trip
    # trading costs, otherwise the model would learn "winners" that may be flat
    # or negative after commissions and slippage.
    net_threshold = float(mcfg.get("positive_return", 0.03))
    cost_pct = float(cfg.get("risk", {}).get("round_trip_cost_pct", 0.0))
    cost_fraction = max(0.0, cost_pct) / 100.0
    gross_threshold = net_threshold + cost_fraction
    data = _dataset(frames, horizon, gross_threshold)
    if len(data) < int(mcfg.get("min_samples", 500)):
        return {}, {"enabled": True, "samples": int(len(data)), "auc": None, "error": "عينات غير كافية"}

    cols = [c for c in FEATURES if c in data.columns]
    X = data[cols].astype(float)
    y = data["target"].astype(int)

    # Split by dates, not rows: symbols from the same session must not leak across
    # train/validation. Purge the target horizon before validation to prevent
    # overlapping forward-return labels from crossing the boundary.
    dates = pd.to_datetime(data["date"])
    unique_dates = pd.Index(dates.drop_duplicates().sort_values())
    cut_date_idx = max(int(len(unique_dates) * (1.0 - float(mcfg.get("validation_fraction", 0.20)))), 1)
    if cut_date_idx >= len(unique_dates):
        cut_date_idx = len(unique_dates) - 1
    validation_start = unique_dates[cut_date_idx]
    purge_horizon = horizon if mcfg.get("purge_horizon", True) else 0
    train_end_idx = max(0, cut_date_idx - purge_horizon)
    if train_end_idx < 2:
        return {}, {"enabled": True, "samples": int(len(data)), "auc": None, "error": "تاريخ غير كافٍ بعد عزل فترة التحقق"}
    train_cutoff = unique_dates[train_end_idx]
    train_mask = dates < train_cutoff
    validation_mask = dates >= validation_start
    Xtr, ytr = X.loc[train_mask], y.loc[train_mask]
    Xva, yva = X.loc[validation_mask], y.loc[validation_mask]
    if len(Xtr) < int(mcfg.get("min_samples", 500)) * 0.5 or len(Xva) < 20:
        return {}, {"enabled": True, "samples": int(len(data)), "auc": None, "error": "عينات تدريب أو تحقق غير كافية بعد الفصل الزمني"}
    if ytr.nunique() < 2 or yva.nunique() < 2:
        return {}, {"enabled": True, "samples": int(len(data)), "auc": None, "error": "تنوع الهدف غير كافٍ في الفصل الزمني"}

    rf = RandomForestClassifier(
        n_estimators=int(mcfg.get("rf_trees", 120)),
        max_depth=int(mcfg.get("rf_depth", 6)),
        min_samples_leaf=8,
        class_weight="balanced_subsample",
        random_state=42,
        n_jobs=-1,
    )
    deep = Pipeline([
        ("scale", StandardScaler()),
        ("mlp", MLPClassifier(
            hidden_layer_sizes=(32, 16),
            activation="relu",
            solver="adam",
            alpha=0.0005,
            batch_size=128,
            learning_rate_init=0.001,
            max_iter=120,
            early_stopping=True,
            validation_fraction=0.15,
            random_state=42,
        )),
    ])

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        rf.fit(Xtr, ytr)
        deep.fit(Xtr, ytr)

    p_rf = rf.predict_proba(Xva)[:, 1]
    p_deep = deep.predict_proba(Xva)[:, 1]
    p = 0.55 * p_rf + 0.45 * p_deep
    auc = float(roc_auc_score(yva, p))
    brier = float(brier_score_loss(yva, p))
    # مرجع احتمالي بسيط: توقع معدل النجاح في بيانات التدريب لكل عينات التحقق.
    baseline_rate = float(ytr.mean())
    baseline_brier = float(brier_score_loss(yva, np.full(len(yva), baseline_rate)))
    validation_meta = {
        "auc": round(auc, 4),
        "brier": round(brier, 4),
        "baseline_brier": round(baseline_brier, 4),
        "validation_samples": int(len(yva)),
        "validation_start": str(validation_start.date()),
        "validation_end": str(dates.loc[validation_mask].max().date()),
    }

    # لا نسمح للنموذج بتغيير ترتيب الفرص إلا إذا اجتاز AUC وحسّن
    # خط الأساس في Brier؛ جودة الترتيب وحدها لا تثبت جودة الاحتمالات.
    min_auc = float(mcfg.get("min_auc", 0.52))
    min_brier_improvement = float(mcfg.get("min_brier_improvement", 0.0))
    required_brier = baseline_brier * (1.0 - min_brier_improvement)
    if auc < min_auc or brier >= required_brier:
        reason = (
            "AUC أقل من الحد الأدنى؛ تم تجاهل النموذج"
            if auc < min_auc
            else "دقة الاحتمالات لم تتفوق على خط الأساس؛ تم تجاهل النموذج"
        )
        return {}, {
            "enabled": True, "samples": int(len(data)), **validation_meta,
            "model_used": False, "error": reason,
        }

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        rf.fit(X, y)
        deep.fit(X, y)

    latest_rows = []
    for code, f in frames.items():
        if len(f) == 0:
            continue
        row = f.iloc[-1]
        if not all(c in row.index for c in cols):
            continue
        vals = pd.DataFrame([[row[c] for c in cols]], columns=cols).replace([np.inf, -np.inf], np.nan)
        if vals.isna().any().any():
            continue
        pr = float(0.55 * rf.predict_proba(vals)[:, 1][0] + 0.45 * deep.predict_proba(vals)[:, 1][0])
        latest_rows.append((code, pr))

    return dict(latest_rows), {
        "enabled": True, "samples": int(len(data)), **validation_meta,
        "model_used": True, "model": "RandomForest + MLP(32,16)",
        "horizon_days": horizon,
        "net_positive_return": net_threshold,
        "round_trip_cost_pct": cost_pct,
        "gross_return_threshold": gross_threshold,
    }
