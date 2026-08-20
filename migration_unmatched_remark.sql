-- migration_unmatched_remark.sql
-- เพิ่มคอลัมน์ remark ให้ unmatched_assets — เก็บโน้ตที่ auditor พิมพ์ตอนสแกนไม่เจอ (บางคนใช้ช่องนี้
-- จด Serial No.) แยกจาก hq_note ซึ่งไว้ให้ HQ เขียนทีหลังตอน review เท่านั้น
-- (ตาม pattern เดียวกับ scan_logs ที่มีทั้ง note และ hq_note แยกกัน)
-- เจอบั๊กจริง 2026-08-20: POST /unmatched รับ remark เข้ามาแต่ไม่เคย INSERT ลง DB เลย ข้อมูลหายเงียบๆ
ALTER TABLE unmatched_assets ADD COLUMN IF NOT EXISTS remark TEXT;
