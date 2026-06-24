"""จัดไฟล์ใบเสร็จเข้าโฟลเดอร์ตาม ปี/เดือน/หมวด และตั้งชื่อไฟล์ใหม่ให้อ่านง่าย."""

from __future__ import annotations

import re
import shutil
from pathlib import Path

from .models import Receipt


def _safe(text: str, max_len: int = 40) -> str:
    """ทำชื่อให้ปลอดภัยสำหรับใช้เป็นชื่อไฟล์/โฟลเดอร์."""
    text = re.sub(r"[^\w฀-๿.-]+", "_", text.strip())
    text = text.strip("_.")
    return (text or "unknown")[:max_len]


def organize_file(source: Path, receipt: Receipt, organized_root: Path) -> Path:
    """ย้ายไฟล์เข้า organized/<ปี>/<เดือน>/<หมวด>/ พร้อมเปลี่ยนชื่อ.

    ชื่อใหม่: YYYY-MM-DD_ร้านค้า_ยอดเงิน.ext
    คืนค่า path ปลายทาง
    """
    date = receipt.receipt_date or "0000-00-00"
    year, month = (date.split("-") + ["00", "00"])[:2]

    dest_dir = organized_root / year / month / _safe(receipt.category)
    dest_dir.mkdir(parents=True, exist_ok=True)

    amount = f"{receipt.total_amount:.2f}"
    filename = f"{date}_{_safe(receipt.vendor)}_{amount}{source.suffix.lower()}"
    dest = dest_dir / filename

    # กันชื่อชนกัน
    counter = 1
    while dest.exists():
        dest = dest_dir / f"{date}_{_safe(receipt.vendor)}_{amount}_{counter}{source.suffix.lower()}"
        counter += 1

    shutil.move(str(source), str(dest))
    return dest
