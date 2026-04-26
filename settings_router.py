# =============================================================================
# backend/routers/settings_router.py -- User Settings (Telegram, Auto-start)
# =============================================================================

from fastapi  import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing   import Optional
from sqlalchemy.orm import Session

from database import get_db, UserSettings, Account, User
from auth     import get_current_user

router = APIRouter(prefix="/settings", tags=["Settings"])


class TelegramSettings(BaseModel):
    token:   str
    chat_id: str
    enabled: bool = True


class AutoStartRequest(BaseModel):
    account_id: int
    auto_start: bool


@router.get("")
def get_settings(db: Session = Depends(get_db),
                 user: User  = Depends(get_current_user)):
    s = db.query(UserSettings).filter(UserSettings.user_id == user.id).first()
    if not s:
        return {"telegram_enabled": False, "telegram_token": None, "telegram_chat_id": None}
    return {
        "telegram_enabled":  s.telegram_enabled,
        "telegram_token":    s.telegram_token,
        "telegram_chat_id":  s.telegram_chat_id,
    }


@router.post("/telegram")
def save_telegram(req: TelegramSettings,
                  db: Session = Depends(get_db),
                  user: User  = Depends(get_current_user)):
    s = db.query(UserSettings).filter(UserSettings.user_id == user.id).first()
    if not s:
        s = UserSettings(user_id=user.id)
        db.add(s)
    s.telegram_token   = req.token
    s.telegram_chat_id = req.chat_id
    s.telegram_enabled = req.enabled
    db.commit()
    return {"message": "Telegram settings saved"}


@router.post("/telegram/test")
def test_telegram(db: Session = Depends(get_db),
                  user: User  = Depends(get_current_user)):
    s = db.query(UserSettings).filter(UserSettings.user_id == user.id).first()
    if not s or not s.telegram_token or not s.telegram_chat_id:
        raise HTTPException(400, "Telegram not configured")
    ok = _send_telegram(s.telegram_token, s.telegram_chat_id,
                        "✅ AutonomusAI Telegram connected successfully!")
    if not ok:
        raise HTTPException(500, "Failed to send message — check token and chat ID")
    return {"message": "Test message sent"}


@router.post("/auto-start")
def set_auto_start(req: AutoStartRequest,
                   db: Session = Depends(get_db),
                   user: User  = Depends(get_current_user)):
    account = db.query(Account).filter(
        Account.id == req.account_id, Account.user_id == user.id
    ).first()
    if not account:
        raise HTTPException(404, "Account not found")
    account.auto_start = req.auto_start
    db.commit()
    return {"message": f"Auto-start {'enabled' if req.auto_start else 'disabled'}"}


def _send_telegram(token: str, chat_id: str, message: str) -> bool:
    try:
        import urllib.request, urllib.parse
        url  = f"https://api.telegram.org/bot{token}/sendMessage"
        data = urllib.parse.urlencode({"chat_id": chat_id, "text": message, "parse_mode": "HTML"}).encode()
        urllib.request.urlopen(url, data, timeout=5)
        return True
    except Exception:
        return False
