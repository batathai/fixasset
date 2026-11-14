-- migration_holdings_ledger.sql
-- ต่อยอด employee_holdings ให้เป็น "สมุดประวัติผู้ถือครอง" (ledger): 1 แถว = ช่วงเวลาที่คนหนึ่งถืออุปกรณ์ 1 ชิ้น
--   ended_at IS NULL  = ถืออยู่ตอนนี้;  มีค่า = เลิกถือแล้ว (โอนให้คนอื่น / รับคืน)
-- ต้องรัน migration_employee_holdings.sql มาก่อน (รันแล้ว 2026-11-14)
ALTER TABLE employee_holdings ADD COLUMN IF NOT EXISTS employee_id  TEXT;   -- อ้าง employees.employee_id (NULL = จับคู่พนักงานไม่ได้)
ALTER TABLE employee_holdings ADD COLUMN IF NOT EXISTS asset_key    TEXT;   -- Serial (ตัวพิมพ์ใหญ่ไม่มีช่องว่าง) ถ้าไม่มีใช้เลข Asset — ใช้ตามรอยอุปกรณ์ข้ามผู้ถือ
ALTER TABLE employee_holdings ADD COLUMN IF NOT EXISTS started_at   DATE;   -- วันเริ่มถือ (จากไฟล์ = ปี-เดือนตามรหัส Asset/วันที่ซื้อ; โอนผ่านระบบ = วันที่โอนจริง)
ALTER TABLE employee_holdings ADD COLUMN IF NOT EXISTS start_source TEXT;   -- 'asset_summary' | 'asset_code' | 'manual' | 'transfer'
ALTER TABLE employee_holdings ADD COLUMN IF NOT EXISTS ended_at     DATE;
ALTER TABLE employee_holdings ADD COLUMN IF NOT EXISTS ended_reason TEXT;   -- 'transfer' | 'return'
ALTER TABLE employee_holdings ADD COLUMN IF NOT EXISTS recorded_by  TEXT;   -- employee_id ของ HQ ที่บันทึก
CREATE INDEX IF NOT EXISTS idx_employee_holdings_key ON employee_holdings(asset_key);
CREATE INDEX IF NOT EXISTS idx_employee_holdings_emp ON employee_holdings(employee_id);

-- ตรวจผล (ควรได้ cols = 17)
-- SELECT table_name, count(*) AS cols FROM information_schema.columns WHERE table_name = 'employee_holdings' GROUP BY table_name;
