"""اختبارات بدون إنترنت (بيانات وهمية). التشغيل:  python tests/test_engine.py   أو   pytest tests

ملحوظة: نحدد EGX_DATA_DIR قبل استيراد أي شيء من src، لأن المسارات بتتحدد وقت الاستيراد.
"""
from __future__ import annotations

import os
import runpy
import shutil
import sys
import tempfile
import types
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
TMP = Path(tempfile.mkdtemp(prefix="egx_test_"))
os.environ["EGX_DATA_DIR"] = str(TMP)

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from tests.synth import make_prices  # noqa: E402

from src import config as C  # noqa: E402
from src import pipeline, report, telegram  # noqa: E402
from src.backtest import run_backtest  # noqa: E402
from src.indicators import atr, compute_indicators, rsi, sma  # noqa: E402
from src.scoring import compute_scores  # noqa: E402
from src.signals import analyze, build_result, classify, latest_table  # noqa: E402
from src.sim import simulate_trade  # noqa: E402
from src.track_record import COMPONENTS, component_stats, load_history, log_signals, save_history, summarize, update_history  # noqa: E402
from src.universe import build_universe  # noqa: E402

CFG = C.load_config()
CAIRO = ZoneInfo("Africa/Cairo")
SUN_9AM = datetime(2026, 9, 20, 9, 5, tzinfo=CAIRO)


# ------------------------------------------------------------------ تجهيز البيانات
def _bull_prices(n: int = 50) -> dict[str, pd.DataFrame]:
    rng = np.random.default_rng(3)
    return {
        f"B{i:03d}": make_prices(
            100 + i, drift=float(rng.choice([0.0015, 0.001, 0.0006, 0.0002])), vol=float(rng.uniform(0.012, 0.022)),
            start_price=float(rng.uniform(5, 80)),
        )
        for i in range(n)
    }


def _setup_data_dir() -> list[str]:
    (TMP / "prices").mkdir(parents=True, exist_ok=True)
    codes = []
    for c, df in _bull_prices().items():
        df.to_csv(TMP / "prices" / f"{c}.csv")
        codes.append(c)
    make_prices(999, drift=0.001, base_volume=2_000, start_price=10).to_csv(TMP / "prices" / "ILLQ.csv")
    make_prices(998, drift=0.001, end="2026-08-20").to_csv(TMP / "prices" / "STAL.csv")
    make_prices(997, n=90).to_csv(TMP / "prices" / "SHRT.csv")
    listed = codes[:45] + ["ILLQ", "STAL", "SHRT"]
    pd.DataFrame({"code": listed, "name_ar": [f"شركة {c}" for c in listed]}).to_csv(TMP / "universe.csv", index=False)
    (TMP / "egx33.txt").write_text("# test\n" + "\n".join(f"{c},Company {c}" for c in codes[40:]) + "\n", encoding="utf-8")
    (TMP / "holidays.txt").write_text("# none\n2026-10-06\n", encoding="utf-8")
    return codes


def _reset_outputs() -> None:
    for name in ("signals", "report", "backtest"):
        shutil.rmtree(TMP / name, ignore_errors=True)
    (TMP / "state.json").unlink(missing_ok=True)


CODES = _setup_data_dir()


def _analysis(prices=None):
    prices = prices or {c: p for c, p in _bull_prices().items()}
    frames, regime_df, _ = analyze(prices, None, CFG)
    latest = latest_table(frames, {c: c for c in frames}, CFG)
    last = regime_df.iloc[-1]
    cls = classify(latest, last["regime"], last["regime_score"], CFG)
    result = build_result(frames, regime_df, cls, len(prices), CFG)
    return frames, regime_df, cls, result


# ------------------------------------------------------------------ المؤشرات
def test_rsi_bounds_and_extremes():
    up = pd.Series(np.linspace(10, 20, 60))
    assert rsi(up).iloc[-1] == 100.0
    down = pd.Series(np.linspace(20, 10, 60))
    assert rsi(down).iloc[-1] < 1.0
    r = rsi(make_prices(1)["close"]).dropna()
    assert (r >= 0).all() and (r <= 100).all()


def test_sma_and_atr():
    s = pd.Series(np.arange(1.0, 101.0))
    assert abs(sma(s, 20).iloc[-1] - s.iloc[-20:].mean()) < 1e-9
    df = make_prices(2)
    a = atr(df["high"], df["low"], df["close"]).dropna()
    assert (a > 0).all()


