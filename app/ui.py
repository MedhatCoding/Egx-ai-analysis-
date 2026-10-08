"""عناصر الواجهة (CSS + HTML) للوحة Streamlit. دوال نقية بدون أي استيراد من streamlit عشان تتختبر بسهولة.

اتجاه التصميم: موقع تحليل مالي عربي بخلفية فاتحة وشريط علوي كحلي، خط IBM Plex Sans Arabic،
وأرقام متساوية العرض. العنصر المميز الوحيد هو «سلّم السعر» اللي بيوري الوقف ومنطقة الدخول والأهداف
على مقياس واحد، وباقي الصفحة هادي: خطوط رفيعة بدل كروت متكررة، وألوان بمعنى فقط (أخضر صعود، أحمر هبوط، كهرماني حذر).
"""
from __future__ import annotations

import html
import math
from datetime import date, datetime

from src.report import ar_date
from src.signals import SETUP_AR, SIGNAL_AR

TONE = {"strong_up": "good", "up": "good", "neutral": "mid", "weak": "bad", "down": "bad"}
ORDER = ["down", "weak", "neutral", "up", "strong_up"]
REGIME_AR = {"strong_up": "صاعد بقوة", "up": "صاعد", "neutral": "محايد", "weak": "ضعيف", "down": "هابط"}

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans+Arabic:wght@400;500;600;700&display=swap');
:root{--navy:#12284C;--paper:#F3F5F9;--surface:#FFFFFF;--ink:#0F1B2D;--muted:#5B6B82;--line:#D9E0EA;--gain:#0E9F6E;--loss:#D9383A;--amber:#B7791F}
.stApp{background:var(--paper);color:var(--ink);font-family:'IBM Plex Sans Arabic',system-ui,-apple-system,'Segoe UI',Tahoma,sans-serif;direction:rtl;font-size:15px}
header[data-testid="stHeader"],footer,#MainMenu,[data-testid="stToolbar"],[data-testid="stDecoration"]{display:none!important}
.block-container,[data-testid="stMainBlockContainer"]{padding:0 1rem 4rem!important;max-width:1180px!important}
.stApp h1,.stApp h2,.stApp h3{font-family:inherit}
.js-plotly-plot,.plotly{direction:ltr}
bdi{unicode-bidi:isolate;font-variant-numeric:tabular-nums}
.up{color:var(--gain)}.dn{color:var(--loss)}
.topbar{background:var(--navy);color:#fff;margin:0 -1rem 1.1rem;padding:.85rem 1rem;box-shadow:0 0 0 100vmax var(--navy);clip-path:inset(0 -100vmax)}
.topbar-in{max-width:1180px;margin:0 auto;display:flex;justify-content:space-between;align-items:baseline;gap:.4rem 1.5rem;flex-wrap:wrap}
.brand-name{font-weight:700;font-size:1.2rem}
.brand-sub{font-size:.8rem;opacity:.65;margin-inline-start:.7rem}
.asof{font-size:.82rem;opacity:.88;line-height:1.6}
.verdict{display:grid;grid-template-columns:1.2fr 1fr;gap:1.2rem 2.5rem;padding:.6rem 0 1.4rem;border-bottom:1px solid var(--line)}
@media(max-width:820px){.verdict{grid-template-columns:1fr}}
.v-title{font-size:2.15rem;font-weight:700;line-height:1.2;margin:0 0 .5rem}
.tone-good{color:var(--gain)}.tone-mid{color:var(--amber)}.tone-bad{color:var(--loss)}
.v-text{color:var(--muted);line-height:1.85;margin:0;max-width:62ch}
.meter{display:flex;gap:4px;margin:1rem 0 .35rem;max-width:21rem;align-items:flex-end}
.meter i{flex:1;height:5px;background:var(--line)}
.meter i.on{height:11px}
.meter i.on.good{background:var(--gain)}.meter i.on.mid{background:var(--amber)}.meter i.on.bad{background:var(--loss)}
.meter-cap{font-size:.8rem;color:var(--muted)}
.stats{display:grid;grid-template-columns:1fr 1fr;border-top:1px solid var(--line);border-inline-start:1px solid var(--line);align-self:start}
.stat{padding:.8rem 1rem;border-bottom:1px solid var(--line);border-inline-end:1px solid var(--line);background:var(--surface)}
.stat-l{display:block;font-size:.8rem;color:var(--muted)}
.stat-v{display:block;font-size:1.35rem;font-weight:600;font-variant-numeric:tabular-nums;margin-top:.15rem}
.flag{margin:.9rem 0 0;padding:.55rem .8rem;border-inline-start:3px solid var(--amber);background:#FBF5E9;font-size:.85rem;line-height:1.7;color:#5C430F}
.sec{margin:1.7rem 0 .7rem}
.sec h2{font-size:1.15rem;font-weight:700;margin:0}
.sec p{margin:.2rem 0 0;color:var(--muted);font-size:.87rem}
.pick{background:var(--surface);border:1px solid var(--line);border-inline-start:4px solid var(--gain);padding:1rem 1.15rem 1.1rem;margin:0 0 1rem}
.pick-top{display:flex;justify-content:space-between;gap:1rem;align-items:flex-start;flex-wrap:wrap}
.pick-code{font-size:1.4rem;font-weight:700;letter-spacing:.02em}
.pick-name{color:var(--muted);margin-inline-start:.6rem}
.pick-facts{display:flex;flex-wrap:wrap;gap:.25rem 1.3rem;margin:.35rem 0 0;color:var(--muted);font-size:.86rem}
.score{min-width:7.5rem;text-align:end}
.score b{font-size:1.75rem;font-variant-numeric:tabular-nums}
.score small{color:var(--muted);margin-inline-start:.25rem}
.score-bar{display:block;height:4px;background:var(--line);margin-top:.3rem}
.score-bar i{display:block;height:100%;background:var(--navy)}
.pick-body{display:grid;grid-template-columns:1fr 1fr;gap:.4rem 2rem;margin-top:.7rem}
@media(max-width:720px){.pick-body{grid-template-columns:1fr}}
.h4{font-size:.85rem;font-weight:600;color:var(--muted);margin:0}
.pick ul,.plan ul{margin:.3rem 0 0;padding-inline-start:1.1rem;line-height:1.8;font-size:.9rem}
.pick ul.warn li::marker,.plan ul.warn li::marker{color:var(--amber)}
.note{background:#EAF0F8;border-inline-start:3px solid var(--navy);padding:.65rem .9rem;margin:.75rem 0 0;font-size:.9rem;line-height:1.85}
.lad{position:relative;height:98px;margin:.7rem .4rem .1rem;direction:ltr}
.lad-track{position:absolute;top:42px;left:0;right:0;height:14px;background:#E6EBF2}
.lad-track span{position:absolute;top:0;height:100%}
.lad-risk{background:rgba(217,56,58,.38)}
.lad-r1{background:rgba(14,159,110,.32)}
.lad-r2{background:rgba(14,159,110,.62)}
.lad-entry{top:-6px!important;height:26px!important;border:2px solid var(--navy);background:rgba(18,40,76,.10);box-sizing:border-box}
.lad-tick{width:2px;top:-3px!important;height:20px!important;background:var(--navy)}
.lab{position:absolute;font-size:.76rem;line-height:1.3;white-space:nowrap;text-align:center;direction:rtl}
.lab b{display:block;font-size:.9rem;font-variant-numeric:tabular-nums;direction:ltr}
.lab-top{top:0}.lab-bot{top:64px}
.al-l{transform:translateX(0);text-align:left}.al-c{transform:translateX(-50%)}.al-r{transform:translateX(-100%);text-align:right}
.lad-foot{font-size:.84rem;color:var(--muted);margin:.2rem 0 0;line-height:1.8}
.chip{display:inline-block;padding:.05rem .55rem;font-size:.78rem;font-weight:600;border:1px solid currentColor}
.chip-buy{color:var(--gain)}.chip-watch{color:var(--amber)}.chip-avoid{color:var(--loss)}.chip-mute{color:var(--muted)}
.comp{display:grid;grid-template-columns:8.5rem 1fr 2.6rem;gap:.6rem;align-items:center;margin:.42rem 0;font-size:.88rem}
.comp .bar{height:8px;background:var(--line)}
.comp .bar i{display:block;height:100%;background:var(--navy)}
.comp .val{text-align:end;font-variant-numeric:tabular-nums;color:var(--muted)}
.plan{background:var(--surface);border:1px solid var(--line);padding:.9rem 1.1rem}
.empty{background:var(--surface);border:1px solid var(--line);border-inline-start:4px solid var(--amber);padding:1rem 1.2rem;line-height:1.9}
.kv{display:grid;grid-template-columns:auto 1fr;gap:.25rem 1.2rem;font-size:.9rem;margin:.4rem 0}
.kv span:nth-child(odd){color:var(--muted)}
.stTabs [data-baseweb="tab-list"]{gap:1.3rem;border-bottom:1px solid var(--line);margin-top:.3rem}
.stTabs button[role="tab"]{padding:.6rem .1rem;font-weight:600}
.legal{margin-top:2.2rem;padding-top:1rem;border-top:1px solid var(--line);color:var(--muted);font-size:.8rem;line-height:1.9}
</style>
"""


# ------------------------------------------------------------------ أدوات صغيرة
def e(x) -> str:
    return html.escape(str(x), quote=True)


def bdi(x) -> str:
    return f"<bdi>{e(x)}</bdi>"


def fnum(x, nd: int = 2) -> str:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return "-"
    return f"{v:,.{nd}f}" if math.isfinite(v) else "-"


def change_html(x) -> str:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return "-"
    if not math.isfinite(v):
        return "-"
    if v > 0:
        return f'<span class="up">▲ {bdi(f"{v:.2f}%")}</span>'
    if v < 0:
        return f'<span class="dn">▼ {bdi(f"{abs(v):.2f}%")}</span>'
    return f'<span>{bdi("0.00%")}</span>'


def _parse_dt(s) -> datetime | None:
    try:
        return datetime.fromisoformat(str(s))
    except (TypeError, ValueError):
        return None


def section(title: str, sub: str = "") -> str:
    return f'<div class="sec"><h2>{e(title)}</h2>' + (f"<p>{e(sub)}</p>" if sub else "") + "</div>"


def chip(signal: str) -> str:
    cls = {"BUY": "chip-buy", "WATCH": "chip-watch", "AVOID": "chip-avoid"}.get(signal, "chip-mute")
    return f'<span class="chip {cls}">{e(SIGNAL_AR.get(signal, signal))}</span>'


# ------------------------------------------------------------------ الرأس وحالة السوق
def header_html(latest: dict, report: dict | None) -> str:
    dd = date.fromisoformat(latest["data_date"])
    gen = _parse_dt((report or {}).get("generated_at") or latest.get("generated_at"))
    upd = f"آخر تحديث {ar_date(gen)} الساعة {gen:%H:%M}" if gen else ""
    return (
        '<div class="topbar"><div class="topbar-in">'
        '<div><span class="brand-name">مستشار البورصة</span><span class="brand-sub">EGX Advisor</span></div>'
        f'<div class="asof">بيانات إغلاق {e(ar_date(dd))}<br>{e(upd)}</div>'
        "</div></div>"
    )


def verdict_html(latest: dict, view: str, warnings: list[str]) -> str:
    rg, m = latest["regime"], latest["market"]
    tone = TONE.get(rg["label"], "mid")
    idx = ORDER.index(rg["label"]) if rg["label"] in ORDER else 2
    meter = "".join(f'<i class="on {tone}"></i>' if i == idx else "<i></i>" for i in range(len(ORDER)))
    n_buy = len(latest.get("picks", []))
    b50 = m.get("breadth50")
    stats = (
        f'<div class="stat"><span class="stat-l">{e(m.get("bench_name", "المؤشر"))} في آخر جلسة</span>'
        f'<span class="stat-v">{change_html(m.get("bench_change_1d"))}</span></div>'
        f'<div class="stat"><span class="stat-l">الأسهم فوق متوسط 50 يومًا</span>'
        f'<span class="stat-v">{bdi(f"{b50:.0f}%") if b50 is not None else "-"}</span></div>'
        f'<div class="stat"><span class="stat-l">أسهم صاعدة مقابل هابطة</span>'
        f'<span class="stat-v">{bdi(m.get("advancers", 0))} / {bdi(m.get("decliners", 0))}</span></div>'
        f'<div class="stat"><span class="stat-l">فرص الشراء اليوم</span>'
        f'<span class="stat-v">{bdi(n_buy)} <small style="font-size:.8rem;color:var(--muted);font-weight:400">'
        f'من حد أقصى {bdi(rg.get("max_buys", 0))}</small></span></div>'
    )
    flag = ""
    if warnings:
        flag = '<div class="flag">' + "<br>".join(e(w) for w in warnings[:3]) + "</div>"
    score_txt = f"{rg['score']:.0f}"
    return (
        '<section class="verdict"><div>'
        f'<h1 class="v-title tone-{tone}">السوق {e(rg["label_ar"])}</h1>'
        f'<p class="v-text">{e(view)}</p>'
        f'<div class="meter">{meter}</div>'
        f'<div class="meter-cap">درجة السوق {bdi(score_txt)} من 100، ومقياسها يجمع اتجاه المؤشر واتساع الأسهم</div>'
        f"{flag}</div>"
        f'<div class="stats">{stats}</div></section>'
    )


# ------------------------------------------------------------------ سلّم السعر
def ladder_html(p: dict) -> str:
    """وقف الخسارة ← منطقة الدخول ← الهدفان على مقياس سعر واحد. المساحة الحمراء = المخاطرة والخضراء = المكافأة."""
    try:
        stop, lo, hi, close, t1, t2 = (float(p[k]) for k in ("stop", "entry_low", "entry_high", "close", "t1", "t2"))
    except (KeyError, TypeError, ValueError):
        return ""
    span = t2 - stop
    if span <= 0 or not (stop < close < t1 < t2):
        return ""

    def pos(v: float) -> float:
        return max(0.0, min(100.0, (v - stop) / span * 100.0))

    def align(x: float) -> str:
        return "al-l" if x < 11 else "al-r" if x > 89 else "al-c"

    pc, p1, pl, ph = pos(close), pos(t1), pos(lo), pos(hi)
    mid = (pl + ph) / 2
    risk = (close - stop) / close * 100
    g1 = (t1 - close) / close * 100
    g2 = (t2 - close) / close * 100
    r1 = (t1 - close) / (close - stop)
    r2 = (t2 - close) / (close - stop)
    track = (
        f'<span class="lad-risk" style="left:0;width:{pc:.1f}%"></span>'
        f'<span class="lad-r1" style="left:{pc:.1f}%;width:{p1 - pc:.1f}%"></span>'
        f'<span class="lad-r2" style="left:{p1:.1f}%;width:{100 - p1:.1f}%"></span>'
        f'<span class="lad-entry" style="left:{pl:.1f}%;width:{max(ph - pl, 1.6):.1f}%"></span>'
        '<span class="lad-tick" style="left:0"></span>'
        f'<span class="lad-tick" style="left:calc({p1:.1f}% - 1px)"></span>'
        '<span class="lad-tick" style="right:0"></span>'
    )
    labels = (
        f'<div class="lab lab-top {align(mid)}" style="left:{mid:.1f}%">منطقة الدخول<b>{fnum(lo)} – {fnum(hi)}</b></div>'
        f'<div class="lab lab-top al-r" style="left:100%">الهدف 2<b>{fnum(t2)}</b></div>'
        f'<div class="lab lab-bot al-l" style="left:0">وقف الخسارة<b>{fnum(stop)}</b></div>'
        f'<div class="lab lab-bot {align(p1)}" style="left:{p1:.1f}%">الهدف 1<b>{fnum(t1)}</b></div>'
    )
    foot = (
        f'<div class="lad-foot">المخاطرة {bdi(f"{risk:.1f}%")} مقابل مكافأة {bdi(f"{g1:.1f}%")} عند الهدف الأول '
        f'({bdi(f"1 : {r1:.1f}")}) و{bdi(f"{g2:.1f}%")} عند الهدف الثاني ({bdi(f"1 : {r2:.1f}")})</div>'
    )
    return f'<div class="lad"><div class="lad-track">{track}</div>{labels}</div>{foot}'


def _ul(items: list[str], cls: str = "") -> str:
    if not items:
        return ""
    return f'<ul class="{cls}">' + "".join(f"<li>{e(x)}</li>" for x in items) + "</ul>"


def pick_html(p: dict, note: str | None = None) -> str:
    score = float(p.get("score") or 0)
    facts = [f"النموذج: {p.get('setup_ar', '')}"]
    if p.get("avg_value_m") is not None:
        facts.append(f"سيولة {fnum(p['avg_value_m'], 0)} مليون ج.م يوميًا")
    if p.get("rsi") is not None:
        facts.append(f"RSI {fnum(p['rsi'], 0)}")
    if p.get("rs_pct") is not None:
        facts.append(f"أقوى من {fnum(p['rs_pct'], 0)}% من الأسهم")
    facts_html = "".join(f"<span>{e(f)}</span>" for f in facts)
    why_default = "؛ ".join((p.get("why") or [])[:2])
    note_html = f'<div class="note">{e(note)}</div>' if note and note != why_default else ""
    pos = ""
    if p.get("position_pct") is not None:
        pos_txt = f"{float(p['position_pct']):.0f}%"
        pos = (
            f'<div class="lad-foot">حجم المركز المقترح حتى {bdi(pos_txt)} من المحفظة '
            "حتى تبقى خسارة الوقف في حدود المخاطرة المسموحة للصفقة.</div>"
        )
    return (
        '<article class="pick"><div class="pick-top"><div>'
        f'<span class="pick-code">{bdi(p["code"])}</span><span class="pick-name">{e(p.get("name", ""))}</span>'
        f'<div class="pick-facts">{facts_html}</div></div>'
        f'<div class="score"><b>{bdi(f"{score:.0f}")}</b><small>من 100</small>'
        f'<span class="score-bar"><i style="width:{max(0, min(100, score)):.0f}%"></i></span></div></div>'
        f"{note_html}{ladder_html(p)}{pos}"
        f'<div class="pick-body"><div><p class="h4">لماذا هذا السهم</p>{_ul(p.get("why") or [])}</div>'
        f'<div><p class="h4">انتبه إلى</p>{_ul(p.get("cautions") or [], "warn") or "<ul><li>لا تحذيرات إضافية اليوم</li></ul>"}</div>'
        "</div></article>"
    )


def empty_picks_html(latest: dict) -> str:
    rg = latest["regime"]
    if rg.get("max_buys", 0) == 0:
        why = (f"السوق {rg['label_ar']} حاليًا، فالنظام لا يصدر توصيات شراء في هذه البيئة. "
               "الانتظار قرار مشروع، وقائمة المراقبة تحت تجهّزك لحين تحسّن الاتجاه.")
    else:
        why = ("لم يستوفِ أي سهم كل شروط الشراء اليوم (الاتجاه والسيولة والمقاومة والتشبّع). "
               "قائمة المراقبة تحت فيها الأسهم الأقرب.")
    return f'<div class="empty"><b>لا توصيات شراء اليوم.</b><br>{e(why)}</div>'


# ------------------------------------------------------------------ تحليل سهم
COMPONENTS = [
    ("الاتجاه", "comp_trend", "trend"),
    ("الزخم", "comp_momentum", "momentum"),
    ("القوة النسبية", "comp_rs", "relative_strength"),
    ("الحجم والتجميع", "comp_volume", "volume"),
    ("جودة النموذج", "comp_setup", "setup"),
]


def components_html(row: dict, weights: dict) -> str:
    total = float(sum(weights.values())) or 1.0
    out = []
    for label, key, wkey in COMPONENTS:
        v = row.get(key)
        try:
            v = max(0.0, min(1.0, float(v)))
        except (TypeError, ValueError):
            v = 0.0
        w = weights.get(wkey, 0) / total * 100
        out.append(
            f'<div class="comp"><span>{e(label)} <small style="color:var(--muted)">({bdi(f"{w:.0f}%")})</small></span>'
            f'<span class="bar"><i style="width:{v * 100:.0f}%"></i></span><span class="val">{bdi(f"{v * 100:.0f}")}</span></div>'
        )
    return "".join(out)


def plan_from_row(row: dict) -> dict:
    """خطة إرشادية من صف الجدول (نفس معادلات التوصيات: الدخول = الإغلاق -0.5 إلى +0.25 ATR)."""
    close, atr = row.get("close"), row.get("atr")
    plan = {"stop": row.get("stop"), "t1": row.get("t1"), "t2": row.get("t2"), "close": close}
    try:
        plan["entry_low"] = float(close) - 0.5 * float(atr)
        plan["entry_high"] = float(close) + 0.25 * float(atr)
    except (TypeError, ValueError):
        plan["entry_low"] = plan["entry_high"] = close
    return plan


def kv_html(pairs: list[tuple[str, str]]) -> str:
    return '<div class="kv">' + "".join(f"<span>{e(k)}</span><span>{v}</span>" for k, v in pairs) + "</div>"


LEGAL = (
    "هذه اللوحة أداة تحليل فني آلي للمعلومات والتعلّم وليست نصيحة استثمارية أو توصية شخصية. "
    "الأسعار من بيانات نهاية اليوم وقد تختلف عن أسعار التنفيذ الفعلية خصوصًا في الأسهم قليلة السيولة، "
    "والأداء السابق (بما فيه الاختبار التاريخي) لا يضمن المستقبل. القرار والمسؤولية عليك. "
    "الأسهم المحللة مصدرها قائمتك ومكونات EGX33، وتحديثهما دوريًا مسؤوليتك."
)


def legal_html() -> str:
    return f'<div class="legal">{e(LEGAL)}</div>'


def stat_grid(pairs: list[tuple[str, str]]) -> str:
    """شبكة مؤشرات بخطوط رفيعة (قيمة كبيرة وتحتها وصف). القيم HTML جاهز ومهرَّب من المستدعي."""
    cells = "".join(f'<div class="stat"><span class="stat-l">{e(k)}</span><span class="stat-v">{v}</span></div>' for k, v in pairs)
    return f'<div class="stats" style="margin:.4rem 0 1rem">{cells}</div>'
