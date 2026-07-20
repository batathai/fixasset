# CLAUDE.md

คู่มือสำหรับ Claude (หรือ AI/นักพัฒนาคนอื่น) ที่จะเข้ามาแก้ไขโค้ดใน repo นี้ อ่านไฟล์นี้ก่อนเริ่มแก้ไขทุกครั้ง

---

## 1. ภาพรวมโปรเจกต์

**Bata Fixed Asset Audit System** — ระบบตรวจนับสินทรัพย์ถาวร (fixed asset) ของ Bata Thailand

ใช้แก้ปัญหาการตรวจนับสินทรัพย์ (คอมพิวเตอร์, อุปกรณ์, เฟอร์นิเจอร์ ฯลฯ) ตามสาขาต่างๆ ที่แต่เดิมทำด้วยกระดาษ/Excel โดยให้ทีม audit ใช้เครื่องสแกนบาร์โค้ด (Urovo) หรือคีย์บอร์ดกรอกรหัสสินทรัพย์ทีละชิ้นที่หน้างาน แล้วระบบจะ:

- เทียบกับ "master data" ของสินทรัพย์ที่ HQ import เข้ามา ว่า **พบ (matched)**, **serial ไม่ตรง (serial mismatch)**, หรือ **ไม่รู้จัก (unmatched)**
- ส่งผลขึ้น HQ Dashboard แบบเกือบ realtime ให้ผู้ดูแลส่วนกลางติดตามความคืบหน้าทุกสาขา ตรวจสอบ/อนุมัติ/ส่งกลับแก้ไข และ export รายงาน Excel ที่มีตราสินค้า (branded) ได้

ระบบมี 2 ฝั่งผู้ใช้งานหลัก: **พนักงานสาขา/ทีม audit** (ใช้ `index.html` สแกนของจริง) และ **admin ที่ HQ** (ใช้ `dashboard.html` ดูภาพรวมและจัดการข้อมูล)

---

## 2. สถานะปัจจุบัน

- เวอร์ชัน backend ปัจจุบัน (ตาม `main.py`): **1.2.0**, ผ่านการพัฒนาไปแล้วถึง **v0.8** ตาม `docs/changelog.md`
- ระบบใช้งานจริงอยู่แล้ว (production) มี login จริง มี asset master import จริง ไม่ใช่ prototype
- คอมมิตล่าสุดใน repo นี้ (branch `main`): **2026-07-20**
- มีการแก้ไข "6 ข้อ" ล่าสุดที่ยังไม่ได้สรุปลง `docs/changelog.md` อย่างเป็นทางการ (ดูรายละเอียดใน `CHANGES_README.md` ที่ root) ได้แก่: ระบบรอบตรวจแบบคำนวณอัตโนมัติ, PDF log อัตโนมัติตอนปิดงาน, แก้บั๊กลบข้อมูลทั้งฝั่งแอพสแกนและ Dashboard ให้ลบที่ server จริง, เพิ่ม audit log การลบ (`scan_delete_logs`), และจำ login ข้าม F5
- **ยังไม่ได้แก้ (ทราบปัญหาแล้ว แต่ยังไม่ทำ):** auth session เก็บใน memory ของ backend (ดูหัวข้อ 6)

> ⚠️ **สำคัญ:** เดิม `docs/` มีเอกสารออกแบบรุ่นแรกๆ ที่ไม่ตรงกับโค้ดจริงอยู่หลายไฟล์ (`README.md`, `architecture.md`, `API.md`, `FLOW.md`, `deployment.md`) แต่ถูกลบออกไปแล้วเมื่อ 2026-07-18 (ดูหัวข้อ "จุดที่ต้องระวัง" ข้อ 1) ตอนนี้ `docs/` เหลือแค่ไฟล์ที่ตรงกับโค้ดจริง (`database.md`, `changelog.md`) — ถ้าไม่แน่ใจเรื่อง endpoint ให้ตรวจกับ `main.py` เสมอ

---

## 3. โครงสร้างไฟล์/โฟลเดอร์หลัก