def test_indicators_are_causal():
    """قيمة المؤشر والنقاط في يوم معين لازم ماتتغيرش لو حذفنا بيانات المستقبل (لا تسريب مستقبل)."""
    df = make_prices(11, drift=0.001)
    full = compute_scores(compute_indicators(df), None, None, CFG)
    for i in (300, 420, 560):
        part = compute_scores(compute_indicators(df.iloc[: i + 1]), None, None, CFG)
        for col in ("score", "stop", "t1", "rsi14", "atr14", "sma50", "high20", "buy_raw"):
            a, b = full[col].iloc[i], part[col].iloc[-1]
            assert (pd.isna(a) and pd.isna(b)) or abs(float(a) - float(b)) < 1e-9, (col, i, a, b)


# ------------------------------------------------------------------ المحاكاة
def _path(o, h, l, c):
    return [np.array(x, dtype=float) for x in (o, h, l, c)]


def test_sim_target_stop_gap_and_skip():
    # فهرس 0 = شمعة الإشارة. الدخول افتتاح الشمعة 1 = 100. الوقف 95 والهدف 110
    o, h, l, c = _path([100, 100, 101, 102], [101, 104, 111, 103], [99, 99, 100, 101], [100, 103, 110, 102])
    r = simulate_trade(o, h, l, c, 0, 95, 110, 20, 0.5)
    assert r["status"] == "closed" and r["reason"] == "target" and r["exit"] == 110
    # الوقف والهدف في نفس الشمعة = الوقف الأول
    o, h, l, c = _path([100, 100, 100], [101, 112, 100], [99, 94, 99], [100, 100, 100])
    assert simulate_trade(o, h, l, c, 0, 95, 110, 20, 0.5)["reason"] == "stop"
    # فجوة تحت الوقف: الخروج بالافتتاح
    o, h, l, c = _path([100, 100, 90], [101, 101, 92], [99, 99, 89], [100, 100, 91])
    r = simulate_trade(o, h, l, c, 0, 95, 110, 20, 0.5)
    assert r["reason"] == "stop" and r["exit"] == 90
    # الدخول تحت الوقف أو فوق الهدف = تجاهل
    o, h, l, c = _path([100, 94], [101, 96], [99, 93], [100, 95])
    assert simulate_trade(o, h, l, c, 0, 95, 110, 20, 0.5)["status"] == "skipped"
    # لا شمعة تالية بعد = pending
    assert simulate_trade(*_path([100], [101], [99], [100]), 0, 95, 110, 20, 0.5)["status"] == "pending"


def test_sim_time_exit():
    n = 30
    o = np.full(n, 100.0); h = np.full(n, 101.0); l = np.full(n, 99.0); c = np.full(n, 100.0)
    r = simulate_trade(o, h, l, c, 0, 95, 110, 10, 0.5)
    assert r["status"] == "closed" and r["reason"] == "time" and r["days"] == 10


# ------------------------------------------------------------------ الإشارات وحالة السوق
def test_bull_universe_gives_valid_picks():
    frames, regime_df, cls, result = _analysis()
    assert result["regime"]["label"] in ("up", "strong_up")
    picks = result["picks"]
    assert 0 < len(picks) <= CFG["risk"]["max_buys_by_regime"][result["regime"]["label"]]
    for p in picks:
        assert p["score"] >= CFG["scoring"]["buy_score"]
        assert p["stop"] < p["close"] < p["t1"] < p["t2"]
        assert p["entry_low"] < p["entry_high"]
        assert p["stop"] < p["entry_low"]
        assert 0 < p["position_pct"] <= CFG["risk"]["max_position_pct"]
    assert result["market"]["advancers"] + result["market"]["decliners"] > 0


def test_bear_universe_gives_no_buys():
    rng = np.random.default_rng(5)
    prices = {f"D{i:03d}": make_prices(500 + i, drift=float(rng.choice([-0.0012, -0.0008, -0.0004])), vol=0.015, start_price=50) for i in range(40)}
    _, _, cls, result = _analysis(prices)
    assert result["regime"]["label"] in ("weak", "down")
    assert len(result["picks"]) <= CFG["risk"]["max_buys_by_regime"][result["regime"]["label"]]
    if result["regime"]["label"] == "down":
        assert result["picks"] == []


