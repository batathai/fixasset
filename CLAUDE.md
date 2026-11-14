# CLAUDE.md

คู่มือสำหรับ Claude (หรือ AI/นักพัฒนาคนอื่น) ที่จะเข้ามาแก้ไขโค้ดใน repo นี้ อ่านไฟล์นี้ก่อนเริ่มแก้ไขทุกครั้ง

---

## 1. ภาพรวมโปรเจกต์

**Bata Fixed Asset Audit System** — ระบบตรวจนับสินทรัพย์ถาวร (fixed asset) ของ Bata Thailand

ใช้แก้ปัญหาการตรวจนับสินทรัพย์ (คอมพิวเตอร์, อุปกรณ์, เฟอร์นิเจอร์ ฯลฯ) ตามสาขาต่างๆ ที่แต่เดิมทำด้วยกระดาษ/Excel โดยให้ทีม audit ใช้เครื่องสแกนบาร์โค้ด (Urovo) หรือคีย์บอร์ดกรอกรหัสสินทรัพย์ทีละชิ้นที่หน้างาน แล้วระบบจะ:

- เทียบกับ "master data" ของสินทรัพย์ที่ HQ import เข้ามา ว่า **พบ (matched)**, **serial ไม่ตรง (serial mismatch)**, หรือ **ไม่รู้จัก (unmatched)**
- ส่งผลขึ้น HQ Dashboard แบบเกือบ realtime ให้ผู้ดูแลส่วนกลางติดตามความคืบหน้าทุกสาขา ตรวจสอบ/อนุมัติ/ส่งกลับแก้ไข และ export รายงาน Excel ที่มีตราสินค้า (branded) ได้

ระบบมี 3 ฝั่งผู้ใช้งานหลัก: **พนักงานสาขา/ทีม audit** (ใช้ `index.html` สแกนของจริงตามสาขาร้านค้า), **พนักงาน Office** (ใช้ `office.html` สแกนของใน office พร้อมระบุแผนก+ผู้รับผิดชอบ), และ **admin ที่ HQ** (ใช้ `dashboard.html` ดูภาพรวม จัดการ asset และจัดการรายชื่อพนักงาน)

---

## 2. สถานะปัจจุบัน

- เวอร์ชัน backend ปัจจุบัน (ตาม `main.py`): **1.2.0**
- ระบบใช้งานจริงอยู่แล้ว (production) มี login จริง มี asset master import จริง ไม่ใช่ prototype
- คอมมิตล่าสุดใน repo นี้ (branch `main`): **2026-11-12** (`108d3e3`)
- **2026-07-21 — Office Asset Scan (เวอร์ชันแรก):** หน้าใหม่ `office.html` (clone จาก `index.html`) + คอลัมน์ `department` แบบ free text
- **2026-07-22/23 — Office Asset Scan v2 + ระบบพนักงาน (เพิ่มเข้ามาวันนี้ — ดู section 8 รายละเอียดเต็ม):**
  - เปลี่ยนช่องแผนกใน `office.html` จาก free text → `<select>` แบบ fixed list 11 แผนก (กัน typo)
  - เพิ่มตาราง `employees` (import จากไฟล์ Excel HR, 84 คน) + หน้าจัดการพนักงานใน `dashboard.html` (เมนู "พนักงาน" — list/search/filter/import/deactivate)
  - เพิ่ม dropdown ที่ 2 "มอบหมายให้พนักงาน" ใน `office.html` — เลือกแผนกก่อน ระบบดึงรายชื่อพนักงานเฉพาะแผนกนั้นมาให้เลือก ครอบคลุมทั้งการ์ด matched, serial-check, และ unmatched
  - **แก้บั๊กใหญ่ที่เจอระหว่างทาง:** `assets.department` (และคอลัมน์ที่เกี่ยวข้องใน `scan_logs`/`unmatched_assets`) ที่ระบุไว้ใน entry 2026-07-21 ว่าจะเพิ่ม **ไม่เคยถูกรันจริงในฐานข้อมูล Production** ทำให้ `/hq/assets` (และทุก endpoint ที่ query `a.department`) พัง 500 error มานานโดยไม่มีใครรู้ตัว — อาการที่เห็นคือ browser แจ้ง "CORS error" (เข้าใจผิดได้ง่ายมาก เพราะ FastAPI/Starlette ตอบ unhandled exception เป็น generic `text/plain "Internal Server Error"` ที่ไม่มี CORS header ติดมา) สาเหตุจริงคือ column ไม่มีอยู่ ไม่ใช่ CORS — แก้แล้วโดยรัน migration ที่ค้างไว้จริงๆ ใน Neon (ดู section 6 ข้อ 11 เรื่องวิธี debug อาการนี้)
  - เพิ่ม CORS origin สำหรับทดสอบผ่าน local server (`localhost:8000`, `:5500`, `:3000`)
- **2026-11-05 — UI Redesign (เฉพาะหน้าตา ไม่แตะ logic/backend/DB) — ดู section 8 รายละเอียดเต็ม:**
  - `dashboard.html` ออกแบบใหม่ทั้งหน้า (UI v3): sidebar สีกรมท่า, IBM Plex Sans Thai, หน้าแรกเปลี่ยนชื่อจาก "Overview" เป็น **"Dashboard"** ที่มี KPI 6 ใบ + "สิ่งที่ต้องดูแล" + วงแหวนความคืบหน้า + สาขาที่เหลือมากที่สุด (ตัวเลขทั้งหมดคำนวณจากข้อมูลจริง ไม่มีข้อมูลจำลอง)
  - แบรนด์ในหน้าเว็บเปลี่ยนจาก "Bata Audit" เป็น **"Bata Fix Asset"**
  - หน้า Login ของทั้ง 3 หน้า (`index.html`, `office.html`, `dashboard.html`) ใช้ภาพพนักงานสแกนสินทรัพย์ (`login_scan.gif`) + จุดสถานะการเชื่อมต่อ API เขียว/แดง
  - Workflow ที่ใช้ตลอดรอบนี้: ทำบน branch `staging` ก่อน → ผู้ใช้สั่ง "merge เข้า main" → fast-forward `main` → fetch กลับมาเทียบ md5 ทุกครั้ง
