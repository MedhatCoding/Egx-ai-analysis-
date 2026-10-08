"""رسوم Plotly للوحة، بنفس ألوان ui.py (خلفية فاتحة، أخضر صعود وأحمر هبوط)."""
from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

NAVY, GAIN, LOSS, AMBER = "#12284C", "#0E9F6E", "#D9383A", "#B7791F"
MUTED, LINE, INK, GRID = "#5B6B82", "#D9E0EA", "#0F1B2D", "#EEF2F7"
FONT = dict(family="IBM Plex Sans Arabic, system-ui, sans-serif", color=INK, size=12)
# البورصة المصرية: الجمعة والسبت إجازة، فنخفيهم من محور الزمن عشان مايبقاش فيه فراغات
WEEKEND = dict(bounds=["fri", "sun"])


def _base(fig: go.Figure, height: int, legend: bool = False) -> go.Figure:
    fig.update_layout(
        height=height,
        margin=dict(l=8, r=8, t=28 if legend else 12, b=8),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="#FFFFFF",
        font=FONT,
        hoverlabel=dict(font=FONT),
        showlegend=legend,
        legend=dict(orientation="h", y=1.12, x=0, font=dict(size=12)),
        xaxis_rangeslider_visible=False,
    )
    return fig


def stock_chart(ind: pd.DataFrame, plan: dict | None = None, months: int | None = 6) -> go.Figure:
    """شموع + متوسطات + حجم + RSI + MACD. المؤشرات محسوبة على التاريخ كامل ثم نقص العرض فقط."""
    end = ind.index[-1]
    start = end - pd.DateOffset(months=months) if months else ind.index[0]
    v = ind[ind.index >= start]

    fig = make_subplots(rows=4, cols=1, shared_xaxes=True, vertical_spacing=0.025, row_heights=[0.56, 0.14, 0.15, 0.15])
    fig.add_trace(
        go.Candlestick(
            x=v.index, open=v["open"], high=v["high"], low=v["low"], close=v["close"], name="السعر",
            increasing_line_color=GAIN, increasing_fillcolor=GAIN, decreasing_line_color=LOSS, decreasing_fillcolor=LOSS,
        ),
        row=1, col=1,
    )
    for col, color, w in (("sma20", "#2B6CB0", 1.2), ("sma50", AMBER, 1.5), ("sma200", NAVY, 1.7)):
        fig.add_trace(go.Scatter(x=v.index, y=v[col], mode="lines", name=col.upper().replace("SMA", "م."), line=dict(color=color, width=w)), row=1, col=1)

    up = np.where(v["close"] >= v["open"], GAIN, LOSS)
    fig.add_trace(go.Bar(x=v.index, y=v["volume"], marker_color=up, opacity=0.55, name="الحجم"), row=2, col=1)
    fig.add_trace(go.Scatter(x=v.index, y=v["vol_sma20"], mode="lines", line=dict(color=NAVY, width=1.2), name="متوسط الحجم"), row=2, col=1)

    fig.add_trace(go.Scatter(x=v.index, y=v["rsi14"], mode="lines", line=dict(color=NAVY, width=1.5), name="RSI"), row=3, col=1)
    for lvl in (30, 70):
        fig.add_hline(y=lvl, line=dict(color=MUTED, width=1, dash="dot"), row=3, col=1)

    hist = v["macd_hist"]
    fig.add_trace(go.Bar(x=v.index, y=hist, marker_color=np.where(hist >= 0, GAIN, LOSS), opacity=0.5, name="MACD hist"), row=4, col=1)
    fig.add_trace(go.Scatter(x=v.index, y=v["macd"], mode="lines", line=dict(color=NAVY, width=1.3), name="MACD"), row=4, col=1)
    fig.add_trace(go.Scatter(x=v.index, y=v["macd_signal"], mode="lines", line=dict(color=AMBER, width=1.3), name="Signal"), row=4, col=1)

    lo, hi = float(v["low"].min()), float(v["high"].max())
    if plan:
        for key, color, label in (("stop", LOSS, "الوقف"), ("t1", GAIN, "الهدف 1"), ("t2", GAIN, "الهدف 2")):
            y = plan.get(key)
            if y is None or not np.isfinite(y):
                continue
            fig.add_hline(
                y=float(y), row=1, col=1, line=dict(color=color, width=1.1, dash="dash"),
                annotation_text=f"{label} {float(y):.2f}", annotation_position="right", annotation_font=dict(color=color, size=11),
            )
            lo, hi = min(lo, float(y)), max(hi, float(y))
    pad = (hi - lo) * 0.04
    fig.update_yaxes(range=[lo - pad, hi + pad], row=1, col=1)
    fig.update_yaxes(range=[0, 100], row=3, col=1)
    fig.update_xaxes(rangebreaks=[WEEKEND], showgrid=False, showline=True, linecolor=LINE)
    fig.update_yaxes(gridcolor=GRID, zeroline=False)
    _base(fig, 760, legend=True)
    fig.update_layout(xaxis_rangeslider_visible=False, margin=dict(l=8, r=70, t=32, b=8))
    return fig