```
/
├── main.py                        # Backend ทั้งหมด (FastAPI, ไฟล์เดียว ~1,900 บรรทัด) deploy บน Railway
├── requirements.txt                # Python dependencies ของ backend
├── Procfile                        # คำสั่ง start ของ Railway/Heroku-style (uvicorn)
├── railway.toml                    # Railway build/deploy config (Nixpacks)
├── seed_users.py                   # Script รันครั้งเดียวเพื่อสร้าง user/สาขาทดสอบเริ่มต้น
├── migration_scan_delete_log.sql   # Migration SQL ล่าสุด (ตาราง scan_delete_logs) ต้องรันเองใน Neon ก่อน deploy main.py เวอร์ชันที่ใช้ตารางนี้
├── index.html                      # Frontend: แอพสแกนหน้าสาขา (static, ไฟล์เดียว, ~123KB) host บน GitHub Pages
├── dashboard.html                  # Frontend: HQ Dashboard (static, ไฟล์เดียว, ~144KB) host บน GitHub Pages
├── CNAME                           # Custom domain ของ GitHub Pages: fixasset.batathai.com
├── bata_logo.png                   # โลโก้ที่ใช้ในหน้าเว็บ
├── CHANGES_README.md               # สรุปแก้ไข "6 ข้อ" ล่าสุด (ใหม่กว่า docs/changelog.md — ยังไม่ถูกรวมเข้า changelog อย่างเป็นทางการ)
└── docs/
    ├── database.md        # Schema ฐานข้อมูลจริง + ประวัติการแก้ schema — ตรงกับปัจจุบันที่สุด อัปเดตล่าสุด 2026-06-30
    └── changelog.md       # ประวัติการพัฒนาระบบตั้งแต่ v0.1–v0.8
```

> **หมายเหตุ (2026-07-18):** เดิม `docs/` มีไฟล์ `README.md`, `architecture.md`, `API.md`, `deployment.md`, `FLOW.md` ด้วย แต่ถูกลบออกแล้วเพราะเป็นเอกสารออกแบบรุ่นแรกๆ ที่ไม่ตรงกับโค้ดจริง (เช่น บอกว่า scanner ใช้ `html5-qrcode` กล้อง ทั้งที่จริงใช้เครื่องสแกน Urovo, บอกว่ารูปเก็บใน Supabase Storage ทั้งที่จริงใช้ Cloudinary) เนื้อหาที่ยังใช้ได้ถูกย้าย/สรุปมาไว้ใน `CLAUDE.md` ฉบับนี้แล้ว ถ้าต้องการ endpoint reference แบบละเอียด ให้ดูจาก `main.py` โดยตรง หรือเปิด Swagger UI ที่ `/docs` ของ backend ที่ deploy จริง

**ไม่มีโฟลเดอร์ `src/`, ไม่มี build step, ไม่มี package.json** — ทั้งหมดเป็นไฟล์ static/สคริปต์เดี่ยวๆ ตามเจตนาการออกแบบ (ดูข้อ 5)

---

## 4. Tech Stack

**Backend**
- Python + **FastAPI** (`main.py` ไฟล์เดียว ไม่มีการแยก router/module)
- **psycopg2** เชื่อมต่อ Postgres โดยตรง (ไม่มี ORM)
- Deploy บน **Railway** (Nixpacks, auto-deploy ทุกครั้งที่ push ขึ้น branch `main`)
- Auth: token แบบสุ่ม (`secrets.token_hex`) เก็บใน dict ในหน่วยความจำ (`sessions = {}`) — **ไม่ใช่ JWT** และไม่ persist
- Password hash: SHA-256 ธรรมดา (ไม่ใช่ bcrypt/argon2 แม้เอกสารบางที่จะบอกว่าเปลี่ยนมาใช้ bcrypt แล้วก็ตาม — ของจริงในโค้ดคือ `hashlib.sha256`)
- Excel: `openpyxl` (อ่าน .xlsx + สร้างไฟล์ export ที่มีสไตล์), `xlrd` (อ่าน .xls เก่า)
- รูปภาพ: อัปโหลดตรงไป **Cloudinary** จาก client (unsigned upload preset `bata_audit`, cloud `dhpwh4io1`) ฝั่ง backend ใช้ signed API (`CLOUDINARY_CLOUD_NAME/API_KEY/API_SECRET`) สำหรับลบรูปและอัปโหลดรูปจากหน้า HQ

**Database**
- **Postgres บน Neon** (`neon.tech`) — ไม่มี auto-migration ตอน startup ต้องรัน SQL เองผ่าน Neon SQL editor ทุกครั้งที่ schema เปลี่ยน

