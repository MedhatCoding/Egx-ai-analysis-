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
from sklearn.metrics import roc_auc_score

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
    threshold = float(mcfg.get("positive_return", 0.03))
    data = _dataset(frames, horizon, threshold)
    if len(data) < int(mcfg.get("min_samples", 500)):
        return {}, {"enabled": True, "samples": int(len(data)), "auc": None, "error": "عينات غير كافية"}

    cols = [c for c in FEATURES if c in data.columns]
    X = data[cols].astype(float)
    y = data["target"].astype(int)
    cut = max(int(len(X) * 0.8), 1)
    if cut >= len(X):
        cut = len(X) - 1

    Xtr, Xva, ytr, yva = X.iloc[:cut], X.iloc[cut:], y.iloc[:cut], y.iloc[cut:]
    if ytr.nunique() < 2 or yva.nunique() < 2:
        return {}, {"enabled": True, "samples": int(len(data)), "auc": None, "error": "تنوع الهدف غير كافٍ"}

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

    # إذا كان النموذج لا يتفوق على التخمين، لا نسمح له بتغيير الترتيب.
    if auc < float(mcfg.get("min_auc", 0.52)):
        return {}, {
            "enabled": True, "samples": int(len(data)), "auc": round(auc, 4),
            "model_used": False, "error": "AUC أقل من الحد الأدنى؛ تم تجاهل النموذج اليوم",
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
        "enabled": True, "samples": int(len(data)), "auc": round(auc, 4),
        "model_used": True, "model": "RandomForest + MLP(32,16)",
        "horizon_days": horizon, "positive_return": threshold,
    }
