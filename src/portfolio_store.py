"""Encrypted persistent personal portfolio with optional GitHub sync."""
from __future__ import annotations
import base64, json, os
from pathlib import Path
import requests

DEFAULT_PATH = Path("data/portfolio.enc")

def _setting(name: str, default: str = "") -> str:
    value = os.environ.get(name, "").strip()
    if value:
        return value
    # Streamlit Cloud stores app secrets in st.secrets rather than environment variables.
    try:
        import streamlit as st
        value = str(st.secrets.get(name, default)).strip()
        return value
    except Exception:
        return default

def has_credentials() -> bool:
    return bool(_setting("PORTFOLIO_ENCRYPTION_KEY") and _setting("GITHUB_TOKEN"))

def _fernet():
    key = _setting("PORTFOLIO_ENCRYPTION_KEY")
    if not key:
        return None
    from cryptography.fernet import Fernet
    return Fernet(key.encode())

def encrypt(holdings: list[dict]) -> str | None:
    f = _fernet()
    return f.encrypt(json.dumps(holdings, ensure_ascii=False, separators=(",", ":")).encode()).decode() if f else None

def decrypt(blob: str) -> list[dict]:
    f = _fernet()
    if not f or not blob:
        return []
    try:
        obj = json.loads(f.decrypt(blob.encode()).decode())
        return obj if isinstance(obj, list) else []
    except Exception:
        return []

def local_load(path: Path = DEFAULT_PATH) -> list[dict]:
    if not path.exists():
        return []
    return decrypt(path.read_text(encoding="utf-8").strip())

def _gh():
    return (
        _setting("GITHUB_TOKEN"),
        _setting("GITHUB_REPO", "MedhatCoding/Egx-ai-analysis-"),
        _setting("GITHUB_BRANCH", "main"),
    )

def github_load():
    token, repo, branch = _gh()
    if not token or not _fernet():
        return [], False
    try:
        r = requests.get(
            f"https://api.github.com/repos/{repo}/contents/data/portfolio.enc",
            headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"},
            params={"ref": branch}, timeout=15,
        )
        if r.status_code != 200:
            return [], False
        blob = base64.b64decode(r.json().get("content", "")).decode()
        return decrypt(blob), True
    except Exception:
        return [], False

def github_save(holdings: list[dict]) -> tuple[bool, str]:
    token, repo, branch = _gh()
    blob = encrypt(holdings)
    if not token or not blob:
        return False, "يلزم ضبط GITHUB_TOKEN و PORTFOLIO_ENCRYPTION_KEY"
    url = f"https://api.github.com/repos/{repo}/contents/data/portfolio.enc"
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"}
    try:
        old = requests.get(url, headers=headers, params={"ref": branch}, timeout=15)
        sha = old.json().get("sha") if old.status_code == 200 else None
        payload = {
            "message": "portfolio: encrypted personal portfolio update",
            "content": base64.b64encode(blob.encode()).decode(),
            "branch": branch,
        }
        if sha:
            payload["sha"] = sha
        r = requests.put(url, headers=headers, json=payload, timeout=20)
        return r.status_code in (200, 201), str(r.json().get("message") or f"HTTP {r.status_code}")
    except Exception as e:
        return False, type(e).__name__

def load_for_daily() -> list[dict]:
    rows, ok = github_load()
    return rows if ok else local_load()