def test_limit_down_forces_avoid_and_blocks_buy():
    """سهم هبط بالحد الأدنى في آخر جلسة: يُستبعد من الشراء ويتصنّف AVOID حتى لو نقاطه عالية."""
    df = make_prices(321, drift=0.0015, vol=0.014, start_price=40)  # اتجاه صاعد قوي عشان نقاطه تبقى عالية أصلاً
    df.iloc[-1, df.columns.get_loc("close")] = df["close"].iloc[-2] * (1 - 0.098)
    df.iloc[-1, df.columns.get_loc("low")] = df["close"].iloc[-1]
    df.iloc[-1, df.columns.get_loc("open")] = df["close"].iloc[-2]
    df.iloc[-1, df.columns.get_loc("high")] = df["close"].iloc[-2]

    prices = _bull_prices(30)
    prices["LDWN"] = df
    frames, regime_df, cls, result = _analysis(prices)
    row = cls[cls["code"] == "LDWN"].iloc[0]
    assert bool(row["limit_down"]) is True
    assert row["signal"] == "AVOID"
    assert "LDWN" not in [p["code"] for p in result["picks"]]
    assert "LDWN" not in [w["code"] for w in result["watch"]]


def test_near_limit_caution_appears_for_watch_or_buy():
    frames, regime_df, cls, result = _analysis()
    for p in result["picks"] + result["watch"]:
        row = cls[cls["code"] == p["code"]].iloc[0]
        if bool(row["near_limit"]):
            assert any("حد التداول" in c for c in p["cautions"])


def test_illiquid_and_stale_are_excluded():
    prices = _bull_prices(30)
    prices["ILLQ"] = make_prices(999, drift=0.002, base_volume=2_000, start_price=10)
    prices["STAL"] = make_prices(998, drift=0.002, end="2026-08-20")
    _, _, cls, result = _analysis(prices)
    sig = dict(zip(cls["code"], cls["signal"]))
    assert sig["ILLQ"] == "ILLIQUID"
    assert sig["STAL"] == "STALE"
    assert "ILLQ" not in [p["code"] for p in result["picks"]]


# ------------------------------------------------------------------ الاختبار التاريخي وسجل التوصيات
def test_backtest_runs_and_no_overlap_per_symbol():
    frames, *_ = _analysis()
    summary, strat, base = run_backtest(frames, CFG)
    assert summary["strategy"].get("trades", 0) > 0 and summary["baseline"]["trades"] > 0
    for _, g in strat.groupby("code"):
        g = g.sort_values("entry_date")
        assert (pd.to_datetime(g["entry_date"].iloc[1:].values) > pd.to_datetime(g["exit_date"].iloc[:-1].values)).all()


def test_track_record_logging_is_idempotent_and_resolves():
    _reset_outputs()
    frames, regime_df, cls, result = _analysis()
    prices = {c: f[["open", "high", "low", "close", "volume"]] for c, f in frames.items()}
    # نرجّع الزمن يومين لورا عشان تبقى فيه شموع بعد الإشارة
    cut = {c: p.iloc[:-6] for c, p in prices.items()}
    hist = load_history()
    picks = result["picks"][:3]
    date_ = str(cut[picks[0]["code"]].index[-1].date())
    hist = log_signals(hist, picks, date_, "up")
    hist2 = log_signals(hist, picks, date_, "up")
    assert len(hist) == len(hist2) == len(picks)          # تسجيل نفس اليوم مرتين لا يكرر
    hist = update_history(hist, prices, CFG)              # دلوقتي فيه شموع بعد الإشارة
    assert set(hist["status"]) <= {"closed", "open", "skipped", "pending"}
    assert summarize(hist)["recommendations"] == len(picks)


