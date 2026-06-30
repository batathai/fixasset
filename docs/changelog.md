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

## บันทึกเพิ่มเติม
- มีการสร้างคู่มือการใช้งานระบบฉบับย่อ (`bata_audit_manual.txt`) อธิบายภาพรวมการทำงานของ Scanner App และ HQ Dashboard สำหรับผู้ใช้งานทั่วไป
