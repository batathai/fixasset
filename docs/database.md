# Database — Bata Fixed Asset Audit System

Database: **Postgres บน Neon** (`neon.tech`) — schema เดียวกับที่ออกแบบไว้บน Supabase เดิม เปลี่ยนแค่ connection string

## ภาพรวมตาราง

| ตาราง | หน้าที่ |
|---|---|
| `branches` | รายชื่อสาขาทั้งหมด |
| `users` | ผู้ใช้งานระบบ (auditor / branch_manager / hq_admin) |
| `assets` | ข้อมูล asset master ที่ import มาจาก Excel ของ HQ |
| `import_batches` | ประวัติการ import asset แต่ละครั้งจากไฟล์ Excel (ใช้คู่กับ `assets.import_batch_id` เพื่อทำ Undo) |
| `audit_sessions` | รอบการตรวจนับของแต่ละสาขา |
| `scan_logs` | บันทึกทุกครั้งที่สแกน asset ที่พบใน master แล้ว |
| `unmatched_assets` | asset ที่สแกนได้แต่ไม่พบใน master ต้องรอ HQ review |
| `serial_mismatches` | กรณีพบ asset แต่ serial number ไม่ตรงกับ master (เช่น คอมพิวเตอร์ถูกสลับเครื่อง) |

## Schema

