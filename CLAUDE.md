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
- คอมมิตล่าสุดใน repo นี้ (branch `main`): **2026-07-23**
- **2026-07-21 — Office Asset Scan (เวอร์ชันแรก):** หน้าใหม่ `office.html` (clone จาก `index.html`) + คอลัมน์ `department` แบบ free text
- **2026-07-22/23 — Office Asset Scan v2 + ระบบพนักงาน (เพิ่มเข้ามาวันนี้ — ดู section 8 รายละเอียดเต็ม):**
  - เปลี่ยนช่องแผนกใน `office.html` จาก free text → `<select>` แบบ fixed list 11 แผนก (กัน typo)
  - เพิ่มตาราง `employees` (import จากไฟล์ Excel HR, 84 คน) + หน้าจัดการพนักงานใน `dashboard.html` (เมนู "พนักงาน" — list/search/filter/import/deactivate)
  - เพิ่ม dropdown ที่ 2 "มอบหมายให้พนักงาน" ใน `office.html` — เลือกแผนกก่อน ระบบดึงรายชื่อพนักงานเฉพาะแผนกนั้นมาให้เลือก ครอบคลุมทั้งการ์ด matched, serial-check, และ unmatched
  - **แก้บั๊กใหญ่ที่เจอระหว่างทาง:** `assets.department` (และคอลัมน์ที่เกี่ยวข้องใน `scan_logs`/`unmatched_assets`) ที่ระบุไว้ใน entry 2026-07-21 ว่าจะเพิ่ม **ไม่เคยถูกรันจริงในฐานข้อมูล Production** ทำให้ `/hq/assets` (และทุก endpoint ที่ query `a.department`) พัง 500 error มานานโดยไม่มีใครรู้ตัว — อาการที่เห็นคือ browser แจ้ง "CORS error" (เข้าใจผิดได้ง่ายมาก เพราะ FastAPI/Starlette ตอบ unhandled exception เป็น generic `text/plain "Internal Server Error"` ที่ไม่มี CORS header ติดมา) สาเหตุจริงคือ column ไม่มีอยู่ ไม่ใช่ CORS — แก้แล้วโดยรัน migration ที่ค้างไว้จริงๆ ใน Neon (ดู section 6 ข้อ 11 เรื่องวิธี debug อาการนี้)
  - เพิ่ม CORS origin สำหรับทดสอบผ่าน local server (`localhost:8000`, `:5500`, `:3000`)
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
├── CNAME                              # Custom domain ของ GitHub Pages: fixasset.batathai.com
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
13. **แผนกของ Office เป็น fixed list 11 ค่าตายตัวใน `office.html`** (`const OFFICE_DEPARTMENTS`) ไม่ได้ query จาก DB แบบ dynamic — ถ้าจะเพิ่ม/ลบแผนก ต้องแก้ array นี้ตรงๆ ใน `office.html`

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