# ------------------------------------------------------------------ متى يشتغل التقرير
def test_component_stats_needs_min_trades_and_finds_real_separation():
    n_lo, n_hi = 12, 12
    rows = []
    for i in range(n_lo):
        rows.append({"status": "closed", "r_net": -0.3 + 0.01 * i, "comp_trend": 0.2, "comp_momentum": 0.5,
                     "comp_rs": 0.5, "comp_volume": 0.5, "comp_setup": 0.5})
    for i in range(n_hi):
        rows.append({"status": "closed", "r_net": 1.2 + 0.01 * i, "comp_trend": 0.9, "comp_momentum": 0.5,
                     "comp_rs": 0.5, "comp_volume": 0.5, "comp_setup": 0.5})
    closed = pd.DataFrame(rows)
    assert component_stats(closed.iloc[:10]) is None                     # عينة أصغر من الحد الأدنى
    stats = component_stats(closed)
    assert stats is not None and "comp_trend" in stats
    ct = stats["comp_trend"]
    assert ct["high_avg_r"] > ct["low_avg_r"] and ct["high_n"] == n_hi and ct["low_n"] == n_lo
    # مكوّن بدون تباين حقيقي بين النصفين ما يظهرش أصلاً هنا لأن القيم متساوية في كل الصفوف
    assert "comp_momentum" not in stats or abs(stats["comp_momentum"]["high_avg_r"] - stats["comp_momentum"]["low_avg_r"]) < 1e-9


def test_track_record_carries_components_through_pipeline():
    _reset_outputs()
    frames, regime_df, cls, result = _analysis()
    picks = result["picks"][:2]
    for p in picks:
        for c in COMPONENTS:
            assert c in p and p[c] is not None
    hist = log_signals(load_history(), picks, "2026-09-17", "up")
    for c in COMPONENTS:
        assert hist[c].notna().all()


def test_should_run_rules():
    st = {}
    assert pipeline.should_run(CFG, SUN_9AM, st)[0]
    assert not pipeline.should_run(CFG, datetime(2026, 9, 18, 9, 5, tzinfo=CAIRO), st)[0]      # جمعة
    assert not pipeline.should_run(CFG, datetime(2026, 9, 19, 9, 5, tzinfo=CAIRO), st)[0]      # سبت
    assert not pipeline.should_run(CFG, datetime(2026, 10, 6, 9, 5, tzinfo=CAIRO), st)[0]      # إجازة مسجلة
    assert not pipeline.should_run(CFG, datetime(2026, 9, 20, 7, 0, tzinfo=CAIRO), st)[0]      # بدري
    assert not pipeline.should_run(CFG, datetime(2026, 9, 20, 13, 0, tzinfo=CAIRO), st)[0]     # متأخر
    assert not pipeline.should_run(CFG, SUN_9AM, {"last_sent_date": "2026-09-20"})[0]          # اتبعت
    assert pipeline.should_run(CFG, SUN_9AM, {"last_sent_date": "2026-09-20"}, force=True)[0]


def test_expected_last_session():
    assert pipeline.expected_last_session(SUN_9AM, CFG).isoformat() == "2026-09-17"            # الأحد ← الخميس
    assert pipeline.expected_last_session(datetime(2026, 9, 21, 9, 0, tzinfo=CAIRO), CFG).isoformat() == "2026-09-20"


# ------------------------------------------------------------------ التقرير والذكاء الاصطناعي
def test_number_guard():
    al = report.allowed_numbers({"a": 3.3632, "b": 84.0, "c": [22.5367]})
    assert report.numbers_ok("مخاطرة 3.4% وقوة 84 وسعر 22.54", al)
    assert report.numbers_ok("المتوسط ٥٠ يومًا", al)
    assert not report.numbers_ok("الهدف 250 جنيه", al)
    assert not report.numbers_ok("نمو 1500", al)


class _Resp:
    def __init__(self, status=200, body=None, text=""):
        self.status_code, self._b, self.text = status, body, text

    def json(self):
        return self._b