**Frontend**
- **Vanilla HTML/CSS/JavaScript ล้วน ไม่มี framework** ไม่มี build step, ไฟล์เดียวจบต่อหน้า
- ฟอนต์: Barlow, Barlow Condensed, DM Mono (Google Fonts)
- Input หลักของแอพสแกน: **เครื่องสแกนบาร์โค้ด Urovo (HID keyboard emulation)** ดักจับด้วย `keydown` listener ใน `initUrovoScanner()` — ไม่ได้ใช้กล้องอ่าน QR (`html5-qrcode`) แต่อย่างใด
- เก็บ state ฝั่ง client ด้วย `localStorage` (token, session ที่เลือกไว้, offline queue)
- Export ฝั่ง dashboard: `xlsx` (SheetJS, จาก cdnjs) สำหรับ export ง่ายๆ, ส่วน export "branded" (มีโลโก้/สี Bata) ให้ backend สร้างไฟล์ด้วย `openpyxl` แล้วส่งกลับผ่าน `/hq/export/excel`
- Host: **GitHub Pages** ของ repo นี้เอง (`fixasset`) ผ่าน custom domain `fixasset.batathai.com` (ดูไฟล์ `CNAME`)

---

## 5. เหตุผลการออกแบบสำคัญที่ควรรู้ก่อนแก้โค้ด

1. **Frontend ห้ามต่อฐานข้อมูลตรง** — ทุกการเข้าถึงข้อมูลต้องผ่าน backend API ที่มีการตรวจสอบสิทธิ์ (`Authorization: Bearer <token>`) เพื่อกัน dev tools ดึงข้อมูลออกจาก DB ตรงๆ
2. **รองรับ asset ที่ไม่มีใน master (`unmatched_assets`)** — เพราะข้อมูล asset master ที่ import จาก HQ อาจไม่ครบ 100% ระบบจึง "รับของที่ไม่รู้จักไว้ก่อน" แทนที่จะปฏิเสธการสแกน แล้วให้ HQ reconcile ทีหลังผ่าน `/hq/unmatched`
3. **แยก `scan_logs` และ `serial_mismatches`** — เพื่อแยกกรณี asset ที่พบตรงกับ master ออกจากกรณีพบ asset แต่ serial ไม่ตรง (เช่น มีการสลับเครื่อง) ซึ่งต้องให้ HQ ตรวจเพิ่ม
4. **Import batch + soft-delete สำหรับ Undo import** — ทุกแถวที่ import จากไฟล์เดียวกัน tag ด้วย `import_batch_id` เดียวกัน การ undo คือ set `is_active = false` เท่านั้น (ไม่ hard delete) เพื่อไม่กระทบข้อมูลเดิม/scan ที่เกิดไปแล้ว — **ทุก query ที่ดึง asset ต้องกรอง `COALESCE(is_active, true) = true` เสมอ ไม่งั้น asset ที่ถูก undo จะโผล่กลับมา**
5. **Map รหัสสถานะจาก Excel ก่อนเข้า DB เสมอ** — ไฟล์ Excel ต้นทางเก็บสถานะเป็นรหัสย่อ (`A`/`D`/`T`/`M`) แต่ query ทุกหน้ากรองด้วยคำเต็ม (`status = 'active'`) ต้องผ่าน `_STATUS_CODE_MAP` ก่อนเสมอ ห้ามยัดรหัสดิบเข้า DB
6. **แปลงวันที่จาก Excel ผ่าน `_parse_thai_date_string()` เสมอ** — ไฟล์ Excel เก็บวันที่เป็น text รูปแบบ `DD/MM/YYYY` (บางครั้งเป็น พ.ศ.) ไม่ใช่ Excel date serial ถ้าไม่แปลงก่อน Postgres จะตีความผิดเป็น MM/DD/YYYY แล้ว error
7. **แก้ไข scan log ที่มีอยู่แล้วต้องใช้ `PATCH /scans` (by qr_key) ไม่ใช่ยิง `POST /scans` ซ้ำ** — เพราะ `POST /scans` มี guard กันสแกนซ้ำ (`already_scanned`, 409) ถ้าพยายาม POST ซ้ำเพื่อ "เพิ่มรูป/remark ทีหลัง" จะโดน 409 และข้อมูลใหม่หายไปเงียบๆ
8. **ลบ scan log ต้องบันทึก audit log ก่อนลบจริงเสมอ** — ผ่านฟังก์ชัน `_record_scan_delete()` insert เข้า `scan_delete_logs` ก่อน `DELETE` ทุกครั้ง (ทั้งจากฝั่ง HQ และฝั่งสาขา) เพื่อให้มี audit trail การลบแบบถาวร (hard delete)
9. **สาขาลบ/แก้ไข scan ได้เฉพาะตอน session ยังไม่ปิด (`status != 'done'`)** — ถ้าปิดงานแล้วต้องให้ HQ จัดการแทน (ผ่าน `/hq/scans/{id}`) เพื่อให้มี oversight
10. **Schema change ทุกครั้งต้อง apply ผ่าน Neon SQL editor เอง** — ไม่มี auto-migration ตอน backend startup เป็น convention ของโปรเจกต์นี้มาตั้งแต่ต้น (ดู `docs/database.md` และ comment ใน `migration_scan_delete_log.sql`)
11. **ทำไมไม่มี framework/build step ฝั่ง frontend** — เลือกความเรียบง่ายในการ deploy (แค่ upload ไฟล์ .html ขึ้น GitHub Pages) เพราะทีมงานเล็กและต้องการ iterate เร็ว แลกกับการที่ไฟล์ index.html/dashboard.html ใหญ่มาก (100KB+) และแก้ยากขึ้นเรื่อยๆ

