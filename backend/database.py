from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os

# Default DB lives next to this file (backend/finance_tracker.db) regardless
# of the working directory uvicorn was started from — a relative default can
# silently create a second empty database on hosted setups.
_DEFAULT_DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "finance_tracker.db")
DB_PATH = os.environ.get("DB_PATH", _DEFAULT_DB)
SQLALCHEMY_DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False}
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
