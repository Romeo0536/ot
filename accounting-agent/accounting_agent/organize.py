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


def plan_destination(source: Path, receipt: Receipt, organized_root: Path) -> Path:
    """คำนวณ path ปลายทาง (ยังไม่ย้ายไฟล์) — organized/<ปี>/<เดือน>/<หมวด>/.

    ชื่อใหม่: YYYY-MM-DD_ร้านค้า_ยอดเงิน.ext
    """
    date = receipt.receipt_date or "0000-00-00"
    year, month = (date.split("-") + ["00", "00"])[:2]

    dest_dir = organized_root / year / month / _safe(receipt.category)
    dest_dir.mkdir(parents=True, exist_ok=True)

    amount = f"{receipt.total_amount:.2f}"
    ext = source.suffix.lower()
    base = f"{date}_{_safe(receipt.vendor)}_{amount}"
    dest = dest_dir / f"{base}{ext}"

    # กันชื่อชนกัน
    counter = 1
    while dest.exists():
        dest = dest_dir / f"{base}_{counter}{ext}"
        counter += 1
    return dest


def plan_multi_destination(
    source: Path, receipts: list[Receipt], organized_root: Path
) -> Path:
    """ปลายทางสำหรับไฟล์ที่มีหลายบิลแต่แยกไฟล์ไม่ได้.

    เก็บไฟล์รวมไว้ที่ organized/<ปี>/<เดือน>/_หลายบิล/ โดยใช้ชื่อไฟล์เดิม
    (อิงปี/เดือนจากบิลใบแรกที่มีวันที่)
    """
    date = next((r.receipt_date for r in receipts if r.receipt_date), "0000-00-00")
    year, month = (date.split("-") + ["00", "00"])[:2]
    dest_dir = organized_root / year / month / "_หลายบิล"
    dest_dir.mkdir(parents=True, exist_ok=True)

    dest = dest_dir / source.name
    counter = 1
    while dest.exists():
        dest = dest_dir / f"{source.stem}_{counter}{source.suffix.lower()}"
        counter += 1
    return dest


def move_to(source: Path, dest: Path) -> Path:
    """ย้ายไฟล์ไปยังปลายทางที่คำนวณไว้."""
    shutil.move(str(source), str(dest))
    return dest


def organize_file(source: Path, receipt: Receipt, organized_root: Path) -> Path:
    """คำนวณปลายทางแล้วย้ายไฟล์ในขั้นตอนเดียว (คืนค่า path ปลายทาง)."""
    return move_to(source, plan_destination(source, receipt, organized_root))
