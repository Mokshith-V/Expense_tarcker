"""Application entry point: uvicorn app.main:app --reload"""
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from . import models  # noqa: F401  (registers the tables on Base)
from .database import Base, engine
from .deps import DbSession
from .routers import auth, categories, expenses, reports


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Runs once at startup (not at import time), so importing the app
    # in tests never touches MySQL.
    Base.metadata.create_all(bind=engine)
    yield
    # Code after yield would run at shutdown.


app = FastAPI(
    title="Expense Tracker API",
    description="Track daily expenses by category, set monthly budgets, and see where your money goes.",
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(auth.router)
app.include_router(categories.router)
app.include_router(expenses.router)
app.include_router(reports.router)

# ---------- The website ----------
# An absolute path (built from this file's location), so it works no matter
# which folder you start uvicorn from.
STATIC_DIR = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/", include_in_schema=False)
def website():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/health", tags=["health"])
def health(db: DbSession):
    db.execute(text("SELECT 1"))  # fails with 500 if MySQL is unreachable
    return {"status": "ok", "database": "connected"}
