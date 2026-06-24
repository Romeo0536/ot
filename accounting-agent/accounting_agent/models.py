"""Schema ของข้อมูลที่ดึงจากใบเสร็จ — ใช้กับ structured output ของ Claude."""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class LineItem(BaseModel):
    description: str = Field(description="ชื่อรายการสินค้า/บริการ")
    amount: float = Field(description="ราคารวมของรายการนี้")


class Receipt(BaseModel):
    """ข้อมูลหลักที่ดึงจากใบเสร็จ/ใบกำกับภาษีหนึ่งใบ."""

    vendor: str = Field(description="ชื่อร้านค้า/ผู้ขาย ตามที่ปรากฏบนใบเสร็จ")
    receipt_date: Optional[str] = Field(
        default=None,
        description="วันที่บนใบเสร็จ รูปแบบ YYYY-MM-DD; ถ้าไม่พบให้เป็น null",
    )
    total_amount: float = Field(description="ยอดเงินรวมทั้งสิ้นที่ต้องจ่าย")
    tax_amount: Optional[float] = Field(
        default=None, description="ยอดภาษีมูลค่าเพิ่ม (VAT) ถ้ามี"
    )
    tax_id: Optional[str] = Field(
        default=None, description="เลขประจำตัวผู้เสียภาษีของผู้ขาย ถ้ามี (13 หลัก)"
    )
    currency: str = Field(default="THB", description="สกุลเงิน เช่น THB, USD")
    invoice_number: Optional[str] = Field(
        default=None, description="เลขที่ใบเสร็จ/ใบกำกับภาษี ถ้ามี"
    )
    category: str = Field(
        description="หมวดรายจ่าย เลือกจากรายการหมวดที่กำหนดให้เท่านั้น"
    )
    payment_method: Optional[str] = Field(
        default=None, description="วิธีชำระเงิน เช่น เงินสด, บัตรเครดิต, โอน"
    )
    line_items: List[LineItem] = Field(
        default_factory=list, description="รายการสินค้า/บริการในใบเสร็จ ถ้าอ่านได้"
    )
    confidence: float = Field(
        description="ความมั่นใจในการอ่าน 0.0–1.0; ต่ำกว่า 0.6 ควรให้คนตรวจซ้ำ"
    )
    page_start: Optional[int] = Field(
        default=None,
        description="หน้าเริ่มต้นของใบนี้ในไฟล์ PDF เริ่มนับจาก 1 (ใช้เมื่อมีหลายบิลในไฟล์เดียว)",
    )
    page_end: Optional[int] = Field(
        default=None,
        description="หน้าสุดท้ายของใบนี้ในไฟล์ PDF เริ่มนับจาก 1",
    )
    notes: Optional[str] = Field(
        default=None, description="หมายเหตุ เช่น อ่านไม่ชัดตรงไหน หรือใบเสร็จเสียหาย"
    )


class ReceiptBatch(BaseModel):
    """ผลการอ่านหนึ่งไฟล์ — อาจมีใบเสร็จได้หลายใบ (กรณีหลายบิลรวมในไฟล์เดียว)."""

    receipts: List[Receipt] = Field(
        description="ใบเสร็จทุกใบที่พบในเอกสารนี้ (อย่างน้อย 1 ใบ)"
    )
