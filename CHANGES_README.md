# สรุปการแก้ไข 6 ข้อ

## ไฟล์ที่แก้ (3 ไฟล์) + ไฟล์ migration ใหม่ 1 ไฟล์
- `main.py` — backend (FastAPI)
- `index.html` — แอพสแกนหน้าสาขา
- `dashboard.html` — HQ Dashboard (**ไม่ใช่ dashboard01.html**)
- `migration_scan_delete_log.sql` — ไฟล์ใหม่ ต้องรันก่อน deploy

## ขั้นตอน deploy (ทำตามลำดับ)
1. **รัน `migration_scan_delete_log.sql` ใน Neon SQL editor ก่อน** — สร้างตาราง `scan_delete_logs`
   (ถ้าลืมขั้นตอนนี้ endpoint ลบทุกตัวจะ error เพราะ insert log ไม่ได้)
2. Push `main.py` ขึ้น repo `bata-asset-api` → Railway auto-deploy
3. Push `index.html` + `dashboard.html` ขึ้น repo GitHub Pages เดิม (ทับของเก่า)

## รายละเอียดแต่ละข้อ

**1) ระบบ "รอบตรวจ"** — เลิก hardcode "Audit cycle: Q3 2026" แล้ว คำนวณจาก `audit_sessions` จริงผ่าน `/dashboard/summary` แสดง "รอบที่ N — กำลังตรวจ/Complete แล้ว (ผ่านมาแล้ว X รอบ)" ไม่มีการแก้ schema เพิ่ม

**2) PDF Log อัตโนมัติ** — พอกด "ยืนยันปิดงาน" ในแอพสแกน ระบบจะดึงรายการสแกนล่าสุดจาก server แล้วเปิด print dialog ("Save as PDF") ให้ทันที ไม่ต้องกดปุ่มแยก

**3) บั๊กลบในแอพสแกน** — `deleteEntry()` เดิมลบแค่ในเครื่อง ตอนนี้ยิง `DELETE /scans?session_id=..&qr_key=..` ไปลบที่ server จริงก่อนเสมอ (ลบได้เฉพาะตอน session ยังไม่ปิด — ถ้าปิดงานแล้วต้องให้ HQ ลบแทน)

**4) บั๊กลบใน Dashboard** — ปุ่มลบทุกจุด (Overview + Asset Summary + More menu) ต่อเข้ากับ `DELETE /hq/scans/{id}` จริงแล้ว พร้อม reload ข้อมูลจริงหลังลบ

**5) Audit log การลบ** — ตารางใหม่ `scan_delete_logs` (ใคร/ลบอะไร/เมื่อไหร่/จากฝั่งไหน) บันทึกอัตโนมัติทุกครั้งที่มีการลบ ทั้งจาก HQ และจากแอพสแกน ดูย้อนหลังได้ผ่าน `GET /hq/scan-delete-logs`

**6) จำ Login ข้าม F5** — เก็บ token + สาขาที่เลือกไว้ใน `localStorage` กด F5 แล้วไม่ต้อง login ใหม่หรือเลือกสาขาใหม่ (ยกเว้น token หมดอายุจริงหรือ backend restart — ดูหมายเหตุด้านล่าง)

## ข้อควรรู้ / ยังไม่ได้แก้ในรอบนี้
- **Auth token เก็บใน memory ฝั่ง backend** (`sessions = {}` ใน `main.py`) — ถ้า Railway restart/redeploย token ทุกคนจะหลุดพร้อมกันหมด ต่อให้ frontend จำไว้ใน localStorage แล้วก็ตาม (เพราะ backend ลืม token นั้นไปแล้ว) ถ้าอยากแก้ปัญหานี้แบบถาวรต้องเปลี่ยนไปเก็บ session ลง DB หรือใช้ JWT แทน — เป็นงานแยกที่ใหญ่กว่านี้ ไม่ได้รวมอยู่ใน 6 ข้อนี้
- Excel Import ไม่ต้องแก้อะไร ใช้งานได้จริงอยู่แล้วใน `dashboard.html`
