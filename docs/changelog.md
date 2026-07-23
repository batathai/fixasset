# Changelog — Bata Fixed Asset Audit System

รวบรวมจากประวัติการแก้ไขทั้งหมดของโปรเจกต์ เรียงตามลำดับเวลา

## v0.1 — ออกแบบระบบเริ่มต้น
- ออกแบบ Architecture overview: Scanner App (PWA) + Backend (Supabase) + Dashboard
- เลือก stack เริ่มต้น: Supabase (Postgres + Auth + Storage + REST API ในตัวเดียว), `html5-qrcode` สำหรับอ่าน QR
- ออกแบบ database schema ชุดแรก: `branches`, `users`, `assets`, `audit_sessions`, `scan_logs`, `unmatched_assets`
- เพิ่ม `serial_mismatches` เพื่อรองรับ edge case ที่ asset พบ แต่ serial number ไม่ตรงกับ master (เช่น คอมพิวเตอร์ถูกสลับเครื่อง)
- ออกแบบ flow รองรับ asset ที่ไม่มีในระบบ (import master ไม่ครบ 100%) ให้บันทึกเป็น `unmatched_assets` แทนการบล็อกการสแกน

## v0.2 — เปลี่ยน Database จาก Supabase → Neon
- เหตุผล: Supabase free plan จำกัดที่ 2 projects ต่อ organization และ project จะ auto-pause หากไม่ใช้งานเกิน 1 สัปดาห์
- ย้าย **เฉพาะ database** ไปที่ Neon Postgres — ใช้ SQL schema เดิมทุกบรรทัด เปลี่ยนแค่ connection string
- ยังคงใช้ **Supabase Storage** สำหรับเก็บรูปถ่ายต่อไป เนื่องจาก Neon ไม่มี storage ในตัว
- Auth เปลี่ยนจาก Supabase Auth built-in มาเป็น JWT + bcrypt ที่เขียนเองใน FastAPI

## v0.3 — สร้าง Backend API (FastAPI บน Railway)
- สร้าง repo `bata-asset-api` พร้อมไฟล์ `main.py`, `requirements.txt`, `Procfile`, `railway.toml`, `seed_users.py`
- Endpoint ชุดแรก: `POST /auth/login`, `GET /assets/lookup/{qr_key}`, `GET /assets/branch/{branch_id}`, `POST /sessions`, `POST /scans`, `POST /unmatched`, `GET /dashboard/summary`, `GET /health`
- Deploy ขึ้น Railway: `https://bata-asset-api-production.up.railway.app`
- เหตุผลที่ไม่ให้ frontend เชื่อม database โดยตรง: ป้องกันการเข้าถึงข้อมูลโดยไม่ผ่านการตรวจสอบสิทธิ์

## v0.4 — สร้าง Scanner App และ HQ Dashboard, Deploy บน GitHub Pages
- สร้าง `bata_scanner.html` (Scanner App) และ `bata_hq_dashboard.html` (HQ Dashboard)
- ทดลอง deploy ด้วย Netlify Drop ก่อน แต่ credit เต็ม จึงเปลี่ยนมาใช้ GitHub Pages แทน
- เปลี่ยนชื่อไฟล์เป็น `index.html` (scanner) และ `dashboard.html` (dashboard) เพื่อให้ GitHub Pages เสิร์ฟได้ถูกต้อง
- พบและแก้ปัญหาชื่อ repo ไม่ตรงกัน (`bata-asset-api` vs `bata-asset`) ที่ทำให้ URL เข้าไม่ได้
- เพิ่ม HQ Dashboard 5 หน้า: Overview, Branches, Unmatched, Serial Mismatch, Export (Excel)

## v0.5 — เพิ่ม HQ Management Endpoints
- เพิ่ม `GET /hq/scans`, `PATCH /hq/scans/{id}`, `PATCH /hq/unmatched/{id}` ให้ HQ แก้ไขข้อมูล scan log / unmatched ได้จาก Dashboard โดยตรง
- เพิ่ม column ใหม่ผ่าน migration: `scan_logs.hq_note`, `scan_logs.updated_at`, `unmatched_assets.hq_note`, `unmatched_assets.matched_asset_code`, `unmatched_assets.reviewed_by`, `unmatched_assets.reviewed_at`, `unmatched_assets.updated_at`

