"""บันทึกข้อมูลใบเสร็จลงสมุดบัญชีรวม (ledger CSV) และอ่านกลับมาใช้."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Dict, List

from .models import Receipt

FIELDNAMES = [
    "receipt_date",
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


def append_receipt(
    ledger_path: Path,
    receipt: Receipt,
    source_file: str,
    stored_path: str,
) -> None:
    """เพิ่มหนึ่งบรรทัดลง ledger; สร้างไฟล์พร้อม header ถ้ายังไม่มี."""
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    is_new = not ledger_path.exists()

    with ledger_path.open("a", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        if is_new:
            writer.writeheader()
        writer.writerow(
            {
                "receipt_date": receipt.receipt_date or "",
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
