# =============================================================================
# backend/routers/accounts_router.py -- Multi-Account Management
# =============================================================================

from fastapi  import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing   import Optional, List
from sqlalchemy.orm import Session

from database  import get_db, Account, User
from auth      import get_current_user
from encryption import encrypt, decrypt

router = APIRouter(prefix="/accounts", tags=["Accounts"])

# ------------------------------------------------------------------
# Currency conversion rates to USD (approximate, update as needed)
# ------------------------------------------------------------------
FX_TO_USD = {
    "USD": 1.0,
    "ZAR": 0.055,   # South African Rand
    "EUR": 1.08,
    "GBP": 1.27,
    "JPY": 0.0067,
    "AUD": 0.65,
    "CAD": 0.74,
    "CHF": 1.12,
    "NZD": 0.61,
    "SGD": 0.74,
    "HKD": 0.13,
    "NOK": 0.095,
    "SEK": 0.096,
    "DKK": 0.145,
    "MXN": 0.058,
    "BRL": 0.20,
    "INR": 0.012,
    "CNY": 0.138,
    "RUB": 0.011,
    "TRY": 0.031,
}

def to_usd(amount: float, currency: str) -> float:
    rate = FX_TO_USD.get(currency.upper(), 1.0)
    return round(amount * rate, 2)


# ------------------------------------------------------------------
# Schemas
# ------------------------------------------------------------------

class AddAccountRequest(BaseModel):
    broker_name:   str
    account_login: str
    password:      str
    server:        Optional[str] = None
    risk_pct:      float = 0.01


class AccountResponse(BaseModel):
    id:            int
    broker_name:   str
    account_login: str
    server:        Optional[str]
    active:        bool
    risk_pct:      float
    strategy:      Optional[str] = "both"
    mt5_name:      Optional[str] = None

    class Config:
        from_attributes = True


class ToggleRequest(BaseModel):
    account_id: int
    active:     bool


class UpdateRiskRequest(BaseModel):
    account_id: int
    risk_pct:   float


class UpdateStrategyRequest(BaseModel):
    account_id: int
    strategy:   str


# ------------------------------------------------------------------
# Endpoints
# ------------------------------------------------------------------

@router.post("/add", response_model=AccountResponse)
def add_account(req: AddAccountRequest,
                db: Session = Depends(get_db),
                user: User  = Depends(get_current_user)):
    # Prevent duplicate: same account_login for this user
    existing = db.query(Account).filter(
        Account.user_id       == user.id,
        Account.account_login == req.account_login
    ).first()
    if existing:
        raise HTTPException(400, f"Account {req.account_login} is already added")

    account = Account(
        user_id=user.id,
        broker_name=req.broker_name,
        account_login=req.account_login,
        encrypted_password=encrypt(req.password),
        server=req.server,
        risk_pct=req.risk_pct,
        active=True,
        strategy="both",
    )
    db.add(account)
    db.commit()
    db.refresh(account)
    return account


@router.get("", response_model=List[AccountResponse])
def get_accounts(db: Session = Depends(get_db),
                 user: User  = Depends(get_current_user)):
    return db.query(Account).filter(Account.user_id == user.id).all()


@router.delete("/{account_id}")
def delete_account(account_id: int,
                   db: Session = Depends(get_db),
                   user: User  = Depends(get_current_user)):
    account = db.query(Account).filter(
        Account.id == account_id, Account.user_id == user.id
    ).first()
    if not account:
        raise HTTPException(404, "Account not found")
    db.delete(account)
    db.commit()
    return {"message": "Account deleted"}


@router.post("/update-risk")
def update_risk(req: UpdateRiskRequest,
                db: Session = Depends(get_db),
                user: User  = Depends(get_current_user)):
    if not (0.001 <= req.risk_pct <= 0.50):
        raise HTTPException(400, "Risk must be between 0.1% and 50%")
    account = db.query(Account).filter(
        Account.id == req.account_id, Account.user_id == user.id
    ).first()
    if not account:
        raise HTTPException(404, "Account not found")
    account.risk_pct = req.risk_pct
    db.commit()
    from trading.bot_manager import bot_manager
    engine = bot_manager._engines.get(req.account_id)
    if engine:
        engine.risk_pct     = req.risk_pct
        engine.risk_manager = engine.risk_manager.__class__(risk_pct=req.risk_pct)
        engine.scalper      = engine.scalper.__class__(risk_pct=req.risk_pct)
    return {"message": "Risk updated", "live_applied": engine is not None}


