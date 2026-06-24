"""บันทึกข้อมูลใบเสร็จลงสมุดบัญชีรวม (ledger CSV) และอ่านกลับมาใช้."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Dict, List

from .models import Receipt

FIELDNAMES = [
    "receipt_date",
    "date",
    "vendor",
    "category",
    "total_amount",
    "tax_amount",
    "currency",
    "tax_id",
    "invoice_number",
    "payment_method",
    "confidence",
    "source_file",
    "stored_path",
    "notes",
]

BOM = "\ufeff"  # ช่วยให้ Excel อ่านภาษาไทยถูกต้อง


def thai_date(receipt_date: str | None) -> str:
    """แปลงวันที่ ค.ศ. (YYYY-MM-DD) เป็นรูปแบบ DDMMYY ปี พ.ศ.

    เช่น 2026-04-01 -> '010469' (วัน 01 / เดือน 04 / พ.ศ. 2569 เอาสองหลักท้าย)
    คืนค่าว่างถ้าวันที่ไม่ถูกรูปแบบ
    """
    if not receipt_date:
        return ""
    parts = receipt_date.split("-")
    if len(parts) != 3:
        return ""
    try:
        year, month, day = int(parts[0]), int(parts[1]), int(parts[2])
    except ValueError:
        return ""
    buddhist_yy = (year + 543) % 100
    return f"{day:02d}{month:02d}{buddhist_yy:02d}"


def ledger_writable(ledger_path: Path) -> bool:
    """เช็คว่าเขียน ledger ได้ไหม (False ถ้าถูกล็อก เช่น เปิดค้างใน Excel)."""
    if not ledger_path.exists():
        return True  # ยังไม่มีไฟล์ เดี๋ยวสร้างใหม่ได้
    try:
        with ledger_path.open("a", encoding="utf-8"):
            return True
    except PermissionError:
        return False


def append_receipt(
    ledger_path: Path,
    receipt: Receipt,
    source_file: str,
    stored_path: str,
) -> None:
    """เพิ่มหนึ่งบรรทัดลง ledger; สร้างไฟล์พร้อม header ถ้ายังไม่มี."""
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    is_new = not ledger_path.exists()

    # ใช้ utf-8 ธรรมดา แล้วเขียน BOM เองตอนสร้างไฟล์ใหม่เท่านั้น
    # (ถ้าใช้ utf-8-sig กับโหมด append มันจะแทรก BOM กลางไฟล์ทุกครั้งที่ append)
    with ledger_path.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        if is_new:
            f.write(BOM)
            writer.writeheader()
        writer.writerow(
            {
                "receipt_date": receipt.receipt_date or "",
                "date": thai_date(receipt.receipt_date),
                "vendor": receipt.vendor,
                "category": receipt.category,
                "total_amount": receipt.total_amount,
                "tax_amount": receipt.tax_amount if receipt.tax_amount is not None else "",
                "currency": receipt.currency,
                "tax_id": receipt.tax_id or "",
                "invoice_number": receipt.invoice_number or "",
                "payment_method": receipt.payment_method or "",
                "confidence": receipt.confidence,
                "source_file": source_file,
                "stored_path": stored_path,
                "notes": receipt.notes or "",
            }
        )


def read_ledger(ledger_path: Path) -> List[Dict[str, str]]:
    """อ่าน ledger ทั้งหมดเป็น list ของ dict."""
    if not ledger_path.exists():
        return []
    with ledger_path.open(newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))