def test_llm_notes_are_validated():
    _, _, _, result = _analysis()
    p0 = result["picks"][0]["code"]
    good = {"market_view": "السوق داعم بحذر.", "picks": {p0: "اتجاه قوي، والخطر هو التشبع."}, "watch_view": "تابع القائمة."}
    bad = {"market_view": "توقعات بارتفاع 4321 نقطة", "picks": {p0: "هدف 999.99 مضمون"}, "watch_view": "ok"}
    payload = report.build_payload(result, None)
    fb = report.fallback_notes(result)

    def fake(body):
        return lambda *a, **k: _Resp(200, {"content": [{"type": "text", "text": body}]})

    import json

    env = {"ANTHROPIC_API_KEY": "k"}
    data, meta = report.call_llm(payload, CFG, post=fake(json.dumps(good, ensure_ascii=False)), env=env)
    assert meta["ok"] and data["market_view"].startswith("السوق")
    merged, dropped = report.merge_notes(data, fb, payload)
    assert merged["market_view"] == good["market_view"] and merged["picks"][p0] == good["picks"][p0] and dropped == 0

    data, meta = report.call_llm(payload, CFG, post=fake("```json\n" + json.dumps(bad, ensure_ascii=False) + "\n```"), env=env)
    merged, dropped = report.merge_notes(data, fb, payload)
    assert dropped == 2 and merged["market_view"] == fb["market_view"] and merged["picks"][p0] == fb["picks"][p0]

    # فشل الخدمة أو مفتاح ناقص = رجوع للنص الجاهز بدون كسر
    assert report.call_llm(payload, CFG, post=lambda *a, **k: _Resp(500), env=env)[0] is None
    assert report.call_llm(payload, CFG, post=fake("مش JSON"), env=env)[0] is None
    assert report.call_llm(payload, CFG, env={})[0] is None

    gem = {"candidates": [{"content": {"parts": [{"text": json.dumps(good, ensure_ascii=False)}]}}]}
    cfg2 = {**CFG, "llm": {**CFG["llm"], "provider": "gemini"}}
    data, meta = report.call_llm(payload, cfg2, post=lambda *a, **k: _Resp(200, gem), env={"GEMINI_API_KEY": "k"})
    assert meta["ok"] and data["watch_view"] == good["watch_view"]


def test_message_content_and_size():
    _, _, _, result = _analysis()
    now = SUN_9AM
    rep = report.build_report(result, None, CFG, now, ["ملاحظة تجريبية"], env={})
    msg = rep["telegram_html"]
    for p in result["picks"][: CFG["telegram"]["max_picks"]]:
        assert p["code"] in msg
    assert "الوقف" in msg and "الهدف 1" in msg and "ليس نصيحة استثمارية" in msg and "ملاحظة تجريبية" in msg
    assert all(len(c) <= 4096 for c in telegram.split_message(msg))
    assert "<script" not in report.build_report({**result, "picks": [{**result["picks"][0], "name": "<script>x</script>"}]}, None, CFG, now, [], env={})["telegram_html"]


# ------------------------------------------------------------------ تلجرام
def test_telegram_split_and_fallback_and_errors():
    text = "\n\n".join(f"فقرة {i} " + "س" * 900 for i in range(15))
    chunks = telegram.split_message(text)
    assert len(chunks) > 1 and all(len(c) <= telegram.LIMIT for c in chunks)

    calls = []

    def post(url, json=None, timeout=None):
        calls.append(json)
        if json.get("parse_mode") == "HTML" and len(calls) == 1:
            return _Resp(400, text="Bad Request: can't parse entities")
        return _Resp(200)

    assert telegram.send_message("TOKEN", "1", "<b>مرحبا</b>", post=post, pause=0) == 1
    assert calls[1]["text"] == "مرحبا" and "parse_mode" not in calls[1]

    def boom(url, json=None, timeout=None):
        return _Resp(401, text="Unauthorized")

    try:
        telegram.send_message("SECRET-TOKEN-123", "1", "x", post=boom, pause=0)
        raise AssertionError("كان لازم يفشل")
    except RuntimeError as e:
        assert "SECRET-TOKEN-123" not in str(e) and "401" in str(e)


# ------------------------------------------------------------------ التشغيل الكامل
def _run(**kw):
    sent = []
    pipeline.send_message = lambda token, chat, text: (sent.append(text) or 1)
    os.environ["TELEGRAM_BOT_TOKEN"], os.environ["TELEGRAM_CHAT_ID"] = "t", "1"
    os.environ.pop("ANTHROPIC_API_KEY", None)
    return pipeline.run(CFG, offline=True, now=kw.pop("now", SUN_9AM), **kw), sent