@router.post("/update-strategy")
def update_strategy(req: UpdateStrategyRequest,
                    db: Session = Depends(get_db),
                    user: User  = Depends(get_current_user)):
    if req.strategy not in ("both", "smc", "scalp", "news"):
        raise HTTPException(400, "Strategy must be: both, smc, or scalp")
    account = db.query(Account).filter(
        Account.id == req.account_id, Account.user_id == user.id
    ).first()
    if not account:
        raise HTTPException(404, "Account not found")
    account.strategy = req.strategy
    db.commit()
    from trading.bot_manager import bot_manager
    engine = bot_manager._engines.get(req.account_id)
    if engine:
        engine.strategy = req.strategy
    return {"message": "Strategy updated", "live_applied": engine is not None}


@router.post("/toggle")
async def toggle_account(req: ToggleRequest,
                         db: Session = Depends(get_db),
                         user: User  = Depends(get_current_user)):
    account = db.query(Account).filter(
        Account.id == req.account_id, Account.user_id == user.id
    ).first()
    if not account:
        raise HTTPException(404, "Account not found")
    account.active = req.active
    db.commit()
    if not req.active:
        from trading.bot_manager import bot_manager
        if bot_manager.is_running(req.account_id):
            await bot_manager.stop_account(req.account_id)
    return {"message": f"Account {'enabled' if req.active else 'disabled and stopped'}"}


@router.get("/{account_id}/info")
def get_account_info(account_id: int,
                     db: Session = Depends(get_db),
                     user: User  = Depends(get_current_user)):
    account = db.query(Account).filter(
        Account.id == account_id, Account.user_id == user.id
    ).first()
    if not account:
        raise HTTPException(404, "Account not found")
    from trading.bot_manager import bot_manager
    broker = bot_manager._brokers.get(account_id)
    if not broker or not broker._connected:
        raise HTTPException(400, "Account not running — start the bot first")
    # Always re-login to THIS account before reading info
    broker._ensure_logged_in()
    import MetaTrader5 as mt5
    info = mt5.account_info()
    if not info or str(info.login) != str(account.account_login):
        raise HTTPException(500, "Could not fetch MT5 account info for this account")
    # Persist the broker-given name
    account.mt5_name = info.name
    db.commit()
    return {
        "login":    info.login,
        "name":     info.name,
        "broker":   info.company,
        "balance":  info.balance,
        "equity":   info.equity,
        "currency": info.currency,
        "server":   info.server,
        "leverage": info.leverage,
        "running":  True,
    }


# ------------------------------------------------------------------
# Profitability — per account (own currency, filtered by login)
# ------------------------------------------------------------------

@router.get("/profitability/all")
def get_all_profitability(period: str = "month",
                          db: Session = Depends(get_db),
                          user: User  = Depends(get_current_user)):
    """
    Overall profitability across ALL accounts.
    Converts each account's profits to USD using FX rates.
    """
    import MetaTrader5 as mt5
    from datetime import datetime, timezone

    group_fmt = "%Y-%m" if period == "year" else "%Y-%m-%d"
    date_from = datetime(2000, 1, 1, tzinfo=timezone.utc)
    date_to   = datetime.now(timezone.utc)

    accounts_list = db.query(Account).filter(Account.user_id == user.id).all()

    if not mt5.initialize():
        return {"period": period, "currency": "USD", "data": []}

    points = {}

    for acc in accounts_list:
        # Login to each account to get its currency and deals
        try:
            pw = decrypt(acc.encrypted_password)
            mt5.login(login=int(acc.account_login), password=pw, server=acc.server or "")
            info = mt5.account_info()
            if not info or str(info.login) != str(acc.account_login):
                continue
            currency = info.currency
            deals = mt5.history_deals_get(date_from, date_to) or []
            for d in sorted(deals, key=lambda x: x.time):
                if d.entry != 1 or d.profit == 0 or d.magic != 20250101:
                    continue
                profit_usd = to_usd(d.profit, currency)
                label = datetime.fromtimestamp(d.time, tz=timezone.utc).strftime(group_fmt)
                points[label] = points.get(label, 0) + profit_usd
        except Exception:
            continue

    result = []
    cumulative = 0.0
    for label, profit in sorted(points.items()):
        cumulative += profit
        result.append({"date": label, "profit": round(profit, 2), "cumulative": round(cumulative, 2)})

    return {"period": period, "currency": "USD", "data": result}


