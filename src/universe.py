"""بناء قائمة التحليل: الأسهم المتوافقة مع الشريعة داخل EGX33 وخارجه.

لا نفترض أن كل سهم في universe.csv متوافق مع الشريعة. الأسهم خارج EGX33
تدخل التحليل فقط إذا أضيفت إلى sharia_extra.csv بحالة approved مع مصدر تحقق.
"""
from __future__ import annotations

import pandas as pd

from .config import DATA


def read_list() -> pd.DataFrame:
    path = DATA / "universe.csv"
    if not path.exists():
        return pd.DataFrame(columns=["code", "name_ar"])
    df = pd.read_csv(path, dtype=str).fillna("")
    df["code"] = df["code"].str.strip().str.upper()
    return df[["code", "name_ar"]].drop_duplicates("code")


def read_egx33() -> pd.DataFrame:
    rows = []
    path = DATA / "egx33.txt"
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.split("#")[0].strip()
            if not line:
                continue
            code, _, name = line.partition(",")
            if code.strip():
                rows.append({"code": code.strip().upper(), "name_en": name.strip()})
    return pd.DataFrame(rows, columns=["code", "name_en"]).drop_duplicates("code")


def read_sharia_extra() -> pd.DataFrame:
    """Return only externally screened, explicitly approved shares outside EGX33."""
    path = DATA / "sharia_extra.csv"
    columns = ["code", "name_ar", "verification_source", "verified_on", "notes"]
    if not path.exists():
        return pd.DataFrame(columns=columns)
    df = pd.read_csv(path, dtype=str).fillna("")
    for col in columns:
        if col not in df:
            df[col] = ""
    df["code"] = df["code"].str.strip().str.upper()
    df["verification_source"] = df["verification_source"].str.strip()
    df["status"] = df.get("status", pd.Series("", index=df.index)).str.strip().str.lower()
    # Don't silently classify a share as Sharia-compliant without an auditable source.
    approved = df[(df["code"] != "") & (df["status"] == "approved") & (df["verification_source"] != "")]
    return approved[columns].drop_duplicates("code")


def build_universe(cfg: dict) -> pd.DataFrame:
    lst = read_list()
    e33 = read_egx33()
    extra = read_sharia_extra()
    mode = cfg["universe"]["mode"]

    df = lst.merge(e33, on="code", how="outer").merge(
        extra[["code", "name_ar", "verification_source"]].rename(
            columns={"name_ar": "extra_name_ar", "verification_source": "sharia_source"}
        ),
        on="code", how="outer",
    )
    df["in_list"] = df["code"].isin(lst["code"])
    df["in_egx33"] = df["code"].isin(e33["code"])
    df["in_sharia_extra"] = df["code"].isin(extra["code"])
    df["name_ar"] = df["name_ar"].fillna("")
    df["extra_name_ar"] = df["extra_name_ar"].fillna("")
    df["name_en"] = df["name_en"].fillna("")
    df["name_ar"] = df["name_ar"].where(df["name_ar"] != "", df["extra_name_ar"])
    df["name"] = df["name_ar"].where(df["name_ar"] != "", df["name_en"])

    if mode == "sharia_union":
        # EGX33 constituents + independently screened/approved additions outside the index.
        mask = df["in_egx33"] | df["in_sharia_extra"]
    elif mode == "union":
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
    out["sharia_verified"] = out["in_egx33"] | out["in_sharia_extra"]
    return out[["code", "name", "name_ar", "name_en", "in_list", "in_egx33", "in_sharia_extra", "sharia_verified"]]
