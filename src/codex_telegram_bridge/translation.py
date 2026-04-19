from __future__ import annotations

import re


HANGUL_RE = re.compile(r"[가-힣]")


def contains_hangul(text: str) -> bool:
    return bool(HANGUL_RE.search(text or ""))


def translate_to_english(text: str) -> str:
    if not text.strip():
        return text

    try:
        from deep_translator import GoogleTranslator

        translated = GoogleTranslator(source="auto", target="en").translate(text)
        return translated or text
    except Exception:
        return text
