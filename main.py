from fastapi import FastAPI, HTTPException, Depends, Header, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List
import psycopg2, psycopg2.extras, os, hashlib, secrets, time, uuid, io
from datetime import datetime
from dotenv import load_dotenv
import httpx
import xlrd, openpyxl

load_dotenv()

app = FastAPI(title="Bata Asset Audit API", version="1.2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://batathai.github.io","http://localhost","http://127.0.0.1","*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_db():
    conn = psycopg2.connect(os.getenv("DATABASE_URL"), cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        yield conn
    finally:
        conn.close()

sessions = {}

def get_current_user(authorization: str = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")
    token = authorization.split(" ")[1]
    if token not in sessions:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return sessions[token]

# ════════════════════════════════════════════════════════════════
# MODELS
# ════════════════════════════════════════════════════════════════
class LoginRequest(BaseModel):
    employee_id: str
    password: str
    branch_id: str

class ScanLogCreate(BaseModel):
    session_id: int
    qr_key: str
    serial_found: Optional[str] = None
    serial_match: Optional[bool] = None
    condition: str = "good"
    remark: Optional[str] = None
    photo_url: Optional[str] = None

class UnmatchedCreate(BaseModel):
    session_id: int
    scanned_qr: str
    serial_no: Optional[str] = None
    name_guess: Optional[str] = None
    photo_url: Optional[str] = None
    remark: Optional[str] = None

class SessionCreate(BaseModel):
    branch_id: str
    audit_date: str
    name: Optional[str] = None

class ScanLogUpdate(BaseModel):
    condition: Optional[str] = None
    serial_found: Optional[str] = None
    hq_note: Optional[str] = None

class UnmatchedUpdate(BaseModel):
    status: str
    hq_note: Optional[str] = None
    matched_asset_code: Optional[str] = None
    serial_no: Optional[str] = None

class MergeSessionsRequest(BaseModel):
    primary_session_id: int
    merge_session_ids: List[int]
    branch_id: str

# ════════════════════════════════════════════════════════════════
# CLOUDINARY HELPERS
# ════════════════════════════════════════════════════════════════
def _cloudinary_public_id(url: str) -> str:
    url = url.split("?")[0]
    if "/upload/" not in url:
        return ""
    after_upload = url.split("/upload/", 1)[1]
    parts = after_upload.split("/")
    if parts[0].startswith("v") and parts[0][1:].isdigit():
        parts = parts[1:]
    path = "/".join(parts)
    if "." in path.rsplit("/", 1)[-1]:
        path = path.rsplit(".", 1)[0]
    return path

def _cloudinary_sign(params: dict, api_secret: str) -> str:
    sorted_params = "&".join(
        f"{k}={v}" for k, v in sorted(params.items())
        if k not in ("file", "api_key", "resource_type")
    )
    return hashlib.sha1(f"{sorted_params}{api_secret}".encode()).hexdigest()

# ════════════════════════════════════════════════════════════════
# AUTH
# ════════════════════════════════════════════════════════════════
@app.post("/auth/login")
def login(req: LoginRequest, db=Depends(get_db)):
    cur = db.cursor()
    cur.execute("SELECT id, full_name, role, password_hash FROM users WHERE email = %s AND is_active = true", (req.employee_id,))
    user = cur.fetchone()
    pw_hash = hashlib.sha256(req.password.encode()).hexdigest()
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if not user["password_hash"]:
        cur.execute("UPDATE users SET password_hash = %s WHERE id = %s", (pw_hash, user["id"]))
        db.commit()
    elif user["password_hash"] != pw_hash:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = secrets.token_hex(32)
    sessions[token] = {"user_id": user["id"], "employee_id": req.employee_id, "branch_id": req.branch_id, "full_name": user["full_name"], "role": user["role"]}
    return {"token": token, "employee_id": req.employee_id, "full_name": user["full_name"], "branch_id": req.branch_id, "role": user["role"]}

@app.post("/auth/logout")
def logout(authorization: str = Header(None)):
    if authorization and authorization.startswith("Bearer "):
        sessions.pop(authorization.split(" ")[1], None)
    return {"ok": True}

# ════════════════════════════════════════════════════════════════
# ASSETS
# ════════════════════════════════════════════════════════════════
@app.get("/assets/lookup/{qr_key}")
def lookup_asset(qr_key: str, db=Depends(get_db), user=Depends(get_current_user)):
    cur = db.cursor()
    cur.execute("SELECT * FROM assets WHERE qr_key = %s", (qr_key,))
    asset = cur.fetchone()
    if not asset:
        return {"found": False, "qr_key": qr_key}
    return {"found": True, "asset": dict(asset)}

@app.get("/assets/branch/{branch_id}")
def assets_by_branch(branch_id: str, db=Depends(get_db), user=Depends(get_current_user)):
    cur = db.cursor()
    # ดึง master list ทั้งหมดของ branch (ใช้ location_code)
    cur.execute("""
        SELECT id, qr_key, asset_code, seq, name, serial_no,
               purchase_date, status, location_code
        FROM assets
        WHERE location_code = %s AND status = 'active' AND COALESCE(is_active, true) = true
        ORDER BY asset_code, seq
    """, (branch_id,))
    rows = cur.fetchall()

    # Fallback: ถ้าได้น้อยกว่า 10 ให้ดึงจาก scan_logs ที่ branch นี้เคย scan
    if len(rows) < 10:
        cur.execute("""
            SELECT DISTINCT a.id, a.qr_key, a.asset_code, a.seq, a.name,
                   a.serial_no, a.purchase_date, a.status, a.location_code
            FROM assets a
            JOIN scan_logs sl ON sl.asset_id = a.id
            JOIN audit_sessions s ON s.id = sl.session_id
            WHERE s.branch_id = %s AND COALESCE(a.is_active, true) = true
            UNION
            SELECT id, qr_key, asset_code, seq, name, serial_no,
                   purchase_date, status, location_code
            FROM assets
            WHERE location_code = %s AND COALESCE(is_active, true) = true
            ORDER BY asset_code, seq
        """, (branch_id, branch_id))
        rows = cur.fetchall()

    return {"assets": [dict(r) for r in rows]}

# ════════════════════════════════════════════════════════════════
# AUDIT SESSIONS
# audit_sessions columns: id, name, branch_id, audit_date,
#                         started_by, status, created_at, closed_at
# ════════════════════════════════════════════════════════════════
@app.post("/sessions")
def create_session(req: SessionCreate, db=Depends(get_db), user=Depends(get_current_user)):
    cur = db.cursor()
    name = req.name or f"Audit {req.branch_id} {req.audit_date}"
    # ใช้ status != 'done' แทน status = 'open' เพื่อให้ยังจับคู่ session เดิมได้
    # แม้ status จะถูกเปลี่ยนเป็น 'on_process' ไปแล้วหลังมีคนสแกนชิ้นแรก
    # (เดิมเช็คแค่ 'open' ทำให้คนที่ login ตามมาทีหลังได้ session ใหม่ซ้ำซ้อน)
    cur.execute("SELECT id FROM audit_sessions WHERE branch_id = %s AND audit_date = %s AND status != 'done'", (req.branch_id, req.audit_date))
    existing = cur.fetchone()
    if existing:
        return {"session_id": existing["id"], "reused": True}
    cur.execute("INSERT INTO audit_sessions (name, branch_id, audit_date, started_by, status) VALUES (%s,%s,%s,%s,'open') RETURNING id",
                (name, req.branch_id, req.audit_date, user["user_id"]))
    session_id = cur.fetchone()["id"]
    db.commit()
    return {"session_id": session_id, "reused": False}

@app.get("/sessions/{session_id}/progress")
def session_progress(session_id: int, db=Depends(get_db), user=Depends(get_current_user)):
    cur = db.cursor()
    cur.execute("""
        SELECT
            s.id AS session_id, s.branch_id, s.name, s.status, s.audit_date,
            s.created_at, s.closed_at,
            COUNT(sl.id) AS scanned_count,
            (SELECT COUNT(*) FROM assets a
             WHERE a.location_code = s.branch_id AND a.status = 'active') AS total_assets
            (SELECT COUNT(*) FROM unmatched_assets ua WHERE ua.session_id = s.id AND ua.status = 'pending') AS unmatched_count
        FROM audit_sessions s
        LEFT JOIN scan_logs sl ON sl.session_id = s.id
        WHERE s.id = %s
        GROUP BY s.id, s.branch_id, s.name, s.status, s.audit_date, s.created_at, s.closed_at
    """, (session_id,))
    row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Session not found")
    return dict(row)

@app.patch("/sessions/{session_id}/close")
def close_session(session_id: int, db=Depends(get_db), user=Depends(get_current_user)):
    cur = db.cursor()
    cur.execute("UPDATE audit_sessions SET status='done', closed_at=now() WHERE id=%s RETURNING id", (session_id,))
    if not cur.fetchone():
        raise HTTPException(status_code=404, detail="Session not found")
    db.commit()
    return {"ok": True}

# ════════════════════════════════════════════════════════════════
# SCAN LOGS
# scan_logs columns: id, session_id, asset_id, scanned_by,
#   scanned_at, serial_verified, serial_match, serial_found,
#   condition, remark, photo_url, hq_note, updated_at
# ════════════════════════════════════════════════════════════════
@app.post("/scans")
def create_scan(req: ScanLogCreate, db=Depends(get_db), user=Depends(get_current_user)):
    cur = db.cursor()
    cur.execute("SELECT id FROM assets WHERE qr_key = %s", (req.qr_key,))
    asset = cur.fetchone()
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    # เช็คซ้ำข้าม session ในวันเดียวกัน branch เดียวกัน
    # ดึง scanned_by (ชื่อคนสแกน) + scanned_at ออกมาด้วย เพื่อส่งกลับให้ client
    # ตาม contract ใน API.md ({"error":"already_scanned","scanned_by":...,"scanned_at":...})
    # เดิมส่งแค่ detail เป็น string ธรรมดา ทำให้ฝั่ง index.html เช็ค data.error ไม่เจอ
    # และไม่ rollback การ์ดที่ขึ้น "Verified" แบบ optimistic ไปก่อนหน้า กลายเป็นบั๊ก
    # "สแกนซ้ำแล้วยังขึ้น Verified" ที่หน้างานเจอ
    cur.execute("""
        SELECT sl.id, sl.scanned_at, u.full_name AS scanned_by_name
        FROM scan_logs sl
        JOIN audit_sessions s ON s.id = sl.session_id
        LEFT JOIN users u ON u.id = sl.scanned_by
        WHERE sl.asset_id = %s
          AND s.branch_id = (SELECT branch_id FROM audit_sessions WHERE id = %s)
          AND s.audit_date = (SELECT audit_date FROM audit_sessions WHERE id = %s)
    """, (asset["id"], req.session_id, req.session_id))
    dup = cur.fetchone()
    if dup:
        raise HTTPException(status_code=409, detail={
            "error": "already_scanned",
            "scanned_by": dup["scanned_by_name"] or "unknown",
            "scanned_at": str(dup["scanned_at"])
        })
    # เช็คซ้ำเฉพาะ session นี้ (กรณี edge case ที่ query ข้างบนพลาด เช่น audit_date ไม่ตรงกันแบบไม่คาดคิด)
    cur.execute("""
        SELECT sl.id, sl.scanned_at, u.full_name AS scanned_by_name
        FROM scan_logs sl
        LEFT JOIN users u ON u.id = sl.scanned_by
        WHERE sl.session_id = %s AND sl.asset_id = %s
    """, (req.session_id, asset["id"]))
    dup2 = cur.fetchone()
    if dup2:
        raise HTTPException(status_code=409, detail={
            "error": "already_scanned",
            "scanned_by": dup2["scanned_by_name"] or "unknown",
            "scanned_at": str(dup2["scanned_at"])
        })
    cur.execute("""
        INSERT INTO scan_logs
            (session_id, asset_id, scanned_by, serial_found, serial_match, condition, remark, photo_url)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id
    """, (req.session_id, asset["id"], user["user_id"], req.serial_found,
          req.serial_match, req.condition, req.remark, req.photo_url))
    scan_id = cur.fetchone()["id"]
    cur.execute("UPDATE audit_sessions SET status = 'on_process' WHERE id = %s AND status = 'open'", (req.session_id,))
    db.commit()
    return {"scan_id": scan_id, "asset_id": asset["id"]}

@app.get("/sessions/{session_id}/scans")
def get_scans(session_id: int, db=Depends(get_db), user=Depends(get_current_user)):
    cur = db.cursor()
    cur.execute("""
        SELECT sl.id, sl.scanned_at, sl.serial_match, sl.condition, sl.remark,
               a.qr_key, a.name, a.serial_no
        FROM scan_logs sl
        JOIN assets a ON a.id = sl.asset_id
        WHERE sl.session_id = %s
        ORDER BY sl.scanned_at DESC
    """, (session_id,))
    return {"scans": [dict(r) for r in cur.fetchall()]}

# ════════════════════════════════════════════════════════════════
# UNMATCHED ASSETS
# unmatched_assets columns: id, session_id, scanned_qr, serial_no,
#   name_guess, photo_url, scanned_by, branch_id, scanned_at,
#   status, hq_note, reviewed_at, matched_asset_code,
#   reviewed_by, updated_at
# ════════════════════════════════════════════════════════════════
@app.post("/unmatched")
def create_unmatched(req: UnmatchedCreate, db=Depends(get_db), user=Depends(get_current_user)):
    cur = db.cursor()
    cur.execute("""
        INSERT INTO unmatched_assets
            (session_id, scanned_qr, serial_no, name_guess, photo_url, scanned_by, branch_id)
        VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING id
    """, (req.session_id, req.scanned_qr, req.serial_no, req.name_guess,
          req.photo_url, user["user_id"], user["branch_id"]))
    uid = cur.fetchone()["id"]
    db.commit()
    return {"unmatched_id": uid}

@app.get("/unmatched/pending")
def pending_unmatched(db=Depends(get_db), user=Depends(get_current_user)):
    if user["role"] != "hq_admin":
        raise HTTPException(status_code=403, detail="HQ admin only")
    cur = db.cursor()
    cur.execute("""
        SELECT ua.*, u.email as auditor FROM unmatched_assets ua
        LEFT JOIN users u ON u.id = ua.scanned_by
        WHERE ua.status = 'pending' ORDER BY ua.scanned_at DESC
    """)
    return {"items": [dict(r) for r in cur.fetchall()]}

# ════════════════════════════════════════════════════════════════
# DASHBOARD — คำนวณจาก scan_logs จริง ไม่ใช้ v_session_progress
# ════════════════════════════════════════════════════════════════
@app.get("/dashboard/summary")
def dashboard_summary(db=Depends(get_db), user=Depends(get_current_user)):
    cur = db.cursor()
    cur.execute("""
        SELECT
            s.id          AS session_id,
            s.branch_id,
            s.name,
            s.status,
            s.audit_date,
            s.created_at,
            s.closed_at,
            s.started_by,
            COUNT(sl.id)  AS scanned_count,
            (SELECT COUNT(*) FROM assets a
             WHERE a.location_code = s.branch_id
               AND a.status = 'active') AS total_assets,
            (SELECT COUNT(*) FROM unmatched_assets ua
             WHERE ua.session_id = s.id
               AND ua.status = 'pending') AS unmatched_count
        FROM audit_sessions s
        LEFT JOIN scan_logs sl ON sl.session_id = s.id
        GROUP BY s.id, s.branch_id, s.name, s.status,
                 s.audit_date, s.created_at, s.closed_at, s.started_by
        ORDER BY s.audit_date DESC
    """)
    sessions_data = [dict(r) for r in cur.fetchall()]

    # Fallback: ถ้า total_assets = 0 ให้ใช้จำนวน distinct asset ที่ scan ไปแล้ว
    for s in sessions_data:
        if not s["total_assets"]:
            cur.execute("""
                SELECT COUNT(DISTINCT asset_id) AS cnt FROM scan_logs WHERE session_id = %s
            """, (s["session_id"],))
            s["total_assets"] = cur.fetchone()["cnt"] or 0

    cur.execute("SELECT COUNT(*) as total FROM assets WHERE status='active'")
    total_assets = cur.fetchone()["total"]
    cur.execute("SELECT COUNT(*) as total FROM unmatched_assets WHERE status='pending'")
    pending_unmatched = cur.fetchone()["total"]

    return {
        "total_assets": total_assets,
        "pending_unmatched": pending_unmatched,
        "sessions": sessions_data
    }

# ════════════════════════════════════════════════════════════════
# HQ ENDPOINTS
# ════════════════════════════════════════════════════════════════
@app.get("/hq/scans")
def hq_get_scans(db=Depends(get_db), user=Depends(get_current_user)):
    if user["role"] != "hq_admin":
        raise HTTPException(status_code=403, detail="HQ admin only")
    cur = db.cursor()
    cur.execute("""
        SELECT sl.id, sl.condition, sl.serial_found, sl.serial_match, sl.photo_url,
               sl.scanned_at, sl.hq_note, a.asset_code, a.seq, a.qr_key,
               a.name AS asset_name, a.serial_no AS serial_master,
               u.email AS auditor,
               s.id AS session_id, b.id AS branch_id, b.name AS branch_name
        FROM scan_logs sl
        LEFT JOIN assets a ON a.id = sl.asset_id
        LEFT JOIN users u ON u.id = sl.scanned_by
        LEFT JOIN audit_sessions s ON s.id = sl.session_id
        LEFT JOIN branches b ON b.id = s.branch_id
        ORDER BY sl.scanned_at DESC
    """)
    return {"scans": [dict(r) for r in cur.fetchall()]}

@app.patch("/hq/scans/{scan_id}")
def hq_update_scan(scan_id: int, req: ScanLogUpdate, db=Depends(get_db), user=Depends(get_current_user)):
    if user["role"] != "hq_admin":
        raise HTTPException(status_code=403, detail="HQ admin only")
    cur = db.cursor()
    fields, values = [], []
    if req.condition is not None:
        fields.append("condition = %s"); values.append(req.condition)
    if req.serial_found is not None:
        fields.append("serial_found = %s"); values.append(req.serial_found or None)
    if req.hq_note is not None:
        fields.append("hq_note = %s"); values.append(req.hq_note or None)
    if not fields:
        raise HTTPException(status_code=400, detail="No fields to update")
    fields.append("updated_at = NOW()")
    values.append(scan_id)
    cur.execute(f"UPDATE scan_logs SET {', '.join(fields)} WHERE id = %s RETURNING id", values)
    if not cur.fetchone():
        raise HTTPException(status_code=404, detail="Scan log not found")
    db.commit()
    return {"ok": True, "scan_id": scan_id}

@app.delete("/hq/scans/{scan_id}")
def hq_delete_scan(scan_id: int, db=Depends(get_db), user=Depends(get_current_user)):
    if user["role"] != "hq_admin":
        raise HTTPException(status_code=403, detail="HQ admin only")
    cur = db.cursor()
    cur.execute("DELETE FROM scan_logs WHERE id = %s RETURNING id", (scan_id,))
    if not cur.fetchone():
        raise HTTPException(status_code=404, detail="Scan not found")
    db.commit()
    return {"ok": True}

@app.delete("/hq/scans/{scan_id}/photo", status_code=204)
async def hq_delete_scan_photo(scan_id: int, db=Depends(get_db), user=Depends(get_current_user)):
    if user["role"] != "hq_admin":
        raise HTTPException(status_code=403, detail="HQ admin only")
    cur = db.cursor()
    cur.execute("SELECT photo_url FROM scan_logs WHERE id = %s", (scan_id,))
    row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Scan not found")
    old_url = row["photo_url"]
    if old_url and "cloudinary.com" in old_url:
        try:
            cloud  = os.getenv("CLOUDINARY_CLOUD_NAME", "")
            key    = os.getenv("CLOUDINARY_API_KEY", "")
            secret = os.getenv("CLOUDINARY_API_SECRET", "")
            if cloud and key and secret:
                public_id = _cloudinary_public_id(old_url)
                if public_id:
                    ts  = int(time.time())
                    sig = _cloudinary_sign({"public_id": public_id, "timestamp": ts}, secret)
                    async with httpx.AsyncClient() as client:
                        await client.post(
                            f"https://api.cloudinary.com/v1_1/{cloud}/image/destroy",
                            data={"public_id": public_id, "timestamp": ts,
                                  "api_key": key, "signature": sig}, timeout=15)
        except Exception as e:
            print(f"[WARN] Cloudinary delete failed: {e}")
    cur.execute("UPDATE scan_logs SET photo_url = NULL, updated_at = NOW() WHERE id = %s", (scan_id,))
    db.commit()
    cur.close()

@app.post("/hq/scans/{scan_id}/photo")
async def hq_upload_scan_photo(scan_id: int, photo: UploadFile = File(...), db=Depends(get_db), user=Depends(get_current_user)):
    if user["role"] != "hq_admin":
        raise HTTPException(status_code=403, detail="HQ admin only")
    if not photo.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="รองรับเฉพาะไฟล์รูปภาพ")
    content = await photo.read()
    if len(content) > 5 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="ไฟล์ใหญ่เกิน 5MB")
    cur = db.cursor()
    cur.execute("""
        SELECT b.id as branch_id FROM scan_logs sl
        LEFT JOIN audit_sessions s ON s.id = sl.session_id
        LEFT JOIN branches b ON b.id = s.branch_id
        WHERE sl.id = %s
    """, (scan_id,))
    row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Scan not found")
    branch_id = row["branch_id"] or "unknown"
    cloud  = os.getenv("CLOUDINARY_CLOUD_NAME", "")
    key    = os.getenv("CLOUDINARY_API_KEY", "")
    secret = os.getenv("CLOUDINARY_API_SECRET", "")
    if not (cloud and key and secret):
        raise HTTPException(status_code=500, detail="Cloudinary ยังไม่ได้ตั้งค่า ENV")
    ts        = int(time.time())
    public_id = f"bata-audit/{branch_id}/scan_{scan_id}_{ts}"
    sig       = _cloudinary_sign({"public_id": public_id, "timestamp": ts}, secret)
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"https://api.cloudinary.com/v1_1/{cloud}/image/upload",
            data={"api_key": key, "timestamp": ts, "signature": sig, "public_id": public_id},
            files={"file": (photo.filename, content, photo.content_type)}, timeout=30)
    if resp.status_code != 200:
        raise HTTPException(status_code=500, detail=f"Upload ไม่สำเร็จ: {resp.text[:200]}")
    photo_url = resp.json().get("secure_url", "")
    if not photo_url:
        raise HTTPException(status_code=500, detail="ไม่ได้รับ URL จาก Cloudinary")
    cur.execute("UPDATE scan_logs SET photo_url = %s, updated_at = NOW() WHERE id = %s", (photo_url, scan_id))
    db.commit()
    cur.close()
    return {"photo_url": photo_url}

