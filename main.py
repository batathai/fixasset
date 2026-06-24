from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import psycopg2, psycopg2.extras, os, hashlib, secrets, json
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="Bata Asset Audit API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://batathai.github.io",
        "http://localhost",
        "http://127.0.0.1",
        "*",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── DB CONNECTION ─────────────────────────────────────────────
def get_db():
    conn = psycopg2.connect(
        os.getenv("DATABASE_URL"),
        cursor_factory=psycopg2.extras.RealDictCursor
    )
    try:
        yield conn
    finally:
        conn.close()

# ── SIMPLE TOKEN STORE (in-memory, replace with Redis for prod) ──
sessions = {}  # token -> {user_id, branch_id, employee_id}

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
    audit_date: str   # YYYY-MM-DD
    name: Optional[str] = None

# ════════════════════════════════════════════════════════════════
# AUTH
# ════════════════════════════════════════════════════════════════
@app.post("/auth/login")
def login(req: LoginRequest, db=Depends(get_db)):
    cur = db.cursor()
    cur.execute(
        "SELECT id, full_name, role, password_hash FROM users WHERE email = %s AND is_active = true",
        (req.employee_id,)
    )
    user = cur.fetchone()

    # Simple password check (SHA256 — upgrade to bcrypt in production)
    pw_hash = hashlib.sha256(req.password.encode()).hexdigest()

    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    # First login: if no password set yet, accept anything and set it
    if not user["password_hash"]:
        cur.execute("UPDATE users SET password_hash = %s WHERE id = %s", (pw_hash, user["id"]))
        db.commit()
    elif user["password_hash"] != pw_hash:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = secrets.token_hex(32)
    sessions[token] = {
        "user_id":     user["id"],
        "employee_id": req.employee_id,
        "branch_id":   req.branch_id,
        "full_name":   user["full_name"],
        "role":        user["role"],
    }

    return {
        "token":       token,
        "employee_id": req.employee_id,
        "full_name":   user["full_name"],
        "branch_id":   req.branch_id,
        "role":        user["role"],
    }

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
    """หา asset จาก QR key — เรียกตอนสแกน"""
    cur = db.cursor()
    cur.execute("SELECT * FROM assets WHERE qr_key = %s", (qr_key,))
    asset = cur.fetchone()
    if not asset:
        return {"found": False, "qr_key": qr_key}
    return {"found": True, "asset": dict(asset)}

@app.get("/assets/branch/{branch_id}")
def assets_by_branch(branch_id: str, db=Depends(get_db), user=Depends(get_current_user)):
    """ดึง asset ทั้งหมดของสาขา"""
    cur = db.cursor()
    cur.execute(
        "SELECT id, qr_key, asset_code, seq, name, serial_no, purchase_date, status FROM assets WHERE location_code = %s ORDER BY asset_code, seq",
        (branch_id,)
    )
    return {"assets": [dict(r) for r in cur.fetchall()]}

# ════════════════════════════════════════════════════════════════
# AUDIT SESSIONS
# ════════════════════════════════════════════════════════════════
@app.post("/sessions")
def create_session(req: SessionCreate, db=Depends(get_db), user=Depends(get_current_user)):
    """สร้าง audit session ใหม่"""
    cur = db.cursor()
    name = req.name or f"Audit {req.branch_id} {req.audit_date}"

    # ถ้ามี session open ของสาขาวันเดียวกัน ให้ reuse
    cur.execute(
        "SELECT id FROM audit_sessions WHERE branch_id = %s AND audit_date = %s AND status = 'open'",
        (req.branch_id, req.audit_date)
    )
    existing = cur.fetchone()
    if existing:
        return {"session_id": existing["id"], "reused": True}

    cur.execute(
        "INSERT INTO audit_sessions (name, branch_id, audit_date, started_by, status) VALUES (%s,%s,%s,%s,'open') RETURNING id",
        (name, req.branch_id, req.audit_date, user["user_id"])
    )
    session_id = cur.fetchone()["id"]
    db.commit()
    return {"session_id": session_id, "reused": False}

@app.get("/sessions/{session_id}/progress")
def session_progress(session_id: int, db=Depends(get_db), user=Depends(get_current_user)):
    """ดูความคืบหน้า session"""
    cur = db.cursor()
    cur.execute("SELECT * FROM v_session_progress WHERE session_id = %s", (session_id,))
    row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Session not found")
    return dict(row)

@app.patch("/sessions/{session_id}/close")
def close_session(session_id: int, db=Depends(get_db), user=Depends(get_current_user)):
    cur = db.cursor()
    cur.execute(
        "UPDATE audit_sessions SET status='closed', closed_at=now() WHERE id=%s",
        (session_id,)
    )
    db.commit()
    return {"ok": True}

