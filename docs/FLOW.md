# Flow การสแกน — Bata Asset Audit

---

## 1. Flow หลัก (1 สาขา 1 เครื่อง)

```
HQ Dashboard                    สาขา (index.html)              API
─────────────                   ─────────────────              ───
                                Login (user/pass/branch)  →   POST /auth/login
                                ← token + session_id           
                                                          →   GET /assets?branch_id=
                                ← Checklist 300 รายการ        
                                
                                [ วนซ้ำ: สแกนทีละชิ้น ]
                                สแกน Barcode               →   POST /scans
                                ← matched / unmatched          
                                Progress Bar อัปเดต           
                                
เห็น Progress Realtime     ←   GET /sessions/:id/live (polling 30s)

                                [ ครบ 300 หรือบันทึกเหตุผล ]
                                Close Session              →   PATCH /sessions/:id/close
                                แสดง "รอ HQ รับงาน"           

กด "✓ รับงาน"              →   PATCH /hq/sessions/:id/acknowledge
สาขาเห็น "✅ HQ รับแล้ว"  ←   GET /sessions/:id (polling)
```

---

## 2. Flow Multi-Scanner (หลายเครื่องต่อสาขา)

### เช้าก่อนเริ่มงาน
```
HQ / Manager
    │
    ├─ เปิด Session สาขา 54027
    │   POST /sessions { branch_id: "54027" }
    │   ← session_id: 142, PIN: "4829"
    │
    └─ แจก PIN "4829" ให้ Scanner ทุกเครื่อง
```

### ทุกเครื่องเข้าร่วม Session เดียวกัน
```
Scanner A (staff01)                    Scanner B (staff02)
    │                                       │
    ├─ Login → กรอก PIN "4829"              ├─ Login → กรอก PIN "4829"
    │   POST /sessions/join                 │   POST /sessions/join
    │   ← session_id: 142, token_A         │   ← session_id: 142, token_B
    │                                       │
    │   [ แยกย้ายไปคนละโซนในสาขา ]          │
    │                                       │
    ├─ สแกน SFU001                          ├─ สแกน SFU200
    │   POST /scans { scanned_by: A }       │   POST /scans { scanned_by: B }
    │   ← matched ✓                        │   ← matched ✓
    │                                       │
    ├─ สแกน SFU100                          ├─ สแกน SFU100  ← สแกนซ้ำ!
    │   POST /scans { scanned_by: A }       │   POST /scans { scanned_by: B }
    │   ← matched ✓                        │   ← 409 already_scanned by A
    │                                       │   แสดง: "สแกนแล้วโดย staff01"
```

### Dashboard HQ เห็น (1 Session รวม)
```
Session #142 — สาขา 54027
├── Total:    300
├── Scanned:  254  (A: 138 + B: 116)
├── Pending:   46
└── Progress: 84.7% ████████░░
```

---

## 3. Flow ปิดงาน (Close Session)

```
สาขา
 │
 ├─ กด "ปิดงาน"
 │
 ├─ [ถ้ายังเหลือ Pending > 0]
 │   ┌─────────────────────────────────────────┐
 │   │  บังคับเลือกเหตุผล:                    │
 │   │  ○ Asset หาย / ไม่อยู่ในสาขา           │
 │   │  ○ ไม่มี QR label — แจ้ง HQ แล้ว       │
 │   │  ○ QR ชำรุด อ่านไม่ได้                 │
 │   │  ○ อื่นๆ — ระบุเอง                     │
 │   └─────────────────────────────────────────┘
 │
 ├─ ยืนยัน 2 ขั้น (Step 1 → Step 2)
 │
 ├─ PATCH /sessions/:id/close { close_reason: "..." }
 │
 ├─ Scan Lock เปิด → สแกนไม่ได้อีก (persist ใน localStorage)
 │
 └─ แสดง Banner "⏳ รอ HQ รับงาน"
        │
        │ (polling ทุก 30 วินาที)
        │
        ├─ HQ กด "✓ รับงาน" → "✅ HQ รับแล้ว"
        └─ HQ กด "❗ ส่งกลับแก้" → "❗ HQ ต้องการแก้ไข"
```

---

## 4. สถานะ Asset — ทุกรายการถูก Account

| สถานะ | นับจาก | ตัวอย่าง |
|-------|--------|---------|
| **Matched** | สแกนได้ + ตรง Master | สแกน SFU001 → พบใน Master ✓ |
| **Pending** | Master ที่ยังไม่ถูกสแกน | SFU050 อยู่ใน Master แต่ยังไม่สแกน |
| **Unmatched** | สแกนได้ แต่ไม่มีใน Master | สแกน SFU999 → ไม่มีในสาขานี้ |
| **No QR** | เพิ่มด้วยมือ | Asset อยู่ แต่ label หลุด |

> **สูตร**: Matched + Pending + No QR = Total Assets (Master Data)
> Unmatched คือ "นอก Master" — HQ ต้องตัดสินใจแยก

---

## 5. Flow HQ ตรวจสอบงาน

```
HQ Dashboard
 │
 ├─ เห็น Session status: "🔒 Done · รอรับงาน"
 │
 ├─ ตรวจสอบ:
 │   ├── Scan Logs (filter วันนี้ / สาขานี้)
 │   ├── Unmatched Assets → Match หรือ Reject
 │   └── รายการ Pending + เหตุผลที่สาขาระบุ
 │
 ├─ [ถ้าโอเค] กด "✓ รับงาน"
 │   PATCH /hq/sessions/:id/acknowledge
 │   → สาขาเห็น "✅ HQ รับแล้ว"
 │
 └─ [ถ้าพบปัญหา] กด "❗ ส่งกลับแก้"
     PATCH /hq/sessions/:id/needs-correction
     { comment: "Serial ไม่ตรง 3 รายการ" }
     → สาขาเห็น "❗ HQ ต้องการแก้ไข"
```

---

## 6. กฎ Business Logic

| กฎ | รายละเอียด |
|----|-----------|
| **1 สาขา = 1 Session ต่อวัน** | ถ้ามี Session ซ้ำ Dashboard แสดง badge "ซ้ำ" และ Merge ได้ |
| **Scan Lock** | หลัง Close Session สแกนไม่ได้ แม้ refresh หน้า |
| **Duplicate Scan** | API ตอบ 409 พร้อมบอกว่าใคร scan ไปก่อน |
| **Close ต้องมีเหตุผล** | ถ้า Pending > 0 ต้องเลือกเหตุผลทุกรายการก่อนปิด |
| **HQ รับงานได้เมื่อ** | Session status = `done` เท่านั้น |
| **Overdue** | Session ที่เกิน `scheduled_date` แล้วยังไม่ Done → badge เหลืองในตาราง |
| **Auto-refresh** | Dashboard auto-refresh ทุก 60 วินาที |