@app.patch("/hq/unmatched/{unmatched_id}")
def hq_update_unmatched(unmatched_id: int, req: UnmatchedUpdate, db=Depends(get_db), user=Depends(get_current_user)):
    if user["role"] != "hq_admin":
        raise HTTPException(status_code=403, detail="HQ admin only")
    if req.status not in ("matched", "rejected"):
        raise HTTPException(status_code=400, detail="status must be 'matched' or 'rejected'")
    cur = db.cursor()
    cur.execute("""
        SELECT ua.*, u.full_name as auditor_name FROM unmatched_assets ua
        LEFT JOIN users u ON u.id = ua.scanned_by
        WHERE ua.id = %s
    """, (unmatched_id,))
    um = cur.fetchone()
    if not um:
        raise HTTPException(status_code=404, detail="Unmatched asset not found")
    hq_note = req.hq_note or f"{'Matched' if req.status == 'matched' else 'Rejected'} by HQ - {user['employee_id']}"
    cur.execute("""
        UPDATE unmatched_assets
        SET status=%s, hq_note=%s, matched_asset_code=%s,
            serial_no=COALESCE(%s,serial_no), reviewed_by=%s,
            reviewed_at=NOW(), updated_at=NOW()
        WHERE id=%s
    """, (req.status, hq_note, req.matched_asset_code, req.serial_no, user["user_id"], unmatched_id))
    if req.status == "matched" and req.matched_asset_code:
        cur.execute("SELECT id FROM assets WHERE asset_code = %s LIMIT 1", (req.matched_asset_code,))
        asset = cur.fetchone()
        if asset:
            cur.execute("""
                INSERT INTO scan_logs
                    (session_id, asset_id, scanned_by, serial_found, serial_match,
                     condition, remark, photo_url, hq_note, scanned_at)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT DO NOTHING
            """, (um["session_id"], asset["id"], um["scanned_by"],
                  req.serial_no or um.get("serial_no"), None, "good",
                  f"[Matched from Unmatched] QR: {um['scanned_qr']}",
                  um.get("photo_url"), hq_note,
                  um.get("scanned_at") or datetime.now()))
    db.commit()
    return {"ok": True, "unmatched_id": unmatched_id, "status": req.status}

