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
    {"name": "مصر شريعة إكويتي – CI", "category": "sharia_equity", "proxy": "EGX33"},
    {"name": "بلتون وفرة – EGX33", "category": "sharia_equity", "proxy": "EGX33"},
    {"name": "كنز شريعة EGX33 – AAIH", "category": "sharia_equity", "proxy": "EGX33"},
    {"name": "أزيموت فرص الشريعة AZ", "category": "sharia_equity", "proxy": "EGX33"},
    {"name": "نعيم مصر للأسهم المتوافق مع الشريعة", "category": "sharia_equity", "proxy": "EGX33"},
    {"name": "سنابل الإسلامي", "category": "sharia_equity", "proxy": "EGX33"},
    {"name": "الوفاق الإسلامي", "category": "sharia_equity", "proxy": "EGX33"},
    {"name": "البركات – بنك البركة مصر", "category": "sharia_equity", "proxy": "EGX33"},
    {"name": "الحصن – بنك مصر", "category": "sharia_equity", "proxy": "EGX33"},
    {"name": "أمان المتوافق مع الشريعة", "category": "sharia_equity", "proxy": "EGX33"},
    {"name": "ألفا المتوافق مع الشريعة – بيت التمويل الكويتي", "category": "sharia_equity", "proxy": "EGX33"},
    {"name": "هلال – بنك نكست", "category": "sharia_equity", "proxy": "EGX33"},
    {"name": "هيرميس لأسهم الشريعة", "category": "sharia_equity", "proxy": "EGX33"},
    {"name": "الحياة المتوافق مع الشريعة – بنك الكويت الوطني", "category": "sharia_equity", "proxy": "EGX33"},
    {"name": "صندوق استثمار بنك فيصل الإسلامي", "category": "sharia_equity", "proxy": "EGX33"},
    {"name": "بشائر – صندوق البنك الأهلي السادس وبنك البركة", "category": "sharia_equity", "proxy": "EGX33"},
]
GOLD_FUNDS = [
    {"name": "أزيموت جولد", "category": "gold", "proxy": "XAUUSD"},
    {"name": "بلتون سبائك", "category": "gold", "proxy": "XAUUSD"},
    {"name": "الأهلي دهب", "category": "gold", "proxy": "XAUUSD"},
    {"name": "جولد مصر", "category": "gold", "proxy": "XAUUSD"},
    {"name": "دهب مباشر", "category": "gold", "proxy": "XAUUSD"},
    {"name": "هيرميس للاستثمار في الذهب", "category": "gold", "proxy": "XAUUSD"},
    {"name": "الشكمجية بكرة للذهب", "category": "gold", "proxy": "XAUUSD"},
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


def _normalize_digits(value: str) -> str:
    """Normalize Arabic/Persian digits and decimal separators to parse published prices."""
    trans = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹٫٬", "01234567890123456789.,")
    return value.translate(trans)


# App labels -> exact public fund names/codes on Snduk.
FUND_SOURCE_MATCHES = {
    "مصر شريعة إكويتي – CI": ("CSF", ("مصر شريعة إكويتي", "Misr Shariah Equity")),
    "بلتون وفرة – EGX33": ("BWA", ("بلتون وفرة للاستثمار", "Beltone Wafra")),
    "كنز شريعة EGX33 – AAIH": ("KSF", ("كنز شريعة EGX33", "كنز شريعة", "Kenz EGX33 Shariah")),
    "أزيموت فرص الشريعة AZ": ("ASO", ("ازيموت فرص الشريعة", "أزيموت فرص الشريعة", "Azimut Shariah")),
    "نعيم مصر للأسهم المتوافق مع الشريعة": ("NMF", ("صندوق نعيم مصر للأسهم المتوافق مع الشريعة", "نعيم مصر للأسهم المتوافق مع الشريعة",)),
    "سنابل الإسلامي": ("SSF", ("صندوق سنابل الإسلامي", "سنابل الإسلامي", "Sanabel Islamic")),
    "الوفاق الإسلامي": ("WSF", ("الوفاق الإسلامي",)),
    "البركات – بنك البركة مصر": ("BEF", ("صندوق البركات", "البركات المتوافق مع الشريعة", "Al Baraka Bank Islamic Fund")),
    "الحصن – بنك مصر": ("BM4", ("صندوق استثمار بنك مصر الرابع", "صندوق الحصن المتوافق مع الشريعة", "الحصن المتوافق مع الشريعة", "صندوق الحصن")),
    "أمان المتوافق مع الشريعة": ("FCA", ("صندوق أمان المتوافق مع الشريعة", "أمان المتوافق مع الشريعة", "صندوق استثمار بنك فيصل و بنك CIB")),
    "ألفا المتوافق مع الشريعة – بيت التمويل الكويتي": ("KAE", ("ألفا للاستثمار فى الأسهم", "ألفا للاستثمار في الأسهم")),
    "هلال – بنك نكست": ("NHF", ("صندوق هلال",)),
    "هيرميس لأسهم الشريعة": ("HSE", ("صندوق هيرميس لأسهم الشريعة", "هيرميس لأسهم الشريعة", "هيرميس أسهم شريعة EGX 33")),
    "بشائر – صندوق البنك الأهلي السادس وبنك البركة": ("BSF", ("صندوق بشائر", "بشائر - صندوق البنك الأهلى السادس", "بشائر – صندوق البنك الأهلي السادس", "بشائر الإسلامي", "بشائر الاسلامي", "صندوق استثمار البنك الاهلى المصري و بنك البركه")),
    "أزيموت جولد": ("AZG", ("صندوق ازيموت جولد المتوافق مع الشريعة", "ازيموت جولد المتوافق مع الشريعة", "Azimut Gold")),
    "بلتون سبائك": ("BSB", ("صندوق بلتون سبائك", "بلتون سبائك", "Beltone Sabayek")),
    "الأهلي دهب": ("ADF", ("الأهلي دهب",)),
    "جولد مصر": ("CGF", ("جولد مصر", "Gold Misr")),
    "دهب مباشر": ("DMB", ("دهب مباشر",)),
    "هيرميس للاستثمار في الذهب": ("HGF", ("صندوق هيرميس للاستثمار في الذهب", "هيرميس للاستثمار في الذهب", "هيرميس للذهب")),
    "الشكمجية بكرة للذهب": ("SHK", ("صندوق الشكمجية بكرة للاستثمار فى الذهب", "الشكمجية بكرة", "الشكمجية بكرة للاستثمار في الذهب")),
}


def fetch_fund_navs() -> dict:
    """Fetch actual published NAVs for every fund configured in the app from one public daily-price page."""
    url = "https://snduk.com/eg/page/mutual-funds-prices-today?lang=ar"
    result: dict[str, dict] = {}
    try:
        response = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
        response.raise_for_status()
        tables = pd.read_html(response.text)
        for table in tables:
            for _, row in table.iterrows():
                cells = [str(value).strip() for value in row.tolist() if pd.notna(value)]
                line = _normalize_digits(" ".join(cells)).casefold()
                for app_name, (fund_code, aliases) in FUND_SOURCE_MATCHES.items():
                    if app_name in result:
                        continue
                    if not any(alias.casefold() in line for alias in aliases):
                        continue
                    # Prefer the last table cell: SNDUK's daily-price table ends with the published NAV.
                    price_text = _normalize_digits(cells[-1]) if cells else ""
                    import re
                    matches = re.findall(r"(?<![\w])\d[\d,]*(?:\.\d+)?", price_text)
                    nav = None
                    for token in reversed(matches):
                        try:
                            candidate = float(token.replace(",", ""))
                            if candidate > 0:
                                nav = candidate
                                break
                        except ValueError:
                            continue
                    if nav is None:
                        # Fallback: scan numeric-looking cells from right to left, excluding row number.
                        for cell in reversed(cells[1:]):
                            for token in reversed(re.findall(r"\d[\d,]*(?:\.\d+)?", _normalize_digits(cell))):
                                try:
                                    candidate = float(token.replace(",", ""))
                                    if candidate > 0:
                                        nav = candidate
                                        break
                                except ValueError:
                                    continue
                            if nav is not None:
                                break
                    if nav is None:
                        continue
                    date_text = next((v for v in cells if re.search(r"20\d{2}|٢٠\d{2}", v)), None)
                    result[app_name] = {
                        "nav": nav,
                        "nav_date": date_text,
                        "price_source": "Snduk",
                        "fund_code": fund_code,
                    }
    except Exception:
        # No fabricated prices: missing/unreadable rows remain explicitly unavailable.
        return result
    return result

def build_fund_overlay(bench: pd.Series | None, cfg: dict, sharia_close: pd.Series | None = None, state: dict | None = None) -> dict:
    gold = _gold_series(int(cfg.get("data", {}).get("history_years", 5)), state, cfg)
    sh = _score(sharia_close if sharia_close is not None else bench)
    go = _score(gold)
    published_navs = fetch_fund_navs()
    sharia_funds = [dict(f, **published_navs.get(f["name"], {})) for f in SHARIA_FUNDS]
    gold_funds = [dict(f, **published_navs.get(f["name"], {})) for f in GOLD_FUNDS]
    return {
        "sharia_equity": {
            "reference": "EGX33",
            "score": sh["score"], "ret20": sh["ret20"], "ret60": sh["ret60"], "trend": sh["trend"],
            "funds": sharia_funds,
        },
        "gold": {
            "reference": "XAUUSD",
            "score": go["score"], "ret20": go["ret20"], "ret60": go["ret60"], "trend": go["trend"],
            "funds": gold_funds,
        },
        "note": "درجات الفئات مرجعية وليست NAV للصندوق. عند توفر تاريخ NAV موثوق يمكن استبدال المرجع بتحليل الصندوق نفسه.",
    }