- **2026-11-12 — Write off / ย้าย Location / Dashboard v4 (ผู้ใช้ทดสอบจริงแล้วใช้ได้) — ดูข้อ 6.16–6.18 และ section 8:**
  - **Write off asset ที่ยังไม่เคยสแกน:** `POST /hq/assets/{id}/write-off` + คอลัมน์ `assets.write_off_*` (เดิมกด Save แล้วขึ้น toast "รอเชื่อม POST /scans")
  - **ย้าย Location โดย HQ:** `PATCH /hq/assets/{id}/location` + `assets.location_override` — แก้บั๊กที่ช่อง Location ไม่เคยถูก save; กรณี master ถูกแล้วแต่สแกนที่สาขาอื่น (เช่น `MAC022014070001SEQ005`, `MAC022014110001SEQ002`) drawer เตือนแล้วกด Save เพื่อย้ายตาม master
  - **Dashboard v4:** sidebar ไอคอนล้วน, แถบ % ใต้ KPI, การ์ดแผนกไม่ตรง, ภาพรวมสาขาและทีม, แนวโน้มสแกน 7 วัน
  - Migration ที่รันใน Neon แล้ว: `migration_asset_writeoff.sql`, `migration_asset_location_override.sql`
  - Workflow: staging → ผู้ใช้สั่ง "merge เข้า main" → fast-forward → เทียบ md5 (มี PR #1 "Staging" ที่ผู้ใช้เปิดไว้ถูกปิดเป็น merged)
- **ยังไม่ได้แก้ (ทราบปัญหาแล้ว แต่ยังไม่ทำ):** auth session เก็บใน memory ของ backend (ดูหัวข้อ 6)

> ⚠️ **สำคัญ:** `docs/` เหลือแค่ไฟล์ที่ตรงกับโค้ดจริง (`database.md`, `changelog.md`) — ถ้าไม่แน่ใจเรื่อง endpoint ให้ตรวจกับ `main.py` เสมอ

---

## 3. โครงสร้างไฟล์/โฟลเดอร์หลัก

```
/
├── main.py                          # Backend ทั้งหมด (FastAPI, ไฟล์เดียว) deploy บน Railway
├── requirements.txt                  # Python dependencies ของ backend
├── Procfile                          # คำสั่ง start ของ Railway/Heroku-style (uvicorn)
├── railway.toml                      # Railway build/deploy config (Nixpacks)
├── index.html                        # Frontend: แอพสแกนหน้าสาขาร้านค้า (static) host บน GitHub Pages
├── office.html                       # Frontend: แอพสแกนของในออฟฟิศ (static) — clone จาก index.html + ระบบแผนก/พนักงาน (ดูข้อ 6.9)
├── dashboard.html                    # Frontend: HQ Dashboard (static) — asset + พนักงาน host บน GitHub Pages
├── migration_employees.sql           # Migration: ตาราง employees, employee_import_batches + คอลัมน์ assigned_employee_id/name ใน scan_logs — รันแล้ว
├── migration_unmatched_employee.sql  # Migration: คอลัมน์ assigned_employee_id/name ใน unmatched_assets — รันแล้ว
├── migration_department_codes.sql    # Migration: แปลงชื่อแผนกเดิม → รหัสแผนกใหม่ 12 ค่า (scan_logs, unmatched_assets, employees) — รันแล้ว 2026-11-09
├── migration_asset_writeoff.sql      # Migration: คอลัมน์ write_off_reason/write_off_remark/written_off_by/written_off_at ใน assets — รันแล้วใน Neon 2026-11-12 (ตรวจครบ 4 คอลัมน์)
├── migration_asset_location_override.sql # Migration: assets.location_override (HQ ย้าย location) — รันแล้วใน Neon 2026-11-12 (ถ้าตั้ง DB ใหม่ต้องรันก่อน deploy main.py ไม่งั้น GET /hq/assets 500)
├── migration_employee_holdings.sql   # Migration: ตาราง employee_holdings (พนักงานควรถืออุปกรณ์อะไร) — ยังไม่ได้รันใน Neon (ดูข้อ 6.21)
├── CNAME                              # Custom domain ของ GitHub Pages: fixasset.batathai.com
├── login_scan.webp                    # ภาพเคลื่อนไหวแบบนุ่ม (72 เฟรม ~37ms, พื้นโปร่งใส) พนักงานสแกนสินทรัพย์ — ใช้ในหน้า Login ทั้ง 3 หน้า
├── login_scan.gif                     # ไฟล์ต้นฉบับ 9 เฟรม (กระตุก) — เก็บไว้เป็น fallback ของ <picture> สำหรับเบราว์เซอร์ที่ไม่รองรับ WebP
├── login_scan_still.png               # เฟรมนิ่งของ GIF — ใช้แทนเมื่อเครื่องตั้ง prefers-reduced-motion
├── bata_logo.png                      # โลโก้ที่ใช้ในหน้าเว็บ
├── CHANGES_README.md                  # สรุปแก้ไข "6 ข้อ" จากรอบก่อนหน้า (ยังไม่ถูกรวมเข้า docs/changelog.md อย่างเป็นทางการ)
└── docs/
    ├── database.md        # Schema ฐานข้อมูลจริง + ประวัติการแก้ schema
    └── changelog.md       # ประวัติการพัฒนาระบบตั้งแต่ v0.1–v0.8
```

> **หมายเหตุ (2026-07-23):** `seed_users.py`, `migration_scan_delete_log.sql`, และ `migration_office_department.sql` ถูกลบออกจาก repo แล้ว เพราะเป็นสคริปต์/migration ที่รันเสร็จสิ้นไปแล้วจริงในฐานข้อมูล Production ไม่มีโค้ดส่วนไหนอ้างอิง/รันไฟล์เหล่านี้ตอน runtime — **เนื้อหาเต็มถูกเก็บสำรองไว้ใน Section 9 (Archive) ของไฟล์นี้แล้ว** ถ้าต้อง setup ฐานข้อมูลใหม่ตั้งแต่ต้นในอนาคต ให้คัดลอกจาก Section 9 ไปใช้

**ไม่มีโฟลเดอร์ `src/`, ไม่มี build step, ไม่มี package.json** — ทั้งหมดเป็นไฟล์ static/สคริปต์เดี่ยวๆ ตามเจตนาการออกแบบ (ดูข้อ 5)

---

## 4. Tech Stack

**Backend**
- Python + **FastAPI** (`main.py` ไฟล์เดียว ไม่มีการแยก router/module)
- **psycopg2** เชื่อมต่อ Postgres โดยตรง (ไม่มี ORM)
- Deploy บน **Railway** (Nixpacks, auto-deploy ทุกครั้งที่ push ขึ้น branch `main`)
- Auth: token แบบสุ่ม (`secrets.token_hex`) เก็บใน dict ในหน่วยความจำ (`sessions = {}`) — **ไม่ใช่ JWT** และไม่ persist
- Password hash: SHA-256 ธรรมดา (ไม่ใช่ bcrypt/argon2)
- Excel: `openpyxl` (อ่าน .xlsx + สร้างไฟล์ export ที่มีสไตล์), `xlrd` (อ่าน .xls เก่า)
- รูปภาพ: อัปโหลดตรงไป **Cloudinary** จาก client (unsigned upload preset `bata_audit`, cloud `dhpwh4io1`) ฝั่ง backend ใช้ signed API สำหรับลบรูปและอัปโหลดรูปจากหน้า HQ

**Database**
- **Postgres บน Neon** (`neon.tech`) — ไม่มี auto-migration ตอน startup ต้องรัน SQL เองผ่าน Neon SQL editor ทุกครั้งที่ schema เปลี่ยน **แล้วต้องเช็คด้วยว่ารันจริงสำเร็จก่อนจะถือว่างานเสร็จ** (ดูเหตุการณ์ 2026-07-23 ใน section 2 — เคยลืมรันจนพังไปหลายวันโดยไม่รู้ตัว)

**Frontend**
- **Vanilla HTML/CSS/JavaScript ล้วน ไม่มี framework** ไม่มี build step, ไฟล์เดียวจบต่อหน้า
- ฟอนต์: Barlow, Barlow Condensed, DM Mono (Google Fonts)
- Input หลักของแอพสแกน: **เครื่องสแกนบาร์โค้ด Urovo (HID keyboard emulation)** ดักจับด้วย `keydown` listener ใน `initUrovoScanner()`
- เก็บ state ฝั่ง client ด้วย `localStorage` (token, session ที่เลือกไว้, offline queue)
- Export ฝั่ง dashboard: `xlsx` (SheetJS) สำหรับ export ง่ายๆ, ส่วน export "branded" ให้ backend สร้างด้วย `openpyxl` ผ่าน `/hq/export/excel`
- Host: **GitHub Pages** ของ repo นี้เอง ผ่าน custom domain `fixasset.batathai.com` (ดูไฟล์ `CNAME`)

---

## 5. เหตุผลการออกแบบสำคัญที่ควรรู้ก่อนแก้โค้ด

1. **Frontend ห้ามต่อฐานข้อมูลตรง** — ทุกการเข้าถึงข้อมูลต้องผ่าน backend API ที่มีการตรวจสอบสิทธิ์ (`Authorization: Bearer <token>`)
2. **รองรับ asset ที่ไม่มีใน master (`unmatched_assets`)** — รับของที่ไม่รู้จักไว้ก่อน แทนที่จะปฏิเสธการสแกน แล้วให้ HQ reconcile ทีหลังผ่าน `/hq/unmatched`
3. **แยก `scan_logs` และ serial mismatch** — แยกกรณี asset ที่พบตรงกับ master ออกจากกรณี serial ไม่ตรง
4. **Import batch + soft-delete สำหรับ Undo import** — ทุกแถวที่ import จากไฟล์เดียวกัน tag ด้วย `import_batch_id` เดียวกัน undo คือ set `is_active = false` เท่านั้น — **ทุก query ที่ดึง asset/employee ต้องกรอง `COALESCE(is_active, true) = true` เสมอ**
5. **Map รหัสสถานะจาก Excel ก่อนเข้า DB เสมอ** ผ่าน `_STATUS_CODE_MAP` — ห้ามยัดรหัสดิบเข้า DB
6. **แปลงวันที่จาก Excel ผ่าน `_parse_thai_date_string()` เสมอ**
7. **แก้ไข scan log ที่มีอยู่แล้วต้องใช้ `PATCH /scans` (by qr_key) ไม่ใช่ยิง `POST /scans` ซ้ำ** — เพราะมี guard กันสแกนซ้ำ (409 `already_scanned`)
8. **ลบ scan log ต้องบันทึก audit log ก่อนลบจริงเสมอ** ผ่าน `_record_scan_delete()` เข้าตาราง `scan_delete_logs`
9. **สาขาลบ/แก้ไข scan ได้เฉพาะตอน session ยังไม่ปิด (`status != 'done'`)** — ปิดงานแล้วต้องให้ HQ จัดการแทน
10. **Schema change ทุกครั้งต้อง apply ผ่าน Neon SQL editor เอง** — ไม่มี auto-migration ตอน backend startup **และต้องยืนยันว่ารันสำเร็จจริงก่อนประกาศว่างานเสร็จ**
11. **ทำไมไม่มี framework/build step ฝั่ง frontend** — เลือกความเรียบง่ายในการ deploy แลกกับไฟล์ .html ใหญ่มาก (100KB+) และแก้ยากขึ้นเรื่อยๆ
12. **Employee assignment เก็บแบบ denormalized เหมือน department** — `scan_logs.assigned_employee_id`/`assigned_employee_name` และ `unmatched_assets.assigned_employee_id`/`assigned_employee_name` เก็บเป็น text ตรงๆ ไม่ผูก FK กับ `employees` เพื่อไม่ให้ scan record พังถ้าพนักงานถูกปิดใช้งาน/ลบทีหลัง
13. **แผนกของ Office เป็น fixed list 12 "รหัสแผนก" ตายตัว (แสดงและบันทึกเป็นรหัสล้วน ไม่มีชื่อเต็ม)** — `OFFICE_DEPARTMENTS` ใน `office.html` **และ `dashboard.html` (ต้อง sync มือทั้งสองไฟล์)** ไม่ได้ query จาก DB แบบ dynamic: `500R, 600ML, 630, 640, 640M, 680, 999, 999CM, 999FI, 999HR, 999IA, 999IT` (ชื่อเต็มของแต่ละรหัสไม่ได้เก็บในระบบ: 500R Retail Office, 600ML Multi-Channel, 630 Advertising, 640 Merchandising, 640M Merchandising Department, 680 Warehouse, 999 Administration, 999CM Country Manager Office, 999FI Finance Department (Account), 999HR Human Resources, 999IA Internal Audit, 999IT IT Department) — ถ้าจะเพิ่ม/ลบแผนก ต้องแก้ array นี้ทั้งสองไฟล์ และถ้ามีข้อมูลเดิมที่ใช้ค่าเก่าต้องเขียน migration แปลงค่าใน DB ด้วย

---

## 6. จุดที่ต้องระวัง / Known Issues

1. **Auth session เก็บใน memory (`sessions = {}` ใน `main.py`)** — ถ้า Railway restart/redeploy token ของทุกคนจะหลุดพร้อมกันหมดทันที ผู้ใช้ต้อง login ใหม่ทุกครั้งหลัง deploy — ยังไม่ได้แก้
2. **Password hash เป็น SHA-256 ธรรมดา ไม่มี salt** — ไม่ใช่ bcrypt/argon2
3. **`migration_session_uniqueness.sql` ถูกอ้างถึงใน comment ของ `main.py`** (partial unique index `idx_unique_open_session_per_branch_day`) **แต่ไม่มีไฟล์นี้อยู่จริงใน repo** — น่าจะรันตรงใน Neon แล้วไม่ได้ commit เก็บไว้
4. **ต้องรัน SQL migration ก่อน deploy เสมอเมื่อโค้ดอ้างถึง column/ตารางใหม่ — และต้องยืนยันว่ารันสำเร็จจริง** ไม่งั้นจะเจอ `psycopg2.errors.UndefinedColumn` (เกิดขึ้นจริงกับ `assets.department` ค้างอยู่หลายวันโดยไม่มีใครรู้ตัว เพราะอาการแสดงผลเป็น "CORS error" ที่เข้าใจผิดง่าย — ดูข้อ 11)
5. **`index.html`, `office.html`, `dashboard.html` ใหญ่มาก (100KB+ ต่อไฟล์)** — ไฟล์เดียวรวม HTML/CSS/JS ทั้งหมด ไม่มี build/test process ช่วยตรวจ syntax ก่อน deploy — **ควรรัน `node --check` กับ JS ที่ extract ออกมาจาก `<script>` เสมอก่อน push**
6. **Cloudinary upload preset (`bata_audit`) เป็นแบบ unsigned ฝั่ง client** — ใครก็ตามที่เห็น source code สามารถอัปโหลดเข้า Cloudinary account นี้ได้โดยไม่ผ่าน backend
7. **Excel status/date parsing มีจุดเปราะบาง** — ตรวจสอบผลลัพธ์ preview ก่อน confirm import จริงเสมอ
8. **`office.html` เป็นไฟล์ copy เต็มจาก `index.html` ไม่ได้แชร์โค้ดกัน** — บั๊ก/fix ใน scan logic ของ `index.html` จะไม่ถูกแก้ใน `office.html` โดยอัตโนมัติ ต้องไล่แก้ซ้ำสองที่เอง
9. **ระบบ "User/เจ้าของ asset" ใน Office Scan ทำเสร็จแล้ว (2026-07-22/23)** — เป็น dropdown ที่ 2 ดึงจาก master list จริง (ตาราง `employees`) ตามที่เคยออกแบบคุยไว้ ไม่ใช่ free text แล้ว
10. **เหตุการณ์ push ทับไฟล์ด้วย placeholder/เนื้อหาไม่ครบเคยเกิดซ้ำหลายรอบ (2026-07-21 และซ้ำอีกครั้งใน session 2026-07-22)** — ทั้งสองครั้งเป็นความผิดพลาดตอนเรียก tool push ผ่าน GitHub API (พิมพ์/วางเนื้อหาไม่ครบ หรือพลาดใส่ค่า placeholder แทนเนื้อหาจริง) **แนวทางป้องกัน: หลัง push ทุกครั้งที่แก้ไฟล์สำคัญ (`main.py`, `office.html`, `dashboard.html`) ให้ fetch กลับมาจาก GitHub ทันทีเพื่อ verify ว่าเนื้อหาตรงกับที่ตั้งใจ ก่อนจะถือว่างานเสร็จ** — ควรพิจารณา deploy ผ่าน branch แยก (เช่น `staging`) แล้วค่อย merge เข้า `main` หลังทดสอบแล้วว่าใช้งานได้จริง เพื่อลดความเสี่ยงนี้ในระยะยาว
11. **วิธี debug เวลา browser ฟ้อง "CORS error" ทั้งที่ origin ถูกต้องแล้ว:** อย่าเชื่อข้อความ error ของ browser ทันที — เปิด DevTools → Network tab เช็ค status code จริงของ request ที่ fail ก่อนเสมอ ถ้าเป็น 500 (ไม่ใช่ request ที่ไม่ขึ้นเลย/blocked) แปลว่าเป็น backend exception จริง ไม่ใช่ CORS (Starlette/FastAPI ตอบ unhandled exception เป็น `text/plain "Internal Server Error"` แบบไม่มี CORS header ติดมา ทำให้ browser แจ้งเป็น "Failed to fetch" ที่ดูเหมือน CORS) ให้ไปดู Railway → Deploy Logs หา Python traceback ต่อ
12. **หน้าตา UI ของ `dashboard.html` (v3) — ข้อควรรู้ก่อนแก้:**
   - JS เดิมถูกคงไว้ แก้เพิ่มแบบเฉพาะจุด และ **ทุก element `id` / inline handler เดิมยังอยู่ครบ** (ตรวจด้วยการ diff id/handler ทุกรอบ) — ถ้าจะลบ/เปลี่ยนชื่อ id ต้องไล่ดูโค้ด JS ก่อนเสมอ
   - ชิปสาขา (`#storeChips`, `#storeChipsToggle`) ถูกซ่อนด้วย CSS (`display:none !important`) แต่ยังมีใน DOM เพราะโค้ดเดิมยังเรียกใช้ — ใช้ "สาขาที่ยังเหลือมากที่สุด" หรือช่องค้นหาในส่วน "รายละเอียดรายสาขา" แทน
   - รายการ asset ในหน้า Dashboard แบ่งหน้า (`OVERVIEW_PAGE_SIZE = 50` + ปุ่ม "แสดงเพิ่ม"); เวลาพิมพ์ (`beforeprint`) จะขยายเป็นทุกแถวอัตโนมัติ
   - `renderHomeDashboard()` ถูกเรียกท้าย `renderSummary()` และ `updateUnmatchedBadge()` — คำนิยามตัวเลข: Remaining = total − scanned, Exceptions = missing + damaged + unmatched
   - `_hmSet()` มีแอนิเมชันนับเลขขึ้น (เฉพาะจำนวนเต็ม) และการ์ดมี tilt ตามเมาส์ (เฉพาะอุปกรณ์ที่มี hover) ทั้งสองปิดเองเมื่อตั้ง `prefers-reduced-motion`
13. **หน้า Login ทั้ง 3 หน้า (`index.html`, `office.html`, `dashboard.html`) ไม่ได้แชร์โค้ดกัน** (ต่อยอดจากข้อ 8) — การแก้หน้าตา login หรือฟังก์ชัน `checkApiConnection()` ต้องไล่แก้ซ้ำทั้ง 3 ไฟล์เอง:
   - `checkApiConnection()` เรียก `GET {API}/health` ทุก 30 วินาทีตอนอยู่หน้า login; จุดแดงเป็นปกติเมื่อเปิดไฟล์ผ่าน `file://` (origin `null` โดน CORS)
   - แอพสแกน (`index.html`/`office.html`) ซ่อนภาพ GIF อัตโนมัติเมื่อจอเตี้ยกว่า 640px เพื่อให้ปุ่ม SIGN IN ยังอยู่บนจอเครื่อง Urovo โดยไม่ต้องเลื่อน
   - ถ้าจะเปลี่ยนภาพ ให้ใช้ GIF พื้นโปร่งใส แล้วสร้าง `login_scan.webp` (เติมเฟรมคั่นกลางด้วย optical flow จนได้ ~27fps) + `login_scan_still.png` ให้ตรงกัน; อย่าใช้ภาพที่ตัดพื้นหลังอัตโนมัติ (เคยลองแล้ว ขอบไม่คม)
   - GIF ต้นฉบับมีแค่ 9 เฟรม เฟรมละ 300ms ผู้ใช้ติว่า "กระตุก/เป็นสเต็บ" จึงสร้าง WebP แบบเติมเฟรมแทน (`<picture>` เลือก still → webp → gif ตามลำดับ)

14. **รหัสแผนกกับไฟล์ HR / `employees`:** หน้าพนักงานใน Dashboard และ dropdown แผนกแสดง **รหัส (`department_code`) เป็นหลัก** ถ้าแถวไหนไม่มีรหัสค่อย fallback เป็นชื่อ (`department`); `GET /employees/department/{department}` จับคู่ได้ทั้งรหัสและชื่อ (ไม่สนตัวพิมพ์) — **ไฟล์ HR ที่ import ครั้งถัดไปต้องใช้รหัสใหม่ในช่อง Department Code** (เช่น `640M` ไม่ใช่ `640P`, `680` ไม่ใช่ `68001`, `999CM` แทน `999G`/`999MD`) ไม่งั้นรหัสเก่าจะกลับมา; `assets.department` ใน asset master ว่างทั้งหมด (39,746 แถว ณ 2026-11-09) ถ้า HQ จะ import แผนกของ asset ต้องใช้รหัสใหม่
15. **Sidebar ของ `dashboard.html` ซ่อนอัตโนมัติ (2026-11-09):** บนจอ ≥901px ที่มีเมาส์ (`@media (min-width:901px) and (hover:hover)`) sidebar ถูกซ่อน (`translateX(-102%)`) แล้วเลื่อนเข้าเมื่อเมาส์ไปที่แถบ `.sb-edge` (กว้าง 14px ชิดขอบซ้าย) หรืออยู่บน sidebar เอง เป็น CSS ล้วน ไม่มี JS; จอแคบ/มือถือ/อุปกรณ์สัมผัสยังใช้ layout แถบบนแบบเดิม — ห้ามลบ `<div class="sb-edge">` ใน `#appRoot` (อยู่ก่อน `<nav class="sidebar">` เพราะใช้ sibling selector `~`)
16. **Write off ของ asset ที่ยังไม่เคยสแกน (2026-11-12):** ทำที่ตัว asset master ผ่าน `POST /hq/assets/{asset_id}/write-off` (เฉพาะ `hq_admin`) — ตั้ง `assets.status='disposed'` + เก็บเหตุผล/remark/ผู้ทำ/เวลาใน `write_off_*` แล้ว asset จะหลุดจาก `/hq/assets` (กรอง `status='active'`) จึงหายจาก Asset Summary และ Total ลด; `migration_asset_writeoff.sql` รันใน Neon แล้ว (2026-11-12) — ถ้าตั้ง DB ใหม่ต้องรันก่อน deploy `main.py` ไม่งั้น endpoint 500; `saveDrawer()` ใน `dashboard.html` ใช้เส้นทางนี้เฉพาะเมื่อ `!a.scanId && status==='disposed'` — asset ที่เคยสแกนแล้วยังใช้ `PATCH /hq/scans/{id}` (condition=`disposed`) เหมือนเดิม; สถานะอื่นของ asset ที่ยังไม่สแกนยังบันทึกไม่ได้ (ต้องรอ `POST /scans` + session); ยังไม่มีปุ่มยกเลิก write off/หน้ารายงาน (ย้อนกลับต้อง `UPDATE assets SET status='active' WHERE id=...` ใน Neon)
17. **ย้าย location ของ asset โดย HQ (2026-11-12):** ช่อง Location ใน drawer เดิมไม่เคยถูกส่งไป save (เป็นข้อความอิสระ หายตอนโหลดใหม่) — ตอนนี้เลือกจาก datalist "รหัส — ชื่อสาขา" แล้วเรียก `PATCH /hq/assets/{id}/location` (แก้ `assets.location_code` + `location_override=true`); `buildStoresFromRealAssets()` จัดกลุ่มตามสาขาของ session ที่สแกนเสมอ **ยกเว้น** asset ที่ `location_override=true` ให้ใช้ `location_code` ใน master แทน; `/hq/assets` ส่ง `location_override` ด้วย จึงต้องรัน `migration_asset_location_override.sql` ก่อน deploy (รันแล้ว 2026-11-12) — กรณี master ถูกอยู่แล้วแต่ asset ถูกสแกนที่สาขาอื่น (เช่น master = 0068000 แต่สแกนใน session Office): drawer จะขึ้นข้อความเตือนใต้ช่อง Location และกด Save เพื่อตั้ง `location_override=true` ให้ Dashboard ใช้ตาม master (`drawerMovePending` ใน `dashboard.html`)
18. **Dashboard v4 (2026-11-12, หน้าตา + การ์ดใหม่):** sidebar เป็นไอคอนล้วน 72px บนจอ ≥901px (ชื่อเมนูอยู่ใน `<span class="nav-text">` + `title`/`aria-label`, กด Enter/Space ได้; มือถือยังเป็นแถบบนมีข้อความ; ยังซ่อนอัตโนมัติตามข้อ 15); หน้า Dashboard เพิ่มแถบ % ใต้ KPI, การ์ด "แผนกไม่ตรง" (นับ `deptMismatch`), แถว "ภาพรวมสาขาและทีม" และ "แนวโน้มการสแกน" (`renderHomeTrend()` นับ `scanned_at` ย้อนหลัง 7 วันเทียบ 7 วันก่อนหน้า จาก `homeScanList` + `unmatchedItems`) — ไม่แตะ backend/DB
19. **ชื่อ Asset ยาวในตาราง Asset Summary (2026-11-13):** ตัดด้วย `...` ที่ความกว้าง clamp(160px,16vw,320px) (จอ 1400px ≈ 224px, จอ ≥2000px = 320px) (`.as-cell-name` ใน `renderAssetSummary()`) เพื่อให้คอลัมน์สถานะ/เวลาสแกน/Actions เห็นครบโดยไม่ต้องเลื่อนแนวนอน; ชี้เมาส์ที่ชื่อเพื่อดูชื่อเต็ม (`title`); ตารางในหน้า Overview (`.asset-row`) ตัดด้วยวิธีอื่น ดูข้อ 6.20; dropdown เลือกสาขาในหน้านี้เรียง A–Z (`populateBranchFilter()` ใช้ `localeCompare('en', numeric)`, "ทุกสาขา" อยู่บนสุดเสมอ)
20. **ตารางรายการ Asset ในหน้า Overview (`.asset-row` / `.asset-head`, 2026-11-09 บ่าย):** รายละเอียด/ชื่อ asset, Serial, Location และ Employee แสดงบรรทัดเดียว ตัดด้วย `...` (class `.asset-cell-1l` + `title` แสดงข้อความเต็มเมื่อชี้เมาส์; ใน `@media print` ปิดการตัดเพื่อให้รายงานมีข้อมูลครบ); คอลัมน์ใช้ `minmax(0,Nfr)` (ต้องมี `min-width:0` ไม่งั้นข้อความยาวดันตารางล้น) และ Qty/Status กว้างขึ้นให้ชิดขวา; หัวคอลัมน์ "Department" เปลี่ยนเป็น **"Dept."** (ใน `OVERVIEW_SORT_COLUMNS` — ส่วนหัวคอลัมน์ในไฟล์ export Excel `OVERVIEW_EXPORT_HEADERS_OFFICE` ยังเป็น "Department"); `.content-body` ขยาย `max-width` จาก 1480px เป็น 2400px เพราะ sidebar ซ่อนอัตโนมัติแล้วเนื้อหาควรเต็มจอ
21. **ชิปอุปกรณ์ที่พนักงานถือครอง (2026-11-14, หน้า "พนักงาน"):** แหล่งข้อมูลคือตาราง `employee_holdings` (`migration_employee_holdings.sql` — **ต้องรันใน Neon ก่อน deploy `main.py` และก่อนใช้ปุ่ม Import ถือครอง**) ที่ import จากไฟล์ User Asset List (CSV/TSV ของ HQ: 1 คน = Notebook/PC + Monitor + กระเป๋า) ผ่านปุ่ม "Import ถือครอง" → `POST /hq/employee-holdings/import` (hq_admin; แทนที่ข้อมูลเดิมทั้งชุดด้วย soft-delete `is_active=false`) และ `GET /hq/employee-holdings`; parser อยู่ฝั่ง `dashboard.html` (`parseHoldingsFile()` — แถวหัวแผนกหาจากคอลัมน์ `Computer Name`, PC→`CPU`, อย่างอื่นที่อยู่ช่อง Computer→`Notebook`, กระเป๋าโน้ตบุ๊กไม่นำเข้าเพราะไม่มีเลข Asset); ชิปโชว์เฉพาะที่ไฟล์ระบุว่าถือ **เขียว** = หา Asset ใน Asset Summary เจอ (จับคู่ด้วย Serial ก่อน, ไฟล์ไม่มี Serial ค่อยลองเลข Asset โดยแก้ `COMO`→`COM0`), **แดง** = ตรวจสอบไม่ได้ (ชี้เมาส์ดูเหตุผล); ชื่อในไฟล์จับคู่กับ `employees.full_name` แบบโทเคนทุกตัวต้องอยู่ในชื่อเต็มและเจอคนเดียวเท่านั้น (ชื่อที่จับคู่ไม่ได้ลิสต์ไว้ใต้ตาราง); ข้อมูลในไฟล์เองมี Serial ซ้ำข้ามคน และเลข Asset ที่ไม่มีส่วน SEQ/พิมพ์ผิด จึงเป็นเรื่องปกติที่หลายชิปเป็นแดง — แก้ที่ไฟล์ต้นทางหรือ Asset Summary แล้ว import ใหม่
22. **กฎอุปกรณ์อายุ 5 ปี + สรุปรายแผนก (2026-11-14, หน้า "พนักงาน"):** ชิปอุปกรณ์มีตัวบอกอายุ — **ม่วง `5+`** = ซื้อมาครบ 5 ปีแล้ว (ควรเปลี่ยน), **ส้ม `5`** = จะครบ 5 ปีภายในปีปฏิทินนี้ (วางแผนเปลี่ยน) (`EMP_AGE_YEARS`, `deviceAgeInfo()` ใน `dashboard.html`); วันที่ซื้อใช้ `assets.purchase_date` ของ Asset ที่จับคู่เจอ (ต้องไหลผ่าน `purchaseDate` ใน item ของ `buildStoresFromRealAssets()`) ถ้าไม่เจอใช้ปี-เดือนที่ฝังในเลข Asset (`COM012022090002` = 2022-09, `purchaseDateFromAssetCode()`) ถ้าไม่มีทั้งคู่ = ไม่ทราบอายุ (ไม่แสดงตัวบอก); มีตัวกรอง "อายุอุปกรณ์" (`#empAgeFilter`) และการ์ดสรุปรายแผนก (`#empDeptGrid`: จำนวนพนักงาน active + กี่คนถือเครื่องเกิน/ครบ 5 ปี, ชี้เมาส์ดูชื่อ, คลิกเพื่อกรองแผนก)
23. **แผนงานอนาคต (ยังไม่ได้ทำ — ผู้ใช้แจ้งทิศทางไว้ 2026-11-14):** ต่อยอดจากข้อมูลถือครองไปเป็นการ **ส่งมอบ Asset ให้พนักงานใหม่ / รับคืนจากพนักงานที่ลาออก** พร้อมเปิด-ปิด AD, Email, เบอร์โทร โดยอ้างอิงวันที่ HR แจ้งเข้า-ออกเป็นหลัก และต้องมี **รายงานที่มีลายเซ็นหัวหน้า (Approve)**; สิ่งที่ต้องเตรียมก่อนทำ: ตาราง `employees` ยังไม่มีวันเริ่มงาน/วันลาออก, `employee_holdings` ผูกด้วยชื่อ (ควรผูกด้วย `employee_id` และมี asset จริง ไม่ใช่แค่ serial), ต้องมีตารางคำขอ/การอนุมัติ (ผู้ขอ, หัวหน้าที่อนุมัติ, วันที่, สถานะ) และรูปแบบรายงานพิมพ์ที่มีช่องลายเซ็น (มีแม่แบบ `.sig-block` ในหน้า Overview ให้ดูได้)
24. **สมุดบันทึกการถือครอง (ledger) + ปุ่ม Import เดียว (2026-11-14, หน้า "พนักงาน"):** `employee_holdings` เปลี่ยนเป็น ledger — 1 แถว = 1 ช่วงที่คนหนึ่งถืออุปกรณ์หนึ่งชิ้น (`ended_at` NULL = ถืออยู่); **ต้องรัน `migration_holdings_ledger.sql` ใน Neon ก่อน deploy `main.py`** (ตรวจ cols = 17) ไม่งั้น `/hq/employee-holdings*` 500; ปุ่ม `⬆ Import` ปุ่มเดียวเปิดหน้าต่างเลือกชนิดไฟล์ (พนักงาน HR / ถือครอง); Import ถือครอง = merge ไม่ลบเดิม (คนเดิมไม่เปลี่ยน, คนใหม่ = โอนอัตโนมัติ); คีย์อุปกรณ์ `asset_key` = Serial ก่อน ไม่งั้นเลข Asset ที่มี `SEQ` (เลขที่ไม่มี SEQ ใช้ร่วมหลายเครื่อง จึงไม่ใช้เป็นคีย์); วันเริ่มถือของแถวจากไฟล์ = ปี-เดือนในรหัส Asset (`purchaseDateFromAssetCode`) ถ้าไม่มีใช้ `purchase_date` ของ Asset Summary; คลิกชื่อพนักงาน → drawer (`#empDrawer`: กำลังถือ/ประวัติ/รับต่อจาก/ส่งต่อให้/รับคืน/มอบ Asset ให้คนนี้); drawer ของ Asset มีกลุ่ม "ผู้ถือครอง" (`#holderGroup`, `renderAssetHolders()`); endpoints เพิ่ม: `POST /hq/employee-holdings/assign`, `POST /hq/employee-holdings/{id}/return`

---

## 7. วิธีรัน / Build / Deploy

โปรเจกต์นี้ **ไม่มี build step** และไม่มี local dev server แบบ hot-reload พิเศษ

### รัน Backend ในเครื่อง (local)
```bash
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```
Environment variables ที่ backend ต้องการ:
- `DATABASE_URL` — connection string ของ Neon Postgres
- `CLOUDINARY_CLOUD_NAME`, `CLOUDINARY_API_KEY`, `CLOUDINARY_API_SECRET` — สำหรับ endpoint ลบ/อัปโหลดรูปฝั่ง HQ เท่านั้น

### รัน Frontend ในเครื่อง (local)
เปิด `index.html`/`office.html`/`dashboard.html` ตรงๆ ในเบราว์เซอร์ได้ แต่ต้องแก้ตัวแปร `API`/`API_BASE` ให้ชี้ไปที่ backend ที่รันอยู่ก่อนเสมอ — **ถ้าเปิดผ่าน `file://` โดยตรง จะโดน CORS บล็อก (origin `null` ไม่อยู่ใน allow list) ให้รันผ่าน local server แทน เช่น `python3 -m http.server 8000` แล้วเปิด `http://localhost:8000/...`**

### Deploy Backend (Railway)
1. Push โค้ดขึ้น branch `main` ของ repo นี้ → Railway auto-deploy (ตั้งค่าไว้แล้วผ่าน `railway.toml`)
2. **ถ้าโค้ดใหม่อ้างถึง column/ตารางใหม่ ต้องรัน SQL migration ใน Neon SQL editor ก่อน push เสมอ แล้วต้องยืนยันว่ารันสำเร็จจริง** (เช่น `SELECT` เช็คว่า column/ตารางมีอยู่จริง) — ห้ามข้ามขั้นตอนนี้
3. ตรวจสอบว่า deploy สำเร็จ: `GET /health` ควรคืน `{"status":"ok","assets_in_db":...}`, `GET /docs` แสดง Swagger UI
4. ถ้าเป็นฐานข้อมูลใหม่ (ครั้งแรก) ต้องรัน schema ทั้งหมดจาก `docs/database.md` ก่อน แล้วรัน user-seeding script (ดู Section 9 — Archive สำหรับโค้ดเต็มของ `seed_users.py` เดิม)

### Deploy Frontend (GitHub Pages — repo นี้เอง)
- Push `index.html` / `office.html` / `dashboard.html` ขึ้น branch `main` → GitHub Pages serve อัตโนมัติที่ `https://fixasset.batathai.com`
- **ต้อง fetch ไฟล์กลับมาจาก GitHub เพื่อ verify เนื้อหาหลัง push ทุกครั้ง** (ดูเหตุผลในข้อ 6.10)

### Health Check
| สิ่งที่เช็ค | URL |
|---|---|
| API ทำงานหรือไม่ | `https://bata-asset-api-production.up.railway.app/health` |
| Endpoint ทั้งหมด (Swagger) | `https://bata-asset-api-production.up.railway.app/docs` |
| Scanner App (สาขา) | `https://fixasset.batathai.com/` |
| Office Scan App | `https://fixasset.batathai.com/office.html` |
| HQ Dashboard | `https://fixasset.batathai.com/dashboard.html` |

### Login ทดสอบ
| Employee ID | Password | Role |
|---|---|---|
| `Acc01` / `Acc02` | `bata1234` | Account |
| `Audit01` | `bata1234` | auditor |
| `Admin01` | `admin999` | hq_admin |

---

## 8. Changelog

- **2026-07-18** — สร้างไฟล์นี้ครั้งแรก, ลบเอกสารล้าสมัยออกจาก `docs/`
- **2026-07-20** — เพิ่ม Bata Loading popup, คอลัมน์ Serial ใน Overview, filter คลิกได้ในหน้า Summary
- **2026-07-21** — เพิ่มฟีเจอร์ Office Asset Scan เวอร์ชันแรก (`office.html`, คอลัมน์ `department` แบบ free text) — มีเหตุการณ์ push ทับด้วย placeholder หลายครั้งระหว่างทำ (ดู section 6.10)
- **2026-07-22/23 — Office Asset Scan v2 + ระบบพนักงานเต็มรูปแบบ:**
  - เพิ่มตาราง `employees`, `employee_import_batches` (`migration_employees.sql`) — import จริงจากไฟล์ Excel HR แล้ว 84 คน
  - เพิ่ม endpoints: `GET /employees/department/{department}`, `GET/PATCH/DELETE /hq/employees[/{id}]`, `POST /hq/employees/import/preview|confirm`
  - แก้ `POST /scans`, `PATCH /scans`, `POST /unmatched` ให้รับ-บันทึก `assigned_employee_id`/`assigned_employee_name`
  - `office.html`: เปลี่ยนช่องแผนกจาก free text → `<select>` fixed list 11 ค่า, เพิ่ม dropdown "มอบหมายให้พนักงาน" ครบทั้ง 3 การ์ด (matched/serial-check/unmatched)
  - `dashboard.html`: เพิ่มเมนู "พนักงาน" (list/search/filter/import popup/deactivate)
  - **บั๊กใหญ่ที่พบและแก้:** `assets.department` (จาก entry 2026-07-21) ไม่เคยถูกรันจริงใน Production DB มาก่อน ทำให้ `/hq/assets` พัง 500 error โดยแสดงผลเป็น "CORS error" ที่เข้าใจผิดง่าย (ดู section 6.11 วิธี debug) — แก้แล้วด้วย `migration_office_department.sql` (รันแล้ว, เนื้อหาเก็บใน Section 9)
  - เพิ่ม CORS origins สำหรับทดสอบผ่าน local server
  - ลบ `seed_users.py`, `migration_scan_delete_log.sql`, `migration_office_department.sql` ออกจาก repo (รันเสร็จสิ้นแล้ว ไม่มีโค้ดอ้างอิงตอน runtime) — เนื้อหาเก็บสำรองไว้ที่ Section 9
- **2026-11-05 — UI Redesign: Dashboard + หน้า Login (หน้าตาเท่านั้น):**
  - `dashboard.html` UI v3 (commit `7d5f401`) → รอบ 2: ชิปสาขาพับได้, แบ่งหน้ารายการ asset, `d9c5cf1` → รอบ 3: หน้า Dashboard แบบ KPI + attention center, `d9f95ad` → ปรับแบรนด์เป็น "Bata Fix Asset", `002f97d` → แอนิเมชันการ์ดตัวเลข/วงแหวนความคืบหน้า, `46d31b5` → เอาบรรทัด URL ของ API ออกจากหน้า login, เพิ่มจุดสถานะการเชื่อมต่อ (`344928d`)
  - หน้า Login: ลองฉาก 3D CSS (กล่อง/สาขา Bata) แล้วผู้ใช้ไม่เอา เลยเอาออก (`9c1b864`) → ใช้ GIF ภาพพนักงานสแกนที่ผู้ใช้ทำมาเอง (`79e83c3`) → ใช้ GIF เดียวกันกับ `index.html`/`office.html` พร้อมจุดสถานะการเชื่อมต่อ (`faec384`) → เปลี่ยนเป็น `login_scan.webp` แบบเติมเฟรมให้เคลื่อนไหวนุ่มขึ้น (GIF เดิมกระตุก)
  - ข้อความฝั่งแดงหน้า login ของ Dashboard เปลี่ยนเป็น "ระบบตรวจนับสินทรัพย์ถาวร / Fixed Asset Audit · Bata Thailand" (ผู้ใช้ไม่ชอบสโลแกนแบบเดิม)
  - เพิ่มไฟล์ `login_scan.gif`, `login_scan.webp`, `login_scan_still.png` — **ไม่มีการเปลี่ยน `main.py`, schema หรือฐานข้อมูล**
  - Commit ก่อนเริ่มรอบนี้ (ใช้ย้อนกลับได้): `db5ef4e`; ก่อนรอบแก้ login ของแอพสแกน: `79e83c3`
- **2026-11-09 — เปลี่ยนแผนกเป็นรหัสแผนก 12 ค่า (แสดงเฉพาะรหัส):**
  - `office.html` + `dashboard.html`: `OFFICE_DEPARTMENTS` จาก 11 ชื่อ → 12 รหัส; หน้าพนักงานใน Dashboard แสดง/กรองด้วยรหัส
  - `main.py`: `employees_by_department` จับคู่ทั้ง `department_code` และ `department` (UPPER/TRIM), `departments_found` และการเรียง `/hq/employees` ใช้รหัสก่อน
  - ฐานข้อมูล: รัน `migration_department_codes.sql` แล้วใน Neon (ตรวจผลตรง: 500R=18, 600ML=4, 630=6, 640M=16, 680=1, 999CM=3, 999FI=17, 999HR=5, 999IA=7, 999IT=6, ว่าง=1) — แผนก Procurement ถูกยกเลิก (พนักงาน 1 คนเหลือเป็น "ไม่มีแผนก"), "Country Manager" → `999CM`
  - เพิ่มข้อ 6.14 เรื่องรหัสในไฟล์ HR; แก้ข้อ 5.13 เป็นรายการ 12 รหัส

- **2026-11-09 (บ่าย)** — `dashboard.html`: sidebar ซ่อนอัตโนมัติ เลื่อนเข้า/ออกเมื่อเมาส์ไปขอบซ้ายสุด (ดูข้อ 6.15) — หน้าตาเท่านั้น ไม่แตะ backend/DB
- **2026-11-12** — Write off asset ที่ยังไม่เคยสแกน: เพิ่ม `POST /hq/assets/{asset_id}/write-off` (`main.py`), `migration_asset_writeoff.sql` (รันแล้ว), และแก้ `saveDrawer()` ใน `dashboard.html` (ดูข้อ 6.16) — เดิมกด Save แล้วขึ้น toast "Asset นี้ยังไม่เคยถูกสแกน…รอเชื่อม POST /scans"
- **2026-11-12 (บ่าย)** — ย้าย location ของ asset โดย HQ (`PATCH /hq/assets/{id}/location`, `migration_asset_location_override.sql` รันแล้ว, ดูข้อ 6.17) และ Dashboard v4 (ดูข้อ 6.18)
- **2026-11-09 (บ่ายแก่)** — `dashboard.html`: ตาราง asset หน้า Overview ตัดรายละเอียดเป็นบรรทัดเดียว (`...`), เปลี่ยนหัวคอลัมน์เป็น "Dept.", ปรับคอลัมน์ Qty/Status, ขยายความกว้างเนื้อหาเต็มจอ (ดูข้อ 6.20) — หน้าตาเท่านั้น ไม่แตะ backend/DB
- **2026-11-14** — หน้า "พนักงาน": ชิปอุปกรณ์ที่ถือครอง (Notebook/CPU/Monitor เขียว/แดง) + ปุ่ม Import ถือครอง, ตาราง `employee_holdings`, endpoints `/hq/employee-holdings` (ดูข้อ 6.21)
- **2026-11-14 (เย็น)** — ปุ่ม Import เดียว + ledger การถือครอง + drawer พนักงาน + ประวัติผู้ถือใน drawer Asset (ดูข้อ 6.24) — `migration_holdings_ledger.sql` ยังไม่ได้รัน

---

## 9. Archive — เนื้อหาไฟล์ที่ถูกลบออกจาก repo (เก็บไว้อ้างอิง)

### 9.1 `seed_users.py` (ลบ 2026-07-23)
สคริปต์รันครั้งเดียวตอน setup ฐานข้อมูลใหม่ เพื่อสร้าง user ทดสอบเริ่มต้น + branch ตัวอย่าง

```python
"""สร้าง user สำหรับทดสอบ — รันครั้งเดียว"""
import psycopg2, hashlib, os
from dotenv import load_dotenv

load_dotenv()

USERS = [
    ("Acc01", "bata1234", "Account Team 1", "Account",  None),
    ("Acc02", "bata1234", "Account Team 2", "Account",  None),
    ("Audit01", "bata1234", "Admin Audit Team 1", "auditor",  None),
    ("Admin01","admin999", "HQ Admin",     "hq_admin", None),
]

def hash_pw(pw): return hashlib.sha256(pw.encode()).hexdigest()

conn = psycopg2.connect(os.getenv("DATABASE_URL"))
cur  = conn.cursor()

# สร้าง branch ตัวอย่าง ถ้ายังไม่มี
for branch_id in ["0054011","0099999","0068000"]:
    cur.execute(
        "INSERT INTO branches (id, name) VALUES (%s,%s) ON CONFLICT (id) DO NOTHING",
        (branch_id, f"Branch {branch_id}")
    )

for emp_id, pw, name, role, branch in USERS:
    cur.execute("""
        INSERT INTO users (email, password_hash, full_name, role, branch_id)
        VALUES (%s,%s,%s,%s,%s)
        ON CONFLICT (email) DO UPDATE SET password_hash=EXCLUDED.password_hash
    """, (emp_id, hash_pw(pw), name, role, branch))
    print(f"  ✓ {emp_id} / {pw} ({role})")

conn.commit()
cur.close()
conn.close()
print("\nSeed complete")
```

### 9.2 `migration_scan_delete_log.sql` (ลบ 2026-07-23, รันสำเร็จไปแล้วก่อนหน้านี้)
สร้างตาราง `scan_delete_logs` — audit trail ทุกครั้งที่มีการลบ scan_logs แบบถาวร

```sql
-- Migration: scan_delete_logs
CREATE TABLE IF NOT EXISTS scan_delete_logs (
  id              uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  scan_log_id     integer,
  session_id      integer,
  branch_id       text,
  asset_code      text,
  asset_name      text,
  qr_key          text,
  deleted_by      text,
  deleted_by_role text,
  source          text,
  deleted_at      timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_scan_delete_logs_branch  ON scan_delete_logs(branch_id);
CREATE INDEX IF NOT EXISTS idx_scan_delete_logs_session ON scan_delete_logs(session_id);
CREATE INDEX IF NOT EXISTS idx_scan_delete_logs_time    ON scan_delete_logs(deleted_at);
```

### 9.3 `migration_office_department.sql` (ลบ 2026-07-23, รันสำเร็จไปแล้ว 2026-07-23)
เพิ่มคอลัมน์ `department` ที่ `main.py` อ้างอิงมาตั้งแต่ 2026-07-21 แต่ไม่เคยถูกรันจริง (ดู section 6.4 และ 8)

```sql
-- migration_office_department.sql
ALTER TABLE assets ADD COLUMN IF NOT EXISTS department TEXT;

ALTER TABLE scan_logs ADD COLUMN IF NOT EXISTS scanned_department TEXT;
ALTER TABLE scan_logs ADD COLUMN IF NOT EXISTS dept_mismatch BOOLEAN DEFAULT false;
ALTER TABLE scan_logs ADD COLUMN IF NOT EXISTS dept_note TEXT;

ALTER TABLE unmatched_assets ADD COLUMN IF NOT EXISTS department_guess TEXT;
```
