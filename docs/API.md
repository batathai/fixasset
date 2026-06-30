# API Reference — Bata Asset Audit

Base URL: `https://your-api-domain.com`

Authentication: `Authorization: Bearer <token>` (ทุก endpoint ยกเว้น `/auth/login`)

---

## Authentication

### POST `/auth/login`
Login สำหรับสาขาและ HQ

**Request**
```json
{
  "username": "staff01",
  "password": "••••••",
  "branch_id": "54027"
}
```

**Response 200**
```json
{
  "token": "eyJ...",
  "user": "staff01",
  "branch_id": "54027",
  "branch_name": "บิ๊กซี สาขามีนบุรี",
  "role": "branch"
}
```

**Roles**: `branch` | `manager` | `hq`

---

## Sessions

### GET `/sessions`
ดึง Session ทั้งหมด (HQ เท่านั้น)

**Query params**
| Param | Type | Description |
|-------|------|-------------|
| `branch_id` | string | filter สาขา |
| `status` | string | `open` \| `on_process` \| `done` \| `done_reviewed` |
| `date` | string | `2024-06-27` (วันที่เปิด session) |

**Response 200**
```json
[
  {
    "session_id": 142,
    "branch_id": "54027",
    "branch_name": "บิ๊กซี สาขามีนบุรี",
    "status": "on_process",
    "total_assets": 300,
    "scanned_count": 254,
    "unmatched_count": 3,
    "scheduled_date": "2024-06-27",
    "hq_ack": false,
    "hq_ack_by": null,
    "hq_ack_at": null,
    "created_at": "2024-06-27T08:00:00Z",
    "closed_at": null
  }
]
```

---

### POST `/sessions`
เปิด Session ใหม่

**Request**
```json
{
  "branch_id": "54027",
  "scheduled_date": "2024-06-27"
}
```

**Response 201**
```json
{
  "session_id": 142,
  "branch_id": "54027",
  "pin": "4829",
  "status": "open"
}
```

> `pin` ใช้สำหรับ Multi-Scanner Join — แจกให้เครื่องสแกนทุกเครื่อง

---

### POST `/sessions/join`
Scanner เข้าร่วม Session ที่มีอยู่แล้วด้วย PIN (Multi-Scanner)

**Request**
```json
{
  "branch_id": "54027",
  "pin": "4829",
  "scanner_user": "staff02"
}
```

**Response 200**
```json
{
  "session_id": 142,
  "token": "eyJ...",
  "branch_name": "บิ๊กซี สาขามีนบุรี",
  "total_assets": 300,
  "scanned_count": 138
}
```

---

### GET `/sessions/:id`
ดูรายละเอียด Session + HQ Status

**Response 200**
```json
{
  "session_id": 142,
  "status": "done",
  "hq_status": "pending_review",
  "hq_comment": null,
  "scanners": [
    { "user": "staff01", "scanned_count": 138 },
    { "user": "staff02", "scanned_count": 116 }
  ],
  "pending_list": [
    { "asset_code": "SFU012024010001SE0001", "asset_name": "Classic Pump Black" },
    { "asset_code": "SFU012024010002SE0001", "asset_name": "Relax Sandal White" }
  ]
}
```

---

### GET `/sessions/:id/live`
Progress Realtime (polling ทุก 30 วินาที)

**Response 200**
```json
{
  "session_id": 142,
  "scanned_count": 254,
  "total_assets": 300,
  "pct": 84.7,
  "last_scan_at": "2024-06-27T10:32:15Z",
  "active_scanners": 2
}
```

---

### PATCH `/sessions/:id/close`
ปิดงาน Session (สาขา)

**Request**
```json
{
  "close_reason": "asset_missing — พบ Asset หายไป 40 รายการ, no_qr — QR ชำรุด 6 รายการ"
}
```

**Response 200**
```json
{
  "session_id": 142,
  "status": "done",
  "closed_at": "2024-06-27T17:00:00Z",
  "summary": {
    "matched": 254,
    "pending": 46,
    "unmatched": 3,
    "no_qr": 6
  }
}
```

---

### PATCH `/hq/sessions/:id/acknowledge`
HQ รับงานและยืนยัน (HQ เท่านั้น)

