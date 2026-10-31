#!/usr/bin/env python
"""Daily report and opening-hour review runner."""
import argparse
import json
from datetime import datetime, time
from zoneinfo import ZoneInfo

from src import config as C, pipeline
from src.live_quotes import fetch_live_quotes, compare_snapshot, validate_quote_freshness
from src.telegram import send_message


def opening_review(cfg, now):
    state = C.load_state()
    day = now.date().isoformat()
    if state.get("opening_review_attempt_date") == day or state.get("last_opening_review_date") == day:
        return {"status": "skipped", "detail": "تم تسجيل محاولة مراجعة اليوم؛ منعًا لتكرار رسالة محتملة"}
    path = C.SIGNALS / "latest.json"
    if not path.exists():
        return {"status": "not_sent", "detail": "لا يوجد تقرير توصيات"}
    try:
        report = json.loads(path.read_text(encoding="utf-8"))
        generated = datetime.fromisoformat(report["generated_at"])
        if generated.tzinfo is None:
            generated = generated.replace(tzinfo=ZoneInfo(cfg["market"]["timezone"]))
        age = (now - generated.astimezone(now.tzinfo)).total_seconds() / 60
        if generated.astimezone(now.tzinfo).date() != now.date() or age < 0 or age > 180:
            return {"status": "not_sent", "detail": "تقرير التوصيات ليس تقرير اليوم أو تجاوز عمره 180 دقيقة"}
    except Exception:
        return {"status": "not_sent", "detail": "تعذر التحقق من تاريخ التقرير"}
    picks = [p for p in report.get("picks", []) if p.get("signal") == "BUY"][:20]
    if not picks:
        state["last_opening_review_date"] = day
        C.save_state(state)
        return {"status": "skipped", "detail": "لا توجد فرص شراء"}
    snapshot = fetch_live_quotes([p["code"] for p in picks])
    if not snapshot.get("ok"):
        return {"status": "not_sent", "detail": snapshot.get("error", "فشل جلب الأسعار")}
    freshness = validate_quote_freshness(snapshot, now=now, max_age_minutes=30)
    if not freshness.get("ok"):
        return {"status": "not_sent", "detail": freshness.get("error", "تعذر التحقق من حداثة الأسعار")}
    quotes = {q.get("code"): q for q in snapshot.get("quotes", [])}
    lines = [
        "🔎 <b>مراجعة GPT-Mi بعد ساعة من الافتتاح</b>",
        f"بيانات التقرير: {report.get('data_date')}",
        f"وقت جلب الأسعار: {snapshot.get('retrieved_at')} UTC",
        "مراجعة سعرية للخطة وليست إعادة تحليل أو أمر شراء.",
        "",
    ]
    for pick in picks:
        code = str(pick.get("code", "")).upper()
        q = quotes.get(code)
        if not q:
            lines.append(f"• <b>{code}</b>: السعر غير متاح؛ التوصية غير متحقق منها.")
            continue
        result = compare_snapshot(pick, q)
        lines.append(
            f"• <b>{code} — {pick.get('name', code)}</b>\n"
            f"السعر: {q['price']:.4f} | التغير: {q.get('change_percent')}%\n"
            f"الحالة: {result['status']}\n"
            f"الدخول: {pick.get('entry_low')}–{pick.get('entry_high')} | الوقف المرجعي: {pick.get('stop')}"
        )
    lines.extend(["", "الأسعار Snapshot وليست ضمانًا للتنفيذ. افحص السيولة وسعر العرض/الطلب والإفصاحات وحدود السعر."])
    import os
    token, chat = os.getenv("TELEGRAM_BOT_TOKEN", ""), os.getenv("TELEGRAM_CHAT_ID", "")
    if not token or not chat:
        return {"status": "not_sent", "detail": "بيانات Telegram غير مضبوطة"}
    # Reserve the daily attempt before Telegram: prefer at-most-once delivery over duplicate alerts.
    # An interrupted/ambiguous send requires manual inspection; automatic retries are blocked.
    state["opening_review_attempt_date"] = day
    state["opening_review_attempt_at"] = now.isoformat(timespec="seconds")
    C.save_state(state)
    sent = send_message(token, chat, "\n\n".join(lines))
    state["last_opening_review_date"] = day
    state["last_opening_review_at"] = now.isoformat(timespec="seconds")
    C.save_state(state)
    return {"status": "sent", "messages": sent, "picks": len(picks), "quotes": len(quotes)}


def main():
    ap = argparse.ArgumentParser(description="EGX report and opening review")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--offline", action="store_true")
    ap.add_argument("--opening-review", action="store_true")
    args = ap.parse_args()
    cfg = C.load_config()
    now = C.cairo_now(cfg)
    if args.opening_review:
        if now.weekday() not in cfg["market"]["trading_weekdays"] or now.date() in C.load_holidays():
            result = {"status": "skipped", "detail": "إجازة سوق"}
        else:
            local = now.timetz().replace(tzinfo=None)
            if not args.force and not (time(10, 50) <= local <= time(11, 20)):
                result = {"status": "skipped", "detail": "خارج نافذة مراجعة 11 صباحًا بتوقيت القاهرة"}
            else:
                result = opening_review(cfg, now)
    else:
        local = now.timetz().replace(tzinfo=None)
        if not args.force and not args.dry_run and not (time(8, 50) <= local <= time(9, 20)):
            result = {"status": "skipped", "detail": "التقرير التلقائي محدد 09:00 صباحًا بتوقيت القاهرة"}
        else:
            result = pipeline.run(cfg=cfg, force=args.force, dry_run=args.dry_run, offline=args.offline, now=now)
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    return 1 if result.get("status") == "not_sent" else 0


if __name__ == "__main__":
    raise SystemExit(main())
