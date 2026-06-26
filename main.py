# ══════════════════════════════════════════════════════════════
# วาง code นี้ต่อท้าย main.py — ก่อน @app.get("/") และ @app.get("/health")
# ══════════════════════════════════════════════════════════════

from fastapi import UploadFile, File
from typing import List
import httpx, hashlib, time

# ── helper: ดึง public_id จาก Cloudinary URL ──────────────────
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
    return path  # เช่น "bata-audit/0051548/bvkzg2di6itorxnehhmw"

# ── helper: สร้าง Cloudinary signature ────────────────────────
def _cloudinary_sign(params: dict, api_secret: str) -> str:
    sorted_params = "&".join(
        f"{k}={v}" for k, v in sorted(params.items())
        if k not in ("file", "api_key", "resource_type")
    )
    return hashlib.sha1(f"{sorted_params}{api_secret}".encode()).hexdigest()


# ── 1. DELETE รูปถ่าย ─────────────────────────────────────────
@app.delete("/hq/scans/{scan_id}/photo", status_code=204)
async def hq_delete_scan_photo(
    scan_id: int,
    db=Depends(get_db),
    user=Depends(get_current_user)
):
    """ลบเฉพาะรูปถ่าย — ข้อมูล scan log ยังอยู่"""
    if user["role"] != "hq_admin":
        raise HTTPException(status_code=403, detail="HQ admin only")

    cur = db.cursor()
    cur.execute("SELECT photo_url FROM scan_logs WHERE id = %s", (scan_id,))
    row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Scan not found")

    old_url = row["photo_url"]

    # ลบจาก Cloudinary ถ้ามี URL
    if old_url and "cloudinary.com" in old_url:
        try:
            cloud  = os.getenv("CLOUDINARY_CLOUD_NAME", "")
            key    = os.getenv("CLOUDINARY_API_KEY", "")
            secret = os.getenv("CLOUDINARY_API_SECRET", "")
            if cloud and key and secret:
                public_id = _cloudinary_public_id(old_url)
                if public_id:
                    ts     = int(time.time())
                    params = {"public_id": public_id, "timestamp": ts}
                    sig    = _cloudinary_sign(params, secret)
                    async with httpx.AsyncClient() as client:
                        await client.post(
                            f"https://api.cloudinary.com/v1_1/{cloud}/image/destroy",
                            data={
                                "public_id": public_id,
                                "timestamp": ts,
                                "api_key":   key,
                                "signature": sig,
                            },
                            timeout=15,
                        )
        except Exception as e:
            print(f"[WARN] Cloudinary delete failed (continuing): {e}")

    # เคลียร์ photo_url ใน DB
    cur.execute(
        "UPDATE scan_logs SET photo_url = NULL, updated_at = NOW() WHERE id = %s",
        (scan_id,)
    )
    db.commit()
    cur.close()
    # 204 No Content


# ── 2. POST อัปโหลดรูปใหม่ ────────────────────────────────────
@app.post("/hq/scans/{scan_id}/photo")
async def hq_upload_scan_photo(
    scan_id: int,
    photo: UploadFile = File(...),
    db=Depends(get_db),
    user=Depends(get_current_user)
):
    """อัปโหลดหรือเปลี่ยนรูปถ่ายของ scan log"""
    if user["role"] != "hq_admin":
        raise HTTPException(status_code=403, detail="HQ admin only")

    if not photo.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="รองรับเฉพาะไฟล์รูปภาพ")
    content = await photo.read()
    if len(content) > 5 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="ไฟล์ใหญ่เกิน 5MB")

    cur = db.cursor()
    cur.execute("""
        SELECT b.id as branch_id
        FROM scan_logs sl
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

    public_id = f"bata-audit/{branch_id}/scan_{scan_id}_{int(time.time())}"
    ts        = int(time.time())
    params    = {"public_id": public_id, "timestamp": ts}
    sig       = _cloudinary_sign(params, secret)

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"https://api.cloudinary.com/v1_1/{cloud}/image/upload",
            data={
                "api_key":   key,
                "timestamp": ts,
                "signature": sig,
                "public_id": public_id,
            },
            files={"file": (photo.filename, content, photo.content_type)},
            timeout=30,
        )

    if resp.status_code != 200:
        raise HTTPException(status_code=500, detail=f"Upload ไม่สำเร็จ: {resp.text[:200]}")

    photo_url = resp.json().get("secure_url", "")
    if not photo_url:
        raise HTTPException(status_code=500, detail="ไม่ได้รับ URL จาก Cloudinary")

    cur.execute(
        "UPDATE scan_logs SET photo_url = %s, updated_at = NOW() WHERE id = %s",
        (photo_url, scan_id)
    )
    db.commit()
    cur.close()
    return {"photo_url": photo_url}


# ── 3. MERGE Sessions ─────────────────────────────────────────
class MergeSessionsRequest(BaseModel):
    primary_session_id: int
    merge_session_ids: List[int]
    branch_id: str

@app.post("/hq/sessions/merge")
def hq_merge_sessions(
    req: MergeSessionsRequest,
    db=Depends(get_db),
    user=Depends(get_current_user)
):
    """Merge sessions ซ้ำ — ย้าย scan_logs เข้า primary แล้วลบซ้ำออก"""
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
            UPDATE scan_logs SET session_id = %s
            WHERE session_id = %s
              AND asset_id NOT IN (
                  SELECT asset_id FROM scan_logs WHERE session_id = %s
              )
        """, (req.primary_session_id, sid, req.primary_session_id))
        moved_scans += cur.rowcount
        cur.execute("DELETE FROM scan_logs WHERE session_id = %s", (sid,))
        cur.execute("""
            UPDATE unmatched_assets SET session_id = %s WHERE session_id = %s
        """, (req.primary_session_id, sid))
        moved_unmatched += cur.rowcount
        cur.execute("DELETE FROM audit_sessions WHERE id = %s", (sid,))
        deleted_sessions += cur.rowcount

    cur.execute("""
        UPDATE audit_sessions SET status = 'on_process'
        WHERE id = %s AND status = 'open'
          AND EXISTS (SELECT 1 FROM scan_logs WHERE session_id = %s)
    """, (req.primary_session_id, req.primary_session_id))

    db.commit()
    cur.close()
    return {
        "ok": True,
        "primary_session_id": req.primary_session_id,
        "deleted_sessions":   deleted_sessions,
        "moved_scans":        moved_scans,
        "moved_unmatched":    moved_unmatched,
    }
