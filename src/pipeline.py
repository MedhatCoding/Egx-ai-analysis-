"""التشغيلة اليومية: فحص اليوم والوقت ← تحديث البيانات ← تحليل ← سجل التوصيات ← تقرير ← تلجرام.

كل مخرجات لوحة Streamlit بتتكتب هنا في مجلد data (ملفات JSON/CSV صغيرة تُرفع على GitHub).
"""
from __future__ import annotations

import json
import os
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd

from . import config as C
from .backtest import run_backtest
from .data_fetch import fetch_benchmark, load_prices, refresh_all
from .report import build_report, compose_alert
from .signals import analyze, build_result, classify, latest_table
from .telegram import send_message
from .funds import build_fund_overlay
from .track_record import load_history, log_signals, save_history, summarize, update_history
from .universe import build_universe


class DataError(RuntimeError):
    """مشكلة في البيانات تمنع إصدار تقرير موثوق."""


def report_dir() -> Path:
    return C.DATA / "report"


def _write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


# ------------------------------------------------------------------ متى نشتغل؟
def should_run(cfg: dict, now: datetime, state: dict, force: bool = False) -> tuple[bool, str]:
    if force:
        return True, "تشغيل يدوي"
    if now.weekday() not in cfg["market"]["trading_weekdays"]:
        return False, "اليوم إجازة أسبوعية (الجمعة/السبت)"
    if now.date() in C.load_holidays():
        return False, "إجازة رسمية مسجلة في data/holidays.txt"
    start, end = cfg["market"]["report_window"]
    if not (start <= now.strftime("%H:%M") <= end):
        return False, f"خارج نافذة الإرسال ({start}-{end} بتوقيت القاهرة)"
    if state.get("last_sent_date") == now.date().isoformat():
        return False, "تقرير اليوم اتبعت بالفعل"
    return True, "ok"


def expected_last_session(now: datetime, cfg: dict) -> date:
    """آخر جلسة مفروض تكون بياناتها متاحة (بدون احتساب إجازات غير مسجلة)."""
    hol = C.load_holidays()
    d = now.date()
    after_close = now.hour >= cfg["market"]["session_close_hour"]
    if not (after_close and d.weekday() in cfg["market"]["trading_weekdays"] and d not in hol):
        d -= timedelta(days=1)
    for _ in range(21):
        if d.weekday() in cfg["market"]["trading_weekdays"] and d not in hol:
            return d
        d -= timedelta(days=1)
    return d


# ------------------------------------------------------------------ مخرجات اللوحة
def save_outputs(result: dict, latest_cls: pd.DataFrame, regime_df: pd.DataFrame, cov: pd.DataFrame, uni: pd.DataFrame, cfg: dict) -> None:
    C.SIGNALS.mkdir(parents=True, exist_ok=True)
    tbl = latest_cls.copy()
    tbl["why_not_buy"] = tbl["why_not_buy"].apply(lambda x: " | ".join(x) if isinstance(x, list) else "")
    tbl["date"] = pd.to_datetime(tbl["date"]).dt.date.astype(str)
    tbl = tbl.merge(uni[["code", "in_list", "in_egx33"]], on="code", how="left")
    tbl.round(4).to_csv(C.SIGNALS / "table.csv", index=False)

    reg = regime_df.tail(400).copy()
    reg.index.name = "date"
    reg.round(4).to_csv(C.SIGNALS / "regime.csv")
    cov.to_csv(C.SIGNALS / "coverage.csv", index=False)

    out = dict(result)
    out["universe"] = {
        "mode": cfg["universe"]["mode"],
        "total": int(len(uni)),
        "in_list": int(uni["in_list"].sum()),
        "in_egx33": int(uni["in_egx33"].sum()),
        "both": int((uni["in_list"] & uni["in_egx33"]).sum()),
    }
    _write_json(C.SIGNALS / "latest.json", out)


def maybe_backtest(cfg: dict, state: dict, frames: dict, now: datetime, force: bool = False) -> bool:
    every = cfg["backtest"]["refresh_every_days"]
    last = state.get("last_backtest")
    due = force or not last or (now.date() - date.fromisoformat(last)).days >= every
    if not due:
        return False
    summary, strat, _base = run_backtest(frames, cfg)
    summary["generated_at"] = now.isoformat(timespec="seconds")
    summary["stocks"] = len(frames)
    _write_json(C.BACKTEST / "summary.json", summary)
    if len(strat):
        strat.to_csv(C.BACKTEST / "strategy_trades.csv", index=False)
    state["last_backtest"] = now.date().isoformat()
    return True


