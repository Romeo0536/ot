"""ตัวเชื่อม AI provider — รองรับทั้ง Gemini และ Claude สลับกันได้ผ่าน config.

แต่ละ provider ทำ 2 อย่าง:
  - extract_receipts: อ่านไฟล์ใบเสร็จ (PDF/รูป) คืนค่าเป็นรายการ Receipt (อาจหลายใบ)
  - write_text: ให้ AI เขียนข้อความบรรยาย (ใช้กับ Monthly Brief)

import SDK แบบ lazy — ติดตั้งเฉพาะตัวที่ใช้ก็พอ
"""

from __future__ import annotations

import json
import time
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

    _MAX_RETRIES = 4
    _RETRY_CODES = {"503", "UNAVAILABLE", "429", "RESOURCE_EXHAUSTED"}

    def __init__(self, model: str):
        from google import genai

        self.genai = genai
        self.client = genai.Client()
        self.model = model

    def _generate(self, **kwargs):
        """เรียก generate_content พร้อม retry อัตโนมัติเมื่อ Gemini 503/429."""
        last_exc: Exception = RuntimeError("no attempt")
        for attempt in range(self._MAX_RETRIES):
            try:
                return self.client.models.generate_content(**kwargs)
            except Exception as exc:
                msg = str(exc)
                if any(code in msg for code in self._RETRY_CODES):
                    if attempt < self._MAX_RETRIES - 1:
                        wait = 2 ** attempt  # 1s, 2s, 4s
                        time.sleep(wait)
                        last_exc = exc
                        continue
                raise
        raise last_exc

    def extract_receipts(self, path: Path, instructions: str) -> List[Receipt]:
        from google.genai import types

        response = self._generate(
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
        if isinstance(response.parsed, ReceiptBatch):
            return response.parsed.receipts
        return ReceiptBatch.model_validate(json.loads(response.text)).receipts

    def write_text(self, prompt: str, max_tokens: int) -> str:
        from google.genai import types

        response = self._generate(
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

    มี 2 โหมดอัตโนมัติตามชื่อ model:
      • Vision mode (qwen2.5vl, llava, minicpm-v, llama3.2-vision ฯลฯ)
        - ส่งรูปตรงเข้า Ollama — ไม่ต้องใช้ OCR/Tesseract!
        - PDF: ถ้ามี text layer ใช้ text mode (เร็วกว่า); ถ้าสแกน render เป็นรูป
      • Text mode (mistral, llama3.2, qwen2.5 ฯลฯ)
        - PDF digital → อ่าน text layer ด้วย pypdf (ไม่ต้องลงโปรแกรมเสริม)
        - PDF สแกน/รูป → OCR ด้วย pytesseract + poppler

    env ที่เกี่ยวข้อง (ตั้งใน .env ได้):
      OLLAMA_HOST    เปลี่ยน URL ของ Ollama (ค่าเริ่มต้น http://localhost:11434)
      POPPLER_PATH   โฟลเดอร์ bin ของ poppler (ใช้ตอน OCR/render PDF)
      TESSERACT_CMD  พาธไฟล์ tesseract.exe (ถ้าไม่ได้อยู่ใน PATH)
    """

    # ชื่อ model ที่บ่งบอกว่า support vision (จะเปิด vision mode อัตโนมัติ)
    _VISION_KEYWORDS = ("vl", "vision", "llava", "minicpm-v", "bakllava", "moondream")

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
                f"ให้ติดตั้ง Ollama ที่ https://ollama.com/download "
                f"หรือรัน 'docker-compose up -d'\nError: {e}"
            )

    @property
    def is_vision_model(self) -> bool:
        m = self.model.lower()
        return any(kw in m for kw in self._VISION_KEYWORDS)

    # --- การดึงข้อความออกจากไฟล์ (text mode) ------------------------------ #
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

        for img in self._pdf_or_image_to_pil(path):
            yield self._ocr_image_obj(img)

    def _pdf_or_image_to_pil(self, path: Path):
        """แปลงไฟล์เป็น PIL Image list (ใช้ทั้ง OCR และ vision mode)."""
        if path.suffix.lower() == ".pdf":
            return self._pdf_to_pil(path)
        from PIL import Image

        return [Image.open(path)]

    def _pdf_to_pil(self, path: Path):
        """Render PDF เป็น list ของ PIL Image — ลอง pypdfium2 ก่อน (ไม่ต้องมี poppler)."""
        try:
            import pypdfium2 as pdfium

            pdf = pdfium.PdfDocument(str(path))
            return [pdf[i].render(scale=2.0).to_pil() for i in range(len(pdf))]
        except ImportError:
            pass

        # fallback: pdf2image (ต้องมี poppler ติดตั้งไว้)
        import os

        from pdf2image import convert_from_path

        poppler_path = os.getenv("POPPLER_PATH") or None
        return convert_from_path(str(path), poppler_path=poppler_path)

    def _document_text(self, path: Path) -> str:
        """ดึงข้อความจากไฟล์ พร้อมคั่นรายหน้าไว้ให้ LLM อ้างเลขหน้าได้."""
        if path.suffix.lower() == ".pdf":
            pages = self._pdf_text_layer(path)
            if sum(len(p.strip()) for p in pages) < _MIN_TEXT_LAYER:
                pages = list(self._ocr_pages(path))  # PDF สแกน → OCR
        else:
            pages = list(self._ocr_pages(path))

        return "\n\n".join(
            f"=== หน้า {i} ===\n{text.strip()}" for i, text in enumerate(pages, 1)
        )

    # --- ส่งรูปตรงเข้า Ollama (vision mode) ------------------------------- #
    def _image_to_b64(self, path: Path) -> List[str]:
        """แปลงไฟล์รูปเดียวเป็น base64 (รายการ 1 ตัว — ให้ format ตรงกับ PDF)."""
        import base64

        return [base64.standard_b64encode(path.read_bytes()).decode("utf-8")]

    def _pdf_pages_to_b64(self, path: Path) -> List[str]:
        """แปลง PDF ทุกหน้าเป็นรูป base64 (PNG)."""
        import base64
        import io

        out: List[str] = []
        for img in self._pdf_or_image_to_pil(path):
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            out.append(base64.standard_b64encode(buf.getvalue()).decode("utf-8"))
        return out

    # --- เรียก Ollama ----------------------------------------------------- #
    def _chat(
        self,
        prompt: str,
        fmt: object | None = None,
        images_b64: List[str] | None = None,
    ) -> str:
        import requests

        message: dict = {"role": "user", "content": prompt}
        if images_b64:
            message["images"] = images_b64

        payload: dict = {
            "model": self.model,
            "messages": [message],
            "stream": False,
            "options": {"temperature": 0},
        }
        if fmt is not None:
            payload["format"] = fmt  # โครง JSON บังคับ output (Ollama structured output)
        response = requests.post(f"{self.base_url}/api/chat", json=payload, timeout=600)
        response.raise_for_status()
        return response.json().get("message", {}).get("content", "") or ""

    def _parse(self, text: str) -> List[Receipt]:
        try:
            return ReceiptBatch.model_validate_json(text).receipts
        except Exception:
            return ReceiptBatch.model_validate(json.loads(text)).receipts

    def extract_receipts(self, path: Path, instructions: str) -> List[Receipt]:
        # Vision mode — ส่งรูปตรง ไม่ต้องผ่าน OCR
        if self.is_vision_model:
            if path.suffix.lower() == ".pdf":
                # PDF digital → text mode เร็วกว่า; PDF สแกน → render เป็นรูป
                text_pages = self._pdf_text_layer(path)
                if sum(len(p.strip()) for p in text_pages) >= _MIN_TEXT_LAYER:
                    return self._extract_text_mode(path, instructions)
                images_b64 = self._pdf_pages_to_b64(path)
            else:
                images_b64 = self._image_to_b64(path)

            prompt = f"{instructions}\n\n{_EXTRACT_PROMPT}"
            text = self._chat(
                prompt, fmt=ReceiptBatch.model_json_schema(), images_b64=images_b64
            )
            return self._parse(text)

        # Text mode — OCR แล้วส่งข้อความ (model ที่ไม่รองรับ vision)
        return self._extract_text_mode(path, instructions)

    def _extract_text_mode(self, path: Path, instructions: str) -> List[Receipt]:
        doc_text = self._document_text(path)
        if not doc_text.strip():
            raise ValueError(
                "อ่านข้อความจากไฟล์ไม่ได้ — ถ้าเป็น PDF สแกน/รูป ลองใช้ vision model "
                "(เช่น qwen2.5vl, llava) หรือติดตั้ง Tesseract + poppler"
            )
        prompt = f"{instructions}\n\n{_EXTRACT_PROMPT}\n\nเนื้อหาเอกสาร:\n{doc_text}"
        text = self._chat(prompt, fmt=ReceiptBatch.model_json_schema())
        return self._parse(text)

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
