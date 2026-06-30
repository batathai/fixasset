# Architecture — Bata Fixed Asset Audit System

## ภาพรวม

ระบบตรวจนับสินทรัพย์ถาวร (Fixed Asset Audit) สำหรับ Bata Thailand ประกอบด้วย 4 ส่วนหลัก ทำงานร่วมกันแบบ client-server ผ่าน REST API

```
┌─────────────────┐       ┌──────────────────┐       ┌──────────────────┐
│   Scanner App    │  HTTP  │   Backend API     │  SQL   │   Database        │
│  (index.html)     │ ─────► │  (FastAPI, Railway)│ ─────► │  (Postgres, Neon)  │
│  GitHub Pages      │ ◄───── │                    │ ◄───── │                    │
└─────────────────┘       └──────────────────┘       └──────────────────┘
        ▲                          ▲
        │                          │
┌─────────────────┐                │
│  HQ Dashboard     │ ──────────────┘
│  (dashboard.html)  │   เรียก endpoint /hq/* และ /dashboard/summary
│  GitHub Pages      │
└─────────────────┘
```

## Components

### 1. Scanner App
- Progressive Web App แบบ static HTML/JS หนึ่งไฟล์ (`index.html`)
- รันบน Android ผ่าน browser (Chrome) ไม่ต้อง build APK
- ใช้ไลบรารี `html5-qrcode` อ่าน QR code จากกล้อง
- Host บน GitHub Pages: `https://batathai.github.io/bata-asset/`
- หน้าที่: login ทีม audit, สแกน QR, ค้นหา asset, บันทึก scan log, ส่งข้อมูล unmatched/serial mismatch พร้อมรูปถ่าย

### 2. HQ Dashboard
- ไฟล์ static เดียว (`dashboard.html`) host บน GitHub Pages ที่ repo เดียวกัน
- ใช้สำหรับ admin ดูภาพรวม progress ของแต่ละสาขา, review รายการ unmatched/serial mismatch, export ข้อมูลเป็น Excel
- เรียก API ผ่าน endpoint กลุ่ม `/hq/*` และ `/dashboard/summary` เท่านั้น ไม่เชื่อมต่อ database โดยตรง

### 3. Backend API
- เขียนด้วย Python (FastAPI), ไฟล์หลักคือ `main.py`
- Deploy บน Railway: `https://bata-asset-api-production.up.railway.app`
- หน้าที่หลัก: ตรวจสอบสิทธิ์ (auth), เป็นตัวกลางเข้าถึง database อย่างปลอดภัย (ไม่เปิด DB ให้ browser เข้าตรง), อัปโหลด/ลบรูปถ่ายผ่าน Supabase Storage
- Auto-deploy ทุกครั้งที่ push โค้ดขึ้น GitHub repo `bata-asset-api`

### 4. Database
- Postgres บน Neon (เปลี่ยนจาก Supabase Database เดิม เพื่อให้ใช้ free plan ได้ไม่จำกัดจำนวน project — ดูรายละเอียดใน `deployment.md`)
- เก็บ schema เดียวกับที่ออกแบบไว้ตอนแรกใน Supabase (SQL เหมือนเดิมทุกบรรทัด มีแค่ connection string ต่างกัน)
- รูปถ่ายยังคงเก็บอยู่ใน **Supabase Storage** (ใช้เฉพาะส่วน storage ของ Supabase แม้ database หลักจะย้ายไป Neon แล้ว)

## Data Flow

1. ผู้ใช้ (auditor) login ผ่าน Scanner App → เรียก `POST /auth/login`
2. เลือกสาขา + สร้าง/เลือก audit session → `POST /sessions`
3. สแกน QR code บน asset → app เรียก `GET /assets/lookup/{qr_key}` ไปหา asset ใน database ผ่าน API
   - ถ้าพบ → บันทึก `POST /scans` พร้อมเช็ค serial number; ถ้า serial ไม่ตรงจะถูกบันทึกเป็น serial mismatch
   - ถ้าไม่พบ → ส่งเป็น unmatched asset ผ่าน `POST /unmatched` พร้อมรูปถ่ายและข้อมูลที่กรอกเอง
4. HQ Dashboard ดึงข้อมูลสรุปผ่าน `GET /dashboard/summary` และรายการรอตรวจสอบผ่าน `GET /hq/scans`, `GET /hq/unmatched`
5. Admin ที่ HQ review และ approve/reject ผ่าน `PATCH /hq/scans/{id}`, `PATCH /hq/unmatched/{id}` หรือ merge session ที่ซ้ำกันผ่าน `POST /hq/sessions/merge`

## เหตุผลของการออกแบบ

- **ไม่ให้ Scanner/Dashboard เชื่อม database โดยตรง** — เพื่อความปลอดภัย ป้องกันไม่ให้ใครก็ตามที่เปิด dev tools ดึงข้อมูลออกจาก database ได้ตรงๆ ทุกการเข้าถึงต้องผ่าน API ที่มีการตรวจสอบสิทธิ์ก่อน
- **รองรับ asset ที่ไม่มีในระบบ (unmatched)** — เนื่องจากข้อมูล asset master ที่ import มาจาก HQ อาจไม่ครบ 100% (มีเฉพาะ asset อายุ 5-7 ปีย้อนหลัง) ระบบจึงออกแบบ flow ให้ "รับของที่ไม่รู้จัก" ไว้ก่อน แล้วให้ HQ ไป reconcile ภายหลัง แทนที่จะปฏิเสธการสแกน
- **แยก scan_logs และ serial_mismatches** — เพื่อแยกกรณี asset ที่พบและตรงกับ master ออกจากกรณีที่พบ asset แต่ serial number ไม่ตรง (เช่น มีการสลับเครื่องคอมพิวเตอร์) ซึ่งต้องให้ HQ ตรวจสอบเพิ่มเติม
