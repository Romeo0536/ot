"""สร้าง Monthly Brief — สรุปบัญชีรายเดือน พร้อมส่งสำนักงานบัญชี."""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Dict, List

from .config import Config
from .providers import Provider
from .store import read_ledger


def _to_float(value: str) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def summarize_month(ledger_path: Path, month: str) -> dict:
    """รวมตัวเลขของเดือนที่ระบุ (month = 'YYYY-MM')."""
    rows = [r for r in read_ledger(ledger_path) if (r.get("receipt_date") or "").startswith(month)]

    by_category: Dict[str, float] = defaultdict(float)
    total = 0.0
    total_tax = 0.0
    low_confidence: List[dict] = []

    for r in rows:
        amount = _to_float(r.get("total_amount", "0"))
        by_category[r.get("category", "อื่นๆ")] += amount
        total += amount
        total_tax += _to_float(r.get("tax_amount", "0"))
        if _to_float(r.get("confidence", "1")) < 0.6:
            low_confidence.append(r)

    return {
        "month": month,
        "count": len(rows),
        "total": total,
        "total_tax": total_tax,
        "by_category": dict(sorted(by_category.items(), key=lambda x: -x[1])),
        "low_confidence": low_confidence,
        "rows": rows,
    }


def _render_markdown(summary: dict, narrative: str | None) -> str:
    lines = [
        f"# สรุปบัญชีประจำเดือน {summary['month']}",
        "",
        f"- จำนวนใบเสร็จ: **{summary['count']}** ใบ",
        f"- ยอดรวมทั้งสิ้น: **{summary['total']:,.2f}**",
        f"- ภาษีมูลค่าเพิ่มรวม: **{summary['total_tax']:,.2f}**",
        "",
        "## แยกตามหมวดรายจ่าย",
        "",
        "| หมวด | ยอดรวม | สัดส่วน |",
        "| --- | ---: | ---: |",
    ]
    total = summary["total"] or 1.0
    for category, amount in summary["by_category"].items():
        pct = amount / total * 100
        lines.append(f"| {category} | {amount:,.2f} | {pct:.1f}% |")

    if summary["low_confidence"]:
        lines += ["", "## ⚠️ ใบเสร็จที่ควรตรวจซ้ำ (ความมั่นใจต่ำ)", ""]
        for r in summary["low_confidence"]:
            lines.append(
                f"- {r.get('receipt_date','?')} {r.get('vendor','?')} "
                f"({r.get('total_amount','?')}) — {r.get('source_file','')}"
            )

    if narrative:
        lines += ["", "## สรุปสำหรับสำนักงานบัญชี", "", narrative]

    return "\n".join(lines) + "\n"


def _narrative(summary: dict, provider: Provider) -> str:
    """ให้ AI เขียนสรุปสั้นๆ เป็นภาษาคนสำหรับส่งสำนักงานบัญชี."""
    facts = "\n".join(
        f"- {cat}: {amt:,.2f}" for cat, amt in summary["by_category"].items()
    )
    prompt = (
        "เขียนสรุปบัญชีรายเดือนสั้นๆ 3-5 ประโยค เป็นภาษาไทย "
        "สำหรับส่งให้สำนักงานบัญชี น้ำเสียงเป็นทางการแต่อ่านง่าย "
        "ชี้ประเด็นที่น่าสนใจ เช่น หมวดที่ใช้จ่ายเยอะ หรือสิ่งที่ควรระวัง\n\n"
        f"เดือน: {summary['month']}\n"
        f"จำนวนใบเสร็จ: {summary['count']}\n"
        f"ยอดรวม: {summary['total']:,.2f}\n"
        f"ภาษีรวม: {summary['total_tax']:,.2f}\n"
        f"แยกตามหมวด:\n{facts}"
    )
    return provider.write_text(prompt, max_tokens=1024)


def generate_brief(
    month: str,
    config: Config,
    provider: Provider | None = None,
    with_narrative: bool = True,
) -> tuple[dict, str]:
    """สร้าง brief ของเดือน คืนค่า (summary, markdown)."""
    summary = summarize_month(config.ledger, month)
    narrative = None
    if with_narrative and provider is not None and summary["count"] > 0:
        narrative = _narrative(summary, provider)
    return summary, _render_markdown(summary, narrative)