@app.get("/hq/unmatched")
def hq_get_unmatched(db=Depends(get_db), user=Depends(get_current_user)):
    if user["role"] != "hq_admin":
        raise HTTPException(status_code=403, detail="HQ admin only")
    cur = db.cursor()
    cur.execute("""
        SELECT ua.id, ua.scanned_qr, ua.name_guess, ua.serial_no, ua.photo_url,
               ua.scanned_at, ua.status, ua.hq_note, ua.matched_asset_code,
               u.email AS auditor, b.id AS branch_id, b.name AS branch_name
        FROM unmatched_assets ua
        LEFT JOIN users u ON u.id = ua.scanned_by
        LEFT JOIN audit_sessions s ON s.id = ua.session_id
        LEFT JOIN branches b ON b.id = s.branch_id
        ORDER BY ua.scanned_at DESC
    """)
    return {"items": [dict(r) for r in cur.fetchall()]}

@app.get("/hq/assets")
def hq_get_all_assets(db=Depends(get_db), user=Depends(get_current_user)):
    if user["role"] != "hq_admin":
        raise HTTPException(status_code=403, detail="HQ admin only")
    cur = db.cursor()
    cur.execute("""
        SELECT a.id, a.qr_key, a.asset_code, a.seq, a.name, a.serial_no,
               a.location_code, a.purchase_date, a.status,
               CASE WHEN sl.id IS NOT NULL THEN true ELSE false END AS is_scanned,
               sl.scanned_at, u.email AS scanned_by, s.branch_id
        FROM assets a
        LEFT JOIN scan_logs sl ON sl.asset_id = a.id
        LEFT JOIN users u ON u.id = sl.scanned_by
        LEFT JOIN audit_sessions s ON s.id = sl.session_id
        WHERE a.status = 'active' AND COALESCE(a.is_active, true) = true
        ORDER BY a.location_code, a.asset_code, a.seq
    """)
    assets = [dict(r) for r in cur.fetchall()]
    total   = len(assets)
    scanned = sum(1 for a in assets if a["is_scanned"])
    return {"total": total, "scanned": scanned, "pending": total - scanned, "assets": assets}

