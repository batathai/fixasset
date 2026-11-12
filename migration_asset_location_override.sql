-- migration_asset_location_override.sql
-- เพิ่มคอลัมน์ flag ให้ assets: HQ ย้าย location ของ asset ด้วยมือ (PATCH /hq/assets/{id}/location)
-- location_override = true -> หน้า Dashboard จัดกลุ่ม asset ตาม assets.location_code (ค่าที่ HQ ตั้ง)
--   แทนที่จะจัดกลุ่มตามสาขาของ session ที่สแกน (พฤติกรรมเดิมตั้งแต่ 2026-08-21 ยังคงไว้สำหรับ asset ที่ไม่เคยถูกย้าย)
-- ⚠️ ต้องรันใน Neon ก่อน deploy main.py ใหม่ ไม่งั้น GET /hq/assets จะ 500 (UndefinedColumn) แล้ว Dashboard โหลดไม่ขึ้น
ALTER TABLE assets ADD COLUMN IF NOT EXISTS location_override BOOLEAN DEFAULT false;
UPDATE assets SET location_override = false WHERE location_override IS NULL;

-- ตรวจหลังรัน: ต้องเห็น 1 แถว
-- SELECT column_name FROM information_schema.columns WHERE table_name='assets' AND column_name='location_override';
