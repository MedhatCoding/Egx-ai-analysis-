"""تخزين محفظة شخصية بشكل مشفر مع مزامنة اختيارية إلى GitHub.
البيانات نفسها لا تُحفظ كنص صريح داخل المستودع؛ المفتاح يبقى في Secrets.
"""
from __future__ import annotations
import base64, json, os
from pathlib import Path
import requests

DEFAULT_PATH = Path("data/portfolio.enc")

def _key():
    return os.environ.get("PORTFOLIO_ENCRYPTION_KEY","").strip()

def _fernet():
    key=_key()
    if not key:
        return None
    from cryptography.fernet import Fernet
    return Fernet(key.encode())

def encrypt(holdings:list[dict]) -> str|None:
    f=_fernet()
    return f.encrypt(json.dumps(holdings,ensure_ascii=False,separators=(",",":")).encode()).decode() if f else None

def decrypt(blob:str) -> list[dict]:
    f=_fernet()
    if not f or not blob:
        return []
    try:
        obj=json.loads(f.decrypt(blob.encode()).decode())
        return obj if isinstance(obj,list) else []
    except Exception:
        return []

def local_load(path:Path=DEFAULT_PATH)->list[dict]:
    if not path.exists(): return []
    return decrypt(path.read_text(encoding="utf-8").strip())

def github_config():
    return os.environ.get("GITHUB_TOKEN","").strip(), os.environ.get("GITHUB_REPO","MedhatCoding/Egx-ai-analysis-").strip(), os.environ.get("GITHUB_BRANCH","main").strip()

def github_load():
    token,repo,branch=github_config()
    if not token: return [], False
    u=f"https://api.github.com/repos/{repo}/contents/data/portfolio.enc?ref={branch}"
    r=requests.get(u,headers={"Authorization":f"Bearer {token}","Accept":"application/vnd.github+json"},timeout=15)
    if r.status_code!=200: return [], False
    try:
        blob=base64.b64decode(r.json()["content"]).decode()
        return decrypt(blob), True
    except Exception: return [], False

def github_save(holdings:list[dict])->tuple[bool,str]:
    token,repo,branch=github_config()
    blob=encrypt(holdings)
    if not token or not blob: return False,"أضف GITHUB_TOKEN و PORTFOLIO_ENCRYPTION_KEY"
    u=f"https://api.github.com/repos/{repo}/contents/data/portfolio.enc"
    h={"Authorization":f"Bearer {token}","Accept":"application/vnd.github+json","Content-Type":"application/json"}
    old=requests.get(u,headers=h,params={"ref":branch},timeout=15)
    sha=old.json().get("sha") if old.status_code==200 else None
    payload={"message":"portfolio: encrypted personal portfolio update","content":base64.b64encode(blob.encode()).decode(),"branch":branch}
    if sha: payload["sha"]=sha
    r=requests.put(u,headers=h,json=payload,timeout=20)
    return r.status_code in (200,201), (r.json().get("message") or f"HTTP {r.status_code}")

def load_for_daily()->list[dict]:
    rows,ok=github_load()
    return rows if ok else local_load()