@app.delete("/hq/sessions/{session_id}")
def hq_delete_session(session_id: int, db=Depends(get_db), user=Depends(get_current_user)):
    if user["role"] != "hq_admin":
        raise HTTPException(status_code=403, detail="HQ admin only")
    cur = db.cursor()
    cur.execute("DELETE FROM scan_logs WHERE session_id = %s", (session_id,))
    cur.execute("DELETE FROM unmatched_assets WHERE session_id = %s", (session_id,))
    cur.execute("DELETE FROM audit_sessions WHERE id = %s RETURNING id", (session_id,))
    if not cur.fetchone():
        raise HTTPException(status_code=404, detail="Session not found")
    db.commit()
    return {"ok": True, "session_id": session_id}

@app.post("/hq/sessions/merge")
def hq_merge_sessions(req: MergeSessionsRequest, db=Depends(get_db), user=Depends(get_current_user)):
    if user["role"] != "hq_admin":
        raise HTTPException(status_code=403, detail="HQ admin only")
    if not req.merge_session_ids:
        raise HTTPException(status_code=400, detail="ไม่มี session ที่ต้อง merge")
    cur = db.cursor()
    cur.execute("SELECT id FROM audit_sessions WHERE id = %s", (req.primary_session_id,))
    if not cur.fetchone():
        raise HTTPException(status_code=404, detail=f"Primary session #{req.primary_session_id} ไม่พบ")
    moved_scans = moved_unmatched = deleted_sessions = 0
    for sid in req.merge_session_ids:
        if sid == req.primary_session_id:
            continue
        cur.execute("""
            UPDATE scan_logs SET session_id=%s
            WHERE session_id=%s
              AND asset_id NOT IN (SELECT asset_id FROM scan_logs WHERE session_id=%s)
        """, (req.primary_session_id, sid, req.primary_session_id))
        moved_scans += cur.rowcount
        cur.execute("DELETE FROM scan_logs WHERE session_id = %s", (sid,))
        cur.execute("UPDATE unmatched_assets SET session_id=%s WHERE session_id=%s", (req.primary_session_id, sid))
        moved_unmatched += cur.rowcount
        cur.execute("DELETE FROM audit_sessions WHERE id = %s", (sid,))
        deleted_sessions += cur.rowcount
    cur.execute("""
        UPDATE audit_sessions SET status='on_process'
        WHERE id=%s AND status='open'
          AND EXISTS (SELECT 1 FROM scan_logs WHERE session_id=%s)
    """, (req.primary_session_id, req.primary_session_id))
    db.commit()
    cur.close()
    return {"ok": True, "primary_session_id": req.primary_session_id,
            "deleted_sessions": deleted_sessions, "moved_scans": moved_scans,
            "moved_unmatched": moved_unmatched}

