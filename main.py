import hashlib, os, re, sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from fastapi import FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

APP_VERSION = "1.0.0"
DATABASE_VERSION = 1
BLOCK_THRESHOLD = int(os.getenv("BLOCK_THRESHOLD", "3"))
DB_PATH = Path(os.getenv("DATABASE_PATH", "antibrouteur.db"))
DB_PATH.parent.mkdir(parents=True, exist_ok=True)
ADMIN_API_KEY = os.getenv("ADMIN_API_KEY", "").strip()

app = FastAPI(title="AntiBrouteur Community API", version=APP_VERSION)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

class ReportRequest(BaseModel):
    number: str = Field(min_length=3, max_length=40)
    reporter_id: str = Field(min_length=8, max_length=200)
    category: str = Field(default="spam", max_length=80)
    comment: Optional[str] = Field(default=None, max_length=500)

def now():
    return datetime.now(timezone.utc).isoformat()

def normalize_number(value: str):
    value = value.strip()
    has_plus = value.startswith("+")
    digits = re.sub(r"\D", "", value)
    if len(digits) < 3 or len(digits) > 18:
        raise HTTPException(400, "Format de numéro invalide")
    return ("+" if has_plus else "") + digits

def reporter_hash(value: str):
    return hashlib.sha256(value.strip().encode()).hexdigest()

def connect():
    db = sqlite3.connect(DB_PATH, timeout=15)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA journal_mode=WAL")
    return db

def init_db():
    with closing(connect()) as db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS reports(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          number TEXT NOT NULL,
          reporter_hash TEXT NOT NULL,
          category TEXT NOT NULL,
          comment TEXT,
          created_at TEXT NOT NULL,
          UNIQUE(number, reporter_hash)
        );
        CREATE INDEX IF NOT EXISTS idx_reports_number ON reports(number);
        CREATE TABLE IF NOT EXISTS allowlist(
          number TEXT PRIMARY KEY,
          reason TEXT,
          created_at TEXT NOT NULL
        );
        """)
        db.commit()

@app.on_event("startup")
def startup():
    init_db()

@app.get("/")
def root():
    return {"service":"AntiBrouteur Community API","status":"online","version":APP_VERSION,"docs":"/docs"}

@app.get("/health")
def health():
    with closing(connect()) as db:
        db.execute("SELECT 1")
    return {"status":"ok"}

@app.get("/version")
def version():
    with closing(connect()) as db:
        total_reports = db.execute("SELECT COUNT(*) c FROM reports").fetchone()["c"]
        total_numbers = db.execute("SELECT COUNT(DISTINCT number) c FROM reports").fetchone()["c"]
    return {
      "api_version":APP_VERSION,
      "database_version":DATABASE_VERSION,
      "block_threshold":BLOCK_THRESHOLD,
      "total_reports":total_reports,
      "total_numbers":total_numbers,
      "updated_at":now()
    }

@app.get("/check/{number:path}")
def check(number: str):
    number = normalize_number(number)
    with closing(connect()) as db:
        allowlisted = db.execute("SELECT 1 FROM allowlist WHERE number=?", (number,)).fetchone() is not None
        row = db.execute("SELECT COUNT(*) reports, MAX(created_at) last_reported_at FROM reports WHERE number=?", (number,)).fetchone()
    reports = int(row["reports"] or 0)
    blocked = reports >= BLOCK_THRESHOLD and not allowlisted
    status = "trusted" if allowlisted else "spam" if blocked else "suspect" if reports else "unknown"
    return {
      "number":number,"status":status,"reports":reports,"blocked":blocked,
      "allowlisted":allowlisted,"threshold":BLOCK_THRESHOLD,
      "last_reported_at":row["last_reported_at"]
    }

@app.post("/report")
def report(payload: ReportRequest):
    number = normalize_number(payload.number)
    rhash = reporter_hash(payload.reporter_id)
    with closing(connect()) as db:
        if db.execute("SELECT 1 FROM allowlist WHERE number=?", (number,)).fetchone():
            raise HTTPException(409, "Numéro sur liste blanche")
        duplicate = False
        try:
            db.execute(
              "INSERT INTO reports(number,reporter_hash,category,comment,created_at) VALUES(?,?,?,?,?)",
              (number,rhash,payload.category.strip().lower() or "spam",payload.comment,now())
            )
            db.commit()
        except sqlite3.IntegrityError:
            duplicate = True
        reports = db.execute("SELECT COUNT(*) c FROM reports WHERE number=?", (number,)).fetchone()["c"]
    return {
      "accepted":not duplicate,"duplicate":duplicate,"number":number,
      "reports":reports,"blocked":reports >= BLOCK_THRESHOLD,
      "message":"Signalement déjà enregistré" if duplicate else "Signalement enregistré"
    }

@app.get("/updates")
def updates(
    since: Optional[str] = None,
    minimum_reports: int = Query(1, ge=1, le=1000),
    limit: int = Query(1000, ge=1, le=5000)
):
    q = "SELECT number, COUNT(*) reports, MAX(created_at) updated_at FROM reports"
    params = []
    if since:
        q += " WHERE created_at > ?"
        params.append(since)
    q += " GROUP BY number HAVING COUNT(*) >= ? ORDER BY updated_at DESC LIMIT ?"
    params += [minimum_reports, limit]
    with closing(connect()) as db:
        rows = db.execute(q, params).fetchall()
        allow = {r["number"] for r in db.execute("SELECT number FROM allowlist")}
    items = [
      {"number":r["number"],"reports":r["reports"],"blocked":r["reports"] >= BLOCK_THRESHOLD,"updated_at":r["updated_at"]}
      for r in rows if r["number"] not in allow
    ]
    return {
      "database_version":DATABASE_VERSION,"generated_at":now(),
      "threshold":BLOCK_THRESHOLD,"count":len(items),"items":items,
      "numbers":[x["number"] for x in items if x["blocked"]]
    }

def admin_check(key):
    if not ADMIN_API_KEY:
        raise HTTPException(503, "ADMIN_API_KEY non configurée")
    if key != ADMIN_API_KEY:
        raise HTTPException(401, "Clé administrateur invalide")

@app.post("/admin/allowlist/{number:path}")
def add_allow(number: str, reason: str="Ajout administrateur", x_admin_key: Optional[str]=Header(None)):
    admin_check(x_admin_key)
    number = normalize_number(number)
    with closing(connect()) as db:
        db.execute("INSERT OR REPLACE INTO allowlist(number,reason,created_at) VALUES(?,?,?)",(number,reason,now()))
        db.commit()
    return {"ok":True,"number":number,"allowlisted":True}
