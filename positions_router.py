# =============================================================================
# backend/routers/positions_router.py -- Live Open Positions
# =============================================================================

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db, Account, User
from auth     import get_current_user
from trading.bot_manager import bot_manager

router = APIRouter(prefix="/positions", tags=["Positions"])


@router.get("")
def get_all_positions(db: Session = Depends(get_db),
                      user: User  = Depends(get_current_user)):
    accounts = db.query(Account).filter(Account.user_id == user.id).all()
    result = []
    for acc in accounts:
        broker = bot_manager._brokers.get(acc.id)
        if not broker or not broker._connected:
            continue
        positions = broker.get_positions()
        for p in positions:
            result.append({
                "account_id":    acc.id,
                "account_name":  acc.mt5_name or acc.broker_name,
                "account_login": acc.account_login,
                **p
            })
    return result


@router.get("/balance")
def get_all_balances(db: Session = Depends(get_db),
                     user: User  = Depends(get_current_user)):
    accounts = db.query(Account).filter(Account.user_id == user.id).all()
    result = []
    for acc in accounts:
        broker   = bot_manager._brokers.get(acc.id)
        running  = bot_manager.is_running(acc.id)
        balance  = broker.get_balance()  if broker and broker._connected else None
        equity   = broker.get_equity()   if broker and broker._connected else None
        currency = broker.get_currency() if broker and broker._connected else "USD"
        result.append({
            "account_id":    acc.id,
            "account_name":  acc.broker_name,
            "account_login": acc.account_login,
            "broker":        acc.broker_name,
            "currency":      currency,
            "balance":       balance,
            "equity":        equity,
            "running":       running,
        })
    return result