# ════════════════════════════════════════════════════════════════
# SCAN LOGS
# ════════════════════════════════════════════════════════════════
@app.post("/scans")
def create_scan(req: ScanLogCreate, db=Depends(get_db), user=Depends(get_current_user)):
    """บันทึก scan log"""
    cur = db.cursor()

    # หา asset id จาก qr_key
    cur.execute("SELECT id FROM assets WHERE qr_key = %s", (req.qr_key,))
    asset = cur.fetchone()
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")

    # เช็ค duplicate ใน session
    cur.execute(
        "SELECT id FROM scan_logs WHERE session_id = %s AND asset_id = %s",
        (req.session_id, asset["id"])
    )
    if cur.fetchone():
        raise HTTPException(status_code=409, detail="Already scanned in this session")

    cur.execute("""
        INSERT INTO scan_logs
          (session_id, asset_id, scanned_by, serial_found, serial_match, condition, remark, photo_url)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
        RETURNING id
    """, (
        req.session_id, asset["id"], user["user_id"],
        req.serial_found, req.serial_match,
        req.condition, req.remark, req.photo_url
    ))
    scan_id = cur.fetchone()["id"]
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
# ════════════════════════════════════════════════════════════════
@app.post("/unmatched")
def create_unmatched(req: UnmatchedCreate, db=Depends(get_db), user=Depends(get_current_user)):
    """บันทึก asset ที่ไม่พบในระบบ"""
    cur = db.cursor()
    cur.execute("""
        INSERT INTO unmatched_assets
          (session_id, scanned_qr, serial_no, name_guess, photo_url, scanned_by, branch_id)
        VALUES (%s,%s,%s,%s,%s,%s,%s)
        RETURNING id
    """, (
        req.session_id, req.scanned_qr, req.serial_no,
        req.name_guess, req.photo_url,
        user["user_id"], user["branch_id"]
    ))
    uid = cur.fetchone()["id"]
    db.commit()
    return {"unmatched_id": uid}

@app.get("/unmatched/pending")
def pending_unmatched(db=Depends(get_db), user=Depends(get_current_user)):
    """HQ ดู unmatched ทั้งหมดที่ยังรอ review"""
    if user["role"] != "hq_admin":
        raise HTTPException(status_code=403, detail="HQ admin only")
    cur = db.cursor()
    cur.execute("""
        SELECT ua.*, u.email as auditor
        FROM unmatched_assets ua
        LEFT JOIN users u ON u.id = ua.scanned_by
        WHERE ua.status = 'pending'
        ORDER BY ua.scanned_at DESC
    """)
    return {"items": [dict(r) for r in cur.fetchall()]}

# ════════════════════════════════════════════════════════════════
# DASHBOARD (HQ)
# ════════════════════════════════════════════════════════════════
@app.get("/dashboard/summary")
def dashboard_summary(db=Depends(get_db), user=Depends(get_current_user)):
    """สรุปภาพรวมทุกสาขา"""
    cur = db.cursor()
    cur.execute("SELECT * FROM v_session_progress ORDER BY audit_date DESC")
    sessions_data = [dict(r) for r in cur.fetchall()]

    cur.execute("SELECT COUNT(*) as total FROM assets WHERE status='active'")
    total_assets = cur.fetchone()["total"]

    cur.execute("SELECT COUNT(*) as total FROM unmatched_assets WHERE status='pending'")
    pending_unmatched = cur.fetchone()["total"]

    return {
        "total_assets":      total_assets,
        "pending_unmatched": pending_unmatched,
        "sessions":          sessions_data,
    }
# ════════════════════════════════════════════════════════════════
# HQ ENDPOINTS — เพิ่มใน main.py ต่อจาก /dashboard/summary
# ════════════════════════════════════════════════════════════════

class ScanLogUpdate(BaseModel):
    condition: Optional[str] = None
    serial_found: Optional[str] = None
    hq_note: Optional[str] = None

class UnmatchedUpdate(BaseModel):
    status: str  # 'matched' | 'rejected'
    hq_note: Optional[str] = None
    matched_asset_code: Optional[str] = None