# ════════════════════════════════════════════════════════════════
# ASSET IMPORT (HQ only)
# ════════════════════════════════════════════════════════════════
EXPECTED_COLUMNS = [
    "รหัสสินทรัพย์", "ลำดับ", "รหัสที่ตั้ง", "ชื่อที่ตั้ง",
    "รายละเอียดสินทรัพย์(อังกฤษ)", "สถานะสินทรัพย์", "เลขที่เครื่อง",
    "วันที่ซื้อ", "จำนวน", "มูลค่าสินทรัพย์", "คสส.", "มูลค่าทางบัญชี",
]

def _parse_thai_date_string(value):
    """แปลง string วันที่ที่มาจากไฟล์ Excel (เก็บเป็น text ไม่ใช่ date serial) ให้เป็น ISO YYYY-MM-DD
    รองรับรูปแบบที่เจอจริง: 26/06/2026 (DD/MM/YYYY ค.ศ.), 26/06/2569 (DD/MM/YYYY พ.ศ.)"""
    if not value:
        return None
    s = str(value).strip()
    if not s:
        return None
    for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(s, fmt)
            year = dt.year
            if year > 2400:  # พ.ศ. -> ค.ศ.
                year -= 543
            return f"{year:04d}-{dt.month:02d}-{dt.day:02d}"
        except ValueError:
            continue
    # เผื่อรูปแบบไม่ตรง pattern ใดเลย ส่งกลับ None แทนที่จะยิงค่าผิดเข้า DB
    return None