**Request**
```json
{
  "ack_by": "hq_manager01",
  "ack_at": "2024-06-27T18:00:00Z"
}
```

**Response 200**
```json
{
  "session_id": 142,
  "status": "done_reviewed",
  "hq_ack": true,
  "hq_ack_by": "hq_manager01",
  "hq_ack_at": "2024-06-27T18:00:00Z"
}
```

---

### PATCH `/hq/sessions/:id/needs-correction`
HQ ส่งกลับให้สาขาแก้ไข

**Request**
```json
{
  "comment": "Serial number ไม่ตรงกับ Master data 3 รายการ กรุณาตรวจสอบใหม่",
  "reviewer": "hq_manager01"
}
```

**Response 200**
```json
{
  "session_id": 142,
  "status": "needs_correction",
  "hq_comment": "Serial number ไม่ตรงกับ Master data 3 รายการ กรุณาตรวจสอบใหม่"
}
```

---

## Scans

### POST `/scans`
บันทึก Scan Log (สาขา)

**Request**
```json
{
  "session_id": 142,
  "qr_key": "SFU012024010001SE0001",
  "serial_found": "SN-20240001",
  "serial_match": true,
  "condition": "good",
  "remark": null,
  "scanned_by": "staff01"
}
```

**Response 201** — Matched
```json
{
  "id": 8821,
  "type": "matched",
  "asset_name": "Classic Pump Black",
  "asset_code": "SFU012024010001SE0001"
}
```

**Response 409** — Already scanned (Duplicate / Multi-Scanner conflict)
```json
{
  "error": "already_scanned",
  "scanned_by": "staff02",
  "scanned_at": "2024-06-27T10:15:33Z"
}
```

**Response 200** — Unmatched (ไม่มีใน Master Data)
```json
{
  "id": 8822,
  "type": "unmatched",
  "qr_key": "SFU012099999999SE0001"
}
```

---

### GET `/scans`
ดึง Scan Logs (HQ)

**Query params**
| Param | Type | Description |
|-------|------|-------------|
| `session_id` | number | filter session |
| `branch_id` | string | filter สาขา |
| `date_from` | string | `2024-06-01` |
| `date_to` | string | `2024-06-30` |
| `condition` | string | `good` \| `damaged` \| `missing` |
| `type` | string | `matched` \| `unmatched` |

---

### PATCH `/scans/:id`
แก้ไข Scan Log (HQ)

**Request**
```json
{
  "condition": "damaged",
  "serial_found": "SN-20240001-REVISED",
  "remark": "พบรอยขีดข่วน"
}
```

---

## Assets (Master Data)

### GET `/assets`
ดึง Asset List ของสาขา (ใช้ตอนเปิด Session เพื่อสร้าง Checklist)

**Query params**
| Param | Type | Description |
|-------|------|-------------|
| `branch_id` | string | **required** |

**Response 200**
```json
[
  {
    "qr_key": "SFU012024010001SE0001",
    "asset_code": "SFU012024010001",
    "seq": "SE0001",
    "asset_name": "Classic Pump Black",
    "category": "Shoes",
    "serial_master": "SN-20240001"
  }
]
```

---

### GET `/assets/unmatched`
ดึง Unmatched Assets ที่รอ HQ ตรวจสอบ

**Query params**: `session_id`, `branch_id`, `status`

---

### PATCH `/assets/unmatched/:id/match`
HQ จับคู่ Unmatched กับ Asset ใน Master

**Request**
```json
{
  "asset_code": "SFU012024010001SE0001",
  "remark": "Asset ย้ายมาจากสาขา 54020"
}
```

---

## Error Codes

| Code | HTTP | ความหมาย |
|------|------|-----------|
| `unauthorized` | 401 | Token หมดอายุหรือไม่ถูกต้อง |
| `forbidden` | 403 | Role ไม่มีสิทธิ์ทำ action นี้ |
| `session_closed` | 400 | Session ปิดแล้ว ไม่สามารถสแกนเพิ่ม |
| `already_scanned` | 409 | Asset นี้ถูกสแกนแล้ว (บอก scanned_by ด้วย) |
| `invalid_pin` | 400 | PIN ไม่ถูกต้องหรือหมดอายุ |
| `session_not_found` | 404 | ไม่พบ Session |
