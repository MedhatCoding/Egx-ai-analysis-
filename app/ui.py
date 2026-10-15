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
:root{--ink:#172b4d;--muted:#75839a;--paper:#f5f7fb;--surface:#fff;--line:#e7ebf2;--green:#07866d;--red:#d94a55;--amber:#b47b23;--blue:#315fcb}
.stApp{background:var(--paper);color:var(--ink);font-family:'IBM Plex Sans Arabic',system-ui,-apple-system,'Segoe UI',Tahoma,sans-serif;direction:rtl;font-size:14px}
header[data-testid="stHeader"],footer,#MainMenu,[data-testid="stToolbar"],[data-testid="stDecoration"]{display:none!important}
.block-container,[data-testid="stMainBlockContainer"]{padding:.5rem 1.1rem 3.5rem!important;max-width:1160px!important}
.stApp h1,.stApp h2,.stApp h3{font-family:inherit}
.js-plotly-plot,.plotly{direction:ltr} bdi{unicode-bidi:isolate;font-variant-numeric:tabular-nums}
.up{color:var(--green)}.dn{color:var(--red)}
.topbar{background:#fff;color:var(--ink);margin:0 0 1rem;padding:.9rem 1rem;border:1px solid var(--line);border-radius:18px;box-shadow:0 2px 10px rgba(20,39,74,.025)}
.topbar-in{display:flex;justify-content:space-between;align-items:center;gap:.6rem 1rem;flex-wrap:wrap}
.brand-name{font-weight:700;font-size:1.22rem;letter-spacing:-.025em}
.brand-sub{display:inline-block;color:var(--blue);background:#eef3ff;border-radius:6px;padding:.15rem .45rem;margin-inline-start:.55rem;font-size:.7rem;font-weight:700}
.asof{font-size:.76rem;color:var(--muted);line-height:1.7}
.verdict{display:grid;grid-template-columns:1.05fr 1fr;gap:1rem;padding:1.15rem;background:#fff;border:1px solid var(--line);border-radius:18px;margin-bottom:1rem}
.v-title{font-size:1.65rem;font-weight:700;line-height:1.25;margin:0 0 .35rem}
.tone-good{color:var(--green)}.tone-mid{color:var(--amber)}.tone-bad{color:var(--red)}
.v-text{color:var(--muted);line-height:1.8;margin:0}
.meter{display:flex;gap:4px;margin:.75rem 0 .3rem;max-width:18rem}
.meter i{flex:1;height:5px;background:#e8edf4;border-radius:9px}.meter i.on{height:7px}.meter i.on.good{background:var(--green)}.meter i.on.mid{background:var(--amber)}.meter i.on.bad{background:var(--red)}
.meter-cap{font-size:.74rem;color:var(--muted)}
.stats{display:grid;grid-template-columns:1fr 1fr;gap:.55rem;align-self:start}
.stat{padding:.75rem .85rem;border:1px solid var(--line);border-radius:13px;background:#fbfcfe;min-width:0}
.stat-l{display:block;font-size:.75rem;color:var(--muted)}
.stat-v{display:block;font-size:1.22rem;font-weight:700;font-variant-numeric:tabular-nums;margin-top:.1rem}
.flag{margin:.7rem 0 0;padding:.55rem .7rem;border-inline-start:3px solid var(--amber);background:#fff7e9;border-radius:8px;font-size:.82rem;line-height:1.7;color:#67480f}
.sec{margin:1.35rem 0 .65rem;display:flex;align-items:baseline;justify-content:space-between;gap:.5rem;flex-wrap:wrap}
.sec h2{font-size:1.08rem;font-weight:700;margin:0}.sec p{margin:0;color:var(--muted);font-size:.8rem}
.pick{background:var(--surface);border:1px solid var(--line);border-radius:16px;padding:1rem;margin:0 0 .75rem;box-shadow:0 2px 8px rgba(20,39,74,.025)}
.pick-top{display:flex;justify-content:space-between;gap:.75rem;align-items:flex-start;flex-wrap:wrap}
.pick-code{font-size:1.28rem;font-weight:700;letter-spacing:.02em}
.pick-name{color:var(--muted);margin-inline-start:.55rem;font-size:.9rem}
.pick-facts{display:flex;flex-wrap:wrap;gap:.2rem .9rem;margin:.35rem 0 0;color:var(--muted);font-size:.78rem}
.score{min-width:5.8rem;text-align:end}.score b{font-size:1.55rem;font-variant-numeric:tabular-nums}.score small{color:var(--muted);margin-inline-start:.2rem;font-size:.72rem}
.score-bar{display:block;height:4px;background:#e9edf4;border-radius:10px;margin-top:.25rem;overflow:hidden}.score-bar i{display:block;height:100%;background:var(--blue);border-radius:10px}
.pick-body{display:grid;grid-template-columns:1fr 1fr;gap:.35rem 1.5rem;margin-top:.6rem}
.h4{font-size:.8rem;font-weight:600;color:var(--muted);margin:0}.pick ul,.plan ul{margin:.25rem 0 0;padding-inline-start:1.1rem;line-height:1.7;font-size:.83rem}
.pick ul.warn li::marker,.plan ul.warn li::marker{color:var(--amber)}
.note{background:#f2f6ff;border:1px solid #e1eaff;border-inline-start:3px solid var(--blue);border-radius:10px;padding:.6rem .8rem;margin:.65rem 0 0;font-size:.84rem;line-height:1.75}
.lad{position:relative;height:96px;margin:.6rem .4rem .1rem;direction:ltr}.lad-track{position:absolute;top:41px;left:0;right:0;height:12px;background:#e8edf4;border-radius:10px;overflow:visible}
.lad-track span{position:absolute;top:0;height:100%}.lad-risk{background:#f6c9cd}.lad-r1{background:#b9e8d9}.lad-r2{background:#67c9ad}.lad-entry{top:-5px!important;height:22px!important;border:2px solid var(--blue);background:#dfe8ff;box-sizing:border-box;border-radius:4px}.lad-tick{width:2px;top:-3px!important;height:18px!important;background:#60718a}
.lab{position:absolute;font-size:.7rem;line-height:1.3;white-space:nowrap;text-align:center;direction:rtl}.lab b{display:block;font-size:.82rem;font-variant-numeric:tabular-nums;direction:ltr}.lab-top{top:0}.lab-bot{top:61px}.al-l{transform:translateX(0);text-align:left}.al-c{transform:translateX(-50%)}.al-r{transform:translateX(-100%);text-align:right}.lad-foot{font-size:.78rem;color:var(--muted);margin:.15rem 0 0;line-height:1.7}
.chip{display:inline-block;padding:.12rem .5rem;font-size:.72rem;font-weight:700;border-radius:6px;border:0}.chip-buy{color:#06765f;background:#e5f7f1}.chip-watch{color:#93620e;background:#fff4db}.chip-avoid{color:#b92e3b;background:#fff0f1}.chip-mute{color:var(--muted);background:#eef1f5}
.comp{display:grid;grid-template-columns:8rem 1fr 2.4rem;gap:.55rem;align-items:center;margin:.4rem 0;font-size:.82rem}.comp .bar{height:7px;background:#e8edf4;border-radius:10px;overflow:hidden}.comp .bar i{display:block;height:100%;background:var(--blue);border-radius:10px}.comp .val{text-align:end;font-variant-numeric:tabular-nums;color:var(--muted)}
.compare-row{display:grid;grid-template-columns:minmax(0,1.4fr) repeat(3,minmax(0,1fr));gap:.7rem;align-items:center;padding:.75rem .85rem;background:#fff;border:1px solid var(--line);border-radius:11px;margin-bottom:.4rem}.compare-row>div{min-width:0}.compare-row span,.compare-row small{display:block;color:var(--muted);font-size:.7rem}.compare-row b{display:block;font-size:.88rem;font-variant-numeric:tabular-nums;margin-top:.1rem}.weight-row{display:grid;grid-template-columns:7rem minmax(0,1fr) 2rem;gap:.65rem;align-items:center;background:#fff;padding:.65rem .8rem;border:1px solid var(--line);border-radius:10px;margin-bottom:.4rem}.weight-row>span{font-size:.82rem}.weight-row>b{font-size:.8rem;text-align:end}.weight-track{height:7px;background:#edf0f6;border-radius:9px;overflow:hidden}.weight-track i{display:block;height:100%;background:var(--blue);border-radius:9px}@media(max-width:640px){.compare-row{grid-template-columns:1fr 1fr;gap:.45rem;padding:.65rem}.compare-row>div:first-child{grid-column:1/-1}.weight-row{grid-template-columns:6rem minmax(0,1fr) 1.5rem}}
/* app-like section navigation */
.nav-heading{display:none}
div[data-testid="stRadio"]{margin:0 0 1rem;padding:.32rem;background:#e9edf5;border:1px solid #e2e7f0;border-radius:13px}
div[data-testid="stRadio"]>label{display:none!important}
div[data-testid="stRadio"] div[role="radiogroup"]{display:flex!important;flex-wrap:nowrap!important;gap:.25rem!important;overflow-x:auto!important;overflow-y:hidden!important;scrollbar-width:none;-webkit-overflow-scrolling:touch;padding:.03rem}
div[data-testid="stRadio"] div[role="radiogroup"]>label{flex:0 0 auto!important;display:flex!important;align-items:center!important;justify-content:center!important;min-height:38px;padding:.4rem .85rem!important;margin:0!important;border:1px solid transparent!important;border-radius:9px!important;background:transparent!important;white-space:nowrap!important;color:#65748a!important;font-weight:600!important;font-size:.82rem!important}
div[data-testid="stRadio"] div[role="radiogroup"]>label:has(input:checked){background:#fff!important;color:#254eaf!important;border-color:#dfe6f2!important;box-shadow:0 1px 4px rgba(20,39,74,.06)!important}
div[data-testid="stRadio"] div[role="radiogroup"]>label>div:first-child{display:none!important}
div[data-testid="stRadio"] div[role="radiogroup"]>label p{margin:0!important}
.stock-row{display:grid;grid-template-columns:minmax(0,1fr) auto auto;gap:.65rem;align-items:center;background:#fff;border:1px solid var(--line);border-radius:13px;padding:.8rem .9rem;margin-bottom:.5rem}
.stock-main{min-width:0}.stock-symbol{font-size:.96rem;font-weight:700;direction:ltr;unicode-bidi:isolate;display:inline-block}.stock-name{font-size:.78rem;color:var(--muted);margin-inline-start:.45rem}.stock-meta{font-size:.72rem;color:var(--muted);margin-top:.2rem}.stock-price{font-weight:700;font-variant-numeric:tabular-nums;white-space:nowrap}.stock-change{font-size:.78rem;font-weight:700;white-space:nowrap}.stock-score{font-size:.72rem;color:var(--muted);margin-top:.12rem}
.index-card{background:#fff;border:1px solid var(--line);border-radius:13px;padding:.85rem;margin-bottom:.5rem}.index-title{font-size:.78rem;color:var(--muted)}.index-value{font-size:1.2rem;font-weight:700;font-variant-numeric:tabular-nums}.news-row{padding:.75rem .1rem;border-bottom:1px solid var(--line);line-height:1.7}.news-title{font-weight:600;font-size:.88rem}.news-source{font-size:.74rem;color:var(--muted);margin-top:.15rem}
.stButton>button,.stDownloadButton>button{border-radius:10px!important;border:1px solid #dfe5ef!important;font-weight:600!important;min-height:2.45rem;transition:all .15s ease}
.stButton>button[kind="primary"]{background:#315fcb!important;border-color:#315fcb!important;color:white!important}
.stButton>button:hover,.stDownloadButton>button:hover{border-color:#9aafd9!important}
div[data-baseweb="select"]>div{border-radius:10px!important;border-color:#dfe5ef!important;background:#fff}
div[data-testid="stTextInput"] input,div[data-testid="stNumberInput"] input{border-radius:10px!important}
div[data-testid="stDataFrame"],div[data-testid="stTable"]{border:1px solid var(--line);border-radius:12px;overflow:hidden;background:#fff}
div[data-testid="stAlert"]{border-radius:12px}
div[data-testid="stExpander"]{border:1px solid var(--line);border-radius:12px;background:#fff}
.js-plotly-plot,.plot-container{border-radius:12px;overflow:hidden}
hr{border-color:var(--line)!important}
@media(max-width:820px){.verdict{grid-template-columns:1fr;padding:.9rem}.stats{gap:.4rem}.stat{padding:.65rem}.v-title{font-size:1.45rem}}
@media(max-width:640px){.block-container,[data-testid="stMainBlockContainer"]{padding-left:.65rem!important;padding-right:.65rem!important}.topbar{padding:.75rem;border-radius:14px}.brand-name{font-size:1.1rem}.asof{font-size:.7rem}.verdict{border-radius:14px;gap:.8rem}.stat-v{font-size:1.08rem}.stock-row{grid-template-columns:minmax(0,1fr) auto;gap:.4rem;padding:.7rem}.stock-price{grid-column:2;grid-row:1}.stock-change{grid-column:2;grid-row:2;text-align:left}.stock-main{grid-column:1;grid-row:1 / span 2}.pick{padding:.8rem;border-radius:13px}.pick-body{grid-template-columns:1fr}.pick-name{display:block;margin:.15rem 0 0}.sec{margin-top:1.15rem}div[data-testid="stRadio"] div[role="radiogroup"]>label{padding:.38rem .7rem!important;font-size:.78rem!important}}
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


def stock_row_html(code: str, name: str, price, change, signal: str = "", score=None, extra: str = "") -> str:
    """Compact mobile-first row inspired by investing apps; avoids spreadsheet-like stock tables."""
    try:
        p = fnum(price, 2)
    except Exception:
        p = "-"
    try:
        c = float(change)
        change_class = "up" if c > 0 else "dn" if c < 0 else ""
        change_text = f"{c:+.2f}%"
    except (TypeError, ValueError):
        change_class, change_text = "", "—"
    score_html = f'<div class="stock-score">نقاط التحليل {fnum(score, 0)}/100</div>' if score is not None else ""
    signal_html = chip(signal) if signal else ""
    extra_html = f'<div class="stock-meta">{e(extra)}</div>' if extra else ""
    return (
        '<div class="stock-row"><div class="stock-main">'
        f'<div><span class="stock-symbol">{bdi(code)}</span><span class="stock-name">{e(name)}</span></div>'
        f'<div class="stock-meta">{signal_html} {score_html}</div>{extra_html}</div>'
        f'<div class="stock-price">{bdi(p)} <small style="font-size:.68rem;color:var(--muted)">ج.م</small></div>'
        f'<div class="stock-change {change_class}">{bdi(change_text)}</div></div>'
    )


def index_card_html(name: str, value, change, date_text: str = "") -> str:
    try:
        c = float(change)
        cls = "up" if c > 0 else "dn" if c < 0 else ""
        ch = f"{c:+.2f}%"
    except (TypeError, ValueError):
        cls, ch = "", "—"
    return (
        f'<div class="index-card"><div class="index-title">{e(name)}</div>'
        f'<div class="index-value">{bdi(fnum(value, 2))}</div>'
        f'<div class="{cls}" style="font-weight:700;font-size:.82rem">{bdi(ch)}</div>'
        f'<div class="stock-meta">{e(date_text)}</div></div>'
    )


def news_row_html(title: str, source: str = "") -> str:
    return f'<div class="news-row"><div class="news-title">{e(title)}</div><div class="news-source">{e(source)}</div></div>'
