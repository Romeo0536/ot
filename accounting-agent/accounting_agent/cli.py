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

import anthropic
from dotenv import load_dotenv

from .brief import generate_brief
from .config import Config
from .extract import SUPPORTED_SUFFIXES, extract_receipt
from .organize import organize_file
from .store import append_receipt


def _client() -> anthropic.Anthropic:
    load_dotenv()
    return anthropic.Anthropic()  # อ่าน ANTHROPIC_API_KEY จาก .env / environment


def cmd_process(config: Config) -> int:
    """อ่านทุกไฟล์ใน inbox -> ดึงข้อมูล -> จัดโฟลเดอร์ -> บันทึก ledger."""
    client = _client()
    files = sorted(
        p for p in config.inbox.iterdir()
        if p.is_file() and p.suffix.lower() in SUPPORTED_SUFFIXES
    )
    if not files:
        print(f"ไม่พบไฟล์ใบเสร็จใน {config.inbox}/ (รองรับ: PDF, JPG, PNG, WEBP, GIF)")
        return 0

    print(f"พบ {len(files)} ไฟล์ กำลังประมวลผล...\n")
    ok = 0
    for path in files:
        try:
            receipt = extract_receipt(path, config, client)
            stored = organize_file(path, receipt, config.organized)
            append_receipt(config.ledger, receipt, path.name, str(stored))
            flag = "  ⚠️ ควรตรวจซ้ำ" if receipt.confidence < 0.6 else ""
            print(
                f"✓ {path.name}\n"
                f"    {receipt.receipt_date} | {receipt.vendor} | "
                f"{receipt.total_amount:,.2f} {receipt.currency} | "
                f"{receipt.category}{flag}\n"
                f"    -> {stored}"
            )
            ok += 1
        except Exception as exc:  # noqa: BLE001 — รายงานต่อ ไม่หยุดทั้งชุด
            print(f"✗ {path.name} : {exc}", file=sys.stderr)

    print(f"\nเสร็จ: {ok}/{len(files)} ไฟล์ | บันทึกลง {config.ledger}")
    return 0 if ok else 1


def cmd_brief(config: Config, month: str, no_ai: bool) -> int:
    """สร้างสรุปบัญชีรายเดือนเป็นไฟล์ Markdown."""
    client = None if no_ai else _client()
    summary, markdown = generate_brief(month, config, client, with_narrative=not no_ai)

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
        "--no-ai", action="store_true", help="สรุปด้วยตัวเลขล้วน ไม่เรียก Claude เขียนบรรยาย"
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
