"""สร้าง user สำหรับทดสอบ — รันครั้งเดียว"""
import psycopg2, hashlib, os
from dotenv import load_dotenv

load_dotenv()

USERS = [
    ("Acc01", "bata1234", "Account Team 1", "Account",  None),
    ("Acc02", "bata1234", "Account Team 2", "Account",  None),
    ("Audit01", "bata1234", "Admin Audit Team 1", "auditor",  None),
    ("Admin01","admin999", "HQ Admin",     "hq_admin", None),
]

def hash_pw(pw): return hashlib.sha256(pw.encode()).hexdigest()

conn = psycopg2.connect(os.getenv("DATABASE_URL"))
cur  = conn.cursor()

# สร้าง branch ตัวอย่าง ถ้ายังไม่มี
for branch_id in ["0054011","0099999","0068000"]:
    cur.execute(
        "INSERT INTO branches (id, name) VALUES (%s,%s) ON CONFLICT (id) DO NOTHING",
        (branch_id, f"Branch {branch_id}")
    )

for emp_id, pw, name, role, branch in USERS:
    cur.execute("""
        INSERT INTO users (email, password_hash, full_name, role, branch_id)
        VALUES (%s,%s,%s,%s,%s)
        ON CONFLICT (email) DO UPDATE SET password_hash=EXCLUDED.password_hash
    """, (emp_id, hash_pw(pw), name, role, branch))
    print(f"  ✓ {emp_id} / {pw} ({role})")

conn.commit()
cur.close()
conn.close()
print("\nSeed complete")
