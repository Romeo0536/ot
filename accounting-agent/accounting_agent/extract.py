"""สร้างคำสั่งให้ AI อ่านใบเสร็จ แล้วเรียก provider ดึงข้อมูลเป็น Receipt.

การอ่านไฟล์จริงและเรียก API อยู่ใน providers.py (Gemini หรือ Claude)
"""

from __future__ import annotations

from pathlib import Path

from .config import Config
from .models import Receipt
from .providers import SUPPORTED_SUFFIXES, Provider  # re-export เพื่อความเข้ากันได้

__all__ = ["SUPPORTED_SUFFIXES", "extract_receipt"]


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


def extract_receipt(path: Path, config: Config, provider: Provider) -> Receipt:
    """อ่านไฟล์ใบเสร็จหนึ่งไฟล์ คืนค่าเป็น Receipt."""
    return provider.extract_receipt(path, _instructions(config))
