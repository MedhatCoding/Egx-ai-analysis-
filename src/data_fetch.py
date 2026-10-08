"""سحب الأسعار: Yahoo أساسي، EODHD احتياطي بميزانية طلبات، والكاش في data/prices."""
from __future__ import annotations

import os
import time
from datetime import date, datetime, timedelta, timezone

import pandas as pd
import requests

from .config import PRICES

COLS = ["open", "high", "low", "close", "volume"]


# ---------------------------------------------------------------- الكاش
def cache_path(code: str):
    return PRICES / f"{code}.csv"


def read_cache(code: str) -> pd.DataFrame | None:
    p = cache_path(code)
    if not p.exists():
        return None
    df = pd.read_csv(p, parse_dates=["date"], index_col="date")
    return df[COLS].sort_index()


def write_cache(code: str, df: pd.DataFrame) -> None:
    PRICES.mkdir(parents=True, exist_ok=True)
    out = df[COLS].copy()
    out.index.name = "date"
    out.round(4).to_csv(cache_path(code))


def _clean(df: pd.DataFrame) -> pd.DataFrame:
    df = df[COLS].copy()
    df.index = pd.to_datetime(df.index).tz_localize(None).normalize()
    df.index.name = "date"
    df = df[~df.index.duplicated(keep="last")].sort_index()
    df = df.dropna(subset=["close", "high", "low", "open"])
    df["volume"] = df["volume"].fillna(0)
    # شموع غير منطقية
    df = df[(df["close"] > 0) & (df["high"] >= df["low"])]
    return df


# ---------------------------------------------------------------- Yahoo
def fetch_yahoo(symbol: str, years: int, retries: int = 3) -> pd.DataFrame | None:
    import yfinance as yf  # استيراد متأخر عشان الاختبار بدون إنترنت

    start = (date.today() - timedelta(days=int(years * 365.25))).isoformat()
    last_err = None
    for attempt in range(retries):
        try:
            raw = yf.Ticker(symbol).history(start=start, auto_adjust=True, actions=False)
            if raw is not None and len(raw) > 0:
                raw = raw.rename(columns=str.lower)
                return _clean(raw)
            return None
        except Exception as e:  # noqa: BLE001
            last_err = e
            time.sleep(1.5 * (attempt + 1))
    print(f"  [Yahoo] فشل {symbol}: {last_err}")
    return None


# ---------------------------------------------------------------- EODHD
def fetch_eodhd(code: str, token: str, start: date) -> pd.DataFrame | None:
    try:
        r = requests.get(
            f"https://eodhd.com/api/eod/{code}.EGX",
            params={"api_token": token, "fmt": "json", "from": start.isoformat()},
            timeout=30,
        )
        if r.status_code != 200:
            print(f"  [EODHD] {code}: HTTP {r.status_code}")
            return None
        rows = r.json()
        if not rows:
            return None
        df = pd.DataFrame(rows)
        df["date"] = pd.to_datetime(df["date"])
        df = df.set_index("date")
        # تعديل الأسعار بمعامل التعديل عشان تتسق مع Yahoo (auto_adjust)
        factor = (df["adjusted_close"] / df["close"]).where(df["close"] > 0, 1.0)
        for c in ("open", "high", "low"):
            df[c] = df[c] * factor
        df["close"] = df["adjusted_close"]
        return _clean(df)
    except Exception as e:  # noqa: BLE001
        print(f"  [EODHD] فشل {code}: {e}")
        return None


def _eodhd_budget(state: dict, cfg: dict) -> int:
    today = datetime.now(timezone.utc).date().isoformat()
    e = state.setdefault("eodhd", {})
    if e.get("date") != today:
        e["date"] = today
        e["calls"] = 0
    return max(0, cfg["data"]["eodhd_daily_budget"] - e["calls"])


# ---------------------------------------------------------------- OANOR (بيانات لحظية للسوق المصري)
def oanor_key() -> str:
    return os.environ.get("OANOR_API_KEY") or os.environ.get("OANOR_KEY") or ""