---

## 6. จุดที่ต้องระวัง / Known Issues

1. **เอกสารเก่าที่เคยไม่ตรงกับโค้ดจริงถูกลบไปแล้ว (2026-07-18)** — `docs/architecture.md`, `docs/README.md`, `docs/API.md`, `docs/FLOW.md`, `docs/deployment.md` เคยมีจุดที่ล้าสมัย (เช่น บอกว่า scanner ใช้กล้อง `html5-qrcode` ทั้งที่จริงใช้เครื่องสแกน Urovo, บอกว่ารูปเก็บใน Supabase Storage ทั้งที่จริงใช้ Cloudinary) จึงถูกลบออกจาก repo แล้วเพื่อไม่ให้สับสน เนื้อหาที่ยังถูกต้องถูกสรุปไว้ใน `CLAUDE.md` ฉบับนี้แทน — **ถ้าจะเขียนเอกสารเพิ่มในอนาคต ให้ยึด `main.py`/`index.html`/`dashboard.html` เป็นความจริงเสมอ อย่าคัดลอกจากเอกสารเก่าที่อาจ outdated โดยไม่ตรวจกับโค้ดก่อน**
2. **Auth session เก็บใน memory (`sessions = {}` ใน `main.py`)** — ถ้า Railway restart/redeploy token ของทุกคนจะหลุดพร้อมกันหมดทันที ต่อให้ frontend จำ token ไว้ใน `localStorage` แล้วก็ตาม (เพราะ backend ลืม token นั้นไปแล้ว) ผู้ใช้ต้อง login ใหม่ทุกครั้งหลัง deploy — ยังไม่ได้แก้ ถ้าจะแก้ถาวรต้องเปลี่ยนไปเก็บ session ลง DB หรือใช้ JWT
3. **Password hash เป็น SHA-256 ธรรมดา ไม่มี salt** — ไม่ใช่ bcrypt/argon2 ความปลอดภัยต่ำกว่ามาตรฐานปัจจุบัน ถ้าจะแก้ต้องมี migration path สำหรับ password hash เดิมของ user ที่มีอยู่แล้วด้วย
4. **`migration_session_uniqueness.sql` ถูกอ้างถึงใน comment ของ `main.py`** (endpoint `POST /sessions`, partial unique index `idx_unique_open_session_per_branch_day`) **แต่ไม่มีไฟล์นี้อยู่จริงใน repo** — เป็นไปได้ว่าไฟล์นี้ถูกรันตรงใน Neon SQL editor แล้วไม่ได้ commit เก็บไว้ ถ้าจะ reproduce schema นี้ในฐานข้อมูลใหม่ ต้องสร้าง unique index นี้เองตามที่ comment อธิบาย
5. **ต้องรัน SQL migration ก่อน deploy เสมอเมื่อโค้ดอ้างถึง column/ตารางใหม่** — ไม่งั้นจะเจอ error แบบ `psycopg2.errors.UndefinedColumn` (เคยเกิดขึ้นจริงกับ `s.scheduled_date`) ตัวอย่างล่าสุดคือต้องรัน `migration_scan_delete_log.sql` ก่อน deploy ฟีเจอร์ audit log การลบ
6. **`index.html` และ `dashboard.html` ใหญ่มาก (~123KB และ ~144KB ต่อไฟล์)** — เป็นไฟล์เดียวรวม HTML/CSS/JS ทั้งหมด แก้ไขต้องระวังเรื่อง scope ของตัวแปร/ฟังก์ชันชนกัน และควรทดสอบทั้งหน้าหลังแก้เสมอ เพราะไม่มี build/test process ใดๆ ช่วยตรวจสอบ syntax error ก่อน deploy — ไฟล์ใหญ่ขนาดนี้ยังทำให้การ push ผ่าน GitHub API (เมื่อไม่มี git credential ในเครื่องมือแก้โค้ด) กิน token/เวลามากตามไปด้วย เพราะต้องส่งเนื้อหาทั้งไฟล์ทุกครั้งที่แก้ ไม่ใช่แค่ diff
7. **Cloudinary upload preset (`bata_audit`) เป็นแบบ unsigned ฝั่ง client** — หมายความว่าใครก็ตามที่มี cloud name + preset name (มองเห็นได้จาก source code ของ `index.html`) สามารถอัปโหลดไฟล์เข้า Cloudinary account นี้ได้โดยไม่ต้องผ่าน backend เลย ควรพิจารณาตั้งค่าจำกัดขนาด/ประเภทไฟล์ที่ฝั่ง Cloudinary preset เองด้วย ไม่ใช่พึ่งแค่ frontend validate
8. **Excel status/date parsing มีจุดเปราะบาง** — ถ้าไฟล์ Excel ที่ HQ ส่งมาเปลี่ยนรูปแบบ (คอลัมน์สลับตำแหน่ง, รหัสสถานะใหม่ที่ไม่อยู่ใน `_STATUS_CODE_MAP`, รูปแบบวันที่ใหม่) ระบบจะ fallback เป็นค่า default (`active`, `purchase_date = NULL`) แทนที่จะ error แบบชัดเจนในทุกกรณี ควรตรวจสอบผลลัพธ์ preview (`/hq/assets/import/preview`) ก่อน confirm import จริงเสมอ

