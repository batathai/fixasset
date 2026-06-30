# Bata Asset Audit System

ระบบตรวจนับ Asset สาขา Bata — สแกน Barcode / QR ผ่านมือถือหรือเครื่องสแกน Urovo แล้ว HQ ติดตาม Progress แบบ Realtime

---

## ภาพรวมระบบ

```
สาขา (index.html)          API Backend              HQ Dashboard (dashboard.html)
─────────────────          ───────────              ────────────────────────────
Login → เลือกสาขา    →    POST /auth/login     →   ดู Session ทุกสาขา
เปิด Session         →    POST /sessions       →   เห็น Progress Realtime
สแกน Asset (x N)    →    POST /scans          →   Matched / Pending / Unmatched
ปิดงาน              →    PATCH /sessions/:id/close
HQ รับงาน           ←    PATCH /sessions/:id/acknowledge
```

---

## โครงสร้างไฟล์

```
/
├── index.html          # แอปสาขา — สแกน Asset (mobile-first, max-width 430px)
├── dashboard.html      # HQ Dashboard — ติดตามทุกสาขา
├── README.md           # เอกสารนี้
├── API.md              # เอกสาร API Endpoints ทั้งหมด
└── FLOW.md             # Flow การสแกน Multi-Scanner
```

---

## วิธีใช้งาน

### ฝั่งสาขา (index.html)

1. เปิด `index.html` บนมือถือหรือเครื่องสแกน Urovo
2. Login ด้วย username / password / รหัสสาขา
3. สแกน Barcode หรือ QR label ของ Asset ทีละชิ้น
4. ระบบแสดงผลทันที: **Matched** / **Unmatched** / **Duplicate**
5. เมื่อสแกนครบ → กด **ปิดงาน / Close Session**
6. รอ HQ ยืนยันรับงาน → เห็น Banner "✅ HQ รับแล้ว"

### ฝั่ง HQ (dashboard.html)

1. Login ด้วย HQ credentials
2. หน้า **Overview** — เห็น Daily Summary + Session ทุกสาขา
3. คอลัมน์ **HQ รับงาน** — กด "✓ รับงาน" หลังตรวจสอบแล้ว
4. ถ้าพบข้อผิดพลาด → กด "❗ ส่งกลับแก้" พร้อม comment
5. หน้า **Scan Logs** — filter ตามวัน / สาขา / สภาพ
6. Export Excel หรือ PDF ได้ทุกเมื่อ

---

## Multi-Scanner (หลายเครื่องต่อสาขา)

กรณีสาขาใช้หลายเครื่องสแกนพร้อมกัน:

1. HQ หรือ Manager เปิด Session → ได้ **Session PIN**
2. แจก PIN ให้ Scanner ทุกเครื่อง → กรอก PIN เข้าร่วม Session เดียวกัน
3. ทุกเครื่องสแกนพร้อมกัน → Progress รวมเป็น 1 Session อัตโนมัติ
4. ไม่มี Duplicate Session → ไม่ต้อง Merge

> รายละเอียดเพิ่มเติมดู [FLOW.md](./FLOW.md)

---

## สถานะ Session

| Status | ความหมาย |
|--------|-----------|
| `open` | เปิด Session แล้ว ยังไม่เริ่มสแกน |
| `on_process` | กำลังสแกนอยู่ |
| `done` | สาขาปิดงานแล้ว รอ HQ รับ |
| `done_reviewed` | HQ รับงานและตรวจสอบแล้ว |
| `needs_correction` | HQ ส่งกลับให้สาขาแก้ไข |

---

## สถานะ Asset ในแต่ละ Session

| สถานะ | ความหมาย |
|-------|-----------|
| **Matched** | สแกนได้ + ตรงกับ Master Data ✓ |
| **Pending** | ยังไม่ได้สแกน (รู้จาก Master Data) |
| **Unmatched** | สแกนได้ แต่ไม่มีใน Master Data สาขานี้ |
| **No QR** | Asset มีอยู่ แต่ QR label ใช้ไม่ได้ (เพิ่มมือ) |

---

## Tech Stack

- **Frontend**: Vanilla HTML / CSS / JavaScript (no framework)
- **Scanner**: Urovo hardware scanner (HID keyboard emulation) + manual input
- **Font**: Barlow, Barlow Condensed, DM Mono (Google Fonts)
- **Voice**: Web Speech API (th-TH)
- **Storage**: localStorage (session persist), API (source of truth)
- **Export**: SheetJS (Excel), jsPDF (PDF)

---

## Environment

ตั้งค่า API Base URL ใน `index.html` และ `dashboard.html`:

```javascript
// index.html (line ~620)
const API = 'https://your-api-domain.com';

// dashboard.html (line ~10)
const API = 'https://your-api-domain.com';
```
