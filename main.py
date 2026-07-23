import os
import re
from datetime import datetime, timezone
from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import (
    create_engine,
    MetaData,
    Table,
    Column,
    Integer,
    String,
    DateTime,
    UniqueConstraint,
    select,
    func,
)
from sqlalchemy.exc import IntegrityError

app = FastAPI(
    title="AntiBrouteur Community API",
    version="1.1.0",
)

DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
REPORT_THRESHOLD = max(1, int(os.getenv("REPORT_THRESHOLD", "3")))

# Render peut fournir postgres:// ; SQLAlchemy attend postgresql+psycopg://
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace(
        "postgres://", "postgresql+psycopg://", 1
    )
elif DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace(
        "postgresql://", "postgresql+psycopg://", 1
    )

engine = None
metadata = MetaData()

reports = Table(
    "community_reports",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("number", String(32), nullable=False, index=True),
    Column("category", String(100), nullable=False),
    Column("installation_id", String(128), nullable=False),
    Column(
        "created_at",
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    ),
    UniqueConstraint(
        "number",
        "installation_id",
        name="uq_report_number_installation",
    ),
)


def get_engine():
    global engine
    if not DATABASE_URL:
        raise HTTPException(
            status_code=503,
            detail="DATABASE_URL absente sur Render",
        )
    if engine is None:
        engine = create_engine(
            DATABASE_URL,
            pool_pre_ping=True,
            pool_recycle=300,
        )
        metadata.create_all(engine)
    return engine


class ReportIn(BaseModel):
    number: str = Field(min_length=3, max_length=32)
    category: str = Field(min_length=2, max_length=100)
    installation_id: str = Field(min_length=8, max_length=128)


def normalize_phone_number(value: str) -> Optional[str]:
    """
    Accepte notamment :
      06 12 34 56 78
      0612345678
      +33 6 12 34 56 78
      0033 6 12 34 56 78
      +1 202-555-0100

    Stockage :
      les numéros français sont normalisés en +33...
      les autres numéros internationaux restent au format +...
    """
    if not value:
        return None

    value = value.strip()

    # Retirer les séparateurs usuels, mais conserver le + initial.
    value = re.sub(r"[\s()./\-]", "", value)

    if value.startswith("00"):
        value = "+" + value[2:]

    # France métropolitaine / DOM : 10 chiffres commençant par 0.
    if re.fullmatch(r"0\d{9}", value):
        return "+33" + value[1:]

    # Numéro français écrit 33XXXXXXXXX sans +.
    if re.fullmatch(r"33\d{9}", value):
        return "+" + value

    # Format international E.164 : 8 à 15 chiffres après +.
    if re.fullmatch(r"\+[1-9]\d{7,14}", value):
        return value

    return None


@app.get("/health")
def health():
    database = "configured" if DATABASE_URL else "missing"
    return {
        "status": "ok",
        "database": database,
        "report_threshold": REPORT_THRESHOLD,
    }


@app.post("/v1/community/report")
def submit_report(payload: ReportIn):
    normalized = normalize_phone_number(payload.number)

    if normalized is None:
        raise HTTPException(
            status_code=400,
            detail=(
                "Numéro invalide. Utilisez par exemple "
                "0612345678 ou +33612345678."
            ),
        )

    db = get_engine()
    category = payload.category.strip().lower()
    installation_id = payload.installation_id.strip()

    inserted = True
    with db.begin() as connection:
        try:
            connection.execute(
                reports.insert().values(
                    number=normalized,
                    category=category,
                    installation_id=installation_id,
                    created_at=datetime.now(timezone.utc),
                )
            )
        except IntegrityError:
            # Un même téléphone ne peut voter qu'une fois pour un même numéro.
            inserted = False

        count = connection.execute(
            select(func.count())
            .select_from(reports)
            .where(reports.c.number == normalized)
        ).scalar_one()

    return {
        "ok": True,
        "inserted": inserted,
        "number": normalized,
        "reports": count,
        "required": REPORT_THRESHOLD,
        "published": count >= REPORT_THRESHOLD,
    }


@app.get("/v1/community/numbers")
def community_numbers():
    db = get_engine()

    with db.connect() as connection:
        rows = connection.execute(
            select(
                reports.c.number,
                func.count().label("reports"),
            )
            .group_by(reports.c.number)
            .having(func.count() >= REPORT_THRESHOLD)
            .order_by(func.count().desc(), reports.c.number.asc())
        ).all()

    return {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "numbers": [
            {
                "number": row.number,
                "reports": row.reports,
            }
            for row in rows
        ],
    }
