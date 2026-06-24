"""จุดเริ่มต้นใช้งาน — สั่งงานผ่าน command line.

ตัวอย่าง:
    python -m accounting_agent.cli process
    python -m accounting_agent.cli brief --month 2026-06
"""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path
from typing import List, Tuple

from dotenv import load_dotenv

from .brief import generate_brief
from .config import Config
from .extract import SUPPORTED_SUFFIXES, extract_receipts
from .models import Receipt
from .organize import move_to, plan_destination, plan_multi_destination
from .pdfsplit import page_count, pypdf_available, split_pages
from .providers import Provider, get_provider
from .store import append_receipt, ledger_writable


def _provider(config: Config) -> Provider:
    load_dotenv()  # โหลด API key จาก .env
    return get_provider(config.provider, config.model)


def _can_split(path: Path, receipts: List[Receipt]) -> bool:
    """แยกไฟล์ PDF ตามบิลได้ไหม (ต้องเป็น PDF หลายบิล + มี pypdf + เลขหน้าครบถูกต้อง)."""
    if path.suffix.lower() != ".pdf" or len(receipts) < 2 or not pypdf_available():
        return False
    try:
        total = page_count(path)
    except Exception:
        return False
    for r in receipts:
        if not r.page_start or not r.page_end:
            return False
        if not (1 <= r.page_start <= r.page_end <= total):
            return False
    return True


def _store_file(
    path: Path, receipts: List[Receipt], config: Config
) -> List[Tuple[Receipt, Path]]:
    """ลง ledger + จัดไฟล์ ให้ใบเสร็จทั้งหมดของไฟล์นี้. คืนค่า (receipt, ปลายทาง) แต่ละใบ."""
    results: List[Tuple[Receipt, Path]] = []

    # หนึ่งบิล — ย้ายไฟล์ทั้งไฟล์ตามปกติ
    if len(receipts) == 1:
        r = receipts[0]
        dest = plan_destination(path, r, config.organized)
        append_receipt(config.ledger, r, path.name, str(dest))
        move_to(path, dest)
        return [(r, dest)]

    # หลายบิล + แยก PDF ได้ — ตัดเป็นไฟล์ละบิล แล้วลบไฟล์รวมต้นฉบับ
    if _can_split(path, receipts):
        for r in receipts:
            dest = plan_destination(path, r, config.organized)
            split_pages(path, r.page_start, r.page_end, dest)  # type: ignore[arg-type]
            append_receipt(config.ledger, r, path.name, str(dest))
            results.append((r, dest))
        path.unlink()  # ไฟล์รวมถูกแยกครบแล้ว
        return results

    # หลายบิลแต่แยกไฟล์ไม่ได้ — เก็บไฟล์รวมไว้ที่เดียว ลง ledger ทุกบิล (ระบุเลขหน้าใน notes)
    dest = plan_multi_destination(path, receipts, config.organized)
    for r in receipts:
        if r.page_start and r.page_end:
            tag = f"[หน้า {r.page_start}-{r.page_end}]"
            r.notes = f"{tag} {r.notes}" if r.notes else tag
        append_receipt(config.ledger, r, path.name, str(dest))
        results.append((r, dest))
    move_to(path, dest)
    return results


def _print_receipt(receipt: Receipt, stored: Path) -> None:
    flag = "  ⚠️ ควรตรวจซ้ำ" if receipt.confidence < 0.6 else ""
    print(
        f"    {receipt.receipt_date} | {receipt.vendor} | "
        f"{receipt.total_amount:,.2f} {receipt.currency} | {receipt.category}{flag}\n"
        f"    -> {stored}"
    )


def cmd_process(config: Config) -> int:
    """อ่านทุกไฟล์ใน inbox -> ดึงข้อมูล -> จัดโฟลเดอร์ -> บันทึก ledger."""
    # เช็คก่อนว่า ledger เขียนได้ไหม จะได้ไม่เสีย API call ฟรีถ้าไฟล์ถูกล็อก
    if not ledger_writable(config.ledger):
        print(
            f"⚠️  เขียน {config.ledger} ไม่ได้ — น่าจะเปิดค้างไว้ใน Excel\n"
            "    ปิดไฟล์นั้นก่อน แล้วรัน process ใหม่อีกครั้ง"
        )
        return 1

    provider = _provider(config)
    files = sorted(
        p for p in config.inbox.iterdir()
        if p.is_file() and p.suffix.lower() in SUPPORTED_SUFFIXES
    )
    if not files:
        print(f"ไม่พบไฟล์ใบเสร็จใน {config.inbox}/ (รองรับ: PDF, JPG, PNG, WEBP, GIF)")
        return 0

    print(f"พบ {len(files)} ไฟล์ | provider: {config.provider} ({config.model})\n")
    ok_files = 0
    total_bills = 0
    for path in files:
        try:
            receipts = extract_receipts(path, config, provider)
            if not receipts:
                print(f"✗ {path.name} : อ่านไม่พบใบเสร็จในไฟล์", file=sys.stderr)
                continue
            results = _store_file(path, receipts, config)
            header = f"✓ {path.name}"
            if len(results) > 1:
                header += f"  (พบ {len(results)} บิลในไฟล์เดียว)"
            print(header)
            for receipt, stored in results:
                _print_receipt(receipt, stored)
            ok_files += 1
            total_bills += len(results)
        except Exception as exc:  # noqa: BLE001 — รายงานต่อ ไม่หยุดทั้งชุด
            print(f"✗ {path.name} : {exc}", file=sys.stderr)

    print(
        f"\nเสร็จ: {ok_files}/{len(files)} ไฟล์ | รวม {total_bills} บิล | "
        f"บันทึกลง {config.ledger}"
    )
    return 0 if ok_files else 1


def cmd_brief(config: Config, month: str, no_ai: bool) -> int:
    """สร้างสรุปบัญชีรายเดือนเป็นไฟล์ Markdown."""
    provider = None if no_ai else _provider(config)
    summary, markdown = generate_brief(month, config, provider, with_narrative=not no_ai)

    out = config.organized / f"brief_{month}.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(markdown, encoding="utf-8")

    print(markdown)
    print(f"\nบันทึกสรุปไว้ที่: {out}")
    if summary["count"] == 0:
        print(f"(ยังไม่มีข้อมูลของเดือน {month} ใน ledger)")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="accounting-agent",
        description="AI Agent นักบัญชี: อ่านใบเสร็จ จัดโฟลเดอร์ สรุปบัญชี",
    )
    parser.add_argument(
        "--config", default="config.yaml", help="พาธไฟล์ config (ค่าเริ่มต้น: config.yaml)"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("process", help="อ่านใบเสร็จใน inbox แล้วจัดเข้าระบบ")

    p_brief = sub.add_parser("brief", help="สร้างสรุปบัญชีรายเดือน")
    p_brief.add_argument(
        "--month",
        default=date.today().strftime("%Y-%m"),
        help="เดือนที่ต้องการ รูปแบบ YYYY-MM (ค่าเริ่มต้น: เดือนปัจจุบัน)",
    )
    p_brief.add_argument(
        "--no-ai", action="store_true", help="สรุปด้วยตัวเลขล้วน ไม่เรียก AI เขียนบรรยาย"
    )

    args = parser.parse_args(argv)
    config = Config.load(args.config)

    if args.command == "process":
        return cmd_process(config)
    if args.command == "brief":
        return cmd_brief(config, args.month, args.no_ai)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