---

## 7. วิธีรัน / Build / Deploy

โปรเจกต์นี้ **ไม่มี build step** และไม่มี local dev server แบบ hot-reload พิเศษ

### รัน Backend ในเครื่อง (local)
```bash
pip install -r requirements.txt
# ตั้งค่า environment variables ที่จำเป็นก่อน (ดูด้านล่าง) เช่นผ่านไฟล์ .env
uvicorn main:app --reload --port 8000
```
Environment variables ที่ backend ต้องการ:
- `DATABASE_URL` — connection string ของ Neon Postgres
- `CLOUDINARY_CLOUD_NAME`, `CLOUDINARY_API_KEY`, `CLOUDINARY_API_SECRET` — สำหรับ endpoint ลบ/อัปโหลดรูปฝั่ง HQ เท่านั้น (ถ้าไม่ตั้งจะ error เฉพาะ endpoint ที่ต้องใช้)

### รัน Frontend ในเครื่อง (local)
เปิด `index.html` หรือ `dashboard.html` ตรงๆ ในเบราว์เซอร์ได้ (ไม่มี build) แต่ต้องแก้ตัวแปร `API`/`API_BASE` ในไฟล์ให้ชี้ไปที่ backend ที่รันอยู่ (local หรือ production) ก่อนเสมอ

### Deploy Backend (Railway)
1. Push โค้ดขึ้น branch `main` ของ repo นี้ → Railway auto-deploy ให้อัตโนมัติ (ตั้งค่าไว้แล้วผ่าน `railway.toml`)
2. **ถ้าโค้ดใหม่อ้างถึง column/ตารางใหม่ ต้องรัน SQL migration ใน Neon SQL editor ก่อน push เสมอ** (ดูข้อ 5.10 และ 6.5)
3. ตรวจสอบว่า deploy สำเร็จ: `GET /health` ควรคืน `{"status":"ok","assets_in_db":...}`, `GET /docs` แสดง Swagger UI
4. ถ้าเป็นฐานข้อมูลใหม่ (ครั้งแรก) ต้องรัน schema ทั้งหมดจาก `docs/database.md` ก่อน แล้วรัน `python seed_users.py` เพื่อสร้าง user ทดสอบเริ่มต้น