```sql
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- 1. MASTER DATA -------------------------------------------------

CREATE TABLE branches (
  id          uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  code        text UNIQUE NOT NULL,        -- e.g. "BKK01", "CNX02"
  name        text NOT NULL,
  region      text,
  is_active   boolean DEFAULT true,
  created_at  timestamptz DEFAULT now()
);

CREATE TABLE users (
  id          uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  email       text UNIQUE NOT NULL,
  full_name   text NOT NULL,
  role        text NOT NULL DEFAULT 'auditor', -- 'auditor' | 'branch_manager' | 'hq_admin'
  branch_id   uuid REFERENCES branches(id),
  is_active   boolean DEFAULT true,
  created_at  timestamptz DEFAULT now()
);

-- 2. ASSET MASTER (import จาก Excel / HQ) -------------------------
-- ⚠️ สำคัญ: schema ด้านล่างนี้คือโครงสร้างจริงที่ใช้งานอยู่ใน Neon ปัจจุบัน
-- (ตรวจสอบด้วย information_schema.columns เมื่อ 2026-06-30 — เวอร์ชันก่อนหน้าของเอกสารนี้เขียนผิดจากของจริง
-- เช่นเคยเขียนว่ามี branch_id/department แต่ของจริงไม่มี ดูคำเตือนท้ายไฟล์)

CREATE TABLE assets (
  id                SERIAL PRIMARY KEY,
  qr_key            text,                    -- = asset_code + seq เช่น "SFU012024010001SE0001" ใช้ผูกกับ QR sticker
  asset_code        text,                    -- รหัสสินทรัพย์ เช่น "SFU042026060001"
  seq               text,                    -- ลำดับ เช่น "000"
  location_code     text,                    -- รหัสที่ตั้ง/สาขา เช่น "0051548"
  location_name     text,                    -- ชื่อที่ตั้ง เช่น "Big C Bangplee"
  name              text,                    -- รายละเอียดสินทรัพย์ (ใช้แสดงเป็นชื่อ asset)
  serial_no         text,                    -- เลขที่เครื่อง
  purchase_date     date,
  qty               integer,
  purchase_price    numeric,                 -- มูลค่าสินทรัพย์
  accumulated_dep   numeric,                 -- คสส. (ค่าเสื่อมสะสม)
  net_book_value    numeric,                 -- มูลค่าทางบัญชี
  status            text DEFAULT 'active',   -- 'active' | 'disposed' | 'transferred' | 'missing'
  imported_at       timestamptz DEFAULT now(),
  import_batch_id   text,                    -- เพิ่มใน v0.8 — อ้างถึง import_batches.batch_id เพื่อทำ Undo เป็นชุด
  is_active         boolean DEFAULT true,    -- เพิ่มใน v0.8 — false = ถูก undo การ import ไปแล้ว (soft-delete)
  -- เพิ่ม 2026-11-12 (migration_asset_writeoff.sql): Write off โดย HQ — status เปลี่ยนเป็น 'disposed'
  write_off_reason  text,                    -- sold | donated | damaged_beyond_repair | lost | other
  write_off_remark  text,                    -- บังคับเมื่อ reason = other
  written_off_by    text,                    -- employee_id ของ HQ ที่ตัด
  written_off_at    timestamptz,
  -- เพิ่ม 2026-11-12 (migration_asset_location_override.sql): HQ ย้าย location ด้วยมือ
  location_override boolean DEFAULT false    -- true = Dashboard จัดกลุ่มตาม location_code แทนสาขาของ session ที่สแกน
);

CREATE INDEX idx_assets_asset_code   ON assets(asset_code);
CREATE INDEX idx_assets_serial_no    ON assets(serial_no);
CREATE INDEX idx_assets_location_code ON assets(location_code);
CREATE INDEX idx_assets_status       ON assets(status);
CREATE UNIQUE INDEX idx_assets_asset_code_seq ON assets(asset_code, seq);
CREATE INDEX idx_assets_import_batch ON assets(import_batch_id);

-- 2b. IMPORT BATCHES (เพิ่มใน v0.8) — ประวัติการ import แต่ละครั้ง ใช้คู่กับปุ่ม Undo -----
CREATE TABLE import_batches (
  batch_id     text PRIMARY KEY,             -- uuid hex string สร้างตอน import แต่ละครั้ง
  file_name    text,
  row_count    integer,
  imported_by  text,                         -- employee_id ของ hq_admin ที่ import
  imported_at  timestamptz DEFAULT now(),
  status       text DEFAULT 'active'         -- 'active' | 'undone'
);

-- 3. AUDIT SESSION (รอบการตรวจนับ) --------------------------------

CREATE TABLE audit_sessions (
  id          uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  name        text NOT NULL,              -- เช่น "Q2/2567 สาขาเชียงใหม่"
  branch_id   uuid NOT NULL REFERENCES branches(id),
  audit_date  date NOT NULL,
  started_by  uuid REFERENCES users(id),
  status      text DEFAULT 'open',        -- 'open' | 'on_process' | 'closed' | 'reviewing'
  note        text,
  created_at  timestamptz DEFAULT now(),
  closed_at   timestamptz
);

CREATE INDEX idx_sessions_branch ON audit_sessions(branch_id);
CREATE INDEX idx_sessions_status ON audit_sessions(status);

-- 4. SCAN LOG (asset ที่พบในระบบ) ----------------------------------

CREATE TABLE scan_logs (
  id              uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  session_id      uuid NOT NULL REFERENCES audit_sessions(id),
  asset_id        uuid NOT NULL REFERENCES assets(id),
  scanned_by      uuid NOT NULL REFERENCES users(id),
  scanned_at      timestamptz DEFAULT now(),
  serial_verified boolean DEFAULT false,
  serial_match    boolean,
  serial_found    text,
  condition       text DEFAULT 'good',    -- 'good' | 'damaged' | 'missing_label'
  note            text,
  hq_note         text,
  photo_url       text,
  updated_at      timestamptz,
  UNIQUE(session_id, asset_id)
);

CREATE INDEX idx_scanlogs_session ON scan_logs(session_id);
CREATE INDEX idx_scanlogs_asset   ON scan_logs(asset_id);
CREATE INDEX idx_scanlogs_user    ON scan_logs(scanned_by);

-- 5. UNMATCHED ASSETS (สแกนได้ แต่ไม่พบใน master) -------------------

CREATE TABLE unmatched_assets (
  id                  uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  session_id          uuid NOT NULL REFERENCES audit_sessions(id),
  scanned_qr          text NOT NULL,
  serial_no           text,
  name_guess          text,
  category_guess      text,
  photo_url           text,
  scanned_by          uuid NOT NULL REFERENCES users(id),
  branch_id           uuid NOT NULL REFERENCES branches(id),
  scanned_at          timestamptz DEFAULT now(),
  status              text DEFAULT 'pending', -- 'pending' | 'matched' | 'new_asset' | 'disposed' | 'rejected'
  matched_asset_id    uuid REFERENCES assets(id),
  matched_asset_code  text,
  hq_reviewed_by      uuid REFERENCES users(id),
  hq_reviewed_at      timestamptz,
  hq_note             text,
  updated_at          timestamptz
);

CREATE INDEX idx_unmatched_session ON unmatched_assets(session_id);
CREATE INDEX idx_unmatched_status  ON unmatched_assets(status);

-- 6. SERIAL MISMATCH LOG (asset พบ แต่ serial ไม่ตรง) ----------------

CREATE TABLE serial_mismatches (
  id              uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  scan_log_id     uuid NOT NULL REFERENCES scan_logs(id),
  asset_id        uuid NOT NULL REFERENCES assets(id),
  serial_expected text,                   -- serial ใน master
  serial_found    text,                   -- serial ที่ user อ่านได้จากเครื่องจริง
  photo_url       text,
  status          text DEFAULT 'pending', -- 'pending' | 'resolved' | 'update_master'
  hq_note         text,
  created_at      timestamptz DEFAULT now()
);
```

