"""محاكاة صفقة واحدة. نفس الدالة تُستخدم في الـ backtest وفي تتبع التوصيات الفعلية،
عشان الأرقام تكون قابلة للمقارنة.

الافتراضات (متحفظة):
- الدخول بسعر افتتاح الشمعة التالية لشمعة الإشارة.
- لو الافتتاح تحت الوقف أو فوق الهدف الأول، الصفقة تُتجاهل (skipped).
- لو الوقف والهدف اتلمسوا في نفس الشمعة، نفترض أن الوقف اتضرب الأول.
- لو الافتتاح فتح بفجوة تحت الوقف، الخروج بسعر الافتتاح (مش بسعر الوقف).
- خروج زمني بعد max_days جلسة بسعر الإغلاق.
"""
from __future__ import annotations

import numpy as np


def simulate_trade(o, h, l, c, sig_i: int, stop: float, t1: float, max_days: int, cost_pct: float) -> dict:
    n = len(c)
    e = sig_i + 1
    if e >= n:
        return {"status": "pending"}
    entry = float(o[e])
    if not np.isfinite(entry) or not np.isfinite(stop) or not np.isfinite(t1):
        return {"status": "skipped"}
    if entry <= stop or entry >= t1:
        return {"status": "skipped"}

    risk = entry - stop
    cost = cost_pct / 100.0 * entry
    last = min(e + max_days - 1, n - 1)

    def done(status: str, j: int, px: float, reason: str) -> dict:
        r_net = ((px - entry) - cost) / risk
        return {
            "status": status,
            "entry": entry,
            "exit": float(px),
            "entry_idx": e,
            "exit_idx": j,
            "reason": reason,
            "r_net": float(r_net),
            "ret_pct": float((px / entry - 1.0) * 100.0 - cost_pct),
            "days": int(j - e + 1),
        }

    for j in range(e, last + 1):
        if j > e:
            if o[j] <= stop:
                return done("closed", j, o[j], "stop")
            if o[j] >= t1:
                return done("closed", j, o[j], "target")
        if l[j] <= stop:
            return done("closed", j, stop, "stop")
        if h[j] >= t1:
            return done("closed", j, t1, "target")

    if last - e + 1 >= max_days:
        return done("closed", last, c[last], "time")
    return done("open", n - 1, c[n - 1], "open")