def _parse_asset_excel(content: bytes, filename: str):
    """อ่านไฟล์ .xls/.xlsx แล้วคืน list of dict ที่ map เป็นชื่อ column ของ DB แล้ว"""
    rows_out = []

    def _row_to_dict(values):
        if not values or not str(values[0]).strip():
            return None
        if str(values[0]).strip().lower() in ("grand total", "รหัสสินทรัพย์"):
            return None
        try:
            asset_code = str(values[0]).strip()
            seq        = str(values[1]).strip() if values[1] not in (None, "") else ""
            location_code = str(values[2]).strip() if len(values) > 2 else ""
            location_name = str(values[3]).strip() if len(values) > 3 else ""
            name          = str(values[4]).strip() if len(values) > 4 else ""
            status        = str(values[5]).strip() if len(values) > 5 else "A"
            serial_no     = str(values[6]).strip() if len(values) > 6 and values[6] else None
            purchase_date_raw = values[7] if len(values) > 7 else None
            qty            = float(values[8]) if len(values) > 8 and values[8] not in (None, "") else 0
            purchase_price = float(values[9]) if len(values) > 9 and values[9] not in (None, "") else 0
            accumulated_dep = float(values[10]) if len(values) > 10 and values[10] not in (None, "") else 0
            net_book_value  = float(values[11]) if len(values) > 11 and values[11] not in (None, "") else 0
        except (ValueError, IndexError) as e:
            raise HTTPException(status_code=400, detail=f"แถวข้อมูลผิดรูปแบบ: {values} ({e})")
        if not asset_code:
            return None
        return {
            "asset_code": asset_code, "seq": seq, "qr_key": asset_code + seq,
            "location_code": location_code, "location_name": location_name,
            "name": name, "status": status, "serial_no": serial_no,
            "purchase_date_raw": purchase_date_raw,
            "qty": qty, "purchase_price": purchase_price,
            "accumulated_dep": accumulated_dep, "net_book_value": net_book_value,
        }

    if filename.lower().endswith(".xls"):
        wb = xlrd.open_workbook(file_contents=content)
        sheet = wb.sheet_by_index(0)
        for r in range(1, sheet.nrows):
            values = sheet.row_values(r)
            d = _row_to_dict(values)
            if d:
                if isinstance(d["purchase_date_raw"], float):
                    y, m, day, *_ = xlrd.xldate_as_tuple(d["purchase_date_raw"], wb.datemode)
                    d["purchase_date"] = f"{y:04d}-{m:02d}-{day:02d}"
                else:
                    d["purchase_date"] = _parse_thai_date_string(d["purchase_date_raw"])
                rows_out.append(d)
    elif filename.lower().endswith(".xlsx"):
        wb = openpyxl.load_workbook(io.BytesIO(content), data_only=True)
        sheet = wb.worksheets[0]
        for row in sheet.iter_rows(min_row=2, values_only=True):
            d = _row_to_dict(list(row))
            if d:
                pd = d["purchase_date_raw"]
                d["purchase_date"] = pd.strftime("%Y-%m-%d") if hasattr(pd, "strftime") else _parse_thai_date_string(pd)
                rows_out.append(d)
    else:
        raise HTTPException(status_code=400, detail="รองรับเฉพาะไฟล์ .xls หรือ .xlsx เท่านั้น")

    if not rows_out:
        raise HTTPException(status_code=400, detail="ไม่พบข้อมูลในไฟล์ (หรือไฟล์ว่างเปล่า)")
    return rows_out


