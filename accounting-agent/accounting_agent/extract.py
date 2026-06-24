"""สร้างคำสั่งให้ AI อ่านใบเสร็จ แล้วเรียก provider ดึงข้อมูลเป็น Receipt.

การอ่านไฟล์จริงและเรียก API อยู่ใน providers.py (Gemini หรือ Claude)
"""

from __future__ import annotations

from pathlib import Path
from typing import List

from .config import Config
from .models import Receipt
from .providers import SUPPORTED_SUFFIXES, Provider  # re-export เพื่อความเข้ากันได้

__all__ = ["SUPPORTED_SUFFIXES", "extract_receipts"]


def _instructions(config: Config) -> str:
    category_list = "\n".join(f"- {c}" for c in config.categories)
    return (
        "คุณคือผู้ช่วยนักบัญชีที่อ่านใบเสร็จและใบกำกับภาษีของไทย "
        "ดึงข้อมูลให้ครบและแม่นยำตาม schema ที่กำหนด\n\n"
        "กติกาสำคัญ:\n"
        "1. วันที่ให้แปลงเป็นรูปแบบ YYYY-MM-DD เสมอ "
        "(ระวังปี พ.ศ. ให้ลบ 543 เป็น ค.ศ. เช่น 2569 → 2026, 2568 → 2025)\n"
        "2. ยอดเงินให้เป็นตัวเลขล้วน ไม่มีสัญลักษณ์สกุลเงินหรือคอมมา\n"
        f"3. field 'category' ต้องเลือกจากหมวดเหล่านี้เท่านั้น:\n{category_list}\n"
        f"4. ถ้าใบเสร็จไม่ระบุสกุลเงิน ให้ใช้ {config.default_currency}\n"
        "5. ถ้าอ่านบางช่องไม่ออก ให้ใส่ null และลด confidence ลง "
        "พร้อมอธิบายใน notes — อย่าเดาตัวเลขเอง\n"
        "6. เอกสาร PDF อาจมีใบเสร็จหลายใบ ให้แยกเป็นหลายรายการใน receipts:\n"
        "   - ถ้าใบเดียวกันยาวหลายหน้า (หัวบิล/รายการ/ยอดรวม) ให้รวมเป็น 1 รายการ\n"
        "   - ถ้าเป็นคนละบิล (คนละร้าน/คนละเลขที่/คนละวันที่) ให้แยกเป็นคนละรายการ\n"
        "   - ทุกรายการให้ระบุ page_start และ page_end (เลขหน้าใน PDF เริ่มนับจาก 1) ให้ถูกต้อง"
    )


def extract_receipts(path: Path, config: Config, provider: Provider) -> List[Receipt]:
    """อ่านไฟล์หนึ่งไฟล์ คืนค่าเป็นรายการใบเสร็จ (อาจมีได้หลายใบ)."""
    return provider.extract_receipts(path, _instructions(config))
