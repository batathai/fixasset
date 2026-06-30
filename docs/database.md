# Database — Bata Fixed Asset Audit System

Database: **Postgres บน Neon** (`neon.tech`) — schema เดียวกับที่ออกแบบไว้บน Supabase เดิม เปลี่ยนแค่ connection string

## ภาพรวมตาราง

| ตาราง | หน้าที่ |
|---|---|
| `branches` | รายชื่อสาขาทั้งหมด |
| `users` | ผู้ใช้งานระบบ (auditor / branch_manager / hq_admin) |
| `assets` | ข้อมูล asset master ที่ import มาจาก Excel ของ HQ |
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

CREATE TABLE assets (
  id                uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  asset_code        text UNIQUE NOT NULL,    -- รหัสบน QR sticker เช่น "SFU022011050002"
  serial_no         text,                    -- Serial No. จริงของอุปกรณ์
  alt_codes         text[],                  -- รหัสสำรอง / รหัสเก่า
  name              text NOT NULL,
  category          text,                    -- "Computer", "Furniture", "Equipment"
  description       text,
  branch_id         uuid REFERENCES branches(id),
  location_detail   text,
  department        text,
  purchase_date     date,
  purchase_price    numeric(15,2),
  useful_life_years int,
  net_book_value    numeric(15,2),
  status            text DEFAULT 'active',   -- 'active' | 'disposed' | 'transferred' | 'missing'
  data_source       text DEFAULT 'hq_import',-- 'hq_import' | 'manual' | 'unmatched_approved'
  imported_at       timestamptz DEFAULT now(),
  updated_at        timestamptz DEFAULT now()
);

CREATE INDEX idx_assets_asset_code ON assets(asset_code);
CREATE INDEX idx_assets_serial_no  ON assets(serial_no);
CREATE INDEX idx_assets_branch_id  ON assets(branch_id);
CREATE INDEX idx_assets_status     ON assets(status);

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
           ├─< assets
           └─< audit_sessions ──┬─< scan_logs ──< serial_mismatches
                                 └─< unmatched_assets
```

## รูปถ่าย (Storage)

รูปถ่ายจาก scan (column `photo_url` ใน `scan_logs` และ `unmatched_assets`) ไม่ได้เก็บใน Postgres โดยตรง แต่เก็บไฟล์จริงไว้ใน **Supabase Storage** แล้วบันทึกแค่ URL กลับเข้าฐานข้อมูล Neon — backend ใช้ `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, `SUPABASE_BUCKET` ในการอัปโหลด/ลบไฟล์ ดูรายละเอียดใน `deployment.md`