@router.get("/{account_id}/profitability")
def get_profitability(account_id: int,
                      period: str = "month",
                      db: Session = Depends(get_db),
                      user: User  = Depends(get_current_user)):
    """
    Per-account profitability in the account's own currency.
    Filters deals by the account's login number.
    """
    account = db.query(Account).filter(
        Account.id == account_id, Account.user_id == user.id
    ).first()
    if not account:
        raise HTTPException(404, "Account not found")

    import MetaTrader5 as mt5
    from datetime import datetime, timezone

    group_fmt = "%Y-%m" if period == "year" else "%Y-%m-%d"
    date_from = datetime(2000, 1, 1, tzinfo=timezone.utc)
    date_to   = datetime.now(timezone.utc)

    if not mt5.initialize():
        return {"period": period, "currency": "USD", "data": []}

    # Login to this specific account
    try:
        pw = decrypt(account.encrypted_password)
        mt5.login(login=int(account.account_login), password=pw, server=account.server or "")
    except Exception:
        pass

    info = mt5.account_info()
    # Verify we are on the right account
    if not info or str(info.login) != str(account.account_login):
        return {"period": period, "currency": "USD", "data": [],
                "error": f"Could not connect to account {account.account_login}"}

    currency = info.currency
    deals    = mt5.history_deals_get(date_from, date_to) or []

    points = {}
    for d in sorted(deals, key=lambda x: x.time):
        if d.entry != 1 or d.profit == 0 or d.magic != 20250101:
            continue
        label = datetime.fromtimestamp(d.time, tz=timezone.utc).strftime(group_fmt)
        points[label] = points.get(label, 0) + d.profit

    result = []
    cumulative = 0.0
    for label, profit in sorted(points.items()):
        cumulative += profit
        result.append({"date": label, "profit": round(profit, 2), "cumulative": round(cumulative, 2)})

    return {"period": period, "currency": currency, "data": result}


@router.get("/{account_id}/positions")
def get_positions(account_id: int,
                  db: Session = Depends(get_db),
                  user: User  = Depends(get_current_user)):
    account = db.query(Account).filter(
        Account.id == account_id, Account.user_id == user.id
    ).first()
    if not account:
        raise HTTPException(404, "Account not found")
    from trading.bot_manager import bot_manager
    broker = bot_manager._brokers.get(account_id)
    if not broker or not broker._connected:
        return []
    return broker.get_positions()


@router.get("/{account_id}/logs")
def get_logs(account_id: int,
             limit: int = 100,
             db: Session = Depends(get_db),
             user: User  = Depends(get_current_user)):
    account = db.query(Account).filter(
        Account.id == account_id, Account.user_id == user.id
    ).first()
    if not account:
        raise HTTPException(404, "Account not found")
    from database import TradeLog
    logs = db.query(TradeLog).filter(
        TradeLog.account_id == account_id
    ).order_by(TradeLog.timestamp.desc()).limit(limit).all()
    return [{"timestamp": l.timestamp, "level": l.level,
             "message": l.message, "symbol": l.symbol,
             "direction": l.direction, "ticket": l.ticket,
             "profit": l.profit, "strategy_tag": l.strategy_tag} for l in logs]
