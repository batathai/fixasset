# Deployment — Bata Fixed Asset Audit System

ระบบประกอบด้วย 3 ส่วนที่ deploy แยกกัน ทั้งหมดอยู่ใน budget ฟรี

| ส่วน | Host | ค่าใช้จ่าย |
|---|---|---|
| Database (Postgres) | Neon (neon.tech) | ฟรี — ไม่จำกัดจำนวน project, 0.5 GB storage, ไม่มี auto-pause |
| Backend API (FastAPI) | Railway (railway.app) | ฟรี (free tier) |
| Scanner App + HQ Dashboard | GitHub Pages | ฟรี |
| รูปถ่าย (Storage) | Supabase Storage | ฟรี 1 GB |

> เดิมวางแผนใช้ Supabase ทั้ง Database + Auth + Storage แต่ Supabase free plan จำกัดที่ 2 projects และมี auto-pause หากไม่ใช้งานเกิน 1 สัปดาห์ จึงย้าย **เฉพาะ database** มาที่ Neon (SQL schema เหมือนเดิมทุกบรรทัด เปลี่ยนแค่ connection string) ส่วน **Storage รูปถ่าย** ยังใช้ Supabase ต่อ เพราะ Neon ไม่มี storage ในตัว

## 1. Database — Neon Postgres

1. สมัครที่ `neon.tech` (ใช้ Google login ได้) → Create Project → ตั้งชื่อ `fixed-asset-audit` → เลือก Region: **Singapore**
2. รัน SQL schema ทั้งหมด (ดู `database.md`) ผ่าน Neon SQL Editor
3. คัดลอก Connection String ที่ได้ทันทีหลังสร้าง project รูปแบบ:
   ```
   postgresql://user:pass@ep-xxx.ap-southeast-1.aws.neon.tech/neondb?sslmode=require
   ```
4. เก็บไว้ใช้เป็นค่า `DATABASE_URL`

## 2. Backend API — Railway

Repo: `bata-asset-api` (GitHub)

ไฟล์ที่ต้องมีใน repo:
- `main.py` — FastAPI app หลัก
- `requirements.txt`
- `Procfile`
- `railway.toml`
- `seed_users.py` — script สร้าง user เริ่มต้น

`requirements.txt`:
```
fastapi==0.111.0
uvicorn==0.29.0
psycopg2-binary==2.9.9
python-dotenv==1.0.1
pydantic==2.7.1
httpx
python-multipart
```

### ขั้นตอน deploy

1. Push โค้ดทั้งหมดขึ้น GitHub repo `bata-asset-api`
2. ไปที่ `railway.app` → สมัครด้วย GitHub → **New Project → Deploy from GitHub** → เลือก repo
3. ไปที่ **Variables** ใน Railway แล้วตั้งค่า:
   ```
   DATABASE_URL=postgresql://...neon.tech/neondb?sslmode=require
   SUPABASE_URL=https://xxxx.supabase.co
   SUPABASE_SERVICE_KEY=eyJ...   (ใช้ service_role key ไม่ใช่ anon key)
   SUPABASE_BUCKET=photos
   ```
4. Railway จะ build และ deploy อัตโนมัติ ได้ URL รูปแบบ:
   ```
   https://bata-asset-api-production.up.railway.app
   ```
5. ตรวจสอบว่า deploy สำเร็จ:
   - `GET /health` ควรคืน `{"status":"ok"}`
   - `GET /docs` ควรแสดง Swagger UI พร้อม endpoint ทั้งหมด
6. ก่อนใช้งานจริงครั้งแรก รัน `python seed_users.py` เพื่อสร้าง user ทดสอบ (เช่น `EMP001 / bata1234`, `ADMIN01 / admin999`)

### Auto-deploy

ทุกครั้งที่ push โค้ดใหม่ขึ้น branch `main` ของ repo `bata-asset-api` Railway จะ auto-deploy ให้อัตโนมัติ — ไม่ต้องสั่ง deploy เอง

### ข้อควรระวังเรื่อง migration

การแก้ logic ใน `main.py` (เช่น เปลี่ยนเงื่อนไข status) จะใช้ผลกับ scan/transaction ใหม่เท่านั้น ข้อมูลเก่าที่มีอยู่แล้วใน database ต้อง migrate ด้วยคำสั่ง SQL แยกต่างหาก เช่น:
```sql
UPDATE audit_sessions
SET status = 'on_process'
WHERE status = 'open'
  AND id IN (SELECT DISTINCT session_id FROM scan_logs);
```
หากเพิ่มฟีเจอร์ใหม่ที่ใช้ column ใหม่ ต้องรัน `ALTER TABLE ... ADD COLUMN IF NOT EXISTS ...` บน Neon ก่อน push โค้ดที่อ้างถึง column นั้นเสมอ ไม่อย่างนั้นจะเจอ error `psycopg2.errors.UndefinedColumn`

## 3. Frontend — GitHub Pages

ทั้ง Scanner App และ HQ Dashboard เป็นไฟล์ static HTML/JS ไฟล์เดียว host อยู่ใน repo `bata-asset` (repo คนละตัวกับ `bata-asset-api` ที่เป็น backend)

### Scanner App
1. ตั้งชื่อไฟล์เป็น `index.html` ก่อน upload (สำคัญ — เพื่อให้เป็นหน้า default ของ GitHub Pages)
2. ใน `index.html` ต้องแก้ตัวแปร API base URL ให้ตรงกับ Railway URL จริง:
   ```javascript
   const API = 'https://bata-asset-api-production.up.railway.app';
   ```
3. Upload ขึ้น repo `bata-asset`

### HQ Dashboard
1. Upload ขึ้น repo เดียวกัน (`bata-asset`) ในชื่อ `dashboard.html`
2. เข้าถึงได้ที่ `https://batathai.github.io/bata-asset/dashboard.html`

### เปิดใช้ GitHub Pages
ใน repo `bata-asset`: **Settings → Pages → Branch: `main`, folder: `/ (root)` → Save**

รอประมาณ 1-2 นาที จะได้:
```
https://batathai.github.io/bata-asset/           (Scanner App)
https://batathai.github.io/bata-asset/dashboard.html  (HQ Dashboard)
```

> หมายเหตุ: เปิดไฟล์ `.html` จาก local file โดยตรง (ดับเบิลคลิกเปิดใน Chrome) จะใช้กล้องสแกน QR ไม่ได้ เพราะ browser block การเข้าถึงกล้องบน local file — ต้อง deploy ขึ้นเว็บจริง (GitHub Pages) ก่อนใช้งานบน Android

## 4. Login ทดสอบ

| Role | Username | Password |
|---|---|---|
| Auditor | `EMP001` | `bata1234` |
| HQ Admin | `ADMIN01` | `admin999` |

## ตรวจสอบสุขภาพระบบ (Health Check)

| สิ่งที่เช็ค | URL |
|---|---|
| API ทำงานหรือไม่ | `https://bata-asset-api-production.up.railway.app/health` |
| ดู endpoint ทั้งหมด | `https://bata-asset-api-production.up.railway.app/docs` |
| Scanner App | `https://batathai.github.io/bata-asset/` |
| HQ Dashboard | `https://batathai.github.io/bata-asset/dashboard.html` |
