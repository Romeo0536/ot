# 🧾 AI Agent นักบัญชี (Local)

ระบบ AI ที่รันบนเครื่องคุณเอง อ่านใบเสร็จจากโฟลเดอร์ ดึงข้อมูลด้วย Claude
จัดไฟล์เข้าโฟลเดอร์อัตโนมัติ และสรุปบัญชีรายเดือนพร้อมส่งสำนักงานบัญชี

> สร้างตามแนวคิด "AI Agent นักบัญชี" — แต่เป็นโค้ดของคุณเอง ข้อมูลอยู่บนเครื่องคุณ

## ระบบทำอะไรได้บ้าง

| Skill | โมดูล | ทำอะไร |
|---|---|---|
| ดึงเอกสาร | `cli.py` (process) | อ่านทุกไฟล์ใน `inbox/` |
| อ่านใบเสร็จด้วย AI | `extract.py` | PDF/รูป → ดึง วันที่/ร้านค้า/ยอดเงิน/ภาษี เป็น JSON |
| จัดโฟลเดอร์ | `organize.py` | ย้ายเข้า `organized/ปี/เดือน/หมวด/` + เปลี่ยนชื่อ |
| สมุดบัญชีรวม | `store.py` | บันทึกทุกใบลง `data/ledger.csv` |
| Monthly Brief | `brief.py` | สรุปรายเดือน + ให้ AI เขียนบรรยาย เป็นไฟล์ `.md` |

## ติดตั้ง

```bash
cd accounting-agent
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env       # แล้วเปิด .env ใส่ ANTHROPIC_API_KEY ของคุณ
```

ขอ API key ได้ที่ https://console.anthropic.com/

## วิธีใช้

**1. ทิ้งใบเสร็จลงโฟลเดอร์** `inbox/` (รองรับ PDF, JPG, PNG, WEBP, GIF)

**2. สั่งประมวลผล**
```bash
python -m accounting_agent.cli process
```
ระบบจะอ่านทุกใบ ดึงข้อมูล ย้ายเข้า `organized/` และบันทึกลง `data/ledger.csv`

**3. สรุปบัญชีรายเดือน**
```bash
python -m accounting_agent.cli brief --month 2026-06
# ไม่อยากเรียก AI เขียนบรรยาย (ประหยัด): เพิ่ม --no-ai
```
ได้ไฟล์ `organized/brief_2026-06.md` พร้อมส่งสำนักงานบัญชี

## ตั้งให้รันอัตโนมัติ (Automation Scheduler)

ให้ระบบทำงานเองทุกวัน/ทุกเดือน ไม่ต้องสั่งเอง:

**macOS / Linux (cron)** — รัน process ทุกวัน 8 โมงเช้า, สรุปทุกวันที่ 1:
```cron
0 8 * * *  cd /path/to/accounting-agent && .venv/bin/python -m accounting_agent.cli process
0 9 1 * *  cd /path/to/accounting-agent && .venv/bin/python -m accounting_agent.cli brief
```

**Windows** — ใช้ Task Scheduler เรียกคำสั่งเดียวกัน

## ปรับแต่ง

แก้ `config.yaml` เพื่อเปลี่ยนหมวดรายจ่าย โฟลเดอร์ หรือสกุลเงินเริ่มต้น

## ความปลอดภัย

- ข้อมูลและใบเสร็จอยู่บนเครื่องคุณ (`.gitignore` กันไม่ให้ commit ขึ้น git)
- ส่งไปที่ Claude API เฉพาะตอนอ่านใบเสร็จเท่านั้น
- ใบเสร็จที่ AI ไม่มั่นใจ (confidence < 0.6) จะถูกทำเครื่องหมาย ⚠️ ให้คนตรวจซ้ำ

## โครงสร้าง

```
accounting-agent/
├── config.yaml              # หมวดหมู่ + พาธ
├── accounting_agent/
│   ├── models.py            # schema ของใบเสร็จ (Pydantic)
│   ├── config.py            # โหลด config
│   ├── extract.py           # อ่านใบเสร็จด้วย Claude
│   ├── organize.py          # จัดโฟลเดอร์
│   ├── store.py             # สมุดบัญชี CSV
│   ├── brief.py             # สรุปรายเดือน
│   └── cli.py               # คำสั่ง process / brief
├── inbox/                   # ทิ้งใบเสร็จที่นี่
├── organized/               # ผลลัพธ์ที่จัดเรียงแล้ว
└── data/ledger.csv          # ข้อมูลรวมทุกใบเสร็จ
```