### employee_holdings (เพิ่ม 2026-11-14 — `migration_employee_holdings.sql` รันแล้ว; ledger: `migration_holdings_ledger.sql` ยังไม่ได้รัน)
สมุดบันทึกการถือครอง — 1 แถว = 1 ช่วงเวลาที่พนักงานคนหนึ่งถืออุปกรณ์ 1 ชิ้น (`ended_at` NULL = ถืออยู่ปัจจุบัน); เปลี่ยนผู้ถือ = ปิดแถวเก่า (`ended_reason='transfer'`) แล้วเปิดแถวใหม่ (`start_source='transfer'`); Import ไม่ลบข้อมูลเดิมแล้ว (merge)

```sql
CREATE TABLE employee_holdings (
  id SERIAL PRIMARY KEY,
  person_name TEXT NOT NULL,     -- ชื่อตามไฟล์ (จับคู่กับ employees.full_name ฝั่ง Dashboard)
  dept_label TEXT,
  device_type TEXT NOT NULL,     -- 'Notebook' | 'CPU' | 'Monitor'
  model TEXT, asset_code TEXT, serial_no TEXT,
  import_batch_id TEXT, is_active BOOLEAN DEFAULT true, imported_at TIMESTAMPTZ DEFAULT now(),
  -- เพิ่มโดย migration_holdings_ledger.sql
  employee_id TEXT,              -- ผูกกับ employees.employee_id (text ไม่ใช่ FK)
  asset_key TEXT,                -- Serial (ตัวพิมพ์ใหญ่ ไม่มีช่องว่าง) หรือเลข Asset ที่มี SEQ; ใช้เชื่อมประวัติของอุปกรณ์ชิ้นเดียวกัน
  started_at DATE, start_source TEXT,  -- 'asset_code' | 'asset_summary' | 'manual' | 'transfer'
  ended_at DATE, ended_reason TEXT,    -- 'transfer' | 'return'
  recorded_by TEXT
);
```

## หมายเหตุการแก้ไข schema ที่เกิดขึ้นจริง

ระหว่างใช้งานจริง มีการเพิ่ม column ผ่าน migration เพิ่มเติม (idempotent ด้วย `IF NOT EXISTS`):

