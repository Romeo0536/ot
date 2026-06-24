"""แยกไฟล์ PDF ออกเป็นช่วงหน้า — ใช้ตอนมีหลายบิลในไฟล์เดียว.

ต้องติดตั้ง pypdf ก่อนถึงจะแยกได้ (ไม่มีก็ยังใช้ระบบได้ แค่ไม่แยกไฟล์)
"""

from __future__ import annotations

from pathlib import Path


def pypdf_available() -> bool:
    try:
        import pypdf  # noqa: F401

        return True
    except ImportError:
        return False


def page_count(path: Path) -> int:
    from pypdf import PdfReader

    return len(PdfReader(str(path)).pages)


def split_pages(source: Path, page_start: int, page_end: int, dest: Path) -> Path:
    """คัดเฉพาะหน้า page_start..page_end (เริ่มนับ 1) เขียนเป็นไฟล์ใหม่ที่ dest."""
    from pypdf import PdfReader, PdfWriter

    reader = PdfReader(str(source))
    writer = PdfWriter()
    for i in range(page_start - 1, page_end):
        writer.add_page(reader.pages[i])
    with dest.open("wb") as f:
        writer.write(f)
    return dest