# ------------------------------------------------------------------ التنفيذ
def _execute(cfg: dict, now: datetime, state: dict, dry_run: bool, offline: bool, force: bool) -> dict:
    uni = build_universe(cfg)
    codes = uni["code"].tolist()
    names = dict(zip(uni["code"], uni["name"]))
    print(f"الأسهم المحللة: {len(codes)} (قائمتك {int(uni['in_list'].sum())} | EGX33 {int(uni['in_egx33'].sum())} | وضع الدمج: {cfg['universe']['mode']})")

    cov = refresh_all(cfg, codes, state, offline=offline)
    bench = fetch_benchmark(cfg, offline=offline)
    prices = load_prices(codes, cfg, now)
    if len(prices) < max(5, int(0.5 * len(codes))):
        raise DataError(f"بيانات غير كافية: {len(prices)} سهم فقط من {len(codes)} وصلت بيانات كافية (Yahoo/EODHD).")

    frames, regime_df, _panel = analyze(prices, bench, cfg)
    latest = latest_table(frames, names, cfg, regime_df.attrs.get("ml_probs", {}))
    last = regime_df.iloc[-1]
    cls = classify(latest, last["regime"], last["regime_score"], cfg)
    result = build_result(frames, regime_df, cls, len(codes), cfg)
    result["funds"] = build_fund_overlay(bench, cfg)
    result["generated_at"] = now.isoformat(timespec="seconds")

    # ---- ملاحظات جودة البيانات
    warnings: list[str] = []
    data_d = date.fromisoformat(result["data_date"])
    exp = expected_last_session(now, cfg)
    if data_d < exp:
        warnings.append(f"آخر جلسة في البيانات {data_d} بينما المتوقع {exp}؛ قد تكون البيانات متأخرة أو الجلسة إجازة غير مسجلة.")
    missing = [c for c in codes if c not in prices]
    if missing:
        warnings.append(f"{len(missing)} سهم بدون بيانات كافية (منها: {', '.join(missing[:6])}).")
    n_cache = int(cov["source"].astype(str).str.startswith("cache").sum())
    if n_cache:
        warnings.append(f"{n_cache} سهم اتحلل ببيانات محفوظة لأن Yahoo فشل معها.")
    if bench is None or len(bench) < 60:
        warnings.append("تعذر جلب EGX30 فاستخدمنا مؤشرًا داخليًا متساوي الأوزان من الأسهم المحللة.")
    n_stale = int(result["signal_counts"].get("STALE", 0))
    if n_stale:
        warnings.append(f"{n_stale} سهم بيانات آخر شمعة له قديمة (موقوف أو متأخر).")

    # ---- سجل التوصيات
    hist = load_history()
    hist = update_history(hist, prices, cfg)
    hist = log_signals(hist, result["picks"], result["data_date"], result["regime"]["label"])
    save_history(hist)
    track = summarize(hist)

    save_outputs(result, cls, regime_df, cov, uni, cfg)
    ran_bt = maybe_backtest(cfg, state, frames, now, force=False)
    if ran_bt:
        print("تم تحديث نتائج الاختبار التاريخي.")

    # ---- التقرير
    rep = build_report(result, track, cfg, now, warnings)
    rep["track_record"] = track
    _write_json(report_dir() / "latest.json", rep)
    print(f"الذكاء الاصطناعي: {rep['llm']}")

    status = "generated"
    detail = ""
    if cfg["telegram"]["enabled"]:
        if dry_run:
            status = "dry_run"
        else:
            token, chat = os.environ.get("TELEGRAM_BOT_TOKEN", ""), os.environ.get("TELEGRAM_CHAT_ID", "")
            if not token or not chat:
                status, detail = "not_sent", "TELEGRAM_BOT_TOKEN أو TELEGRAM_CHAT_ID غير مضبوط في الـ Secrets."
            else:
                n = send_message(token, chat, rep["telegram_html"])
                state["last_sent_date"] = now.date().isoformat()
                status, detail = "sent", f"{n} رسالة"
    return {
        "status": status,
        "detail": detail,
        "data_date": result["data_date"],
        "regime": result["regime"]["label_ar"],
        "buys": [p["code"] for p in result["picks"]],
        "warnings": warnings,
    }


def _alert(cfg: dict, reason: str) -> None:
    token, chat = os.environ.get("TELEGRAM_BOT_TOKEN", ""), os.environ.get("TELEGRAM_CHAT_ID", "")
    if cfg["telegram"]["enabled"] and token and chat:
        try:
            send_message(token, chat, compose_alert(reason))
        except Exception as e:  # noqa: BLE001
            print(f"تعذر إرسال تنبيه الفشل: {type(e).__name__}")


def run(cfg: dict | None = None, force: bool = False, dry_run: bool = False, offline: bool = False,
        now: datetime | None = None, notify_errors: bool = True) -> dict:
    cfg = cfg or C.load_config()
    now = now or C.cairo_now(cfg)
    state = C.load_state()
    ok, why = should_run(cfg, now, state, force)
    if not ok:
        print(f"تخطي التشغيل: {why}")
        return {"status": "skipped", "detail": why}
    try:
        return _execute(cfg, now, state, dry_run, offline, force)
    except Exception as e:  # noqa: BLE001
        if notify_errors and not dry_run:
            _alert(cfg, f"{type(e).__name__}: {e}")
        raise
    finally:
        C.save_state(state)