@app.post("/hq/assets/import/preview")
async def hq_import_assets_preview(file: UploadFile = File(...), user=Depends(get_current_user), db=Depends(get_db)):
    if user["role"] != "hq_admin":
        raise HTTPException(status_code=403, detail="HQ admin only")
    content = await file.read()
    rows = _parse_asset_excel(content, file.filename)

    cur = db.cursor()
    codes = [(r["asset_code"], r["seq"]) for r in rows]
    if codes:
        cur.execute("SELECT asset_code, seq FROM assets WHERE (asset_code, seq) IN %s", (tuple(codes),))
        existing = {(r["asset_code"], r["seq"]) for r in cur.fetchall()}
    else:
        existing = set()

    preview = []
    for r in rows:
        is_dup = (r["asset_code"], r["seq"]) in existing
        preview.append({**{k: v for k, v in r.items() if k != "purchase_date_raw"}, "duplicate": is_dup})

    return {"file_name": file.filename, "total_rows": len(rows),
            "duplicate_count": sum(1 for p in preview if p["duplicate"]), "rows": preview}


@app.post("/hq/assets/import/confirm")
async def hq_import_assets_confirm(file: UploadFile = File(...), user=Depends(get_current_user), db=Depends(get_db)):
    if user["role"] != "hq_admin":
        raise HTTPException(status_code=403, detail="HQ admin only")
    content = await file.read()
    rows = _parse_asset_excel(content, file.filename)

    batch_id = uuid.uuid4().hex
    cur = db.cursor()
    inserted = skipped = 0
    try:
        for r in rows:
            cur.execute("""
                INSERT INTO assets
                    (asset_code, seq, qr_key, location_code, location_name, name,
                     status, serial_no, purchase_date, qty, purchase_price,
                     accumulated_dep, net_book_value, import_batch_id, is_active, imported_at)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,true,NOW())
                ON CONFLICT (asset_code, seq) DO NOTHING
            """, (r["asset_code"], r["seq"], r["qr_key"], r["location_code"], r["location_name"],
                  r["name"], r["status"], r["serial_no"], r["purchase_date"], r["qty"],
                  r["purchase_price"], r["accumulated_dep"], r["net_book_value"], batch_id))
            if cur.rowcount:
                inserted += 1
            else:
                skipped += 1

        cur.execute("""
            INSERT INTO import_batches (batch_id, file_name, row_count, imported_by, status)
            VALUES (%s,%s,%s,%s,'active')
        """, (batch_id, file.filename, inserted, user["employee_id"]))
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Import ล้มเหลว ไม่มีข้อมูลเข้าระบบ: {e}")

    return {"ok": True, "batch_id": batch_id, "inserted": inserted, "skipped_duplicates": skipped}


