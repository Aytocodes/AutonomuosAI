# =============================================================================
# backend/routers/bot_router.py -- Bot Control Endpoints
# =============================================================================

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database          import get_db, Account, User
from auth              import get_current_user
from trading.bot_manager import bot_manager

router = APIRouter(prefix="/bot", tags=["Bot"])


class AccountActionRequest(BaseModel):
    account_id: int


# ------------------------------------------------------------------
# Canonical aliases required by spec: /bot/start  /bot/stop  /bot/status
# ------------------------------------------------------------------

@router.post("/start")
async def start_bot(db: Session = Depends(get_db),
                    user: User  = Depends(get_current_user)):
    """Start all active accounts for the current user."""
    results = await bot_manager.start_all(user.id)
    return {"results": results}


@router.post("/stop")
async def stop_bot(db: Session = Depends(get_db),
                   user: User  = Depends(get_current_user)):
    """Stop all running accounts for the current user."""
    results = await bot_manager.stop_all(user.id)
    return {"results": results}


@router.get("/status")
def bot_status(user: User = Depends(get_current_user)):
    """Return running/stopped status for every account."""
    return bot_manager.get_status()


# ------------------------------------------------------------------
# Per-account control
# ------------------------------------------------------------------

@router.post("/start/all")
async def start_all(db: Session = Depends(get_db),
                    user: User  = Depends(get_current_user)):
    results = await bot_manager.start_all(user.id)
    return {"results": results}


@router.post("/stop/all")
async def stop_all(db: Session = Depends(get_db),
                   user: User  = Depends(get_current_user)):
    results = await bot_manager.stop_all(user.id)
    return {"results": results}


@router.post("/start/account")
async def start_account(req: AccountActionRequest,
                        db: Session = Depends(get_db),
                        user: User  = Depends(get_current_user)):
    account = db.query(Account).filter(
        Account.id == req.account_id, Account.user_id == user.id
    ).first()
    if not account:
        raise HTTPException(404, "Account not found")
    return await bot_manager.start_account(req.account_id)


@router.post("/stop/account")
async def stop_account(req: AccountActionRequest,
                       db: Session = Depends(get_db),
                       user: User  = Depends(get_current_user)):
    account = db.query(Account).filter(
        Account.id == req.account_id, Account.user_id == user.id
    ).first()
    if not account:
        raise HTTPException(404, "Account not found")
    return await bot_manager.stop_account(req.account_id)


@router.get("/status/{account_id}")
def account_status(account_id: int,
                   db: Session = Depends(get_db),
                   user: User  = Depends(get_current_user)):
    account = db.query(Account).filter(
        Account.id == account_id, Account.user_id == user.id
    ).first()
    if not account:
        raise HTTPException(404, "Account not found")
    return {
        "account_id": account_id,
        "running": bot_manager.is_running(account_id),
    }
