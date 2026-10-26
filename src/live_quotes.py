"""OANOR EGX live quotes for explicit pre-trade rechecks.

Quotes are a snapshot, not intraday OHLCV history. Never overwrite EOD candles or
recalculate RSI/MACD from a single quote. Caller must display as-of and freshness.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

import requests


def fetch_live_quotes(codes: list[str], timeout: int = 12) -> dict[str, Any]:
    """Fetch up to 20 EGX quotes in one request. Returns safe structured status."""
    unique = list(dict.fromkeys(str(c).strip().upper() for c in codes if str(c).strip()))
    if not unique:
        return {"ok": False, "error": "لا توجد رموز مختارة", "quotes": []}
    if len(unique) > 20:
        unique = unique[:20]
    key = (
        os.environ.get("OANOR_API_KEY")
        or os.environ.get("OANOR_API_TOKEN")
        or os.environ.get("OANOR_KEY")
        or ""
    ).strip().strip('"').strip("'")
    if not key:
        return {"ok": False, "error": "مفتاح OANOR غير مضبوط في بيئة التطبيق", "quotes": []}
    try:
        response = requests.get(
            "https://api.oanor.com/egx-api/v1/quote",
            params={"codes": ",".join(unique)},
            headers={"x-oanor-key": key},
            timeout=timeout,
        )
        if response.status_code == 429:
            return {"ok": False, "error": "تم بلوغ حد الطلبات المجاني؛ حاول لاحقًا", "quotes": []}
        response.raise_for_status()
        payload = response.json()
        data = payload.get("data") if isinstance(payload, dict) else None
        quotes = data.get("quotes", []) if isinstance(data, dict) else []
        if not isinstance(quotes, list):
            quotes = []
        clean = []
        for item in quotes:
            if not isinstance(item, dict):
                continue
            ticker = str(item.get("ticker") or "").strip().upper()
            try:
                price = float(item.get("price"))
            except (TypeError, ValueError):
                continue
            if ticker not in unique or price <= 0:
                continue
            clean.append({
                "code": ticker,
                "company": str(item.get("company") or ticker),
                "price": price,
                "change": _num(item.get("change")),
                "change_percent": _num(item.get("change_percent")),
                "open": _num(item.get("open")),
                "high": _num(item.get("high")),
                "low": _num(item.get("low")),
                "volume": _num(item.get("volume")),
                "source": str(data.get("source") or "OANOR / EGX"),
                "as_of": str((payload.get("meta") or {}).get("timestamp") or ""),
            })
        if not clean:
            return {"ok": False, "error": "المصدر لم يرجع أسعارًا صالحة للرموز المطلوبة", "quotes": []}
        return {"ok": True, "source": "OANOR / EGX", "retrieved_at": datetime.now(timezone.utc).isoformat(), "quotes": clean}
    except requests.Timeout:
        return {"ok": False, "error": "انتهت مهلة جلب الأسعار اللحظية", "quotes": []}
    except Exception as exc:  # noqa: BLE001
        # Never expose request headers or secret-bearing URLs in UI/logs.
        return {"ok": False, "error": f"تعذر جلب الأسعار اللحظية ({type(exc).__name__})", "quotes": []}


def _num(value):
    try:
        number = float(value)
        return number if number == number and abs(number) != float("inf") else None
    except (TypeError, ValueError):
        return None


def compare_snapshot(pick: dict, quote: dict) -> dict:
    """Classify price-vs-plan status; does not invent a replacement recommendation."""
    try:
        p = float(quote["price"])
        low = float(pick["entry_low"])
        high = float(pick["entry_high"])
        stop = float(pick["stop"])
        target = float(pick["t1"])
    except (KeyError, TypeError, ValueError):
        return {"status": "تعذر المقارنة", "price": quote.get("price")}
    if p <= stop:
        status = "السعر عند/أسفل الوقف المرجعي — أعد التقييم"
    elif p >= target:
        status = "وصل/تجاوز الهدف الأول — لا تطارد السعر"
    elif p > high:
        status = "أعلى من نطاق الدخول الأصلي — الإشارة القديمة لا تعني شراء الآن"
    elif p < low:
        status = "أسفل نطاق الدخول الأصلي — أعد فحص سبب الهبوط والسيولة"
    else:
        status = "داخل نطاق الدخول الأصلي فقط؛ يلزم فحص بقية الشروط"
    return {"status": status, "price": p, "change_percent": quote.get("change_percent")}