@app.get("/hq/scans")
def hq_get_scans(db=Depends(get_db), user=Depends(get_current_user)):
    """HQ ดู scan logs ทั้งหมดทุกสาขา พร้อมรูปและข้อมูล asset"""
    if user["role"] != "hq_admin":
        raise HTTPException(status_code=403, detail="HQ admin only")
    cur = db.cursor()
    cur.execute("""
        SELECT
            sl.id,
            sl.condition,
            sl.serial_found,
            sl.serial_match,
            sl.photo_url,
            sl.scanned_at,
            sl.hq_note,
            a.asset_code,
            a.name        AS asset_name,
            a.serial_no   AS serial_master,
            u.email       AS auditor,
            s.id          AS session_id,
            b.id          AS branch_id,
            b.name        AS branch_name
        FROM scan_logs sl
        LEFT JOIN assets         a ON a.id = sl.asset_id
        LEFT JOIN users          u ON u.id = sl.scanned_by
        LEFT JOIN audit_sessions s ON s.id = sl.session_id
        LEFT JOIN branches       b ON b.id = s.branch_id
        ORDER BY sl.scanned_at DESC
    """)
    return {"scans": [dict(r) for r in cur.fetchall()]}


@app.patch("/hq/scans/{scan_id}")
def hq_update_scan(scan_id: int, req: ScanLogUpdate, db=Depends(get_db), user=Depends(get_current_user)):
    """HQ แก้ไข scan log — condition, serial_found, hq_note"""
    if user["role"] != "hq_admin":
        raise HTTPException(status_code=403, detail="HQ admin only")
    cur = db.cursor()

    fields = []
    values = []
    if req.condition is not None:
        fields.append("condition = %s")
        values.append(req.condition)
    if req.serial_found is not None:
        fields.append("serial_found = %s")
        values.append(req.serial_found or None)
    if req.hq_note is not None:
        fields.append("hq_note = %s")
        values.append(req.hq_note or None)

    if not fields:
        raise HTTPException(status_code=400, detail="No fields to update")

    fields.append("updated_at = NOW()")
    values.append(scan_id)

    cur.execute(
        f"UPDATE scan_logs SET {', '.join(fields)} WHERE id = %s RETURNING id",
        values
    )
    if not cur.fetchone():
        raise HTTPException(status_code=404, detail="Scan log not found")
    db.commit()
    return {"ok": True, "scan_id": scan_id}


@app.patch("/hq/unmatched/{unmatched_id}")
def hq_update_unmatched(unmatched_id: int, req: UnmatchedUpdate, db=Depends(get_db), user=Depends(get_current_user)):
    """HQ approve หรือ reject unmatched asset"""
    if user["role"] != "hq_admin":
        raise HTTPException(status_code=403, detail="HQ admin only")
    if req.status not in ("matched", "rejected"):
        raise HTTPException(status_code=400, detail="status must be 'matched' or 'rejected'")

    cur = db.cursor()
    cur.execute("""
        UPDATE unmatched_assets
        SET status = %s,
            hq_note = %s,
            matched_asset_code = %s,
            reviewed_by = %s,
            reviewed_at = NOW(),
            updated_at = NOW()
        WHERE id = %s
        RETURNING id
    """, (
        req.status,
        req.hq_note or f"{'Approved' if req.status == 'matched' else 'Rejected'} by HQ - {user['employee_id']}",
        req.matched_asset_code,
        user["user_id"],
        unmatched_id
    ))
    if not cur.fetchone():
        raise HTTPException(status_code=404, detail="Unmatched asset not found")
    db.commit()
    return {"ok": True, "unmatched_id": unmatched_id, "status": req.status}


@app.get("/hq/unmatched")
def hq_get_unmatched(db=Depends(get_db), user=Depends(get_current_user)):
    """HQ ดู unmatched assets ทั้งหมด (ทุก status)"""
    if user["role"] != "hq_admin":
        raise HTTPException(status_code=403, detail="HQ admin only")
    cur = db.cursor()
    cur.execute("""
        SELECT
            ua.id,
            ua.scanned_qr,
            ua.name_guess,
            ua.serial_no,
            ua.photo_url,
            ua.scanned_at,
            ua.status,
            ua.hq_note,
            ua.matched_asset_code,
            u.email  AS auditor,
            b.id     AS branch_id,
            b.name   AS branch_name
        FROM unmatched_assets ua
        LEFT JOIN users          u ON u.id = ua.scanned_by
        LEFT JOIN audit_sessions s ON s.id = ua.session_id
        LEFT JOIN branches       b ON b.id = s.branch_id
        ORDER BY ua.scanned_at DESC
    """)
    return {"items": [dict(r) for r in cur.fetchall()]}    

# ════════════════════════════════════════════════════════════════
# HEALTH CHECK
# ════════════════════════════════════════════════════════════════
@app.get("/")
def root():
    return {"status": "ok", "service": "Bata Asset Audit API", "version": "1.1.0"}

@app.get("/health")
def health(db=Depends(get_db)):
    cur = db.cursor()
    cur.execute("SELECT COUNT(*) as cnt FROM assets")
    cnt = cur.fetchone()["cnt"]
    return {"status": "ok", "assets_in_db": cnt}
