# =============================================================================
# backend/trading/broker.py -- Broker Abstraction Layer
# Wraps MetaTrader 5 with a clean interface per account
# =============================================================================

import pandas as pd
from typing import Optional, List, Dict

try:
    import MetaTrader5 as mt5
    MT5_AVAILABLE = True
except ImportError:
    MT5_AVAILABLE = False

MT5_PATH = "C:\\Program Files\\MetaTrader 5 EXNESS\\terminal64.exe"

# Route each server to its dedicated MT5 terminal
SERVER_TERMINAL_MAP = {
    "exness": "C:\\Program Files\\MetaTrader 5 EXNESS\\terminal64.exe",
    "xm":     "C:\\Program Files\\XM Global MT5\\terminal64.exe",
    "xmglobal": "C:\\Program Files\\XM Global MT5\\terminal64.exe",
    "default": "C:\\Program Files\\MetaTrader 5\\terminal64.exe",
}

def get_terminal_path(server: str) -> str:
    s = (server or "").lower()
    for key, path in SERVER_TERMINAL_MAP.items():
        if key in s:
            return path
    return SERVER_TERMINAL_MAP["default"]

TF_MAP = {"M1": 1, "M5": 5, "M15": 15, "H1": 16385}


class BrokerClient:
    """
    Generic broker interface for one trading account.
    Each account gets its own BrokerClient instance.
    """

    def __init__(self, account_login: str, password: str,
                 server: str, account_id: int):
        self.account_login = account_login
        self.password      = password
        self.server        = server
        self.account_id    = account_id
        self._connected    = False
        self.mt5_name      = None
        self.terminal_path = get_terminal_path(server)

    def connect(self) -> bool:
        if not MT5_AVAILABLE:
            return False
        # Initialize with the correct terminal for this broker
        if not mt5.initialize(path=self.terminal_path):
            return False
        # Check if already on the right account
        info = mt5.account_info()
        if info and str(info.login) == str(self.account_login):
            self._connected = True
            self.mt5_name   = info.name
            return True
        # Login
        authorized = mt5.login(
            login=int(self.account_login),
            password=self.password,
            server=self.server,
        )
        if authorized:
            info = mt5.account_info()
            self.mt5_name = info.name if info else None
        self._connected = authorized
        return authorized

    def disconnect(self):
        self._connected = False

    def _ensure_logged_in(self) -> bool:
        """Re-login to this specific account if MT5 is on a different one."""
        info = mt5.account_info()
        if info and str(info.login) == str(self.account_login):
            return True
        return mt5.login(
            login=int(self.account_login),
            password=self.password,
            server=self.server,
        )

    def get_balance(self) -> float:
        if not self._connected or not MT5_AVAILABLE:
            return 0.0
        self._ensure_logged_in()
        info = mt5.account_info()
        if not info or str(info.login) != str(self.account_login):
            return 0.0
        return info.balance

    def get_equity(self) -> float:
        if not self._connected or not MT5_AVAILABLE:
            return 0.0
        self._ensure_logged_in()
        info = mt5.account_info()
        if not info or str(info.login) != str(self.account_login):
            return 0.0
        return info.equity

    def get_currency(self) -> str:
        if not self._connected or not MT5_AVAILABLE:
            return "USD"
        self._ensure_logged_in()
        info = mt5.account_info()
        if not info or str(info.login) != str(self.account_login):
            return "USD"
        return info.currency

    def get_positions(self) -> list:
        if not self._connected or not MT5_AVAILABLE:
            return []
        self._ensure_logged_in()
        info = mt5.account_info()
        if not info or str(info.login) != str(self.account_login):
            return []
        positions = mt5.positions_get()
        if not positions:
            return []
        return [{"ticket": p.ticket, "symbol": p.symbol,
                 "direction": "buy" if p.type == 0 else "sell",
                 "volume": p.volume, "profit": p.profit,
                 "open_price": p.price_open, "sl": p.sl, "tp": p.tp}
                for p in positions]

    def has_open_position(self, symbol: str) -> bool:
        if not self._connected or not MT5_AVAILABLE:
            return False
        pos = mt5.positions_get(symbol=symbol)
        return pos is not None and len(pos) > 0

    def get_ohlc(self, symbol: str, timeframe: str, count: int = 200) -> pd.DataFrame:
        if not self._connected or not MT5_AVAILABLE:
            return pd.DataFrame()
        tf    = TF_MAP.get(timeframe, 15)
        rates = mt5.copy_rates_from_pos(symbol, tf, 0, count)
        if rates is None or len(rates) == 0:
            return pd.DataFrame()
        df = pd.DataFrame(rates)
        df["time"] = pd.to_datetime(df["time"], unit="s")
        df.set_index("time", inplace=True)
        return df[["open", "high", "low", "close", "tick_volume"]].rename(
            columns={"tick_volume": "volume"}
        )

    def get_spread(self, symbol: str) -> float:
        if not self._connected or not MT5_AVAILABLE:
            return 0.0
        info = mt5.symbol_info(symbol)
        tick = mt5.symbol_info_tick(symbol)
        if not info or not tick:
            return 0.0
        return round((tick.ask - tick.bid) / info.point, 1)

    def modify_sl(self, symbol: str, ticket: int, new_sl: float) -> bool:
        if not self._connected or not MT5_AVAILABLE:
            return False
        request = {
            "action":   mt5.TRADE_ACTION_SLTP,
            "position": ticket,
            "sl":       new_sl,
        }
        result = mt5.order_send(request)
        return result.retcode == mt5.TRADE_RETCODE_DONE

    def place_order(self, symbol: str, direction: str,
                    lot: float, sl: float, tp: float,
                    magic: int = 20250101) -> dict:
        if not self._connected or not MT5_AVAILABLE:
            return {"success": False, "message": "Not connected"}

        tick = mt5.symbol_info_tick(symbol)
        info = mt5.symbol_info(symbol)
        if not tick or not info:
            return {"success": False, "message": "Symbol not found"}

        order_type = mt5.ORDER_TYPE_BUY if direction == "bullish" else mt5.ORDER_TYPE_SELL
        price      = tick.ask if direction == "bullish" else tick.bid

        request = {
            "action":       mt5.TRADE_ACTION_DEAL,
            "symbol":       symbol,
            "volume":       lot,
            "type":         order_type,
            "price":        price,
            "sl":           sl,
            "tp":           tp,
            "deviation":    30,
            "magic":        magic,
            "comment":      "AutonomusAI",
            "type_time":    mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        result = mt5.order_send(request)
        if result.retcode == mt5.TRADE_RETCODE_DONE:
            return {"success": True, "ticket": result.order}
        return {"success": False, "message": result.comment}
