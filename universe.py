"""بناء قائمة الأسهم المحللة من قائمتك ومؤشر EGX33."""
from __future__ import annotations

import pandas as pd

from .config import DATA


def read_list() -> pd.DataFrame:
    df = pd.read_csv(DATA / "universe.csv", dtype=str).fillna("")
    df["code"] = df["code"].str.strip().str.upper()
    return df[["code", "name_ar"]].drop_duplicates("code")


def read_egx33() -> pd.DataFrame:
    rows = []
    f = DATA / "egx33.txt"
    if f.exists():
        for line in f.read_text(encoding="utf-8").splitlines():
            line = line.split("#")[0].strip()
            if not line:
                continue
            code, _, name = line.partition(",")
            rows.append({"code": code.strip().upper(), "name_en": name.strip()})
    return pd.DataFrame(rows, columns=["code", "name_en"]).drop_duplicates("code")


def build_universe(cfg: dict) -> pd.DataFrame:
    lst = read_list()
    e33 = read_egx33()
    mode = cfg["universe"]["mode"]

    df = pd.merge(lst, e33, on="code", how="outer")
    df["in_list"] = df["code"].isin(lst["code"])
    df["in_egx33"] = df["code"].isin(e33["code"])
    df["name_ar"] = df["name_ar"].fillna("")
    df["name_en"] = df["name_en"].fillna("")
    df["name"] = df["name_ar"].where(df["name_ar"] != "", df["name_en"])

    if mode == "union":
        mask = df["in_list"] | df["in_egx33"]
    elif mode == "intersection":
        mask = df["in_list"] & df["in_egx33"]
    elif mode == "list_only":
        mask = df["in_list"]
    elif mode == "egx33_only":
        mask = df["in_egx33"]
    else:
        raise ValueError(f"universe.mode غير معروف: {mode}")

    out = df[mask].sort_values("code").reset_index(drop=True)
    return out[["code", "name", "name_ar", "name_en", "in_list", "in_egx33"]]
