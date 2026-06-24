"""อ่านใบเสร็จ (PDF/รูป) แล้วดึงข้อมูลออกมาเป็น Receipt ด้วย Claude.

ใช้ structured output (messages.parse) เพื่อรับประกันว่าผลลัพธ์ตรงตาม schema.
"""

from __future__ import annotations

import base64
from pathlib import Path

import anthropic

from .config import Config
from .models import Receipt

PDF_SUFFIXES = {".pdf"}
IMAGE_MEDIA_TYPES = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".gif": "image/gif",
    ".webp": "image/webp",
}

SUPPORTED_SUFFIXES = PDF_SUFFIXES | set(IMAGE_MEDIA_TYPES)


def _build_document_block(path: Path) -> dict:
    """สร้าง content block ให้เหมาะกับชนิดไฟล์ (PDF หรือรูป)."""
    suffix = path.suffix.lower()
    data = base64.standard_b64encode(path.read_bytes()).decode("utf-8")

    if suffix in PDF_SUFFIXES:
        return {
            "type": "document",
            "source": {
                "type": "base64",
                "media_type": "application/pdf",
                "data": data,
            },
        }
    if suffix in IMAGE_MEDIA_TYPES:
        return {
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": IMAGE_MEDIA_TYPES[suffix],
                "data": data,
            },
        }
    raise ValueError(f"ไม่รองรับไฟล์ชนิดนี้: {path.name}")


def _instructions(config: Config) -> str:
    category_list = "\n".join(f"- {c}" for c in config.categories)
    return (
        "คุณคือผู้ช่วยนักบัญชีที่อ่านใบเสร็จและใบกำกับภาษีของไทย "
        "ดึงข้อมูลให้ครบและแม่นยำตาม schema ที่กำหนด\n\n"
        "กติกาสำคัญ:\n"
        "1. วันที่ให้แปลงเป็นรูปแบบ YYYY-MM-DD เสมอ "
        "(ระวังปี พ.ศ. ให้ลบ 543 เป็น ค.ศ.)\n"
        "2. ยอดเงินให้เป็นตัวเลขล้วน ไม่มีสัญลักษณ์สกุลเงินหรือคอมมา\n"
        f"3. field 'category' ต้องเลือกจากหมวดเหล่านี้เท่านั้น:\n{category_list}\n"
        f"4. ถ้าใบเสร็จไม่ระบุสกุลเงิน ให้ใช้ {config.default_currency}\n"
        "5. ถ้าอ่านบางช่องไม่ออก ให้ใส่ null และลด confidence ลง "
        "พร้อมอธิบายใน notes — อย่าเดาตัวเลขเอง"
    )


def extract_receipt(path: Path, config: Config, client: anthropic.Anthropic) -> Receipt:
    """อ่านไฟล์ใบเสร็จหนึ่งไฟล์ คืนค่าเป็น Receipt."""
    document_block = _build_document_block(path)

    response = client.messages.parse(
        model=config.model,
        max_tokens=4096,
        system=_instructions(config),
        messages=[
            {
                "role": "user",
                "content": [
                    document_block,
                    {
                        "type": "text",
                        "text": "อ่านใบเสร็จนี้แล้วดึงข้อมูลออกมาตาม schema",
                    },
                ],
            }
        ],
        output_format=Receipt,
    )
    return response.parsed_output
