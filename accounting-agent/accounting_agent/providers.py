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


# --------------------------------------------------------------------------- #
# Groq (Free + Fast)
# --------------------------------------------------------------------------- #
class GroqProvider:
    """ใช้ Groq API (อ่าน GROQ_API_KEY จาก env) — ฟรี ไม่มี rate limit เหมาะสำหรับใบเสร็จ."""

    def __init__(self, model: str):
        import os
        from groq import Groq

        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise ValueError("ต้องตั้ง GROQ_API_KEY ใน .env ก่อน")
        self.client = Groq(api_key=api_key)
        self.model = model

    def extract_receipts(self, path: Path, instructions: str) -> List[Receipt]:
        import base64

        data = base64.standard_b64encode(path.read_bytes()).decode("utf-8")
        mime = mime_for(path)
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": instructions + "\n\n" + _EXTRACT_PROMPT,
                        },
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:{mime};base64,{data}"},
                        },
                    ],
                }
            ],
            max_tokens=2048,
        )
        text = response.choices[0].message.content or ""
        try:
            return ReceiptBatch.model_validate_json(text).receipts
        except Exception:
            return ReceiptBatch.model_validate(json.loads(text)).receipts

    def write_text(self, prompt: str, max_tokens: int) -> str:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=max_tokens,
        )
        return (response.choices[0].message.content or "").strip()


# --------------------------------------------------------------------------- #
# Ollama (Local - Free 100%)
# --------------------------------------------------------------------------- #
# ตัวอักษรขั้นต่ำที่ถือว่า "อ่าน text layer จาก PDF ได้จริง" (ต่ำกว่านี้ = PDF สแกน ต้อง OCR)
_MIN_TEXT_LAYER = 30


class OllamaProvider:
    """ใช้ Ollama (รัน local) — ฟรี 100% ไม่ต้องส่งข้อมูลออกไป.

    อ่านใบเสร็จด้วยวิธี: ดึงข้อความออกจากไฟล์ก่อน แล้วส่งให้ LLM แยกข้อมูล
      - PDF ที่เป็นข้อความ (digital) → ใช้ pypdf อ่าน text layer (ไม่ต้องลงโปรแกรมเสริม)
      - PDF สแกน / รูปภาพ → ใช้ OCR (pytesseract + poppler) เป็น fallback

    env ที่เกี่ยวข้อง (ตั้งใน .env ได้):
      OLLAMA_HOST    เปลี่ยน URL ของ Ollama (ค่าเริ่มต้น http://localhost:11434)
      POPPLER_PATH   โฟลเดอร์ bin ของ poppler (ใช้ตอน OCR ไฟล์ PDF สแกน)
      TESSERACT_CMD  พาธไฟล์ tesseract.exe (ถ้าไม่ได้อยู่ใน PATH)
    """

    def __init__(self, model: str):
        import os

        import requests

        self.base_url = os.getenv("OLLAMA_HOST", "http://localhost:11434").rstrip("/")
        self.model = model
        try:
            requests.get(f"{self.base_url}/api/tags", timeout=3)
        except Exception as e:
            raise ValueError(
                f"ไม่สามารถเชื่อมต่อ Ollama ที่ {self.base_url} — "
                f"ให้รัน 'docker-compose up -d' ก่อน\nError: {e}"
            )

    # --- การดึงข้อความออกจากไฟล์ ------------------------------------------ #
    def _pdf_text_layer(self, path: Path) -> List[str]:
        """อ่านข้อความจาก text layer ของ PDF (คืนค่า list ข้อความรายหน้า)."""
        from pypdf import PdfReader

        reader = PdfReader(str(path))
        return [(page.extract_text() or "") for page in reader.pages]

    def _ocr_image_obj(self, img) -> str:
        """OCR รูปหนึ่งรูป — ลองไทย+อังกฤษก่อน ถ้าไม่มี traineddata ไทยก็ใช้อังกฤษ."""
        import pytesseract

        try:
            return pytesseract.image_to_string(img, lang="tha+eng")
        except pytesseract.TesseractError:
            return pytesseract.image_to_string(img, lang="eng")

    def _ocr_pages(self, path: Path) -> List[str]:
        """แปลงไฟล์เป็นรูปแล้ว OCR (คืนค่า list ข้อความรายหน้า)."""
        import os

        import pytesseract

        tess_cmd = os.getenv("TESSERACT_CMD")
        if tess_cmd:
            pytesseract.pytesseract.tesseract_cmd = tess_cmd

        if path.suffix.lower() == ".pdf":
            from pdf2image import convert_from_path

            poppler_path = os.getenv("POPPLER_PATH") or None
            images = convert_from_path(str(path), poppler_path=poppler_path)
        else:
            from PIL import Image

            images = [Image.open(path)]
        return [self._ocr_image_obj(img) for img in images]

    def _document_text(self, path: Path) -> str:
        """ดึงข้อความจากไฟล์ พร้อมคั่นรายหน้าไว้ให้ LLM อ้างเลขหน้าได้."""
        if path.suffix.lower() == ".pdf":
            pages = self._pdf_text_layer(path)
            if sum(len(p.strip()) for p in pages) < _MIN_TEXT_LAYER:
                pages = self._ocr_pages(path)  # PDF สแกน → OCR
        else:
            pages = self._ocr_pages(path)

        return "\n\n".join(
            f"=== หน้า {i} ===\n{text.strip()}" for i, text in enumerate(pages, 1)
        )

    # --- เรียก Ollama ----------------------------------------------------- #
    def _chat(self, prompt: str, fmt: object | None = None) -> str:
        import requests

        payload: dict = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "options": {"temperature": 0},
        }
        if fmt is not None:
            payload["format"] = fmt  # โครง JSON บังคับ output (Ollama structured output)
        response = requests.post(f"{self.base_url}/api/chat", json=payload, timeout=600)
        response.raise_for_status()
        return response.json().get("message", {}).get("content", "") or ""

    def extract_receipts(self, path: Path, instructions: str) -> List[Receipt]:
        doc_text = self._document_text(path)
        if not doc_text.strip():
            raise ValueError(
                "อ่านข้อความจากไฟล์ไม่ได้ — ถ้าเป็น PDF สแกน/รูป ต้องติดตั้ง "
                "Tesseract + poppler และตั้ง POPPLER_PATH/TESSERACT_CMD ใน .env"
            )
        prompt = f"{instructions}\n\n{_EXTRACT_PROMPT}\n\nเนื้อหาเอกสาร:\n{doc_text}"
        text = self._chat(prompt, fmt=ReceiptBatch.model_json_schema())
        try:
            return ReceiptBatch.model_validate_json(text).receipts
        except Exception:
            return ReceiptBatch.model_validate(json.loads(text)).receipts

    def write_text(self, prompt: str, max_tokens: int) -> str:
        return self._chat(prompt).strip()


def get_provider(name: str, model: str) -> Provider:
    name = name.lower()
    if name == "gemini":
        return GeminiProvider(model)
    if name == "claude":
        return ClaudeProvider(model)
    if name == "groq":
        return GroqProvider(model)
    if name == "ollama":
        return OllamaProvider(model)
    raise ValueError(f"provider ไม่รองรับ: {name} (เลือก 'gemini', 'claude', 'groq', หรือ 'ollama')")
