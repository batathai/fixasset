-- migration_employees.sql
-- รันด้วยมือใน Neon SQL editor ครั้งเดียวก่อนใช้ endpoint กลุ่ม /employees และ /hq/employees
--
-- สร้างตาราง employees แยกต่างหากจากตาราง assets/department (คนละเรื่องกัน):
--   - assets.department  = แผนกที่ "ของ" อยู่จริง (ตาม master ที่ import จากไฟล์ asset)
--   - employees.department = แผนกที่ "คน" สังกัด (ตาม master ที่ import จากไฟล์ HR)
-- office.html ใช้ 2 ตัวนี้คู่กัน: เลือกแผนกก่อน (fixed list ใน office.html) แล้วค่อยกรอง
-- รายชื่อพนักงานจากตารางนี้ตามแผนกที่เลือก เพื่อบันทึกว่า asset ชิ้นนี้มอบหมายให้ใคร

CREATE TABLE IF NOT EXISTS employees (
    id SERIAL PRIMARY KEY,
    employee_id TEXT UNIQUE NOT NULL,
    full_name TEXT NOT NULL,
    position TEXT,
    department TEXT,
    department_code TEXT,
    is_active BOOLEAN DEFAULT true,
    import_batch_id TEXT,
    imported_at TIMESTAMPTZ DEFAULT NOW()
);

-- index สำหรับ query หลักที่ office.html ใช้บ่อยสุด: ดึงพนักงานตามแผนก
CREATE INDEX IF NOT EXISTS idx_employees_department
    ON employees(department) WHERE is_active = true;

-- เก็บประวัติการ import พนักงาน (ตาม pattern เดียวกับ import_batches ของ asset)
CREATE TABLE IF NOT EXISTS employee_import_batches (
    batch_id TEXT PRIMARY KEY,
    file_name TEXT,
    row_count INT,
    imported_by TEXT,
    status TEXT DEFAULT 'active',
    imported_at TIMESTAMPTZ DEFAULT NOW()
);

-- เพิ่มคอลัมน์ใน scan_logs เพื่อบันทึกว่า asset ที่สแกนแต่ละครั้ง "มอบหมายให้ใคร"
-- เก็บเป็น employee_id (text) + full_name (text) ตรงๆ แบบ denormalized
-- (ตาม convention เดิมของไฟล์นี้ที่เก็บ scanned_department เป็น text ตรงๆ เช่นกัน
--  ไม่ใช้ foreign key ผูกกับตาราง employees เพื่อไม่ให้ scan_logs พังถ้าพนักงานถูกลบ/ปิดใช้งานทีหลัง)
ALTER TABLE scan_logs ADD COLUMN IF NOT EXISTS assigned_employee_id TEXT;
ALTER TABLE scan_logs ADD COLUMN IF NOT EXISTS assigned_employee_name TEXT;
