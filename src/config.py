"""تحميل الإعدادات والمسارات وحالة التشغيل."""
from __future__ import annotations

import json
import os
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml

ROOT = Path(__file__).resolve().parent.parent
DATA = Path(os.environ.get("EGX_DATA_DIR", ROOT / "data"))
PRICES = DATA / "prices"
SIGNALS = DATA / "signals"
BACKTEST = DATA / "backtest"
STATE_FILE = DATA / "state.json"


def load_config(path: Path | None = None) -> dict:
    path = path or ROOT / "config.yaml"
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def cairo_now(cfg: dict) -> datetime:
    return datetime.now(ZoneInfo(cfg["market"]["timezone"]))


def load_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}
    return {}


def save_state(state: dict) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def load_holidays() -> set[date]:
    f = DATA / "holidays.txt"
    out: set[date] = set()
    if not f.exists():
        return out
    for line in f.read_text(encoding="utf-8").splitlines():
        line = line.split("#")[0].strip()
        if not line:
            continue
        try:
            out.add(date.fromisoformat(line))
        except ValueError:
            print(f"[تحذير] سطر إجازة غير صالح: {line}")
    return out