def fetch_oanor_market() -> dict | None:
    """لقطة لحظية للسوق من OANOR؛ نجرب المفتاح ثم الاختبار العام عند 401/403."""
    key = oanor_key()
    headers = {"x-oanor-key": key} if key else {}
    base = "https://api.oanor.com/egx-api/v1"
    out = {}
    try:
        r = requests.get(f"{base}/index", headers=headers, timeout=20)
        if r.status_code in (401, 403) and headers:
            r = requests.get(f"{base}/index", timeout=20)
        if r.status_code == 200:
            out["index"] = r.json()
        else:
            print(f"  [OANOR] index HTTP {r.status_code}")
        time.sleep(1.1)
        r = requests.get(f"{base}/screener", params={"sort": "change", "order": "desc", "limit": 20}, headers=headers, timeout=20)
        if r.status_code in (401, 403) and headers:
            r = requests.get(f"{base}/screener", params={"sort": "change", "order": "desc", "limit": 20}, timeout=20)
        if r.status_code == 200:
            out["screener"] = r.json()
        else:
            print(f"  [OANOR] screener HTTP {r.status_code}")
        return out or None
    except Exception as e:
        print(f"  [OANOR] تعذر جلب لقطة السوق: {e}")
        return None

def fetch_eodhd_index(symbol: str, token: str, years: int) -> pd.DataFrame | None:
    """EODHD index symbols already contain .INDX; لا نضيف .EGX إليها."""
    try:
        r = requests.get(
            f"https://eodhd.com/api/eod/{symbol}",
            params={"api_token": token, "fmt": "json",
                    "from": (date.today() - timedelta(days=int(years * 365.25))).isoformat()},
            timeout=30,
        )
        if r.status_code != 200:
            return None
        rows = r.json()
        if not rows:
            return None
        df = pd.DataFrame(rows)
        df["date"] = pd.to_datetime(df["date"])
        df = df.set_index("date")
        return _clean(df)
    except Exception as e:
        print(f"  [EODHD] فشل المؤشر {symbol}: {e}")
        return None

def fetch_market_indices(cfg: dict, state: dict, offline: bool = False) -> dict:
    """يجرب المؤشرات الرئيسية، ويحفظ ما ينجح منها بدون اختلاق بيانات."""
    names = {
        "EGX30": "CASE30.INDX",
        "EGX70": "CCSI.INDX",
    }
    token = _eodhd_token()
    result = {}
    for name, symbol in names.items():
        p = PRICES / f"_INDEX_{name.replace(' ', '_')}.csv"
        df = None
        if not offline and token and _eodhd_budget(state, cfg) > 0:
            state["eodhd"]["calls"] += 1
            df = fetch_eodhd_index(symbol, token, cfg["data"]["history_years"])
            if df is not None and len(df) >= 20:
                write_cache(f"_INDEX_{name.replace(' ', '_')}", df)
        if df is None:
            try:
                df = read_cache(f"_INDEX_{name.replace(' ', '_')}")
            except Exception:
                df = None
        if df is not None and len(df):
            last = df.iloc[-1]
            prev = df.iloc[-2]["close"] if len(df) > 1 else None
            result[name] = {
                "symbol": symbol, "close": float(last["close"]),
                "change_pct": float((last["close"] / prev - 1) * 100) if prev else None,
                "date": str(df.index[-1].date()),
            }
    return result

