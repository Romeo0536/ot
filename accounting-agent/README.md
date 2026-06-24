# 🧾 AI Agent นักบัญชี

ระบบ AI อ่านใบเสร็จ/บิล (PDF หรือรูป) แล้วส่งออกเป็น Excel อัตโนมัติ

> ใช้ Google Gemini (ฟรี) — ข้อมูลส่งไปที่ Gemini เฉพาะตอนอ่านใบเสร็จ

## วิธีใช้ (Web Interface — แนะนำ)

**Windows — ดับเบิลคลิก `run_app.bat`** แล้วเปิดเบราว์เซอร์ที่ `http://localhost:8501`

| ขั้นตอน | รายละเอียด |
|---|---|
| 1. ขอ Gemini API Key | ฟรีที่ https://aistudio.google.com/apikey |
| 2. วาง API Key | ในช่องซ้ายมือของหน้าเว็บ |
| 3. อัปโหลดไฟล์ | PDF / JPG / PNG (ลากวางได้หลายไฟล์พร้อมกัน) |
| 4. กด "เริ่มอ่าน" | AI อ่านและดึงข้อมูลทุกใบเสร็จ |
| 5. ดาวน์โหลด | กด "ดาวน์โหลด Excel (.xlsx)" |

## ระบบทำอะไรได้บ้าง

| Skill | โมดูล | ทำอะไร |
|---|---|---|
| Web Interface | `app.py` | อัปโหลด → AI อ่าน → ดาวน์โหลด Excel |
| ดึงเอกสาร | `cli.py` (process) | อ่านทุกไฟล์ใน `inbox/` (command line) |
| อ่านใบเสร็จด้วย AI | `extract.py` | PDF/รูป → ดึง วันที่/ร้านค้า/ยอดเงิน/ภาษี |
| จัดโฟลเดอร์ | `organize.py` | ย้ายเข้า `organized/ปี/เดือน/หมวด/` |
| สมุดบัญชีรวม | `store.py` | บันทึกทุกใบลง `data/ledger.csv` |
| Monthly Brief | `brief.py` | สรุปรายเดือน + ให้ AI เขียนบรรยาย |

## ติดตั้ง (ครั้งแรก)

```bash
cd accounting-agent
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

หรือบน Windows แค่ดับเบิลคลิก `run_app.bat` — มันจะติดตั้งและเปิดเว็บให้เอง

## เลือก AI provider (แนะนำ: Ollama ฟรี 100%)

ค่าเริ่มต้นคือ **Gemini** — แก้ได้ใน `config.yaml`:

```yaml
provider: ollama                  # หรือ gemini, groq, claude
model: mistral                    # ollama: mistral / neural-chat / orca-mini
                                  # gemini: gemini-2.5-flash / gemini-2.5-pro
                                  # groq: mixtral-8x7b-32768
                                  # claude: claude-opus-4-8 / claude-haiku-4-5
```

| Provider | สถานะ | ตั้งค่า |
|---|---|---|
| **Ollama** (Docker) | ✅ ฟรี 100% local | `docker-compose up` (จำเป็น) |
| **Groq** | ฟรี แต่ไม่รองรับ PDF ใหญ่ | `GROQ_API_KEY=...` ใน `.env` |
| **Gemini** | ฟรี แต่ติด 503 บ่อย | `GEMINI_API_KEY=...` ใน `.env` |
| **Claude** | ต้องจ่าย แต่เสถียร | `ANTHROPIC_API_KEY=...` ใน `.env` |

> สลับ provider เมื่อไหร่ก็ได้ แค่แก้ `provider` + `model` ใน `config.yaml` — โค้ดส่วนอื่นเหมือนเดิม

### เริ่มใช้ Ollama (Docker)

**1. รัน Ollama container:**
```bash
docker-compose up -d
```

**2. ดาวน์โหลด model (ครั้งแรกเท่านั้น ~2GB):**
```bash
docker exec ollama-accounting ollama pull mistral
```

**3. แก้ `config.yaml`:**
```yaml
provider: ollama
model: mistral
```

**4. ใช้งาน:**
```bash
python -m accounting_agent.cli process
```

> ต่อจากนี้ให้รัน `docker-compose up -d` ก่อนใช้งาน

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

## ไฟล์ PDF หลายหน้า / หลายบิล

ระบบจัดการ PDF หลายหน้าให้อัตโนมัติ:

- **บิลใบเดียวยาวหลายหน้า** (หัวบิล + รายการ + ยอดรวม) → รวมเป็นใบเสร็จ 1 รายการ
- **หลายบิลรวมในไฟล์เดียว** (เช่นสแกนรวมกัน) → AI แยกเป็นหลายรายการ ลง `ledger.csv` หลายบรรทัด
  - ถ้าติดตั้ง `pypdf` แล้ว: **ตัด PDF เป็นไฟล์ละบิล** จัดเข้าโฟลเดอร์ตามวันที่/หมวดของแต่ละบิล
  - ถ้าไม่มี `pypdf`: เก็บไฟล์รวมไว้ที่ `organized/<ปี>/<เดือน>/_หลายบิล/` แล้วลง ledger ทุกบิล (ระบุเลขหน้าใน notes)

> แยกบิลด้วย AI อาจไม่เป๊ะ 100% แนะนำให้เปิด `ledger.csv` ตรวจยอดรวมของไฟล์ที่มีหลายบิลซ้ำอีกที

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
- ส่งไปที่ AI provider (Gemini/Claude) เฉพาะตอนอ่านใบเสร็จเท่านั้น
- ใบเสร็จที่ AI ไม่มั่นใจ (confidence < 0.6) จะถูกทำเครื่องหมาย ⚠️ ให้คนตรวจซ้ำ

## โครงสร้าง

```
accounting-agent/
├── config.yaml              # หมวดหมู่ + พาธ
├── accounting_agent/
│   ├── models.py            # schema ของใบเสร็จ (Pydantic)
│   ├── config.py            # โหลด config
│   ├── providers.py         # ตัวเชื่อม Gemini / Claude (สลับได้)
│   ├── extract.py           # สร้างคำสั่งอ่านใบเสร็จ
│   ├── organize.py          # จัดโฟลเดอร์
│   ├── store.py             # สมุดบัญชี CSV
│   ├── brief.py             # สรุปรายเดือน
│   └── cli.py               # คำสั่ง process / brief
├── inbox/                   # ทิ้งใบเสร็จที่นี่
├── organized/               # ผลลัพธ์ที่จัดเรียงแล้ว
└── data/ledger.csv          # ข้อมูลรวมทุกใบเสร็จ
```