```sql
ALTER TABLE scan_logs        ADD COLUMN IF NOT EXISTS hq_note TEXT;
ALTER TABLE scan_logs        ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ;
ALTER TABLE unmatched_assets ADD COLUMN IF NOT EXISTS hq_note TEXT;
ALTER TABLE unmatched_assets ADD COLUMN IF NOT EXISTS matched_asset_code VARCHAR(50);
ALTER TABLE unmatched_assets ADD COLUMN IF NOT EXISTS reviewed_by INTEGER;
ALTER TABLE unmatched_assets ADD COLUMN IF NOT EXISTS reviewed_at TIMESTAMPTZ;
ALTER TABLE unmatched_assets ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ;

-- v0.8 — รองรับฟีเจอร์ Import Asset จาก Excel + Undo
ALTER TABLE assets ADD COLUMN IF NOT EXISTS import_batch_id TEXT;
ALTER TABLE assets ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT true;
UPDATE assets SET is_active = true WHERE is_active IS NULL;  -- backfill แถวเก่าก่อนมี column นี้
CREATE UNIQUE INDEX IF NOT EXISTS idx_assets_asset_code_seq ON assets(asset_code, seq);
CREATE TABLE IF NOT EXISTS import_batches (
  batch_id TEXT PRIMARY KEY, file_name TEXT, row_count INT,
  imported_by TEXT, imported_at TIMESTAMPTZ DEFAULT now(), status TEXT DEFAULT 'active'
);

-- 2026-11-12 — Write off asset ที่ยังไม่เคยสแกน (รันใน Neon แล้ว)
ALTER TABLE assets ADD COLUMN IF NOT EXISTS write_off_reason TEXT;
ALTER TABLE assets ADD COLUMN IF NOT EXISTS write_off_remark TEXT;
ALTER TABLE assets ADD COLUMN IF NOT EXISTS written_off_by TEXT;
ALTER TABLE assets ADD COLUMN IF NOT EXISTS written_off_at TIMESTAMPTZ;

-- 2026-11-12 — HQ ย้าย location ของ asset (รันใน Neon แล้ว)
ALTER TABLE assets ADD COLUMN IF NOT EXISTS location_override BOOLEAN DEFAULT false;
UPDATE assets SET location_override = false WHERE location_override IS NULL;
```

> **ข้อควรระวัง:** เคยเจอ error `column s.scheduled_date does not exist` เพราะ query ใน backend อ้างถึง column ที่ไม่เคยถูกสร้างจริงในฐานข้อมูล ก่อนแก้ query หรือเพิ่ม column ใหม่ ควรตรวจสอบ schema จริงในฐานข้อมูลก่อนเสมอ (ผ่าน Neon SQL editor หรือคำสั่ง `\d` ใน psql) เพื่อไม่ให้ code กับ database schema ไม่ตรงกัน

## View ที่มีอยู่

```sql
CREATE VIEW v_session_progress AS
-- ใช้สรุปความคืบหน้าของแต่ละ audit session
-- (จำนวน asset ทั้งหมดของสาขา เทียบกับจำนวนที่สแกนแล้วจริง)
```

## ความสัมพันธ์โดยสรุป

```
branches ──┬─< users
           ├─< assets ──< import_batches (ผ่าน assets.import_batch_id)
           └─< audit_sessions ──┬─< scan_logs ──< serial_mismatches
                                 └─< unmatched_assets
```

> **หมายเหตุ (v0.8):** คอลัมน์ `assets.status` เก็บค่าคำเต็ม (`active`/`disposed`/...) ส่วนไฟล์ Excel ต้นทางใช้รหัสย่อ (`A`/`D`/...) ตอน import ต้อง map ผ่าน `_STATUS_CODE_MAP` ใน `main.py` ก่อนเสมอ ห้ามยัดรหัสดิบจากไฟล์เข้า DB ตรงๆ เพราะ query ทุกหน้ากรองด้วยคำเต็ม

## รูปถ่าย (Storage)

รูปถ่ายจาก scan (column `photo_url` ใน `scan_logs` และ `unmatched_assets`) ไม่ได้เก็บใน Postgres โดยตรง แต่เก็บไฟล์จริงไว้ใน **Supabase Storage** แล้วบันทึกแค่ URL กลับเข้าฐานข้อมูล Neon — backend ใช้ `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, `SUPABASE_BUCKET` ในการอัปโหลด/ลบไฟล์ ดูรายละเอียดใน `deployment.md`
