-- migration_employee_holdings.sql
-- ตาราง "พนักงานควรถืออุปกรณ์อะไร" — import จากไฟล์ User Asset List (Notebook / PC / Monitor)
-- 1 แถว = อุปกรณ์ 1 ชิ้นของพนักงาน 1 คน; import ครั้งใหม่ = soft-delete (is_active=false) ชุดเดิมทั้งหมดแล้วใส่ชุดใหม่
CREATE TABLE IF NOT EXISTS employee_holdings (
  id              SERIAL PRIMARY KEY,
  person_name     TEXT NOT NULL,          -- ชื่อตามไฟล์ (อาจเป็นชื่อต้นอย่างเดียว) — จับคู่กับ employees.full_name ฝั่ง Dashboard
  dept_label      TEXT,                   -- ชื่อแผนกตามไฟล์ (เช่น FINANCE, IT) ใช้อ้างอิงเฉยๆ
  device_type     TEXT NOT NULL,          -- 'Notebook' | 'CPU' | 'Monitor'
  model           TEXT,
  asset_code      TEXT,                   -- เลข Asset ตามไฟล์ (มักไม่มีส่วนท้าย SEQ)
  serial_no       TEXT,
  import_batch_id TEXT,
  is_active       BOOLEAN DEFAULT true,
  imported_at     TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_employee_holdings_active ON employee_holdings(is_active);

-- ตรวจผล (ควรได้ 1 แถว ชื่อตาราง + 10 คอลัมน์)
-- SELECT table_name, count(*) AS cols FROM information_schema.columns WHERE table_name = 'employee_holdings' GROUP BY table_name;
