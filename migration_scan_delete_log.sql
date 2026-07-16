-- Migration: scan_delete_logs
-- รันไฟล์นี้ใน Neon SQL editor ก่อน deploy main.py เวอร์ชันใหม่
-- (ตามหลักที่ใช้ในโปรเจกต์นี้: schema change ต้อง apply เองผ่าน SQL editor
--  ไม่มี auto-migration ตอน startup — ดู docs/database.md)
--
-- ใช้เก็บ audit trail ทุกครั้งที่มีการลบ scan_logs แบบถาวร (hard delete)
-- ทั้งจากฝั่ง HQ (DELETE /hq/scans/{id}) และฝั่งสาขา (DELETE /scans ในแอพสแกน)

CREATE TABLE IF NOT EXISTS scan_delete_logs (
  id              uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  scan_log_id     integer,        -- id เดิมของ scan_logs ก่อนถูกลบ (ไม่ผูก FK เพราะ record ต้นทางถูกลบไปแล้วจริง)
  session_id      integer,
  branch_id       text,
  asset_code      text,
  asset_name      text,
  qr_key          text,
  deleted_by      text,           -- employee_id (หรือชื่อเต็มถ้าไม่มี) ของคนที่กดลบ
  deleted_by_role text,           -- 'hq_admin' | 'branch' | 'manager'
  source          text,           -- 'hq' | 'branch' — ลบจากหน้าไหน
  deleted_at      timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_scan_delete_logs_branch  ON scan_delete_logs(branch_id);
CREATE INDEX IF NOT EXISTS idx_scan_delete_logs_session ON scan_delete_logs(session_id);
CREATE INDEX IF NOT EXISTS idx_scan_delete_logs_time    ON scan_delete_logs(deleted_at);
