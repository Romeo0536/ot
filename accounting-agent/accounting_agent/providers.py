"""ตัวเชื่อม AI provider — รองรับทั้ง Gemini และ Claude สลับกันได้ผ่าน config.

แต่ละ provider ทำ 2 อย่าง:
  - extract_receipts: อ่านไฟล์ใบเสร็จ (PDF/รูป) คืนค่าเป็นรายการ Receipt (อาจหลายใบ)
  - write_text: ให้ AI เขียนข้อความบรรยาย (ใช้กับ Monthly Brief)

import SDK แบบ lazy — ติดตั้งเฉพาะตัวที่ใช้ก็พอ
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import List, Protocol

from .models import Receipt, ReceiptBatch

# ชนิดไฟล์ที่รองรับ -> MIME type (ใช้ได้ทั้ง Gemini และ Claude)
MIME_TYPES = {
    ".pdf": "application/pdf",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".gif": "image/gif",
    ".webp": "image/webp",
}
SUPPORTED_SUFFIXES = set(MIME_TYPES)

_EXTRACT_PROMPT = (
    "อ่านเอกสารนี้แล้วดึงข้อมูลใบเสร็จทุกใบออกมาตาม schema "
    "(เอกสารอาจมีใบเสร็จได้หลายใบ)"
)


def mime_for(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix not in MIME_TYPES:
        raise ValueError(f"ไม่รองรับไฟล์ชนิดนี้: {path.name}")
    return MIME_TYPES[suffix]


class Provider(Protocol):
    def extract_receipts(self, path: Path, instructions: str) -> List[Receipt]: ...
    def write_text(self, prompt: str, max_tokens: int) -> str: ...


# --------------------------------------------------------------------------- #
# Gemini
# --------------------------------------------------------------------------- #
class GeminiProvider:
    """ใช้ Google Gemini (อ่าน GEMINI_API_KEY หรือ GOOGLE_API_KEY จาก env)."""

    def __init__(self, model: str):
        from google import genai

        self.genai = genai
        self.client = genai.Client()
        self.model = model

    def extract_receipts(self, path: Path, instructions: str) -> List[Receipt]:
        from google.genai import types

        response = self.client.models.generate_content(
            model=self.model,
            contents=[
                types.Part.from_bytes(
                    data=path.read_bytes(), mime_type=mime_for(path)
                ),
                _EXTRACT_PROMPT,
            ],
            config=types.GenerateContentConfig(
                system_instruction=instructions,
                response_mime_type="application/json",
                response_schema=ReceiptBatch,
            ),
        )
        # response.parsed คือ ReceiptBatch; เผื่อ parse ไม่สำเร็จก็ fallback อ่าน text
        if isinstance(response.parsed, ReceiptBatch):
            return response.parsed.receipts
        return ReceiptBatch.model_validate(json.loads(response.text)).receipts

    def write_text(self, prompt: str, max_tokens: int) -> str:
        from google.genai import types

        response = self.client.models.generate_content(
            model=self.model,
            contents=prompt,
            config=types.GenerateContentConfig(max_output_tokens=max_tokens),
        )
        return (response.text or "").strip()


# --------------------------------------------------------------------------- #
# Claude (Anthropic)
# --------------------------------------------------------------------------- #
class ClaudeProvider:
    """ใช้ Anthropic Claude (อ่าน ANTHROPIC_API_KEY จาก env)."""

    def __init__(self, model: str):
        import anthropic

        self.client = anthropic.Anthropic()
        self.model = model

    def _document_block(self, path: Path) -> dict:
        import base64

        data = base64.standard_b64encode(path.read_bytes()).decode("utf-8")
        mime = mime_for(path)
        block_type = "document" if mime == "application/pdf" else "image"
        return {
            "type": block_type,
            "source": {"type": "base64", "media_type": mime, "data": data},
        }

    def extract_receipts(self, path: Path, instructions: str) -> List[Receipt]:
        response = self.client.messages.parse(
            model=self.model,
            max_tokens=8096,
            system=instructions,
            messages=[
                {
                    "role": "user",
                    "content": [
                        self._document_block(path),
                        {"type": "text", "text": _EXTRACT_PROMPT},
                    ],
                }
            ],
            output_format=ReceiptBatch,
        )
        return response.parsed_output.receipts

    def write_text(self, prompt: str, max_tokens: int) -> str:
        response = self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        return "".join(b.text for b in response.content if b.type == "text").strip()


def get_provider(name: str, model: str) -> Provider:
    name = name.lower()
    if name == "gemini":
        return GeminiProvider(model)
    if name == "claude":
        return ClaudeProvider(model)
    raise ValueError(f"provider ไม่รองรับ: {name} (เลือก 'gemini' หรือ 'claude')")
