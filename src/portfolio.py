"""محرك محفظة شخصية: يربط المراكز التي يدخلها المستخدم بإشارة النظام اليومية."""
from __future__ import annotations
import pandas as pd

ACTIONS = {
    "SELL": "بيع",
    "HOLD": "احتفاظ",
    "INCREASE": "زيادة",
}

def recommend_stock(row: dict, regime: str, avg_cost: float | None = None) -> tuple[str, str]:
    score = float(row.get("score") or 0)
    signal = str(row.get("signal") or "")
    close = float(row.get("close") or 0)
    stop = row.get("stop")
    if stop is not None and close > 0 and close < float(stop) * 0.98:
        return "SELL", "السعر تحت وقف الخسارة بهامش واضح؛ المخاطرة لم تعد مناسبة."
    if signal == "AVOID" or score < 40:
        return "SELL", "النقاط منخفضة أو الإشارة تجنّب؛ الأفضل تخفيض المخاطرة."
    if regime == "down" and score < 60:
        return "SELL", "اتجاه السوق هابط والسهم لا يملك قوة كافية لتبرير الاحتفاظ."
    if signal == "BUY" and score >= 75 and regime not in {"down", "weak"}:
        if avg_cost and close > avg_cost * 1.20:
            return "HOLD", "السهم قوي، لكن الربح المتحقق كبير؛ الاحتفاظ أفضل من زيادة المركز الآن."
        return "INCREASE", "الإشارة قوية والسوق يسمح بزيادة انتقائية للمركز."
    return "HOLD", "الاتجاه الحالي لا يبرر البيع، وفي الوقت نفسه شروط زيادة المركز غير مكتملة."

def recommend_fund(score: float | None, trend: str, regime: str) -> tuple[str, str]:
    if score is None:
        return "HOLD", "لا توجد بيانات كافية عن الصندوق نفسه؛ لا يتم اختلاق قرار من سعر غير متاح."
    s = float(score)
    if s < 40 or (regime == "down" and s < 55):
        return "SELL", "إشارة الفئة ضعيفة والسوق لا يدعم زيادة المخاطرة."
    if s >= 75 and trend == "صاعد" and regime not in {"down", "weak"}:
        return "INCREASE", "اتجاه الفئة قوي وبيئة السوق تسمح بزيادة انتقائية."
    return "HOLD", "الاتجاه مقبول لكن شروط زيادة المركز ليست قوية بما يكفي."

def evaluate(holdings: list[dict], table: pd.DataFrame | None, funds: dict, regime: str) -> pd.DataFrame:
    rows = []
    table_map = {}
    if table is not None and not table.empty:
        table_map = {str(r["code"]): r.to_dict() for _, r in table.iterrows()}
    fund_map = {}
    for category in ("sharia_equity", "gold"):
        item = funds.get(category) or {}
        for f in item.get("funds", []):
            fund_map[f["name"]] = (category, item)

    for h in holdings:
        typ, key = h.get("type"), h.get("key")
        qty = float(h.get("quantity") or 0)
        avg = float(h.get("avg_cost") or 0)
        if typ == "stock" and key in table_map:
            r = table_map[key]
            action, reason = recommend_stock(r, regime, avg)
            current = float(r.get("close") or 0)
            rows.append({
                "النوع": "سهم", "الأصل": r.get("name", key), "الرمز": key,
                "الكمية": qty, "متوسط التكلفة": avg, "السعر الحالي": current,
                "القيمة": qty * current, "الربح/الخسارة %": ((current / avg - 1) * 100 if avg > 0 else None),
                "النقاط": float(r.get("score") or 0), "القرار": ACTIONS[action], "reason": reason,
            })
        elif typ == "fund" and key in fund_map:
            category, item = fund_map[key]
            action, reason = recommend_fund(item.get("score"), item.get("trend", "غير متاح"), regime)
            rows.append({
                "النوع": "صندوق", "الأصل": key, "الرمز": "",
                "الكمية": qty, "متوسط التكلفة": avg, "السعر الحالي": None,
                "القيمة": None, "الربح/الخسارة %": None,
                "النقاط": item.get("score"), "القرار": ACTIONS[action], "reason": reason,
            })
    return pd.DataFrame(rows)

def totals(df: pd.DataFrame) -> dict:
    if df is None or df.empty:
        return {"value": 0, "cost": 0, "pnl": 0, "pnl_pct": None}
    stocks = df[df["النوع"] == "سهم"].copy()
    value = float(stocks["القيمة"].fillna(0).sum())
    cost = float((stocks["الكمية"].fillna(0) * stocks["متوسط التكلفة"].fillna(0)).sum())
    pnl = value - cost
    return {"value": value, "cost": cost, "pnl": pnl, "pnl_pct": pnl / cost * 100 if cost else None}


def risk_summary(df: pd.DataFrame) -> dict:
    if df is None or df.empty:
        return {"positions": 0, "sell": 0, "hold": 0, "increase": 0, "concentration": 0.0}
    actions = df["القرار"].value_counts().to_dict()
    values = pd.to_numeric(df["القيمة"], errors="coerce").fillna(0)
    total = float(values.sum())
    top = float(values.max()) if len(values) else 0.0
    return {
        "positions": int(len(df)),
        "sell": int(actions.get("بيع", 0)),
        "hold": int(actions.get("احتفاظ", 0)),
        "increase": int(actions.get("زيادة", 0)),
        "concentration": (top / total * 100.0) if total else 0.0,
    }