@app.get("/hq/assets/import-batches")
def hq_list_import_batches(db=Depends(get_db), user=Depends(get_current_user)):
    if user["role"] != "hq_admin":
        raise HTTPException(status_code=403, detail="HQ admin only")
    cur = db.cursor()
    cur.execute("SELECT * FROM import_batches ORDER BY imported_at DESC LIMIT 50")
    return {"batches": [dict(r) for r in cur.fetchall()]}


@app.post("/hq/assets/import-batches/{batch_id}/undo")
def hq_undo_import_batch(batch_id: str, db=Depends(get_db), user=Depends(get_current_user)):
    if user["role"] != "hq_admin":
        raise HTTPException(status_code=403, detail="HQ admin only")
    cur = db.cursor()
    cur.execute("SELECT status FROM import_batches WHERE batch_id = %s", (batch_id,))
    batch = cur.fetchone()
    if not batch:
        raise HTTPException(status_code=404, detail="ไม่พบ import batch นี้")
    if batch["status"] == "undone":
        raise HTTPException(status_code=400, detail="Batch นี้ถูก undo ไปแล้ว")

    cur.execute("UPDATE assets SET is_active = false WHERE import_batch_id = %s", (batch_id,))
    undone_count = cur.rowcount
    cur.execute("UPDATE import_batches SET status = 'undone' WHERE batch_id = %s", (batch_id,))
    db.commit()
    return {"ok": True, "batch_id": batch_id, "undone_rows": undone_count}


# ════════════════════════════════════════════════════════════════
# HEALTH CHECK
# ════════════════════════════════════════════════════════════════
@app.get("/")
def root():
    return {"status": "ok", "service": "Bata Asset Audit API", "version": "1.2.0"}

@app.get("/health")
def health(db=Depends(get_db)):
    cur = db.cursor()
    cur.execute("SELECT COUNT(*) as cnt FROM assets")
    cnt = cur.fetchone()["cnt"]
    return {"status": "ok", "assets_in_db": cnt}