def test_pipeline_end_to_end():
    _reset_outputs()
    res, sent = _run()
    assert res["status"] == "sent" and sent and res["buys"]
    for f in ("signals/latest.json", "signals/table.csv", "signals/regime.csv", "signals/coverage.csv", "signals/history.csv",
              "report/latest.json", "backtest/summary.json"):
        assert (TMP / f).exists(), f
    assert C.load_state()["last_sent_date"] == "2026-09-20"
    # نفس اليوم مرة ثانية = تخطي، ولا رسالة جديدة
    n = len(sent)
    res2, sent2 = _run()
    assert res2["status"] == "skipped" and not sent2
    # الإجازة الأسبوعية
    assert _run(now=datetime(2026, 9, 18, 9, 5, tzinfo=CAIRO))[0]["status"] == "skipped"
    # الاستبعاد ظاهر في الجدول
    tbl = pd.read_csv(TMP / "signals" / "table.csv")
    sig = dict(zip(tbl["code"], tbl["signal"]))
    assert sig["ILLQ"] == "ILLIQUID" and sig["STAL"] == "STALE" and "SHRT" not in sig


def test_pipeline_dry_run_and_missing_secrets_and_alerts():
    _reset_outputs()
    res, sent = _run(dry_run=True)
    assert res["status"] == "dry_run" and not sent and "last_sent_date" not in C.load_state()

    _reset_outputs()
    pipeline.send_message = lambda *a, **k: 1
    os.environ.pop("TELEGRAM_BOT_TOKEN", None)
    assert pipeline.run(CFG, offline=True, now=SUN_9AM)["status"] == "not_sent"

    # بيانات ناقصة = خطأ + تنبيه على تلجرام
    _reset_outputs()
    alerts = []
    os.environ["TELEGRAM_BOT_TOKEN"] = "t"
    pipeline.send_message = lambda token, chat, text: (alerts.append(text) or 1)
    orig = pipeline.load_prices
    pipeline.load_prices = lambda codes, cfg, now: {}
    try:
        pipeline.run(CFG, offline=True, now=SUN_9AM)
        raise AssertionError("كان لازم يرفع DataError")
    except pipeline.DataError:
        pass
    finally:
        pipeline.load_prices = orig
    assert alerts and "تعذّر" in alerts[0]


# ------------------------------------------------------------------ القائمة
def test_universe_modes_on_real_files():
    real = ROOT / "data"
    lst = pd.read_csv(real / "universe.csv")
    assert len(lst) == 113 and lst["code"].is_unique
    backup = {n: (TMP / n).read_bytes() for n in ("universe.csv", "egx33.txt")}
    try:
        shutil.copy(real / "universe.csv", TMP / "universe.csv")
        shutil.copy(real / "egx33.txt", TMP / "egx33.txt")
        cfg = {**CFG, "universe": {"mode": "union"}}
        u = build_universe(cfg)
        both = build_universe({**CFG, "universe": {"mode": "intersection"}})
        only_l = build_universe({**CFG, "universe": {"mode": "list_only"}})
        assert len(only_l) == 113 and len(both) > 0 and len(u) >= 113
        assert set(both["code"]) <= set(only_l["code"]) and set(only_l["code"]) <= set(u["code"])
        assert (u["in_list"] | u["in_egx33"]).all()
    finally:
        for n, b in backup.items():
            (TMP / n).write_bytes(b)


# ------------------------------------------------------------------ الواجهة
def test_ui_html_builders():
    from app import ui

    pick = {"code": "ABCD", "name": "<b>شركة</b> & أخرى", "score": 82.4, "setup_ar": "استمرار اتجاه", "close": 22.5, "entry_low": 22.2,
            "entry_high": 22.7, "stop": 21.8, "t1": 24.0, "t2": 24.8, "avg_value_m": 30.0, "rsi": 58, "rs_pct": 80, "position_pct": 10,
            "why": ["سبب"], "cautions": ["تحذير"]}
    h = ui.pick_html(pick, "تعليق")
    assert "&lt;b&gt;" in h and "<b>شركة" not in h and "21.80" in h and "24.80" in h and "lad-entry" in h
    assert ui.ladder_html({**pick, "stop": 30}) == ""                # وقف فوق السعر = مفيش سلم
    assert ui.ladder_html({"code": "X"}) == ""
    _, _, _, result = _analysis()
    v = ui.verdict_html(result, "ملخص", ["تحذير بيانات"])
    assert result["regime"]["label_ar"] in v and "تحذير بيانات" in v
    assert ui.change_html(float("nan")) == "-" and "▲" in ui.change_html(1.2) and "▼" in ui.change_html(-1.2)
    assert "\n\n" not in ui.pick_html(pick, "x")                     # سطر فاضي بيكسر HTML جوه Markdown


