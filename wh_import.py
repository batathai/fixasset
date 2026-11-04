"""
wh_import.py — นำเข้าผลตรวจนับสินทรัพย์จาก Excel แทนการสแกนบาร์โค้ด (Pending -> Verified)

วิธีต่อเข้า main.py (เพิ่ม 2 บรรทัด วางต่อท้ายไฟล์ หรือหลังนิยาม get_db / get_current_user):
    import wh_import
    wh_import.register(app, get_db, get_current_user)

หลักการ:
- แถวในไฟล์ = "ตรวจนับพบแล้ว" -> สร้าง scan_logs (condition='good', scan_source='excel_import')
- จับคู่ด้วย qr_key = รหัสสินทรัพย์ + ลำดับ ; อ่านคอลัมน์ตามชื่อหัวตาราง (ไม่ใช่ตำแหน่ง)
- ข้าม: ซ้ำกับที่สแกน/นำเข้าแล้วใน branch+วันเดียวกัน, ไม่พบใน master, ที่ตั้งไม่ตรง branch
- ทุกแถวผูก import_batch_id -> Undo ลบ scan_logs ของ batch นั้นได้ (เฉพาะที่ scan_source='excel_import')
- hq_admin เท่านั้น
"""
import io
from datetime import date
from typing import Optional

from fastapi import Depends, File, Form, HTTPException, UploadFile

DEFAULT_BRANCH = "0068000"  # Warehouse
MAX_SIZE = 10 * 1024 * 1024
HEADER_CODE = "รหัสสินทรัพย์"
HEADER_SEQ = "ลำดับ"


def _norm_seq(v) -> str:
    if v is None or str(v).strip() == "":
        return ""
    s = str(v).strip()
    if s.endswith(".0"):
        s = s[:-2]
    return s.zfill(3) if s.isdigit() else s


def _read_rows(content: bytes, filename: str):
    """คืน list[(asset_code, seq)] — หาแถวหัวตารางเองใน 10 แถวแรก"""
    name = (filename or "").lower()
    raw = []
    if name.endswith(".xlsx"):
        import openpyxl
        wb = openpyxl.load_workbook(io.BytesIO(content), data_only=True, read_only=True)
        raw = [list(r) for r in wb.worksheets[0].iter_rows(values_only=True)]
    elif name.endswith(".xls"):
        import xlrd
        sh = xlrd.open_workbook(file_contents=content).sheet_by_index(0)
        raw = [sh.row_values(r) for r in range(sh.nrows)]
    else:
        raise HTTPException(status_code=400, detail="รองรับเฉพาะไฟล์ .xlsx หรือ .xls")

    hdr_idx = None
    for i, row in enumerate(raw[:10]):
        cells = [str(c).strip() if c is not None else "" for c in row]
        if HEADER_CODE in cells and HEADER_SEQ in cells:
            hdr_idx, ci, si = i, cells.index(HEADER_CODE), cells.index(HEADER_SEQ)
            break
    if hdr_idx is None:
        raise HTTPException(status_code=400, detail=f"ไม่พบหัวตาราง '{HEADER_CODE}' และ '{HEADER_SEQ}' ใน 10 แถวแรกของไฟล์")

    out, seen = [], set()
    for row in raw[hdr_idx + 1:]:
        if len(row) <= max(ci, si) or row[ci] in (None, ""):
            continue
        code = str(row[ci]).strip()
        if code.lower() == "grand total":
            continue
        seq = _norm_seq(row[si])
        key = (code, seq)
        if key in seen:
            continue
        seen.add(key)
        out.append(key)
    if not out:
        raise HTTPException(status_code=400, detail="ไม่พบข้อมูลในไฟล์")
    return out


def _classify(cur, pairs, branch_id, session_date):
    """แยกแถวเป็น matched / not_found / wrong_location / already_scanned"""
    qr_keys = [c + s for c, s in pairs]
    cur.execute(
        """SELECT id, qr_key, location_code, name FROM assets
           WHERE qr_key = ANY(%s) AND COALESCE(is_active, true) = true""",
        (qr_keys,),
    )
    found = {r["qr_key"]: r for r in cur.fetchall()}

    asset_ids = [r["id"] for r in found.values()]
    scanned = set()
    if asset_ids:
        cur.execute(
            """SELECT DISTINCT sl.asset_id FROM scan_logs sl
               JOIN audit_sessions s ON s.id = sl.session_id
               WHERE sl.asset_id = ANY(%s) AND s.branch_id = %s AND s.audit_date = %s""",
            (asset_ids, branch_id, session_date),
        )
        scanned = {r["asset_id"] for r in cur.fetchall()}

    res = {"matched": [], "not_found": [], "wrong_location": [], "already_scanned": []}
    for code, seq in pairs:
        k = code + seq
        a = found.get(k)
        if not a:
            res["not_found"].append(k)
        elif (a["location_code"] or "").strip() != branch_id:
            res["wrong_location"].append(k)
        elif a["id"] in scanned:
            res["already_scanned"].append(k)
        else:
            res["matched"].append({"asset_id": a["id"], "qr_key": k})
    return res


