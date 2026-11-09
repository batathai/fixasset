-- migration_department_codes.sql  (2026-11-09)
-- เปลี่ยนค่าแผนกเดิม (ชื่อ) เป็นรหัสแผนกใหม่ 12 ค่า — รันใน Neon SQL editor เอง
-- ลำดับ: (1) ตรวจค่าเดิม → (2) รัน migration → (3) ตรวจผลลัพธ์
-- สคริปต์ส่วน (2) รันซ้ำได้ปลอดภัย (idempotent)

-- ============ (1) ตรวจค่าแผนกที่มีอยู่จริงก่อนรัน ============
SELECT 'assets' AS src, department AS value, COUNT(*) FROM assets GROUP BY 2
UNION ALL SELECT 'scan_logs', scanned_department, COUNT(*) FROM scan_logs GROUP BY 2
UNION ALL SELECT 'unmatched_assets', department_guess, COUNT(*) FROM unmatched_assets GROUP BY 2
UNION ALL SELECT 'employees.department', department, COUNT(*) FROM employees GROUP BY 2
UNION ALL SELECT 'employees.department_code', department_code, COUNT(*) FROM employees GROUP BY 2
ORDER BY 1, 2;

-- ============ (2) Migration ============
CREATE TABLE IF NOT EXISTS dept_code_map (old_name text PRIMARY KEY, new_code text);
TRUNCATE dept_code_map;
INSERT INTO dept_code_map (old_name, new_code) VALUES
  ('Finance',         '999FI'),
  ('Human Resources', '999HR'),
  ('Internal Audit',  '999IA'),
  ('IT',              '999IT'),
  ('Retail',          '500R'),
  ('Warehouse',       '680'),
  ('E-Commerce',      '600ML'),
  ('Marketing',       '630'),
  ('Merchandising',   '640M'),
  ('Management',      '999CM'),
  ('Procurement',     NULL);      -- แผนกถูกยกเลิก: ข้อมูลเดิมกลายเป็น "ไม่มีแผนก" (ไม่ลบ asset/พนักงาน)

UPDATE assets a SET department = m.new_code
  FROM dept_code_map m WHERE lower(trim(a.department)) = lower(m.old_name);

UPDATE scan_logs s SET scanned_department = m.new_code
  FROM dept_code_map m WHERE lower(trim(s.scanned_department)) = lower(m.old_name);

UPDATE unmatched_assets u SET department_guess = m.new_code
  FROM dept_code_map m WHERE lower(trim(u.department_guess)) = lower(m.old_name);

UPDATE employees e SET department_code = m.new_code,
                       department      = CASE WHEN m.new_code IS NULL THEN NULL ELSE e.department END
  FROM dept_code_map m WHERE lower(trim(e.department)) = lower(m.old_name);

DROP TABLE dept_code_map;

-- ============ (3) ตรวจผล: ควรได้ 0 แถว (ถ้ามีแถว = ค่าที่ไม่อยู่ใน 12 รหัสใหม่) ============
SELECT 'assets' AS src, department AS value, COUNT(*) FROM assets
  WHERE department IS NOT NULL AND department NOT IN ('500R','600ML','630','640','640M','680','999','999CM','999FI','999HR','999IA','999IT') GROUP BY 2
UNION ALL SELECT 'scan_logs', scanned_department, COUNT(*) FROM scan_logs
  WHERE scanned_department IS NOT NULL AND scanned_department NOT IN ('500R','600ML','630','640','640M','680','999','999CM','999FI','999HR','999IA','999IT') GROUP BY 2
UNION ALL SELECT 'unmatched_assets', department_guess, COUNT(*) FROM unmatched_assets
  WHERE department_guess IS NOT NULL AND department_guess NOT IN ('500R','600ML','630','640','640M','680','999','999CM','999FI','999HR','999IA','999IT') GROUP BY 2
UNION ALL SELECT 'employees.department_code', department_code, COUNT(*) FROM employees
  WHERE department_code IS NOT NULL AND department_code NOT IN ('500R','600ML','630','640','640M','680','999','999CM','999FI','999HR','999IA','999IT') GROUP BY 2
ORDER BY 1, 2;
