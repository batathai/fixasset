# ── เพิ่ม 2 endpoints นี้ใน main.py ──
# วางต่อจาก @app.delete("/hq/sessions/{session_id}") ได้เลย

from fastapi import UploadFile, File
import httpx, urllib.parse

# ── 1. DELETE รูปถ่าย ─────────────────────────────────────────
@app.delete("/hq/scans/{scan_id}/photo", status_code=204)
def hq_delete_scan_photo(scan_id: int, db=Depends(get_db), user=Depends(get_current_user)):
    """ลบเฉพาะรูปถ่าย — ข้อมูล scan log ยังอยู่"""
    if user["role"] != "hq_admin":
        raise HTTPException(status_code=403, detail="HQ admin only")
    cur = db.cursor()

    # ดึง photo_url เดิม
    cur.execute("SELECT photo_url FROM scan_logs WHERE id = %s", (scan_id,))
    row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Scan not found")

    old_url = row["photo_url"]

    # ลบไฟล์จาก Supabase Storage (ถ้ามี)
    if old_url and "supabase" in old_url:
        try:
            # URL pattern: .../storage/v1/object/public/BUCKET/path/file.jpg
            after_public = old_url.split("/public/")[-1]   # เช่น "photos/abc123.jpg"
            bucket       = after_public.split("/")[0]       # เช่น "photos"
            file_path    = "/".join(after_public.split("/")[1:])  # เช่น "abc123.jpg"

            supabase_url = os.getenv("SUPABASE_URL")
            supabase_key = os.getenv("SUPABASE_SERVICE_KEY")  # ใช้ service key ไม่ใช่ anon key
            if supabase_url and supabase_key:
                import httpx as _httpx
                _httpx.delete(
                    f"{supabase_url}/storage/v1/object/{bucket}/{urllib.parse.quote(file_path)}",
                    headers={"Authorization": f"Bearer {supabase_key}", "apikey": supabase_key},
                    timeout=10
                )
        except Exception as e:
            print(f"[WARN] Storage delete failed (continuing): {e}")
            # ไม่ raise — ลบ URL ใน DB ต่อได้เลย

    # เคลียร์ photo_url ใน DB
    cur.execute("UPDATE scan_logs SET photo_url = NULL, updated_at = NOW() WHERE id = %s", (scan_id,))
    db.commit()
    cur.close()
    # return 204 No Content (FastAPI จัดการให้อัตโนมัติเพราะ status_code=204)


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

    # Validate
    if not photo.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="รองรับเฉพาะไฟล์รูปภาพ")
    content = await photo.read()
    if len(content) > 5 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="ไฟล์ใหญ่เกิน 5MB")

    cur = db.cursor()
    cur.execute("SELECT id FROM scan_logs WHERE id = %s", (scan_id,))
    if not cur.fetchone():
        raise HTTPException(status_code=404, detail="Scan not found")

    # Upload ไป Supabase Storage
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_SERVICE_KEY")
    bucket = os.getenv("SUPABASE_BUCKET", "photos")

    if not supabase_url or not supabase_key:
        raise HTTPException(status_code=500, detail="Storage ยังไม่ได้ตั้งค่า SUPABASE_URL / SUPABASE_SERVICE_KEY")

    ext      = photo.filename.rsplit(".", 1)[-1].lower() if "." in (photo.filename or "") else "jpg"
    filename = f"scan_{scan_id}_{int(datetime.now().timestamp())}.{ext}"

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{supabase_url}/storage/v1/object/{bucket}/{filename}",
            headers={
                "Authorization": f"Bearer {supabase_key}",
                "apikey":        supabase_key,
                "Content-Type":  photo.content_type,
                "x-upsert":      "true",
            },
            content=content,
            timeout=30,
        )
    if resp.status_code not in (200, 201):
        raise HTTPException(status_code=500, detail=f"Upload ไม่สำเร็จ: {resp.text}")

    photo_url = f"{supabase_url}/storage/v1/object/public/{bucket}/{filename}"

    # อัปเดต DB
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
    merge_session_ids: list[int]
    branch_id: str

@app.post("/hq/sessions/merge")
def hq_merge_sessions(req: MergeSessionsRequest, db=Depends(get_db), user=Depends(get_current_user)):
    """
    Merge sessions ซ้ำ — ย้าย scan_logs และ unmatched_assets
    เข้า primary_session แล้วลบ sessions ซ้ำออก
    """
    if user["role"] != "hq_admin":
        raise HTTPException(status_code=403, detail="HQ admin only")
    if not req.merge_session_ids:
        raise HTTPException(status_code=400, detail="ไม่มี session ที่ต้อง merge")

    cur = db.cursor()

    # ตรวจว่า primary session มีอยู่จริง
    cur.execute("SELECT id FROM audit_sessions WHERE id = %s", (req.primary_session_id,))
    if not cur.fetchone():
        raise HTTPException(status_code=404, detail=f"Primary session #{req.primary_session_id} ไม่พบ")

    moved_scans      = 0
    moved_unmatched  = 0
    deleted_sessions = 0

    for sid in req.merge_session_ids:
        if sid == req.primary_session_id:
            continue

        # ย้าย scan_logs — ถ้า asset_id ซ้ำใน primary ให้ข้าม (ON CONFLICT DO NOTHING)
        cur.execute("""
            UPDATE scan_logs
            SET session_id = %s
            WHERE session_id = %s
              AND asset_id NOT IN (
                  SELECT asset_id FROM scan_logs WHERE session_id = %s
              )
        """, (req.primary_session_id, sid, req.primary_session_id))
        moved_scans += cur.rowcount

        # ลบ scan_logs ซ้ำที่ย้ายไม่ได้
        cur.execute("DELETE FROM scan_logs WHERE session_id = %s", (sid,))

        # ย้าย unmatched_assets
        cur.execute("""
            UPDATE unmatched_assets
            SET session_id = %s
            WHERE session_id = %s
        """, (req.primary_session_id, sid))
        moved_unmatched += cur.rowcount

        # ลบ session ซ้ำ
        cur.execute("DELETE FROM audit_sessions WHERE id = %s", (sid,))
        deleted_sessions += cur.rowcount

    # อัปเดต status primary session เป็น on_process ถ้ามี scan
    cur.execute("""
        UPDATE audit_sessions
        SET status = 'on_process'
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
