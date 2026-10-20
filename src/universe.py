"""بناء قائمة التحليل: الأسهم المتوافقة مع الشريعة داخل EGX33 وخارجه.

لا نفترض أن كل سهم في universe.csv متوافق مع الشريعة. الأسهم خارج EGX33
تدخل التحليل فقط إذا أضيفت إلى sharia_extra.csv بحالة approved مع مصدر تحقق.
"""
from __future__ import annotations

from datetime import date

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
    columns = ["code", "name_ar", "verification_source", "verification_url", "verified_on", "notes"]
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

    extra_merge = extra[["code", "name_ar", "verification_source", "verification_url", "verified_on"]].rename(
        columns={
            "name_ar": "extra_name_ar",
            "verification_source": "sharia_source",
            "verified_on": "sharia_verified_on",
            "verification_url": "sharia_source_url",
        }
    )
    df = lst.merge(e33, on="code", how="outer").merge(extra_merge, on="code", how="outer")
    df["in_list"] = df["code"].isin(lst["code"])
    df["in_egx33"] = df["code"].isin(e33["code"])
    df["in_sharia_extra"] = df["code"].isin(extra["code"])
    df["name_ar"] = df["name_ar"].fillna("")
    df["extra_name_ar"] = df["extra_name_ar"].fillna("")
    df["name_en"] = df["name_en"].fillna("")
    df["sharia_source"] = df["sharia_source"].fillna("")
    df["sharia_source_url"] = df["sharia_source_url"].fillna("")
    df["sharia_verified_on"] = df["sharia_verified_on"].fillna("")
    verified_date = pd.to_datetime(df["sharia_verified_on"], errors="coerce").dt.date
    max_age = int(cfg.get("universe", {}).get("verification_max_age_days", 180))
    age_days = verified_date.map(lambda d: (date.today() - d).days if pd.notna(d) else None)
    extra_fresh = df["in_sharia_extra"] & age_days.map(lambda n: n is not None and 0 <= n <= max_age).fillna(False)
    df["sharia_review_status"] = "مراجعة مطلوبة"
    df.loc[df["in_sharia_extra"] & ~extra_fresh, "sharia_review_status"] = "اعتماد خارجي منتهي الصلاحية"
    df.loc[extra_fresh, "sharia_review_status"] = "اعتماد خارجي حديث"
    df.loc[df["in_egx33"], "sharia_review_status"] = "مكوّن في EGX33"
    df["name_ar"] = df["name_ar"].where(df["name_ar"] != "", df["extra_name_ar"])
    df["name"] = df["name_ar"].where(df["name_ar"] != "", df["name_en"])

    if mode == "sharia_union":
        # Strict personal Sharia universe: current EGX33 constituents plus
        # externally screened additions with an auditable, non-expired review.
        # universe.csv is only a candidate/reference list and must never expand
        # the Sharia universe by itself.
        mask = df["in_egx33"] | extra_fresh
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
    # universe.csv is a research candidate list, not proof of Sharia compliance.
    # EGX33 constituents are index-screened; out-of-index additions require an
    # explicit source and a recent verification date.
    out["sharia_verified"] = out["in_egx33"] | (out["in_sharia_extra"] & out["sharia_review_status"].eq("اعتماد خارجي حديث"))
    return out[[
        "code", "name", "name_ar", "name_en", "in_list", "in_egx33",
        "in_sharia_extra", "sharia_verified", "sharia_source", "sharia_source_url", "sharia_verified_on", "sharia_review_status",
    ]]
