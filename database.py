# =============================================================================
# backend/database.py -- SQLAlchemy Models + DB Setup
# =============================================================================

import os
from sqlalchemy import (create_engine, Column, Integer, String,
                        Boolean, Float, DateTime, Text, ForeignKey)
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from datetime import datetime

_DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "autonomusai.db")
DATABASE_URL = f"sqlite:///{_DB_PATH}"

engine       = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base         = declarative_base()


# ------------------------------------------------------------------
# Models
# ------------------------------------------------------------------

class User(Base):
    __tablename__ = "users"
    id             = Column(Integer, primary_key=True, index=True)
    email          = Column(String, unique=True, nullable=True, index=True)
    phone          = Column(String, unique=True, nullable=True, index=True)
    hashed_password = Column(String, nullable=False)
    created_at     = Column(DateTime, default=datetime.utcnow)
    accounts       = relationship("Account", back_populates="owner", cascade="all, delete")


class Account(Base):
    __tablename__ = "accounts"
    id            = Column(Integer, primary_key=True, index=True)
    user_id       = Column(Integer, ForeignKey("users.id"), nullable=False)
    broker_name   = Column(String, nullable=False)
    account_login = Column(String, nullable=False)
    encrypted_password = Column(String, nullable=False)
    server        = Column(String, nullable=True)
    active        = Column(Boolean, default=True)
    risk_pct      = Column(Float, default=0.01)
    strategy      = Column(String, default="both")
    mt5_name      = Column(String, nullable=True)
    created_at    = Column(DateTime, default=datetime.utcnow)
    owner         = relationship("User", back_populates="accounts")
    logs          = relationship("TradeLog", back_populates="account", cascade="all, delete")


class UserSettings(Base):
    __tablename__ = "user_settings"
    id              = Column(Integer, primary_key=True, index=True)
    user_id         = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)
    telegram_token  = Column(String, nullable=True)
    telegram_chat_id= Column(String, nullable=True)
    telegram_enabled= Column(Boolean, default=False)


class TradeLog(Base):
    __tablename__ = "trade_logs"
    id          = Column(Integer, primary_key=True, index=True)
    account_id  = Column(Integer, ForeignKey("accounts.id"), nullable=False)
    timestamp   = Column(DateTime, default=datetime.utcnow)
    level       = Column(String, default="INFO")   # INFO, SIGNAL, TRADE, ERROR
    message     = Column(Text, nullable=False)
    symbol      = Column(String, nullable=True)
    direction   = Column(String, nullable=True)
    lot         = Column(Float, nullable=True)
    entry       = Column(Float, nullable=True)
    sl          = Column(Float, nullable=True)
    tp          = Column(Float, nullable=True)
    ticket      = Column(Integer, nullable=True)
    profit       = Column(Float, nullable=True)
    strategy_tag = Column(String, nullable=True)
    account     = relationship("Account", back_populates="logs")


# ------------------------------------------------------------------
# Init
# ------------------------------------------------------------------

def init_db():
    Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