### Deploy Frontend (GitHub Pages — repo นี้เอง)
- Push `index.html` / `dashboard.html` ขึ้น branch `main` ของ repo นี้ → GitHub Pages serve ให้อัตโนมัติที่ `https://fixasset.batathai.com` (ตาม `CNAME`)
- ไฟล์ `index.html` จะถูกเสิร์ฟเป็นหน้าแรก (แอพสแกน), `dashboard.html` เข้าถึงผ่าน path `/dashboard.html`
- **ต้องเปิดใช้งาน GitHub Pages ที่ Settings → Pages → Branch: `main`, folder: `/ (root)`** (ถ้ายังไม่เปิด)

### Health Check
| สิ่งที่เช็ค | URL |
|---|---|
| API ทำงานหรือไม่ | `https://bata-asset-api-production.up.railway.app/health` |
| Endpoint ทั้งหมด (Swagger) | `https://bata-asset-api-production.up.railway.app/docs` |
| Scanner App | `https://fixasset.batathai.com/` |
| HQ Dashboard | `https://fixasset.batathai.com/dashboard.html` |

### Login ทดสอบ (จาก `seed_users.py`)
| Employee ID | Password | Role |
|---|---|---|
| `Acc01` / `Acc02` | `bata1234` | Account |
| `Audit01` | `bata1234` | auditor |
| `Admin01` | `admin999` | hq_admin |

---

## 8. Changelog

- **2026-07-18** — สร้างไฟล์นี้ครั้งแรก (โดย Claude อ่านโค้ดทั้งหมดใน repo ณ ขณะนั้น รวมถึง `main.py`, `index.html`, `dashboard.html`, ไฟล์ config และเอกสารทั้งหมดใน `docs/` เพื่อสรุปเป็น `CLAUDE.md` ฉบับนี้)
- **2026-07-18** — ลบเอกสารล้าสมัยที่ไม่ตรงกับโค้ดจริงออกจาก `docs/` (`README.md`, `architecture.md`, `API.md`, `FLOW.md`, `deployment.md`) ตามคำขอของผู้ดูแล repo หลังยืนยันว่าเนื้อหาที่ยังถูกต้องถูกสรุปไว้ใน `CLAUDE.md` แล้ว เหลือเก็บไว้เฉพาะ `docs/database.md` และ `docs/changelog.md`
- **2026-07-20** — เพิ่ม 3 ฟีเจอร์ UI ในทั้ง `index.html` และ `dashboard.html`:
  1. **Popup "Bata Loading..." ธีมขาว-แดง (official brand)** — แสดงระหว่างรอ API ตอน login/โหลดข้อมูล ใช้โลโก้คำ "BATA THAILAND" สีแดงเข้ม + แถบโหลด (bar) สีแดงวิ่งบนพื้นชมพูอ่อน แทนที่ spinner ธรรมดารุ่นแรก มี reference-counter (`bataLoadingCount`) กันปัญหา nested show/hide ซ้อนกันแล้วปิดก่อนเวลา
  2. **คอลัม Serial ในตาราง Overview ของ `dashboard.html`** — เดิมมีแค่ใน Asset Summary เพิ่มให้ Overview ด้วยเพื่อให้ดู serial number ได้ทั้งสองหน้าจอ รวมถึงใน export CSV/Excel (`OVERVIEW_EXPORT_HEADERS`) ด้วย
  3. **หน้า Summary ของ `index.html` กดดู Verified/Pending แยกรายการได้** — stat card (Scanned/Verified/Flagged/Unmatched/Pending/Total) กดได้แล้ว (`filterSum()`) กรองรายการด้านล่างตามหมวดที่เลือก โดย "Pending" ดึงจาก `CHECKLIST` (asset ที่ยังไม่สแกนจริง) ไม่ใช่แค่ log ที่สแกนไปแล้ว
  - **หมายเหตุระหว่างทำงาน:** ตอน push `dashboard.html` ขึ้น GitHub ผ่าน GitHub MCP tool (ไม่มี git credential ในเครื่องมือแก้โค้ดตอนนั้น) เกิดพลาดใส่เนื้อหาไม่ครบ 2 ครั้งติดกัน (ไฟล์ถูก truncate เหลือแค่ CSS บางส่วน) ก่อนจะแก้ให้ถูกต้องสมบูรณ์ในคอมมิตสุดท้าย — ถ้าเจอ `dashboard.html` บน `main` ที่ขนาดเล็กผิดปกติ (ไม่ถึง 100KB) ให้สงสัยว่าเกิดปัญหานี้ซ้ำ และเช็ค `git log`/commit history เพื่อ revert ไปคอมมิตล่าสุดที่ขนาดไฟล์ถูกต้อง
