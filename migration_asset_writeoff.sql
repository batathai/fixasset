-- migration_asset_writeoff.sql
-- เพิ่มคอลัมน์เก็บข้อมูล Write off ที่ตัว asset master (HQ ตัด asset ออกจากทะเบียนโดยไม่ต้องมี scan)
-- ใช้คู่กับ endpoint POST /hq/assets/{asset_id}/write-off ใน main.py
-- สถานะจริงของ asset ยังเก็บใน assets.status = 'disposed' (คอลัมน์เดิม) — คอลัมน์ใหม่เก็บแค่รายละเอียดประกอบ
-- ⚠️ ต้องรันใน Neon SQL editor ก่อน deploy main.py ใหม่ ไม่งั้น endpoint จะ 500 (UndefinedColumn)
ALTER TABLE assets ADD COLUMN IF NOT EXISTS write_off_reason TEXT;        -- sold | donated | damaged_beyond_repair | lost | other
ALTER TABLE assets ADD COLUMN IF NOT EXISTS write_off_remark TEXT;        -- หมายเหตุจาก HQ (บังคับเมื่อ reason = other)
ALTER TABLE assets ADD COLUMN IF NOT EXISTS written_off_by TEXT;          -- employee_id (email) ของ HQ ที่กดตัด
ALTER TABLE assets ADD COLUMN IF NOT EXISTS written_off_at TIMESTAMPTZ;   -- เวลาที่ตัด

-- ตรวจหลังรัน: ต้องเห็น 4 แถว
-- SELECT column_name FROM information_schema.columns
--  WHERE table_name = 'assets' AND column_name IN ('write_off_reason','write_off_remark','written_off_by','written_off_at');
