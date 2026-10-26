"""Database connection: engine, session factory, Base, and the get_db dependency."""
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from .config import DATABASE_SSL_CA, DATABASE_URL

PROJECT_DIR = Path(__file__).parent.parent

# SQLite (used by the tests) needs this flag; MySQL does not.
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

# Hosted MySQL (e.g. Aiven): connect over SSL and verify the server with its CA certificate.
if DATABASE_SSL_CA:
    connect_args["ssl"] = {"ca": str(PROJECT_DIR / DATABASE_SSL_CA)}

engine = create_engine(
    DATABASE_URL,
    connect_args=connect_args,
    pool_pre_ping=True,  # MySQL closes idle connections; this checks each one before use
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """One session per request; always closed afterwards, even on errors."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