# ---------------------------------------------------------------- التحديث الكامل
def refresh_all(cfg: dict, codes: list[str], state: dict, offline: bool = False) -> pd.DataFrame:
    """يحدّث الكاش لكل الرموز ويرجع جدول التغطية."""
    d = cfg["data"]
    token = _eodhd_token()
    report = []

    for i, code in enumerate(codes, 1):
        row = {"code": code, "source": "none", "bars": 0, "last_date": "", "note": ""}
        cached = read_cache(code)
        fresh = None

        if not offline:
            fresh = fetch_yahoo(code + d["yahoo_suffix"], d["history_years"])
            time.sleep(d["request_sleep"])

        if fresh is not None and len(fresh) >= 20:
            write_cache(code, fresh)
            row.update(source="yahoo", bars=len(fresh), last_date=str(fresh.index[-1].date()))
        elif cached is not None:
            merged, src = cached, "cache"
            # نحاول نكمّل آخر الشموع من EODHD لو فيه ميزانية
            if not offline and token and _eodhd_budget(state, cfg) > 0:
                state["eodhd"]["calls"] += 1
                add = fetch_eodhd(code, token, (cached.index[-1] - timedelta(days=3)).date())
                if add is not None and len(add) > 0:
                    merged = pd.concat([cached, add])
                    merged = merged[~merged.index.duplicated(keep="last")].sort_index()
                    write_cache(code, merged)
                    src = "cache+eodhd"
            row.update(source=src, bars=len(merged), last_date=str(merged.index[-1].date()))
            row["note"] = "Yahoo فشل، استخدمنا الكاش"
        elif not offline and token and _eodhd_budget(state, cfg) > 0:
            state["eodhd"]["calls"] += 1
            start = date.today() - timedelta(days=365)  # الخطة المجانية = سنة تاريخ
            add = fetch_eodhd(code, token, start)
            if add is not None and len(add) > 0:
                write_cache(code, add)
                row.update(source="eodhd", bars=len(add), last_date=str(add.index[-1].date()))
                row["note"] = "من EODHD فقط (سنة تاريخ)"
            else:
                row["note"] = "لا بيانات (Yahoo وEODHD)"
        else:
            row["note"] = "لا بيانات"

        report.append(row)
        if i % 20 == 0:
            print(f"  ... {i}/{len(codes)}")

    return pd.DataFrame(report)


def _eodhd_token() -> str:
    return os.environ.get("EODHD_API_TOKEN") or os.environ.get("EODHD_API_KEY") or ""

def fetch_benchmark(cfg: dict, state: dict, offline: bool = False) -> pd.DataFrame | None:
    """EGX30: Yahoo أولًا، ثم EODHD كاحتياطي، ثم آخر كاش صالح."""
    sym = cfg["data"].get("benchmark_yahoo_symbol", "^CASE30")
    eodhd_sym = cfg["data"].get("benchmark_eodhd_symbol", "CASE30.INDX")
    p = PRICES / "_BENCH.csv"
    if not offline:
        df = fetch_yahoo(sym, cfg["data"]["history_years"])
        if df is not None and len(df) > 60:
            df.index.name = "date"
            df[COLS].round(4).to_csv(p)
            return df
        token = _eodhd_token()
        if token and _eodhd_budget(state, cfg) > 0:
            state["eodhd"]["calls"] += 1
            try:
                add = fetch_eodhd_index(eodhd_sym, token, cfg["data"]["history_years"])
                if add is not None and len(add) > 60:
                    add[COLS].round(4).to_csv(p)
                    return add
            except Exception as e:
                print(f"  [EODHD] تعذر جلب EGX30: {e}")
    if p.exists():
        try:
            df = pd.read_csv(p, parse_dates=["date"], index_col="date")[COLS]
            if len(df) > 60:
                return df
        except Exception:
            pass
    return None


def drop_incomplete_bar(df: pd.DataFrame, now: datetime, close_hour: int) -> pd.DataFrame:
    """نتجاهل شمعة اليوم لو الجلسة لسه ما خلصتش."""
    if len(df) and df.index[-1].date() >= now.date() and now.hour < close_hour:
        return df.iloc[:-1]
    return df


def load_prices(codes: list[str], cfg: dict, now: datetime) -> dict[str, pd.DataFrame]:
    out = {}
    for c in codes:
        df = read_cache(c)
        if df is None or len(df) == 0:
            continue
        df = drop_incomplete_bar(df, now, cfg["market"]["session_close_hour"])
        if len(df) >= cfg["data"]["min_bars"]:
            out[c] = df
    return out
