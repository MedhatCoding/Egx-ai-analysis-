"""طبقة الأصول البديلة: صناديق أسهم الشريعة وصناديق الذهب.
التحليل الآلي يستخدم مؤشرات مرجعية عندما لا يتوفر تاريخ NAV للصندوق نفسه.
لا يتم اختلاق NAV أو عوائد صندوق غير متاحة.
"""
from __future__ import annotations

from datetime import date, timedelta
import os
import pandas as pd
import requests
import yfinance as yf

SHARIA_FUNDS = [
    {"name": "مصر مؤشر شريعة إكويتي – CI", "category": "sharia_equity", "proxy": "EGX33"},
    {"name": "بلتون وفرة – EGX33", "category": "sharia_equity", "proxy": "EGX33"},
    {"name": "كنز شريعة EGX33 – AAIH", "category": "sharia_equity", "proxy": "EGX33"},
    {"name": "AZ فرص الشريعة", "category": "sharia_equity", "proxy": "EGX33"},
]
GOLD_FUNDS = [
    {"name": "سبيكة – Beltone Evolve Gold", "category": "gold", "proxy": "XAUUSD"},
    {"name": "Gold Misr – CI", "category": "gold", "proxy": "XAUUSD"},
    {"name": "AZ Gold", "category": "gold", "proxy": "XAUUSD"},
    {"name": "EFG Hermes Gold Fund", "category": "gold", "proxy": "XAUUSD"},
]

def _gold_series(years: int = 5, state: dict | None = None, cfg: dict | None = None) -> pd.Series | None:
    """ذهب: Yahoo أولًا ثم EODHD XAUUSD.FOREX كاحتياطي."""
    try:
        raw = yf.Ticker("GC=F").history(start=(date.today() - timedelta(days=int(years * 365.25))).isoformat(), auto_adjust=True, actions=False)
        if raw is not None and not raw.empty:
            s = raw["Close"].dropna()
            s.index = pd.to_datetime(s.index).tz_localize(None).normalize()
            if len(s) >= 220:
                return s
    except Exception:
        pass
    token = os.environ.get("EODHD_API_TOKEN") or os.environ.get("EODHD_API_KEY") or ""
    if token and state is not None and cfg is not None:
        e = state.setdefault("eodhd", {})
        today = date.today().isoformat()
        if e.get("date") != today:
            e["date"], e["calls"] = today, 0
        budget = int(cfg.get("data", {}).get("eodhd_daily_budget", 20))
        if e.get("calls", 0) < budget:
            try:
                e["calls"] += 1
                r = requests.get("https://eodhd.com/api/eod/XAUUSD.FOREX", params={"api_token": token, "fmt": "json", "from": (date.today() - timedelta(days=int(years * 365.25))).isoformat()}, timeout=30)
                if r.status_code == 200:
                    rows = r.json()
                    if rows:
                        df = pd.DataFrame(rows)
                        s = pd.Series(df["close"].astype(float).values, index=pd.to_datetime(df["date"]))
                        s.index = s.index.tz_localize(None).normalize()
                        return s.sort_index()
            except Exception:
                pass
    return None

def _score(s: pd.Series | None) -> dict:
    if s is None or len(s) < 220:
        return {"score": None, "ret20": None, "ret60": None, "trend": "غير متاح"}
    sma50 = s.rolling(50).mean()
    sma200 = s.rolling(200).mean()
    ret20 = float((s.iloc[-1] / s.iloc[-21] - 1) * 100)
    ret60 = float((s.iloc[-1] / s.iloc[-61] - 1) * 100)
    score = 50 + 20 * float(s.iloc[-1] > sma50.iloc[-1]) + 20 * float(s.iloc[-1] > sma200.iloc[-1]) + 10 * float(sma50.iloc[-1] > sma50.iloc[-11])
    return {
        "score": round(min(100, max(0, score)), 1),
        "ret20": round(ret20, 2),
        "ret60": round(ret60, 2),
        "trend": "صاعد" if score >= 70 else "محايد" if score >= 50 else "ضعيف",
    }

def build_fund_overlay(bench: pd.Series | None, cfg: dict, sharia_close: pd.Series | None = None, state: dict | None = None) -> dict:
    gold = _gold_series(int(cfg.get("data", {}).get("history_years", 5)), state, cfg)
    sh = _score(sharia_close if sharia_close is not None else bench)
    go = _score(gold)
    return {
        "sharia_equity": {
            "reference": "EGX33",
            "score": sh["score"], "ret20": sh["ret20"], "ret60": sh["ret60"], "trend": sh["trend"],
            "funds": SHARIA_FUNDS,
        },
        "gold": {
            "reference": "XAUUSD",
            "score": go["score"], "ret20": go["ret20"], "ret60": go["ret60"], "trend": go["trend"],
            "funds": GOLD_FUNDS,
        },
        "note": "درجات الفئات مرجعية وليست NAV للصندوق. عند توفر تاريخ NAV موثوق يمكن استبدال المرجع بتحليل الصندوق نفسه.",
    }
