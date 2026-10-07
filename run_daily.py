#!/usr/bin/env python
"""نقطة تشغيل التقرير اليومي (بيستخدمها GitHub Actions، وتقدر تشغّلها يدويًا).

أمثلة:
  python run_daily.py --dry-run --force     # تجربة كاملة بدون إرسال تلجرام
  python run_daily.py --force               # تشغيل فعلي في أي وقت
  python run_daily.py                       # تشغيل عادي (يحترم أيام التداول والإجازات والوقت)
"""
import argparse
import json
import sys

from src import pipeline


def main() -> int:
    ap = argparse.ArgumentParser(description="التقرير اليومي للأسهم المصرية")
    ap.add_argument("--force", action="store_true", help="تجاهل فحص اليوم والوقت وحالة الإرسال")
    ap.add_argument("--dry-run", action="store_true", help="جهّز التقرير والملفات بدون إرسال تلجرام")
    ap.add_argument("--offline", action="store_true", help="اعتمد على الكاش فقط بدون أي اتصال")
    args = ap.parse_args()

    res = pipeline.run(force=args.force, dry_run=args.dry_run, offline=args.offline)
    print(json.dumps(res, ensure_ascii=False, indent=2, default=str))
    return 1 if res["status"] == "not_sent" else 0


if __name__ == "__main__":
    sys.exit(main())