## v0.6 — จัดการรูปถ่ายและ Session ที่ซ้ำกัน
- เพิ่ม `POST /hq/scans/{id}/photo` และ `DELETE /hq/scans/{id}/photo` สำหรับอัปโหลด/ลบรูปผ่าน Supabase Storage API
- เพิ่ม dependency `httpx` (เรียก Supabase Storage API) และ `python-multipart` (รับ file upload) ใน `requirements.txt`
- เพิ่ม environment variables ใน Railway: `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, `SUPABASE_BUCKET`
- เพิ่ม `POST /hq/sessions/merge` เพื่อรวม audit session ที่ถูกสร้างซ้ำกันโดยไม่ตั้งใจ — ย้าย scan_logs/unmatched_assets เข้า primary session แล้วลบ session ซ้ำ
- เพิ่ม `DELETE /hq/sessions/{session_id}` ให้ HQ ลบ session ได้

## v0.7 — แก้ไขสถานะงานและ bug จาก schema mismatch
- เพิ่ม logic เปลี่ยน session status จาก `open` → `on_process` อัตโนมัติเมื่อมี scan เข้ามาแล้ว
- พบว่า logic ใหม่มีผลกับ scan ใหม่เท่านั้น ต้อง migrate ข้อมูลเก่าด้วย SQL `UPDATE audit_sessions SET status = 'on_process' WHERE ...` แยกต่างหาก
- แก้ bug `psycopg2.errors.UndefinedColumn: column s.scheduled_date does not exist` — เกิดจาก query อ้างอิง column ที่ไม่เคยถูกสร้างจริงในฐานข้อมูล Neon แก้โดยตัด column ที่ไม่มีจริงออกจาก query และคำนวณ `total_assets`/`scanned_count` จากตาราง `assets`/`scan_logs` โดยตรงแทน

## v0.8 — เพิ่ม Import Asset จากไฟล์ Excel (Admin only) พร้อม Undo
- เพิ่มปุ่ม Import บนโลโก้ "B" ที่ sidebar ของ HQ Dashboard — แสดง/ใช้งานได้เฉพาะ user role `hq_admin` เท่านั้น (เช็คทั้งฝั่ง backend เพื่อกันการเรียก API ตรงข้าม role)
- เพิ่ม endpoint `POST /hq/assets/import/preview` (อ่านไฟล์ + preview ก่อนยืนยัน, เช็ค duplicate ด้วย `asset_code+seq`), `POST /hq/assets/import/confirm` (insert จริงแบบ atomic ทั้ง batch), `GET /hq/assets/import-batches` (ดูประวัติ), `POST /hq/assets/import-batches/{batch_id}/undo` (ย้อนกลับการ import)
- ออกแบบระบบ Undo ด้วยแนวคิด Import Batch: ทุกแถวที่ import มาจากไฟล์เดียวกันจะถูก tag ด้วย `import_batch_id` เดียวกัน, การ undo คือ soft-delete (`is_active = false`) เฉพาะแถวใน batch นั้น ไม่กระทบข้อมูลเดิม
- เพิ่ม migration: `assets.import_batch_id`, `assets.is_active` (พร้อม backfill แถวเก่าทั้งหมดเป็น `true`), unique index `(asset_code, seq)`, ตารางใหม่ `import_batches`
- เพิ่ม dependency `xlrd==2.0.1`, `openpyxl==3.1.2` ใน `requirements.txt` เพื่อ parse ไฟล์ `.xls`/`.xlsx`
- **แก้ bug วันที่ผิด**: ไฟล์ Excel เก็บ `วันที่ซื้อ` เป็น text รูปแบบ `26/06/2026` (DD/MM/YYYY) ไม่ใช่ Excel date serial ทำให้ Postgres ตีความผิดเป็น MM/DD/YYYY แล้ว error `date/time field value out of range` (มองว่าเดือน = 26) แก้โดยเพิ่มฟังก์ชัน `_parse_thai_date_string()` แปลงเป็น ISO `YYYY-MM-DD` ก่อนเข้า DB เสมอ (รองรับปี พ.ศ. ด้วยเผื่ออนาคต)
- **แก้ bug status code ไม่ map**: คอลัมน์ "สถานะสินทรัพย์" ในไฟล์ Excel เก็บเป็นรหัสย่อ (`A`) แต่ query ทุกหน้ากรองด้วย `status = 'active'` (คำเต็ม) ทำให้ asset ที่เพิ่ง import หายไปจากหน้า Asset Summary ทั้งที่มีอยู่จริงใน DB แก้โดยเพิ่ม `_STATUS_CODE_MAP` (`A→active, D→disposed, T→transferred, M→missing`) แปลงก่อน insert พร้อม SQL fix ข้อมูลเก่าที่ import ไปแล้วด้วย `UPDATE assets SET status='active' WHERE status='A'`
- แก้ query เดิม 3 จุด (`GET /assets/branch/:id` ทั้ง main query และ fallback union, `GET /hq/assets`) ให้กรองด้วย `COALESCE(is_active, true) = true` เพื่อให้ asset ที่ถูก undo ไปแล้วหายจากทุกหน้าจริง (ไม่ใช่แค่ตอน import)
- **แก้ bug column สลับกันในหน้า Scan Logs (มุมมอง Pending)**: พบว่า `renderPendingScans()` เป็นฟังก์ชันแยกจาก `renderScans()` ปกติ และเรียง `<td>` ไม่ตรงกับลำดับ `<th>` ของตาราง (ใส่ชื่อ Asset ก่อน SEQ) แก้ให้เรียงตรงกับ header: รูป → Asset Code → SEQ → ชื่อ Asset → สภาพ → Serial Match → สาขา → วันที่ → เวลา → Actions
- ปรับ CSS ตารางทั้งหมด: เปลี่ยน `vertical-align` จาก `middle` เป็น `top` (กันแถวที่สูงไม่เท่ากันทำให้คอลัมน์ดูเหมือนสลับ), คอลัมน์ "ชื่อ Asset" ใส่ `white-space:nowrap` ให้อยู่บรรทัดเดียวเสมอพร้อม `title` tooltip แสดงชื่อเต็ม

## v0.9 — Office Asset Scan v2: ระบบแผนก (fixed list) + มอบหมายพนักงาน + เก็บกวาด repo
- **แผนกใน Office Scan เปลี่ยนจาก free text เป็น fixed list**: `office.html` (สร้างครั้งแรกใน v0.8.x ช่วง 2026-07-21 เป็น clone ของ `index.html` เพิ่มคอลัมน์ `department` แบบพิมพ์เอง) เปลี่ยนช่องแผนกเป็น `<select>` ตายตัว 11 ค่า (`OFFICE_DEPARTMENTS` ใน `office.html`: E-Commerce, Finance, Human Resources, Internal Audit, IT, Management, Marketing, Merchandising, Procurement, Retail, Warehouse) เพื่อกันพนักงานพิมพ์แผนกสะกดเพี้ยน (เช่น "Retail" vs "retail" vs "RTL") ซึ่งทำให้ `dept_mismatch` ที่คำนวณจาก string compare ผิดเพี้ยนไปด้วย
- **เพิ่มระบบ "User/เจ้าของ asset" ที่เคยออกแบบไว้ตั้งแต่ v0.8.x แต่ยังไม่ได้ทำ**: เพิ่มตาราง `employees` (employee_id, full_name, position, department, department_code, is_active, import_batch_id, imported_at) และ `employee_import_batches` — import จริงจากไฟล์ Excel ฝ่าย HR (84 คน, 11 แผนก) ผ่าน endpoint ใหม่ `POST /hq/employees/import/preview` + `/confirm` (pattern เดียวกับ asset import ใน v0.8)
- เพิ่ม endpoint: `GET /employees/department/{department}` (dropdown ที่ 2 ใน office.html — เลือกแผนกก่อน ค่อยกรองพนักงานในแผนกนั้น), `GET /hq/employees`, `PATCH /hq/employees/{id}`, `DELETE /hq/employees/{id}` (soft delete — `is_active=false` ตาม convention เดียวกับ asset undo import)
- `office.html`: ทุกการ์ดผลสแกน (matched, serial-check/คอมพิวเตอร์, unmatched) มี dropdown "มอบหมายให้พนักงาน" โผล่/โหลดอัตโนมัติทันทีที่เลือก/auto-fill แผนกเสร็จ
- `scan_logs` และ `unmatched_assets` เพิ่มคอลัมน์ `assigned_employee_id`/`assigned_employee_name` — เก็บแบบ denormalized (text ตรงๆ ไม่ผูก FK กับ `employees`) ตาม convention เดียวกับ `scanned_department` เพื่อไม่ให้ scan record พังถ้าพนักงานถูกปิดใช้งาน/ลบทีหลัง
- `dashboard.html`: เพิ่มเมนู "พนักงาน" ใน sidebar — ตารางรายชื่อ (ค้นหา + กรองแผนก), popup import (drawer ขวา แบบเดียวกับปุ่ม Import asset เดิม, preview ก่อน confirm), ปุ่มปิด/เปิดใช้งานรายคน
- **บั๊กใหญ่ที่พบระหว่างทดสอบ**: `assets.department` (คอลัมน์ที่ `main.py` อ้างอิงมาตั้งแต่เพิ่ม Office Asset Scan ครั้งแรก) **ไม่เคยถูกรันจริงในฐานข้อมูล Production** — migration ที่ควรจะเพิ่มคอลัมน์นี้ถูกวางแผนไว้แต่ไม่เคย apply จริง ทำให้ `/hq/assets` (และทุก endpoint ที่ query `a.department`) พัง `psycopg2.errors.UndefinedColumn` มาโดยไม่มีใครรู้ตัว — **อาการที่เห็นฝั่ง browser คือ "CORS error"** ซึ่งเข้าใจผิดง่ายมาก เพราะ FastAPI/Starlette ตอบ unhandled exception ด้วย response แบบ `text/plain "Internal Server Error"` (21 ตัวอักษรพอดี) ที่ไม่มี CORS header ติดมา (ต่างจาก error ปกติที่ CORSMiddleware จะแนบ header ให้) — วิธี debug ที่ถูกต้องคือเช็ค **status code จริง** ใน Network tab ก่อนเชื่อข้อความ error ของ browser เสมอ; ถ้าเป็น 500 ให้ไปดู Railway Deploy Logs หา Python traceback ต่อ ไม่ใช่ไล่แก้ CORS config
- แก้ด้วยการรัน migration เพิ่มคอลัมน์ที่ขาดจริง (`assets.department`, `scan_logs.scanned_department`/`dept_mismatch`/`dept_note`, `unmatched_assets.department_guess`) ใน Neon SQL editor
- เพิ่ม CORS `allow_origins` ให้ครอบคลุม local dev server ทั่วไป (`localhost:8000`, `:5500`, `:3000` และคู่ `127.0.0.1`) สำหรับทดสอบก่อน push ขึ้น production
- **เก็บกวาด repo**: ลบ `seed_users.py`, `migration_scan_delete_log.sql`, `migration_office_department.sql` ออกจาก repo เพราะเป็นสคริปต์/migration ที่รันเสร็จสิ้นไปแล้วจริง ไม่มีโค้ดส่วนไหนอ้างอิง/รันไฟล์เหล่านี้ตอน runtime — เนื้อหาเต็มถูกเก็บสำรองไว้ใน `CLAUDE.md` (section Archive) แทน เผื่อต้อง setup ฐานข้อมูลใหม่ตั้งแต่ต้นในอนาคต

## บันทึกเพิ่มเติม
- มีการสร้างคู่มือการใช้งานระบบฉบับย่อ (`bata_audit_manual.txt`) อธิบายภาพรวมการทำงานของ Scanner App และ HQ Dashboard สำหรับผู้ใช้งานทั่วไป