def register(app, get_db, get_current_user):
    def _admin(user):
        if user["role"] != "hq_admin":
            raise HTTPException(status_code=403, detail="HQ admin only")

    async def _load(file: UploadFile):
        content = await file.read()
        if len(content) > MAX_SIZE:
            raise HTTPException(status_code=400, detail="ไฟล์ใหญ่เกิน 10MB")
        return _read_rows(content, file.filename)

    @app.post("/hq/scans/import-count/preview")
    async def import_count_preview(file: UploadFile = File(...), branch_id: str = Form(DEFAULT_BRANCH),
                                   user=Depends(get_current_user), db=Depends(get_db)):
        _admin(user)
        pairs = await _load(file)
        cur = db.cursor()
        res = _classify(cur, pairs, branch_id, date.today())
        # Pending ที่จะเหลือใน branch นี้ หลังนำเข้า (ข้อมูลช่วยตัดสินใจ)
        cur.execute("""SELECT COUNT(*) AS n FROM assets
                       WHERE location_code = %s AND status = 'active' AND COALESCE(is_active,true) = true""", (branch_id,))
        total = cur.fetchone()["n"]
        return {
            "file_rows": len(pairs),
            "will_insert": len(res["matched"]),
            "already_scanned": len(res["already_scanned"]),
            "not_found": len(res["not_found"]),
            "wrong_location": len(res["wrong_location"]),
            "branch_total_assets": total,
            "sample_not_found": res["not_found"][:20],
            "sample_wrong_location": res["wrong_location"][:20],
        }

    @app.post("/hq/scans/import-count/confirm")
    async def import_count_confirm(file: UploadFile = File(...), branch_id: str = Form(DEFAULT_BRANCH),
                                   user=Depends(get_current_user), db=Depends(get_db)):
        _admin(user)
        pairs = await _load(file)
        cur = db.cursor()
        today = date.today()
        try:
            # ใช้ session เปิดของ branch+วันนี้ ถ้ายังไม่มีก็สร้าง (กติกาเดียวกับ POST /sessions)
            cur.execute("""INSERT INTO audit_sessions (name, branch_id, audit_date, started_by, status)
                           VALUES (%s,%s,%s,%s,'open')
                           ON CONFLICT (branch_id, audit_date) WHERE status != 'done' DO NOTHING RETURNING id""",
                        (f"Audit {branch_id} {today}", branch_id, today, user["user_id"]))
            row = cur.fetchone()
            if not row:
                cur.execute("SELECT id FROM audit_sessions WHERE branch_id=%s AND audit_date=%s AND status != 'done'",
                            (branch_id, today))
                row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=409, detail="session ของวันนี้ถูกปิดแล้ว (done) — เปิด session ใหม่ก่อน")
            session_id = row["id"]

            res = _classify(cur, pairs, branch_id, today)
            skipped = len(pairs) - len(res["matched"])
            cur.execute("""INSERT INTO count_import_batches
                           (file_name, branch_id, session_id, total_rows, inserted, skipped, imported_by)
                           VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING id""",
                        (file.filename, branch_id, session_id, len(pairs), len(res["matched"]), skipped, user["user_id"]))
            batch_id = cur.fetchone()["id"]

            for m in res["matched"]:
                cur.execute("""INSERT INTO scan_logs
                               (session_id, asset_id, scanned_by, condition, remark, scan_source, import_batch_id)
                               VALUES (%s,%s,%s,'good','นำเข้าจาก Excel (ไม่ได้สแกนบาร์โค้ด)','excel_import',%s)""",
                            (session_id, m["asset_id"], user["user_id"], batch_id))
            cur.execute("UPDATE audit_sessions SET status='on_process' WHERE id=%s AND status='open'", (session_id,))
            db.commit()
        except HTTPException:
            db.rollback()
            raise
        except Exception as e:
            db.rollback()
            raise HTTPException(status_code=500, detail=f"นำเข้าล้มเหลว ไม่มีข้อมูลเข้าระบบ: {e}")
        return {"ok": True, "batch_id": batch_id, "session_id": session_id,
                "inserted": len(res["matched"]), "skipped": skipped}

    @app.get("/hq/scans/import-count/batches")
    def import_count_batches(user=Depends(get_current_user), db=Depends(get_db)):
        _admin(user)
        cur = db.cursor()
        cur.execute("SELECT * FROM count_import_batches ORDER BY id DESC LIMIT 30")
        return {"batches": [dict(r) for r in cur.fetchall()]}

    @app.post("/hq/scans/import-count/batches/{batch_id}/undo")
    def import_count_undo(batch_id: int, user=Depends(get_current_user), db=Depends(get_db)):
        _admin(user)
        cur = db.cursor()
        cur.execute("SELECT is_undone FROM count_import_batches WHERE id=%s", (batch_id,))
        b = cur.fetchone()
        if not b:
            raise HTTPException(status_code=404, detail="ไม่พบ batch")
        if b["is_undone"]:
            raise HTTPException(status_code=409, detail="batch นี้ถูก undo ไปแล้ว")
        # CLAUDE.md §5.8: ลบ scan log ต้องบันทึก audit log (scan_delete_logs) ก่อนลบจริงเสมอ
        cur.execute("""INSERT INTO scan_delete_logs
                       (scan_log_id, session_id, branch_id, asset_code, asset_name, qr_key,
                        deleted_by, deleted_by_role, source)
                       SELECT sl.id, sl.session_id, s.branch_id, a.asset_code, a.name, a.qr_key,
                              %s, %s, 'excel_import_undo'
                       FROM scan_logs sl
                       JOIN audit_sessions s ON s.id = sl.session_id
                       JOIN assets a ON a.id = sl.asset_id
                       WHERE sl.import_batch_id=%s AND sl.scan_source='excel_import'""",
                    (user["employee_id"], user["role"], batch_id))
        cur.execute("DELETE FROM scan_logs WHERE import_batch_id=%s AND scan_source='excel_import'", (batch_id,))
        removed = cur.rowcount
        cur.execute("UPDATE count_import_batches SET is_undone=true, undone_at=now() WHERE id=%s", (batch_id,))
        db.commit()
        return {"ok": True, "removed": removed}