class _Dummy:
    def __call__(self, *a, **k):
        return _Dummy()

    def __getattr__(self, name):
        return _Dummy()

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def __iter__(self):
        return iter([])


class StopApp(Exception):
    pass


class _Col(_Dummy):
    """عمود/تبويب وهمي بيرد بقيم افتراضية معقولة على عناصر الإدخال (عشان الصفحة تكمل)."""

    def multiselect(self, label, options, default=None, **k):
        return default or []

    def slider(self, label, lo, hi, value=None, **k):
        return lo if value is None else value

    def selectbox(self, label, options, index=0, **k):
        return options[index]

    def radio(self, label, options, index=0, **k):
        return options[index]

    def number_input(self, label, min_value=0, max_value=None, value=0, **k):
        return value

    def text_input(self, *a, **k):
        return ""


def _fake_streamlit():
    st = types.ModuleType("streamlit")
    d = _Dummy()

    def cache_data(*a, **k):
        return (lambda f: f) if not (a and callable(a[0])) else a[0]

    def tabs(labels):
        return [_Col() for _ in labels]

    def columns(spec, **k):
        n = spec if isinstance(spec, int) else len(spec)
        return [_Col() for _ in range(n)]

    def multiselect(label, options, default=None, **k):
        return default or []

    def slider(label, lo, hi, value=None, **k):
        return lo if value is None else value

    def selectbox(label, options, index=0, **k):
        return options[index]

    def radio(label, options, index=0, **k):
        return options[index]

    def number_input(label, min_value=0, max_value=None, value=0, **k):
        return value

    def stop():
        raise StopApp()

    st.cache_data, st.tabs, st.columns, st.multiselect, st.slider = cache_data, tabs, columns, multiselect, slider
    st.selectbox, st.radio, st.number_input, st.stop = selectbox, radio, number_input, stop
    st.text_input = lambda *a, **k: ""
    st.column_config = d
    st.__getattr__ = lambda name: d      # noqa: E731  (PEP 562)
    for n in ("set_page_config", "markdown", "dataframe", "plotly_chart", "warning", "info", "caption", "download_button", "metric"):
        setattr(st, n, lambda *a, **k: None)
    return st


def _run_app():
    saved = {k: sys.modules.get(k) for k in ("streamlit", "plotly", "plotly.graph_objects", "plotly.subplots")}
    plotly = types.ModuleType("plotly")
    go = types.ModuleType("plotly.graph_objects")
    go.__getattr__ = lambda name: _Dummy()
    sub = types.ModuleType("plotly.subplots")
    sub.make_subplots = lambda *a, **k: _Dummy()
    plotly.graph_objects, plotly.subplots = go, sub
    sys.modules.update({"streamlit": _fake_streamlit(), "plotly": plotly, "plotly.graph_objects": go, "plotly.subplots": sub})
    for m in [k for k in sys.modules if k in ("app.charts", "app.ui", "app.streamlit_app")]:
        del sys.modules[m]
    try:
        runpy.run_path(str(ROOT / "app" / "streamlit_app.py"), run_name="__main__")
    finally:
        for k, v in saved.items():
            if v is None:
                sys.modules.pop(k, None)
            else:
                sys.modules[k] = v
        for m in [k for k in sys.modules if k in ("app.charts", "app.ui")]:
            del sys.modules[m]


def test_streamlit_app_smoke_run():
    """تشغيل صفحة Streamlit كاملة بـ streamlit وplotly وهميين: بيكشف أي خطأ بايثون في منطق الصفحة."""
    _reset_outputs()
    try:
        _run_app()
        raise AssertionError("كان لازم يوقف لعدم وجود بيانات (empty state)")
    except StopApp:
        pass
    _run(dry_run=True)
    _run_app()


if __name__ == "__main__":
    tests = [(n, f) for n, f in sorted(globals().items()) if n.startswith("test_") and callable(f)]
    failed = 0
    for name, fn in tests:
        try:
            fn()
            print(f"  ok   {name}")
        except Exception as e:  # noqa: BLE001
            failed += 1
            import traceback

            print(f"  FAIL {name}: {type(e).__name__}: {e}")
            traceback.print_exc()
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    shutil.rmtree(TMP, ignore_errors=True)
    sys.exit(1 if failed else 0)
