"""مولّد بيانات وهمية بشكل شموع البورصة المصرية (الأحد-الخميس) للاختبار بدون إنترنت."""
from __future__ import annotations

import numpy as np
import pandas as pd

TRADING_WEEKDAYS = {6, 0, 1, 2, 3}


def egx_dates(n: int, end: str = "2026-09-17") -> pd.DatetimeIndex:
    days = pd.date_range(end=end, periods=n * 2, freq="D")
    days = [d for d in days if d.weekday() in TRADING_WEEKDAYS]
    return pd.DatetimeIndex(days[-n:])


def make_prices(seed: int, n: int = 620, drift: float = 0.0005, vol: float = 0.017,
                base_volume: float = 800_000, end: str = "2026-09-17", start_price: float = 20.0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    dates = egx_dates(n, end)
    rets = rng.normal(drift, vol, n).clip(-0.095, 0.095)
    close = start_price * np.cumprod(1 + rets)
    open_ = np.r_[close[0], close[:-1]] * (1 + rng.normal(0, 0.003, n))
    hi = np.maximum(open_, close) * (1 + np.abs(rng.normal(0, 0.006, n)))
    lo = np.minimum(open_, close) * (1 - np.abs(rng.normal(0, 0.006, n)))
    vol_ = base_volume * np.exp(rng.normal(0, 0.4, n)) * (1 + 3 * np.abs(rets) / 0.02)
    return pd.DataFrame(
        {"open": open_, "high": hi, "low": lo, "close": close, "volume": vol_.round()},
        index=pd.DatetimeIndex(dates, name="date"),
    )


def make_universe_prices(n_stocks: int = 40, seed: int = 7) -> dict[str, pd.DataFrame]:
    """خليط: صاعدة، هابطة، عرضية، وواحد ضعيف السيولة وواحد بيانات قديمة وواحد تاريخه قصير."""
    out: dict[str, pd.DataFrame] = {}
    rng = np.random.default_rng(seed)
    for i in range(n_stocks):
        drift = rng.choice([0.0012, 0.0008, 0.0002, 0.0, -0.0006, -0.001])
        out[f"T{i:03d}"] = make_prices(seed + i, drift=float(drift), vol=float(rng.uniform(0.012, 0.025)),
                                       start_price=float(rng.uniform(5, 80)))
    out["ILLQ"] = make_prices(999, drift=0.001, base_volume=2_000, start_price=10)
    out["STAL"] = make_prices(998, drift=0.001, end="2026-08-20")
    out["SHRT"] = make_prices(997, n=90)
    return out