def index_chart(reg: pd.DataFrame, name: str, sessions: int = 250) -> go.Figure:
    d = reg.tail(sessions)
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=d.index, y=d["bench_close"], mode="lines", name=name, line=dict(color=NAVY, width=2.2)))
    fig.add_trace(go.Scatter(x=d.index, y=d["bench_sma50"], mode="lines", name="متوسط 50", line=dict(color=AMBER, width=1.4)))
    fig.add_trace(go.Scatter(x=d.index, y=d["bench_sma200"], mode="lines", name="متوسط 200", line=dict(color=MUTED, width=1.4, dash="dash")))
    fig.update_xaxes(rangebreaks=[WEEKEND], showgrid=False, showline=True, linecolor=LINE)
    fig.update_yaxes(gridcolor=GRID, zeroline=False)
    return _base(fig, 280, legend=True)


def market_map(tbl: pd.DataFrame) -> go.Figure:
    """خريطة حرارية: حجم المربع = متوسط قيمة التداول، واللون = تغير آخر جلسة."""
    d = tbl.dropna(subset=["ret1"]).copy()
    d = d[~d["stale"].astype(bool)]
    size = d["avg_value_m"].fillna(0.1).clip(lower=0.1)
    ret = d["ret1"].astype(float)
    fig = go.Figure(
        go.Treemap(
            labels=d["code"], parents=[""] * len(d), values=size,
            text=[f"{r:+.1f}%" for r in ret],
            texttemplate="<b>%{label}</b><br>%{text}",
            customdata=np.stack([d["name"].astype(str), ret, d["score"].astype(float)], axis=1),
            hovertemplate="<b>%{label}</b> %{customdata[0]}<br>التغير: %{customdata[1]:.2f}%<br>النقاط: %{customdata[2]:.0f}<extra></extra>",
            marker=dict(colors=ret.clip(-6, 6), colorscale=[[0, LOSS], [0.5, "#EEF1F6"], [1, GAIN]], cmin=-6, cmid=0, cmax=6,
                        line=dict(color="#FFFFFF", width=2)),
            textfont=dict(color=INK, size=13),
        )
    )
    fig.update_layout(height=520, margin=dict(l=0, r=0, t=8, b=0), paper_bgcolor="rgba(0,0,0,0)", font=FONT)
    return fig


def equity_chart(trades: pd.DataFrame) -> go.Figure:
    t = trades.sort_values("exit_date")
    cum = t["r_net"].astype(float).cumsum()
    fig = go.Figure(go.Scatter(x=pd.to_datetime(t["exit_date"]), y=cum, mode="lines", fill="tozeroy", line=dict(color=NAVY, width=2),
                               fillcolor="rgba(18,40,76,0.10)", name="R التراكمي"))
    fig.update_yaxes(gridcolor=GRID, zeroline=True, zerolinecolor=MUTED, title="R تراكمي")
    fig.update_xaxes(showgrid=False, showline=True, linecolor=LINE)
    return _base(fig, 300)
