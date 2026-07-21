-- Migration: เพิ่มรองรับ "แผนก" (department) สำหรับ Office Asset Scan
-- รันใน Neon SQL editor ก่อน deploy main.py เวอร์ชันที่ใช้คอลัมน์เหล่านี้
-- (ตาม convention ของโปรเจกต์นี้ — ไม่มี auto-migration ตอน backend startup)

-- 1. assets (master) — เพิ่มคอลัมน์แผนกที่ asset ติดตั้ง/ประจำอยู่
--    ว่างไว้ก่อนได้ (NULL) จนกว่าไฟล์ Excel จาก HQ ที่มีคอลัมน์แผนกจะ import เข้ามา
ALTER TABLE assets ADD COLUMN IF NOT EXISTS department text;
CREATE INDEX IF NOT EXISTS idx_assets_department ON assets(department);

-- 2. scan_logs — เก็บแผนกที่ auditor เจอจริงตอนสแกน (auto-fill จาก master แต่แก้ไขได้)
ALTER TABLE scan_logs ADD COLUMN IF NOT EXISTS scanned_department text;
ALTER TABLE scan_logs ADD COLUMN IF NOT EXISTS dept_mismatch boolean DEFAULT false;
ALTER TABLE scan_logs ADD COLUMN IF NOT EXISTS dept_note text;

-- 3. unmatched_assets — auditor กรอกแผนกเองแบบ free text เพราะไม่มีใน master
ALTER TABLE unmatched_assets ADD COLUMN IF NOT EXISTS department_guess text;
