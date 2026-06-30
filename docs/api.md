# API — Bata Fixed Asset Audit System

Base URL (production): `https://bata-asset-api-production.up.railway.app`
Interactive docs (Swagger UI): `https://bata-asset-api-production.up.railway.app/docs`
Framework: **FastAPI** (Python) — ไฟล์หลัก `main.py`

## Auth

ทุก endpoint ที่ขึ้นต้นด้วย `/hq/*` และ `/dashboard/*` ต้องผ่านการยืนยันตัวตน (current user) — ตรวจสิทธิ์ role `hq_admin` สำหรับฟังก์ชันฝั่ง HQ

```
POST /auth/login
```
ใช้สำหรับทีม audit / admin login ด้วย email + password (เก็บ hash ด้วย bcrypt)

## Endpoints หลัก

| Method | Path | คำอธิบาย |
|---|---|---|
| GET | `/health` | เช็คว่า API ออนไลน์ — คืน `{"status":"ok"}` |
| POST | `/auth/login` | ทีม audit / admin login |
| GET | `/assets/lookup/{qr_key}` | ค้นหา asset จากรหัสที่อ่านได้จาก QR |
| GET | `/assets/branch/{branch_id}` | โหลดรายการ asset ทั้งหมดของสาขา |
| POST | `/sessions` | สร้าง audit session ใหม่ |
| DELETE | `/hq/sessions/{session_id}` | ลบ audit session (เฉพาะ HQ) |
| POST | `/hq/sessions/merge` | merge session ที่ซ้ำกันเข้าด้วยกัน |
| POST | `/scans` | บันทึก scan log (asset ที่พบใน master) |
| GET | `/hq/scans` | HQ ดู scan log ทั้งหมด พร้อมรูปถ่าย |
| PATCH | `/hq/scans/{id}` | HQ แก้ไข condition / serial / hq_note ของ scan log |
| POST | `/hq/scans/{id}/photo` | อัปโหลดรูปใหม่ให้ scan log (เก็บที่ Supabase Storage) |
| DELETE | `/hq/scans/{id}/photo` | ลบรูปถ่ายของ scan log |
| POST | `/unmatched` | ส่ง asset ที่สแกนแล้วไม่พบใน master ไปรอ HQ review |
| GET | `/hq/unmatched` | HQ ดูรายการ unmatched ทั้งหมด |
| PATCH | `/hq/unmatched/{id}` | HQ approve (`matched`) หรือ reject unmatched asset |
| GET | `/dashboard/summary` | สรุปภาพรวมทุกสาขา (ใช้แสดงในหน้า Overview ของ Dashboard) |

## รายละเอียด endpoint สำคัญ

### `GET /assets/lookup/{qr_key}`
ใช้โดย Scanner App ทุกครั้งที่สแกน QR — ค้นหา `asset_code` (หรือ `alt_codes`) ที่ตรงกับค่าที่อ่านได้
- พบ → คืนข้อมูล asset เพื่อให้ user ยืนยัน serial number
- ไม่พบ → frontend จะสลับไปใช้ flow `POST /unmatched` แทน

### `POST /scans`
บันทึกการสแกนที่ asset มีอยู่ใน master แล้ว มี `UNIQUE(session_id, asset_id)` กันการสแกนซ้ำใน session เดียวกัน หาก `serial_found` ที่ส่งมาไม่ตรงกับ `serial_no` ใน master ระบบจะตั้ง `serial_match = false` และสร้าง record ใน `serial_mismatches` ให้ HQ ตรวจสอบ

### `POST /unmatched`
รับ QR ที่ไม่พบใน master พร้อมข้อมูลที่ user กรอกเอง (`name_guess`, `serial_no`, รูปถ่าย) — กันไม่ให้ audit มี gap แม้ asset master จะ import มาไม่ครบ 100%

### `PATCH /hq/unmatched/{id}`
HQ ใช้ตัดสินใจว่า unmatched asset แต่ละรายการคือ asset ตัวไหน (`status = 'matched'`, ผูกกับ `matched_asset_id`/`matched_asset_code`) หรือปฏิเสธ (`status = 'rejected'`)

### `POST /hq/sessions/merge`
ใช้แก้ปัญหากรณีมี audit session ซ้ำกันโดยไม่ตั้งใจ (เช่น user กดสร้าง session ใหม่ซ้ำ) — endpoint จะย้าย `scan_logs` และ `unmatched_assets` จาก session ซ้ำเข้า primary session (ข้าม record ที่ asset_id ซ้ำโดยไม่ error) แล้วลบ session ซ้ำทิ้ง พร้อมอัปเดตสถานะ session หลักเป็น `on_process` หากมี scan แล้ว

### รูปถ่าย (`/hq/scans/{id}/photo`)
อัปโหลด/ลบรูปผ่าน Supabase Storage API (ใช้ `service_role` key) แล้วอัปเดต/ล้างค่า `photo_url` ใน Postgres (Neon) — ต้องตั้ง environment variable `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, `SUPABASE_BUCKET` ใน Railway และติดตั้ง dependency `httpx`, `python-multipart`

## Models (ตัวอย่างจาก main.py)

```python
class ScanLogUpdate(BaseModel):
    condition: Optional[str] = None
    serial_found: Optional[str] = None
    hq_note: Optional[str] = None

class UnmatchedUpdate(BaseModel):
    status: str  # 'matched' | 'rejected'
    hq_note: Optional[str] = None
    matched_asset_code: Optional[str] = None
```

## Error handling ที่ควรรู้

- การเปลี่ยนแปลง logic ฝั่ง backend (เช่น status `open` → `on_process`) จะมีผลกับ **scan ใหม่เท่านั้น** ข้อมูลเก่าใน database ต้อง migrate ด้วย SQL `UPDATE` แยกต่างหาก ไม่ได้ถูกแก้ย้อนหลังอัตโนมัติ
- ก่อนแก้ query ที่อ้างอิง column ใดๆ ควรตรวจสอบกับ schema จริงก่อน เคยเกิด error `UndefinedColumn` เพราะ backend อ้างถึง column ที่ไม่เคยถูกสร้างจริง
