from __future__ import annotations

import hashlib
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

DB_PATH = Path(__file__).with_name("community.db")
app = FastAPI(title="AntiBrouteur Community API", version="1.0.0")


class ReportIn(BaseModel):
    number: str = Field(min_length=6, max_length=32)
    category: str = Field(min_length=2, max_length=100)
    installation_id: str = Field(min_length=32, max_length=128)


def db() -> sqlite3.Connection:
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("""
        CREATE TABLE IF NOT EXISTS reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            number_hash TEXT NOT NULL,
            display_number TEXT NOT NULL,
            category TEXT NOT NULL,
            installation_id TEXT NOT NULL,
            created_at TEXT NOT NULL,
            UNIQUE(number_hash, installation_id)
        )
    """)
    connection.commit()
    return connection


def normalize_number(value: str) -> str:
    clean = re.sub(r"[^0-9+]", "", value)
    if clean.startswith("00"):
        clean = "+" + clean[2:]
    if len(re.sub(r"\D", "", clean)) < 6:
        raise HTTPException(status_code=400, detail="Numéro invalide")
    return clean


def number_hash(value: str) -> str:
    return hashlib.sha256(("antibrouteur:" + value).encode()).hexdigest()


@app.get("/health")
def health() -> dict:
    return {"ok": True}


@app.post("/v1/community/report")
def submit_report(payload: ReportIn) -> dict:
    number = normalize_number(payload.number)
    now = datetime.now(timezone.utc).isoformat()
    connection = db()
    try:
        connection.execute(
            "INSERT INTO reports(number_hash, display_number, category, installation_id, created_at) VALUES (?, ?, ?, ?, ?)",
            (number_hash(number), number, payload.category.strip(), payload.installation_id, now),
        )
        connection.commit()
    except sqlite3.IntegrityError:
        connection.close()
        return {"accepted": False, "duplicate": True}
    finally:
        if connection:
            connection.close()
    return {"accepted": True, "duplicate": False}


@app.get("/v1/community/numbers")
def community_numbers() -> dict:
    connection = db()
    rows = connection.execute("""
        SELECT display_number,
               COUNT(*) AS reports,
               MAX(created_at) AS last_seen,
               (
                   SELECT category FROM reports r2
                   WHERE r2.number_hash = r.number_hash
                   GROUP BY category
                   ORDER BY COUNT(*) DESC, MAX(created_at) DESC
                   LIMIT 1
               ) AS category
        FROM reports r
        GROUP BY number_hash, display_number
        HAVING COUNT(*) >= 1
        ORDER BY reports DESC, last_seen DESC
        LIMIT 5000
    """).fetchall()
    connection.close()
    return {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "numbers": [
            {
                "number": row["display_number"],
                "reports": row["reports"],
                "category": row["category"] or "Non précisé",
                "last_seen": row["last_seen"],
                "status": (
                    "Campagne confirmée" if row["reports"] >= 10
                    else "Risque élevé" if row["reports"] >= 3
                    else "Suspect" if row["reports"] >= 2
                    else "À surveiller"
                ),
            }
            for row in rows
        ],
    }
