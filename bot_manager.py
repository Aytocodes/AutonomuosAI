# =============================================================================
# backend/trading/bot_manager.py -- Multi-Account Bot Manager
# =============================================================================

import asyncio
import logging
from typing import Dict

from database   import SessionLocal, Account, TradeLog
from encryption import decrypt
from trading.broker import BrokerClient
from trading.engine import AccountEngine

logger = logging.getLogger("autonomusai")

MAX_RECONNECT_ATTEMPTS = 5
RECONNECT_DELAY        = 10   # seconds between reconnect attempts


class BotManager:
    """
    Manages all active trading accounts.
    Each account runs as an independent asyncio task.
    One account failure does NOT stop others.
    """

    def __init__(self):
        self._tasks:   Dict[int, asyncio.Task]  = {}
        self._engines: Dict[int, AccountEngine] = {}
        self._brokers: Dict[int, BrokerClient]  = {}

    # ------------------------------------------------------------------
    # Start / Stop per account
    # ------------------------------------------------------------------

    async def start_account(self, account_id: int):
        if account_id in self._tasks and not self._tasks[account_id].done():
            return {"message": "Already running"}

        db      = SessionLocal()
        account = db.query(Account).filter(Account.id == account_id).first()
        db.close()

        if not account or not account.active:
            return {"message": "Account not found or inactive"}

        password = decrypt(account.encrypted_password)
        broker   = BrokerClient(
            account_login=account.account_login,
            password=password,
            server=account.server or "",
            account_id=account_id,
        )

        if not broker.connect():
            return {"message": "Failed to connect to broker"}

        # Save real MT5 account name to DB
        if broker.mt5_name:
            db2 = SessionLocal()
            acc2 = db2.query(Account).filter(Account.id == account_id).first()
            if acc2:
                acc2.mt5_name = broker.mt5_name
                db2.commit()
            db2.close()

        self._brokers[account_id] = broker

        async def log_callback(level: str, message: str, **kwargs):
            logger.log(
                logging.ERROR if level == "ERROR" else logging.INFO,
                f"[Acc {account_id}] {message}"
            )
            db = SessionLocal()
            log = TradeLog(
                account_id=account_id,
                level=level,
                message=message,
                symbol=kwargs.get("symbol"),
                direction=kwargs.get("direction"),
                lot=kwargs.get("lot"),
                entry=kwargs.get("entry"),
                sl=kwargs.get("sl"),
                tp=kwargs.get("tp"),
                ticket=kwargs.get("ticket"),
                strategy_tag=kwargs.get("strategy_tag") or kwargs.get("signal_tag"),
            )
            db.add(log)
            db.commit()
            db.close()
            # Telegram alert on TRADE
            if level == "TRADE":
                self._send_telegram_alert(account.user_id, message)

        engine = AccountEngine(
            account_id=account_id,
            broker=broker,
            risk_pct=account.risk_pct,
            log_callback=log_callback,
            strategy=account.strategy or "both",
        )
        self._engines[account_id] = engine

        task = asyncio.create_task(
            self._run_with_guard(account_id, engine, broker, account),
            name=f"account_{account_id}"
        )
        self._tasks[account_id] = task
        logger.info(f"Account {account_id} started")
        return {"message": f"Account {account_id} started"}

    async def stop_account(self, account_id: int):
        engine = self._engines.get(account_id)
        if engine:
            engine.stop()

        task = self._tasks.get(account_id)
        if task and not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        broker = self._brokers.get(account_id)
        if broker:
            broker.disconnect()

        self._tasks.pop(account_id, None)
        self._engines.pop(account_id, None)
        self._brokers.pop(account_id, None)
        logger.info(f"Account {account_id} stopped")
        return {"message": f"Account {account_id} stopped"}

    async def start_all(self, user_id: int):
        db       = SessionLocal()
        accounts = db.query(Account).filter(
            Account.user_id == user_id, Account.active == True
        ).all()
        db.close()

        results = []
        for acc in accounts:
            result = await self.start_account(acc.id)
            results.append({"account_id": acc.id, **result})
        return results

    async def stop_all(self, user_id: int):
        db       = SessionLocal()
        accounts = db.query(Account).filter(Account.user_id == user_id).all()
        db.close()

        results = []
        for acc in accounts:
            if acc.id in self._tasks:
                result = await self.stop_account(acc.id)
                results.append({"account_id": acc.id, **result})
        return results

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    def get_status(self) -> dict:
        return {
            acc_id: "running" if not task.done() else "stopped"
            for acc_id, task in self._tasks.items()
        }

    def is_running(self, account_id: int) -> bool:
        task = self._tasks.get(account_id)
        return task is not None and not task.done()

    # ------------------------------------------------------------------
    # Guard wrapper -- auto-reconnect on broker disconnect
    # ------------------------------------------------------------------

    async def _run_with_guard(self, account_id: int, engine: AccountEngine,
                               broker: BrokerClient, account):
        attempt = 0
        engine.running = True
        while engine.running:
            try:
                await engine.run()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Account {account_id} engine crashed: {e}")
                self._log_db(account_id, "ERROR", f"Engine crashed: {e}")

            if not engine.running:
                break

            # Auto-reconnect loop
            attempt += 1
            if attempt > MAX_RECONNECT_ATTEMPTS:
                logger.error(f"Account {account_id} exceeded max reconnect attempts — stopping")
                self._log_db(account_id, "ERROR", "Max reconnect attempts exceeded")
                break

            logger.info(f"Account {account_id} reconnecting (attempt {attempt}/{MAX_RECONNECT_ATTEMPTS})...")
            await asyncio.sleep(RECONNECT_DELAY * attempt)  # exponential backoff

            try:
                broker.disconnect()
            except Exception:
                pass

            password = decrypt(account.encrypted_password)
            broker2  = BrokerClient(
                account_login=account.account_login,
                password=password,
                server=account.server or "",
                account_id=account_id,
            )
            if broker2.connect():
                engine.broker = broker2
                self._brokers[account_id] = broker2
                engine.running = True
                attempt = 0
                logger.info(f"Account {account_id} reconnected successfully")
                self._log_db(account_id, "INFO", "Reconnected to broker")
            else:
                logger.warning(f"Account {account_id} reconnect attempt {attempt} failed")

    def _send_telegram_alert(self, user_id: int, message: str):
        try:
            from database import UserSettings
            db = SessionLocal()
            s  = db.query(UserSettings).filter(
                UserSettings.user_id == user_id,
                UserSettings.telegram_enabled == True
            ).first()
            db.close()
            if not s or not s.telegram_token or not s.telegram_chat_id:
                return
            import urllib.request, urllib.parse
            url  = f"https://api.telegram.org/bot{s.telegram_token}/sendMessage"
            text = f"⚡ AutonomusAI\n{message}"
            data = urllib.parse.urlencode({"chat_id": s.telegram_chat_id, "text": text}).encode()
            urllib.request.urlopen(url, data, timeout=5)
        except Exception:
            pass

    def _log_db(self, account_id: int, level: str, message: str):
        try:
            db  = SessionLocal()
            log = TradeLog(account_id=account_id, level=level, message=message)
            db.add(log)
            db.commit()
            db.close()
        except Exception:
            pass


# Global singleton
bot_manager = BotManager()
