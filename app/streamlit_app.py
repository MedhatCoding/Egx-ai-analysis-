"""لوحة تحليل الأسهم المصرية (Streamlit). بتقرا ملفات data/ اللي بيجهزها التشغيل اليومي.

التشغيل محليًا:   streamlit run app/streamlit_app.py
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402

from app import charts, ui  # noqa: E402
from src import config as C  # noqa: E402
from src.data_fetch import read_cache  # noqa: E402
from src.indicators import compute_indicators  # noqa: E402
from src.signals import SETUP_AR, SIGNAL_AR  # noqa: E402
from src.track_record import HISTORY, load_history, summarize  # noqa: E402
from src.portfolio import evaluate, totals, risk_summary  # noqa: E402
from src.portfolio_store import github_load, github_save, local_load, encrypt, decrypt  # noqa: E402

st.set_page_config(page_title="مستشار البورصة | EGX Advisor", page_icon="📈", layout="wide", initial_sidebar_state="collapsed")
st.markdown(ui.CSS, unsafe_allow_html=True)


# ------------------------------------------------------------------ أدوات
def wide(fn, *args, **kwargs):
    """عرض كامل بغض النظر عن إصدار Streamlit (width='stretch' في الجديد، use_container_width في القديم)."""
    try:
        return fn(*args, width="stretch", **kwargs)
    except Exception:  # noqa: BLE001
        return fn(*args, use_container_width=True, **kwargs)


def mtime(p: Path) -> float:
    return p.stat().st_mtime if p.exists() else 0.0


@st.cache_data(ttl=600, show_spinner=False)
def _json(path: str, stamp: float):
    p = Path(path)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


@st.cache_data(ttl=600, show_spinner=False)
def _csv(path: str, stamp: float, index_col: str | None = None):
    p = Path(path)
    if not p.exists():
        return None
    return pd.read_csv(p, index_col=index_col, parse_dates=bool(index_col))


@st.cache_data(ttl=600, show_spinner=False)
def _indicators(code: str, stamp: float):
    df = read_cache(code)
    return None if df is None or len(df) < 30 else compute_indicators(df)


def load_json(p: Path):
    return _json(str(p), mtime(p))


def load_csv(p: Path, index_col: str | None = None):
    return _csv(str(p), mtime(p), index_col)


cfg = C.load_config()
latest = load_json(C.SIGNALS / "latest.json")

if not latest:
    st.markdown(
        '<div class="topbar"><div class="topbar-in"><div><span class="brand-name">مستشار البورصة</span>'
        '<span class="brand-sub">EGX Advisor</span></div></div></div>'
        '<div class="empty"><b>لسه مفيش تقرير.</b><br>شغّل التشغيل اليومي مرة واحدة عشان تظهر البيانات: '
        'من تبويب Actions في GitHub اختر «EGX Daily Report» ثم Run workflow، أو محليًا: '
        '<bdi>python run_daily.py --force --dry-run</bdi></div>',
        unsafe_allow_html=True,
    )
    st.stop()

report = load_json(C.DATA / "report" / "latest.json") or {}
table = load_csv(C.SIGNALS / "table.csv")
regime = load_csv(C.SIGNALS / "regime.csv", index_col="date")
if table is not None:
    table["why_not_buy"] = table["why_not_buy"].fillna("")
notes = report.get("notes") or {}

st.markdown(ui.header_html(latest, report), unsafe_allow_html=True)
st.markdown(ui.verdict_html(latest, notes.get("market_view", ""), report.get("warnings") or []), unsafe_allow_html=True)

tabs = st.tabs(["فرص اليوم", "خريطة السوق", "كل الأسهم", "تحليل سهم", "محفظتي", "الأداء", "عن النظام"])

# ================================================================== فرص اليوم
with tabs[0]:
    picks, watch = latest["picks"], latest["watch"]
    st.markdown(ui.section("فرص الشراء", f"{len(picks)} فرصة بعد فلاتر السيولة والاتجاه والمقاومة والتشبّع"), unsafe_allow_html=True)
    if picks:
        for p in picks:
            st.markdown(ui.pick_html(p, (notes.get("picks") or {}).get(p["code"])), unsafe_allow_html=True)
    else:
        st.markdown(ui.empty_picks_html(latest), unsafe_allow_html=True)

    if watch:
        st.markdown(ui.section("قائمة المراقبة", notes.get("watch_view", "")), unsafe_allow_html=True)
        wdf = pd.DataFrame(
            [
                {
                    "الرمز": w["code"], "الشركة": w["name"], "النقاط": w["score"], "النموذج": w["setup_ar"],
                    "RSI": w["rsi"], "سبب عدم الوصول للشراء": " | ".join((w.get("why_not_buy") or [])[:2]),
                }
                for w in watch
            ]
        )
        wide(
            st.dataframe, wdf, hide_index=True,
            column_config={
                "النقاط": st.column_config.ProgressColumn("النقاط", min_value=0, max_value=100, format="%.0f"),
                "RSI": st.column_config.NumberColumn("RSI", format="%.0f"),
            },
        )

    if regime is not None and len(regime) > 60:
        st.markdown(ui.section("اتجاه المؤشر", "المؤشر مقابل متوسطيه 50 و200 يومًا"), unsafe_allow_html=True)
        wide(st.plotly_chart, charts.index_chart(regime, latest["market"].get("bench_name", "المؤشر")), config={"displayModeBar": False})

    m = latest["market"]
    if m.get("top_gainers") and m.get("top_losers"):
        gcol, lcol = st.columns(2)
        gcol.markdown(
            ui.section("الأكثر ارتفاعًا")
            + ui.kv_html([(f"{g['code']} {g['name']}", ui.change_html(g["ret1"])) for g in m["top_gainers"]]),
            unsafe_allow_html=True,
        )
        lcol.markdown(
            ui.section("الأكثر انخفاضًا")
            + ui.kv_html([(f"{g['code']} {g['name']}", ui.change_html(g["ret1"])) for g in m["top_losers"]]),
            unsafe_allow_html=True,
        )

# ================================================================== خريطة السوق
with tabs[1]:
    st.markdown(ui.section("السوق والمؤشرات", "بيانات المؤشرات تُجلب من مزودي البيانات المتاحين، والبيانات اللحظية من OANOR عند ضبط المفتاح."), unsafe_allow_html=True)

    idxs = latest.get("market_indices") or {}
    live = latest.get("live_market") or {}
    if idxs:
        rows = []
        for name, x in idxs.items():
            rows.append({"المؤشر": name, "القيمة": x.get("close"), "اليوم %": x.get("change_pct"), "التاريخ": x.get("date")})
        iv = pd.DataFrame(rows)
        wide(st.dataframe, iv, hide_index=True, column_config={
            "القيمة": st.column_config.NumberColumn(format="%.2f"),
            "اليوم %": st.column_config.NumberColumn(format="%.2f"),
        })
    else:
        st.info("لم تتوفر بيانات تاريخية للمؤشرات من EODHD في آخر تشغيل. بعد إضافة OANOR_API_KEY وإعادة تشغيل التقرير ستظهر اللقطة اللحظية المتاحة.")

    if live:
        st.markdown(ui.section("السوق الآن", "OANOR — بيانات لحظية عند توفر المفتاح"), unsafe_allow_html=True)
        oi = live.get("index") or {}
        idx_data = oi.get("data", {}) if isinstance(oi, dict) else {}
        idx_rows = idx_data.get("indices") or []
        if idx_rows:
            wide(st.dataframe, pd.DataFrame(idx_rows), hide_index=True)
        else:
            wide(st.json, oi)

        oscr = live.get("screener") or {}
        scr_data = oscr.get("data", {}) if isinstance(oscr, dict) else {}
        scr_rows = scr_data.get("results") or []
        if scr_rows:
            wide(st.dataframe, pd.DataFrame(scr_rows), hide_index=True)
        elif oscr:
            wide(st.json, oscr)

    news = latest.get("news") or {}
    market_news = news.get("market") or []
    company_news = news.get("companies") or []
    if market_news or company_news:
        st.markdown(ui.section("أخبار السوق", "عناوين حديثة للسياق فقط؛ لا تدخل الأخبار وحدها في قرار الشراء."), unsafe_allow_html=True)
        news_rows = [{"الخبر": x.get("title"), "المصدر": x.get("source", "")} for x in market_news[:8]]
        if news_rows:
            wide(st.dataframe, pd.DataFrame(news_rows), hide_index=True)
        if company_news:
            st.markdown(ui.section("أخبار مرتبطة بالفرص"), unsafe_allow_html=True)
            wide(st.dataframe, pd.DataFrame([{"الرمز": x.get("code"), "الخبر": x.get("title"), "المصدر": x.get("source", "")} for x in company_news[:10]]), hide_index=True)

    st.markdown(ui.section("خريطة السوق", "حجم المربع = متوسط قيمة التداول اليومي، واللون = تغير آخر جلسة"), unsafe_allow_html=True)
    if table is not None and len(table):
        wide(st.plotly_chart, charts.market_map(table), config={"displayModeBar": False})

# ================================================================== كل الأسهم
with tabs[2]:
    st.markdown(ui.section("كل الأسهم المحللة", f"{latest['analyzed']} سهم من {latest['universe_size']} في القائمة"), unsafe_allow_html=True)
    if table is not None:
        c1, c2, c3 = st.columns([2, 1, 1])
        sigs = c1.multiselect("الإشارة", list(SIGNAL_AR), default=["BUY", "WATCH"], format_func=lambda s: SIGNAL_AR[s])
        min_score = c2.slider("أقل نقاط", 0, 100, 0)
        q = c3.text_input("بحث بالرمز أو الاسم")
        f = table[table["signal"].isin(sigs) & (table["score"] >= min_score)]
        if q.strip():
            f = f[f["code"].str.contains(q.strip(), case=False, na=False) | f["name"].astype(str).str.contains(q.strip(), na=False)]
        view = pd.DataFrame(
            {
                "الرمز": f["code"], "الشركة": f["name"], "الإشارة": f["signal"].map(SIGNAL_AR), "النقاط": f["score"],
                "النموذج": f["setup"].map(SETUP_AR), "الإغلاق": f["close"], "اليوم %": f["ret1"], "20 يوم %": f["ret20"],
                "RSI": f["rsi"], "حجم/متوسط": f["vol_ratio"], "سيولة (مليون ج.م)": f["avg_value_m"],
                "القوة النسبية %": f["rs_pct"], "الوقف": f["stop"], "الهدف 1": f["t1"],
            }
        )
        wide(
            st.dataframe, view, hide_index=True, height=560,
            column_config={
                "النقاط": st.column_config.ProgressColumn("النقاط", min_value=0, max_value=100, format="%.0f"),
                "الإغلاق": st.column_config.NumberColumn(format="%.2f"),
                "اليوم %": st.column_config.NumberColumn(format="%.2f"),
                "20 يوم %": st.column_config.NumberColumn(format="%.1f"),
                "RSI": st.column_config.NumberColumn(format="%.0f"),
                "حجم/متوسط": st.column_config.NumberColumn(format="%.1f"),
                "سيولة (مليون ج.م)": st.column_config.NumberColumn(format="%.1f"),
                "القوة النسبية %": st.column_config.NumberColumn(format="%.0f"),
                "الوقف": st.column_config.NumberColumn(format="%.2f"),
                "الهدف 1": st.column_config.NumberColumn(format="%.2f"),
            },
        )
        st.download_button("تنزيل الجدول كملف CSV", table.to_csv(index=False).encode("utf-8-sig"), "egx_signals.csv", "text/csv")

# ================================================================== تحليل سهم
with tabs[3]:
    if table is None or table.empty:
        st.info("لا توجد بيانات.")
    else:
        ranked = table.sort_values("score", ascending=False)
        codes = ranked["code"].tolist()
        names = dict(zip(table["code"], table["name"].astype(str)))
        default = latest["picks"][0]["code"] if latest["picks"] else codes[0]
        cc1, cc2 = st.columns([3, 2])
        code = cc1.selectbox("السهم", codes, index=codes.index(default), format_func=lambda c: f"{c}   {names.get(c, '')}")
        span_map = {"3 شهور": 3, "6 شهور": 6, "سنة": 12, "الكل": None}
        span = cc2.radio("المدى", list(span_map), index=1, horizontal=True)
        row = table[table["code"] == code].iloc[0].to_dict()
        signal = row["signal"]

        st.markdown(
            f'<div class="sec"><h2>{ui.bdi(code)} <span style="font-weight:500;color:var(--muted)">{ui.e(names.get(code, ""))}</span> '
            f"{ui.chip(signal)}</h2></div>",
            unsafe_allow_html=True,
        )
        ind = _indicators(code, mtime(C.PRICES / f"{code}.csv"))
        plan = ui.plan_from_row(row)
        valid_plan = all(isinstance(plan.get(k), (int, float)) and math.isfinite(plan[k]) for k in ("stop", "t1", "t2", "close"))
        if ind is None:
            st.warning("ملف أسعار هذا السهم غير متاح.")
        else:
            wide(
                st.plotly_chart, charts.stock_chart(ind, plan if (valid_plan and signal == "BUY") else None, span_map[span]),
                config={"displayModeBar": False},
            )

        left, right = st.columns(2)
        with left:
            st.markdown(ui.section("الموقف الفني"), unsafe_allow_html=True)
            st.markdown(
                ui.kv_html(
                    [
                        ("الإغلاق", ui.bdi(ui.fnum(row["close"]))),
                        ("اليوم / 5 أيام / 20 يوم", f"{ui.change_html(row['ret1'])} &nbsp; {ui.change_html(row['ret5'])} &nbsp; {ui.change_html(row['ret20'])}"),
                        ("RSI", ui.bdi(ui.fnum(row["rsi"], 0))),
                        ("متوسط المدى اليومي ATR", ui.bdi(ui.fnum(row["atr_pct"], 1) + "%")),
                        ("حجم اليوم إلى متوسطه", ui.bdi(ui.fnum(row["vol_ratio"], 1) + "×")),
                        ("متوسط قيمة التداول", ui.bdi(ui.fnum(row["avg_value_m"], 1) + " مليون ج.م")),
                        ("القوة النسبية", ui.bdi(ui.fnum(row["rs_pct"], 0) + "%")),
                        ("البعد عن قمة 52 أسبوعًا", ui.bdi(ui.fnum(row["dist_high252"], 1) + "%")),
                        ("النموذج", ui.e(SETUP_AR.get(row["setup"], row["setup"]))),
                    ]
                ),
                unsafe_allow_html=True,
            )
            if signal != "BUY" and row.get("why_not_buy"):
                st.markdown(
                    '<div class="empty"><b>لماذا ليست فرصة شراء الآن؟</b>' + ui._ul(str(row["why_not_buy"]).split(" | ")) + "</div>",
                    unsafe_allow_html=True,
                )
        with right:
            st.markdown(ui.section("تفصيل النقاط", f"الإجمالي {row['score']:.0f} من 100"), unsafe_allow_html=True)
            st.markdown(ui.components_html(row, cfg["scoring"]["weights"]), unsafe_allow_html=True)

        if valid_plan:
            title = "خطة الصفقة" if signal == "BUY" else "مستويات إرشادية (الإشارة الحالية ليست شراء)"
            st.markdown(ui.section(title), unsafe_allow_html=True)
            st.markdown(f'<div class="plan">{ui.ladder_html(plan)}</div>', unsafe_allow_html=True)

            st.markdown(ui.section("حاسبة حجم المركز", "بناءً على أقصى خسارة تقبلها إذا ضُرب الوقف (بدون رسوم السمسرة)"), unsafe_allow_html=True)
            k1, k2 = st.columns(2)
            capital = k1.number_input("رأس المال (ج.م)", min_value=1000.0, value=100000.0, step=5000.0)
            risk_pct = k2.number_input("أقصى خسارة للصفقة (% من رأس المال)", min_value=0.1, max_value=5.0,
                                       value=float(cfg["risk"]["risk_per_trade_pct"]), step=0.1)
            per_share = plan["close"] - plan["stop"]
            if per_share > 0:
                by_risk = math.floor(capital * risk_pct / 100 / per_share)
                by_cap = math.floor(capital * cfg["risk"]["max_position_pct"] / 100 / plan["close"])
                qty = max(0, min(by_risk, by_cap))
                cost = qty * plan["close"]
                st.markdown(
                    ui.stat_grid(
                        [
                            ("عدد الأسهم", ui.bdi(f"{qty:,}")),
                            ("قيمة الصفقة", ui.bdi(f"{cost:,.0f} ج.م")),
                            ("خسارة عند الوقف", ui.bdi(f"{qty * per_share:,.0f} ج.م")),
                            ("ربح عند الهدف 1", ui.bdi(f"{qty * (plan['t1'] - plan['close']):,.0f} ج.م")),
                        ]
                    )
                    + ui.e(
                        f"الحد الأقصى لحجم السهم الواحد {cfg['risk']['max_position_pct']:.0f}% من المحفظة"
                        + (" (هو اللي قيّد العدد)." if by_cap < by_risk else ".")
                    ),
                    unsafe_allow_html=True,
                )


# ================================================================== محفظتي
with tabs[4]:
    st.markdown(ui.section("محفظتي", "أدخل المراكز التي تملكها، والنظام يراجعها مع كل تحديث للبيانات ويعطيك: بيع / احتفاظ / زيادة."), unsafe_allow_html=True)

    if "portfolio" not in st.session_state:
        persisted, synced = github_load()
        if not synced:
            persisted = local_load()
        st.session_state.portfolio = persisted if isinstance(persisted, list) else []
        st.session_state.portfolio_sync_ready = synced

    up = st.file_uploader("استيراد محفظة محفوظة CSV", type=["csv"], key="portfolio_upload")
    if up is not None:
        try:
            imported = pd.read_csv(up)
            required = {"type", "key", "quantity", "avg_cost"}
            if required.issubset(imported.columns):
                st.session_state.portfolio = imported.fillna("").to_dict("records")
                st.success("تم استيراد المحفظة.")
            else:
                st.error("ملف CSV لازم يحتوي: type, key, quantity, avg_cost")
        except Exception:
            st.error("تعذر قراءة ملف المحفظة.")

    if table is None or table.empty:
        st.warning("لا توجد بيانات سوق كافية لتقييم المحفظة الآن.")
    else:
        stock_options = table["code"].astype(str).tolist()
        stock_names = dict(zip(table["code"].astype(str), table["name"].astype(str)))
        funds_data = latest.get("funds") or {}
        fund_options = []
        for cat in ("sharia_equity", "gold"):
            fund_options += [f["name"] for f in (funds_data.get(cat) or {}).get("funds", [])]

        ac1, ac2 = st.columns([1, 2])
        asset_type = ac1.selectbox("نوع الاستثمار", ["stock", "fund"], format_func=lambda x: "سهم" if x == "stock" else "صندوق")
        options = stock_options if asset_type == "stock" else fund_options
        if options:
            selected = ac2.selectbox(
                "الأصل", options,
                format_func=lambda x: f"{x} — {stock_names.get(x, '')}" if asset_type == "stock" else x,
                key="portfolio_asset",
            )
            q1, q2 = st.columns(2)
            qty = q1.number_input("الكمية / عدد الوثائق", min_value=0.0, value=0.0, step=1.0, key="portfolio_qty")
            avg = q2.number_input("متوسط تكلفة الشراء", min_value=0.0, value=0.0, step=0.01, key="portfolio_avg")
            if st.button("إضافة إلى المحفظة", type="primary"):
                item = {"type": asset_type, "key": selected, "quantity": qty, "avg_cost": avg}
                st.session_state.portfolio = [x for x in st.session_state.portfolio if not (x.get("type") == asset_type and x.get("key") == selected)]
                st.session_state.portfolio.append(item)
                st.rerun()

    holdings = st.session_state.portfolio
    sc1, sc2 = st.columns([1, 2])
    if sc1.button("حفظ مشفّر للمزامنة مع التقرير اليومي", type="primary", disabled=not bool(__import__("os").environ.get("PORTFOLIO_ENCRYPTION_KEY") and __import__("os").environ.get("GITHUB_TOKEN"))):
        ok, msg = github_save(holdings)
        if ok:
            st.success("تم حفظ المحفظة مشفّرة. ستدخل في التقرير اليومي القادم.")
        else:
            st.error("تعذر الحفظ: " + str(msg))
    sc2.caption("الحفظ السحابي مشفّر؛ يلزم ضبط PORTFOLIO_ENCRYPTION_KEY في Streamlit Secrets، ويُستخدم GitHub Token للمزامنة.")
    if holdings:
        dfp = evaluate(holdings, table, funds_data, latest["regime"]["label"])
        t = totals(dfp)
        st.markdown(
            ui.stat_grid([
                ("قيمة الأسهم الحالية", ui.bdi(f"{t['value']:,.0f} ج.م")),
                ("تكلفة الأسهم", ui.bdi(f"{t['cost']:,.0f} ج.م")),
                ("ربح/خسارة الأسهم", ui.change_html(t["pnl_pct"]) if t["pnl_pct"] is not None else "-"),
                ("عدد المراكز", ui.bdi(len(holdings))),
            ]),
            unsafe_allow_html=True,
        )
        if not dfp.empty:
            view = dfp[["النوع", "الأصل", "الكمية", "متوسط التكلفة", "السعر الحالي", "الربح/الخسارة %", "النقاط", "القرار"]].copy()
            wide(st.dataframe, view, hide_index=True, column_config={
                "متوسط التكلفة": st.column_config.NumberColumn(format="%.2f"),
                "السعر الحالي": st.column_config.NumberColumn(format="%.2f"),
                "الربح/الخسارة %": st.column_config.NumberColumn(format="%.2f"),
                "النقاط": st.column_config.ProgressColumn(min_value=0, max_value=100, format="%.0f"),
            })
            for _, rr in dfp.iterrows():
                st.markdown(ui.section(f"{rr['النوع']}: {rr['الأصل']}", f"قرار: {rr['القرار']}"), unsafe_allow_html=True)
                st.markdown(f'<div class="note">{ui.e(rr["reason"])}</div>', unsafe_allow_html=True)

            exp = pd.DataFrame(holdings).to_csv(index=False).encode("utf-8-sig")
            st.download_button("حفظ المحفظة CSV", exp, "my_egx_portfolio.csv", "text/csv")
            blob = json.dumps(holdings, ensure_ascii=False, indent=2).encode("utf-8")
            st.download_button("تصدير ملف التشغيل اليومي", blob, "portfolio.json", "application/json",
                               help="ضع الملف باسم data/portfolio.json في المستودع ليقرأه التقرير اليومي تلقائيًا.")
            ps = latest.get("portfolio") or {}
            sm = ps.get("summary") or {}
            if sm:
                st.markdown(ui.section("مخاطر المحفظة", "سقف تركيز المركز يمنع النظام من اقتراح زيادة مركز كبير."), unsafe_allow_html=True)
                st.markdown(ui.stat_grid([
                    ("مراكز", ui.bdi(sm.get("positions", 0))),
                    ("بيع", ui.bdi(sm.get("sell", 0))),
                    ("احتفاظ", ui.bdi(sm.get("hold", 0))),
                    ("زيادة", ui.bdi(sm.get("increase", 0))),
                    ("أكبر تركيز", ui.bdi(f"{sm.get('concentration', 0):.1f}%")),
                ]), unsafe_allow_html=True)

        if st.button("مسح المحفظة من هذا الجهاز", type="secondary"):
            st.session_state.portfolio = []
            st.rerun()
    else:
        st.markdown('<div class="empty"><b>المحفظة فارغة.</b><br>أضف الأسهم أو صناديق الشريعة/الذهب التي تملكها.</div>', unsafe_allow_html=True)

# ================================================================== الأداء
with tabs[5]:
    hist = load_history() if HISTORY.exists() else None
    st.markdown(ui.section("سجل توصياتنا الفعلية", "كل توصية شراء بتتسجل وتتابع بنفس قواعد الاختبار التاريخي: دخول بافتتاح الجلسة التالية"), unsafe_allow_html=True)
    if hist is None or hist.empty:
        st.markdown('<div class="empty">لسه مفيش توصيات مسجلة. أول توصية شراء هتظهر هنا، ونتيجتها بتتحدد بعد جلسات.</div>', unsafe_allow_html=True)
    else:
        tr = summarize(hist)
        s = tr["stats"]
        st.markdown(
            ui.stat_grid(
                [
                    ("توصيات مسجلة", ui.bdi(tr["recommendations"])),
                    ("مغلقة / مفتوحة", f"{ui.bdi(tr['closed'])} / {ui.bdi(tr['open'])}"),
                    ("نسبة النجاح", ui.bdi(f"{s.get('win_rate', 0):.0f}%") if tr["closed"] else "-"),
                    ("متوسط النتيجة", ui.bdi(f"{s.get('avg_r', 0):+.2f} R") if tr["closed"] else "-"),
                ]
            ),
            unsafe_allow_html=True,
        )
        if tr["closed"] < 20:
            st.caption("العينة صغيرة (أقل من 20 صفقة مغلقة)، فلا تبنِ عليها استنتاجات قوية.")

        comp = tr.get("component_stats")
        st.markdown(
            ui.section("أي مكوّن نقاط بيفرق فعلاً؟", "متوسط نتيجة الصفقة (R) في النصف الأعلى من كل مكوّن مقابل النصف الأدنى وقت الإشارة"),
            unsafe_allow_html=True,
        )
        if comp:
            cdf = pd.DataFrame(
                [
                    {"المكوّن": v["label"], f"نصف أعلى (عدد {v['high_n']})": v["high_avg_r"], f"نصف أدنى (عدد {v['low_n']})": v["low_avg_r"],
                     "الفرق": round(v["high_avg_r"] - v["low_avg_r"], 2)}
                    for v in comp.values()
                ]
            ).sort_values("الفرق", ascending=False)
            wide(st.dataframe, cdf, hide_index=True)
            st.caption("فرق كبير وموجب معناه المكوّن ده بيميّز فعلًا؛ فرق قريب من الصفر معناه وزنه في الإعدادات ممكن يقل.")
        else:
            st.markdown(
                f'<div class="empty">التحليل بيحتاج {tr["component_stats_min_trades"]} صفقة مغلقة على الأقل عشان يبقى ذا معنى، '
                f'وعندنا دلوقتي {tr["closed"]}. هيظهر هنا تلقائيًا أول ما العدد يكفي.</div>',
                unsafe_allow_html=True,
            )
        shown = hist.sort_values("signal_date", ascending=False).head(40)
        wide(
            st.dataframe,
            shown[["signal_date", "code", "name", "score", "status", "entry", "exit", "reason", "r_net", "ret_pct", "days"]].rename(
                columns={"signal_date": "تاريخ الإشارة", "code": "الرمز", "name": "الشركة", "score": "النقاط", "status": "الحالة",
                         "entry": "الدخول", "exit": "الخروج/آخر سعر", "reason": "سبب الخروج", "r_net": "R", "ret_pct": "العائد %", "days": "أيام"}
            ),
            hide_index=True,
        )

    bt = load_json(C.BACKTEST / "summary.json")
    st.markdown(ui.section("الاختبار التاريخي", "نفس القواعد مطبقة على التاريخ المتاح، مقابل الدخول العشوائي في أسهم سائلة"), unsafe_allow_html=True)
    if not bt:
        st.markdown('<div class="empty">لسه ما اتعملش اختبار تاريخي. بيتحدث تلقائيًا كل أسبوع مع التشغيل اليومي.</div>', unsafe_allow_html=True)
    else:
        a, b = bt["strategy"], bt["baseline"]
        rows = [
            ("عدد الصفقات", "trades", "{:,.0f}"), ("نسبة النجاح %", "win_rate", "{:.1f}"), ("متوسط النتيجة (R)", "avg_r", "{:+.2f}"),
            ("عامل الربحية", "profit_factor", "{:.2f}"), ("متوسط العائد % بعد التكلفة", "avg_ret_pct", "{:+.2f}"),
            ("أطول سلسلة خسائر", "max_losing_streak", "{:.0f}"), ("أقصى تراجع (R)", "max_drawdown_r", "{:.1f}"),
            ("وصلت الهدف %", "pct_target", "{:.1f}"), ("ضُرب الوقف %", "pct_stop", "{:.1f}"), ("خروج زمني %", "pct_time", "{:.1f}"),
        ]

        def cell(d: dict, key: str, fmt_: str) -> str:
            v = d.get(key)
            return "-" if v is None else fmt_.format(v)

        cmp_df = pd.DataFrame({"المقياس": [r[0] for r in rows], "قواعد النظام": [cell(a, r[1], r[2]) for r in rows],
                               "خط الأساس (دخول بدون فلاتر)": [cell(b, r[1], r[2]) for r in rows]})
        wide(st.dataframe, cmp_df, hide_index=True)
        per = bt.get("period", {})
        st.caption(f"الفترة من {per.get('from', '')} إلى {per.get('to', '')} على {bt.get('stocks', '')} سهم، وتكلفة الدخول والخروج {bt['assumptions']['round_trip_cost_pct']}%.")
        tr_csv = load_csv(C.BACKTEST / "strategy_trades.csv")
        if tr_csv is not None and len(tr_csv) > 5:
            wide(st.plotly_chart, charts.equity_chart(tr_csv), config={"displayModeBar": False})
        st.markdown(
            '<div class="flag">تحفّظات مهمة: القائمة الحالية فقط (الأسهم اللي اختفت أو اتوقفت مش موجودة فالنتائج أفضل من الواقع)، '
            "ولا يوجد انزلاق سعري في الأسهم قليلة السيولة، والتاريخ المتاح سنوات قليلة تشمل ظروف سوق خاصة. النتائج للاسترشاد فقط.</div>",
            unsafe_allow_html=True,
        )

# ================================================================== عن النظام
with tabs[6]:
    sc, rk = cfg["scoring"], cfg["risk"]
    st.markdown(ui.section("كيف يعمل النظام"), unsafe_allow_html=True)
    st.markdown(
        ui.e(
            "الكود يحسب كل المؤشرات والنقاط والمستويات، والذكاء الاصطناعي يكتب التعليق فقط، وأي تعليق فيه رقم غير موجود في بيانات اليوم يُستبدل بنص جاهز. "
            "التقرير بيُبنى على إغلاق آخر جلسة ويصلك قبل الافتتاح."
        ),
        unsafe_allow_html=True,
    )
    w = sc["weights"]
    wdf = pd.DataFrame({"المكوّن": [c[0] for c in ui.COMPONENTS], "الوزن": [w[c[2]] for c in ui.COMPONENTS]})
    wide(st.dataframe, wdf, hide_index=True)
    st.markdown(
        ui.kv_html(
            [
                ("حد الشراء / المراقبة", ui.bdi(f"{sc['buy_score']} / {sc['watch_score']}")),
                ("أقصى RSI للشراء", ui.bdi(sc["rsi_max_for_buy"])),
                ("أقل سيولة يومية", ui.bdi(f"{cfg['filters']['min_avg_value_egp'] / 1e6:.1f} مليون ج.م")),
                ("الوقف", ui.e(f"بين {rk['stop_min_atr']} و{rk['stop_max_atr']} ATR أو أسفل قاع 10 جلسات")),
                ("الهدفان", ui.bdi(f"{rk['target_r'][0]}R / {rk['target_r'][1]}R")),
                ("مخاطرة الصفقة / سقف المركز", ui.bdi(f"{rk['risk_per_trade_pct']}% / {rk['max_position_pct']}%")),
                ("أقصى فرص شراء حسب السوق", ui.e("، ".join(f"{ui.REGIME_AR[k]} {v}" for k, v in rk["max_buys_by_regime"].items()))),
            ]
        ),
        unsafe_allow_html=True,
    )

    st.markdown(ui.section("الأسهم والبيانات"), unsafe_allow_html=True)
    u = latest.get("universe", {})
    st.markdown(
        ui.kv_html(
            [
                ("الأسهم في التحليل", ui.bdi(u.get("total", latest["universe_size"]))),
                ("من قائمتك / من EGX33 / في الاثنين", f"{ui.bdi(u.get('in_list', '-'))} / {ui.bdi(u.get('in_egx33', '-'))} / {ui.bdi(u.get('both', '-'))}"),
                ("وضع الدمج", ui.e(u.get("mode", ""))),
                ("الذكاء الاصطناعي", ui.e(
                    "مفعّل: " + str((report.get("llm") or {}).get("model", "")) if (report.get("llm") or {}).get("ok")
                    else "غير مفعّل، والتقرير يستخدم نصوصًا جاهزة" + (f" ({(report.get('llm') or {}).get('error', '')})" if (report.get("llm") or {}).get("error") else "")
                )),
            ]
        ),
        unsafe_allow_html=True,
    )
    cov = load_csv(C.SIGNALS / "coverage.csv")
    if cov is not None:
        weak = cov[(cov["source"] != "yahoo") | (cov["note"].fillna("") != "")]
        if len(weak):
            st.markdown(ui.section("أسهم بها ملاحظات في البيانات"), unsafe_allow_html=True)
            wide(st.dataframe, weak.rename(columns={"code": "الرمز", "source": "المصدر", "bars": "الشموع", "last_date": "آخر تاريخ", "note": "ملاحظة"}), hide_index=True)

st.markdown(ui.legal_html(), unsafe_allow_html=True)
