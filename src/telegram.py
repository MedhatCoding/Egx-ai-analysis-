"""إرسال الرسائل على تلجرام: تقسيم الرسالة الطويلة، وإعادة المحاولة كنص عادي لو فشل تنسيق HTML."""
from __future__ import annotations

import re
import time

import requests

API = "https://api.telegram.org/bot{token}/sendMessage"
LIMIT = 3900  # الحد الرسمي 4096، وبنسيب هامش أمان


def split_message(text: str, limit: int = LIMIT) -> list[str]:
    """يقسّم على حدود الفقرات (سطر فاضي) بحيث كل جزء يبقى HTML سليم بذاته."""
    chunks: list[str] = []
    cur = ""
    for para in text.split("\n\n"):
        # فقرة أطول من الحد: نقسمها على الأسطر
        if len(para) > limit:
            if cur:
                chunks.append(cur)
                cur = ""
            piece = ""
            for line in para.split("\n"):
                if piece and len(piece) + 1 + len(line) > limit:
                    chunks.append(piece)
                    piece = line[:limit]
                else:
                    piece = (piece + "\n" + line) if piece else line[:limit]
            if piece:
                chunks.append(piece)
            continue
        candidate = para if not cur else cur + "\n\n" + para
        if len(candidate) > limit:
            chunks.append(cur)
            cur = para
        else:
            cur = candidate
    if cur:
        chunks.append(cur)
    return [c for c in chunks if c.strip()]


def strip_tags(text: str) -> str:
    return re.sub(r"</?[a-zA-Z][^>]*>", "", text).replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&")


def send_message(token: str, chat_id: str, text: str, post=requests.post, pause: float = 0.6) -> int:
    """يرجع عدد الرسائل المرسلة. يرفع RuntimeError عند الفشل (بدون كتابة التوكن في الرسالة)."""
    sent = 0
    for chunk in split_message(text):
        payload = {"chat_id": chat_id, "text": chunk, "parse_mode": "HTML", "disable_web_page_preview": True}
        r = post(API.format(token=token), json=payload, timeout=30)
        if r.status_code == 400 and "parse entities" in (r.text or "").lower():
            payload = {"chat_id": chat_id, "text": strip_tags(chunk), "disable_web_page_preview": True}
            r = post(API.format(token=token), json=payload, timeout=30)
        if r.status_code != 200:
            raise RuntimeError(f"Telegram HTTP {r.status_code}: {(r.text or '')[:200]}")
        sent += 1
        if pause:
            time.sleep(pause)
    return sent
