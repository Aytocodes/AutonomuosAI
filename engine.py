# =============================================================================
# backend/trading/engine.py -- Trading Engine per Account
# Improvements:
#   1. Trade Manager     -- tracks open trades, manages SL to breakeven
#   2. Duplicate Guard   -- prevents same symbol being traded twice
#   3. Re-entry Cooldown -- waits N minutes after a trade before re-entering
#   4. Weekend/Holiday   -- no trading Friday 5pm ET -> Sunday 5pm ET
# =============================================================================

import sys
import os
import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing   import Optional, Dict, Set
from trading.broker import BrokerClient
import pytz

EA_PATH = os.path.abspath(os.path.join(
    os.path.dirname(__file__),
    "../../../../html+css web/Expert advisor"
))

SMC_SYMBOLS   = ["XAUUSDm", "US30m", "XAGUSDm", "EURUSDm"]
MIN_RR        = 1.5
MAX_SPREAD    = 30
SCALP_SYMBOLS = []

# Re-entry cooldown in minutes per symbol after a trade closes
REENTRY_COOLDOWN_MINUTES = 30

NY_TZ = pytz.timezone("America/New_York")


def _load_ea_modules():
    if EA_PATH not in sys.path:
        sys.path.insert(0, EA_PATH)
    try:
        from strategy_engine   import StrategyEngine
        from scalping_strategy import ScalpingStrategy, SCALP_SYMBOLS as SS
        from news_bot          import A2_NewsBot, NewsFetcher
        from risk_manager      import RiskManager
        global SCALP_SYMBOLS
        SCALP_SYMBOLS = SS
        return StrategyEngine, ScalpingStrategy, A2_NewsBot, NewsFetcher, RiskManager
    except Exception as e:
        logging.getLogger("autonomusai").warning(f"EA modules not loaded: {e}")
        return None, None, None, None, None


def _is_trading_session() -> bool:
    """
    Improvement 4 — Weekend/Holiday filter.
    No trading:
      - Friday after 5:00 PM ET
      - Saturday all day
      - Sunday before 5:00 PM ET
    """
    now  = datetime.now(NY_TZ)
    wday = now.weekday()   # 0=Mon … 4=Fri, 5=Sat, 6=Sun
    hour = now.hour + now.minute / 60.0

    if wday == 4 and hour >= 17:   # Friday after 5pm ET
        return False
    if wday == 5:                   # Saturday
        return False
    if wday == 6 and hour < 17:    # Sunday before 5pm ET
        return False
    return True


class TradeManager:
    """
    Improvement 1 — Trade Manager.
    Tracks open trades per symbol and manages breakeven SL.
    """

    def __init__(self, broker: BrokerClient):
        self.broker = broker
        # symbol -> entry price when trade was placed
        self._open_trades: Dict[str, float] = {}

    def record_trade(self, symbol: str, entry: float):
        self._open_trades[symbol] = entry

    def clear_trade(self, symbol: str):
        self._open_trades.pop(symbol, None)

    def is_open(self, symbol: str) -> bool:
        return self.broker.has_open_position(symbol)

    def manage_open_trades(self):
        """Move SL to breakeven once trade is 1R in profit."""
        for symbol, entry in list(self._open_trades.items()):
            if not self.broker.has_open_position(symbol):
                self.clear_trade(symbol)
                continue
            positions = self.broker.get_positions()
            for p in positions:
                if p["symbol"] != symbol:
                    continue
                current = self.broker.get_ohlc(symbol, "M1", 1)
                if current.empty:
                    continue
                price = current["close"].iloc[-1]
                sl    = p["sl"]
                if sl == 0:
                    continue
                risk  = abs(entry - sl)
                # Move to breakeven when 1R in profit
                if p["direction"] == "buy" and price >= entry + risk and sl < entry:
                    self.broker.modify_sl(symbol, p["ticket"], entry)
                elif p["direction"] == "sell" and price <= entry - risk and sl > entry:
                    self.broker.modify_sl(symbol, p["ticket"], entry)


class AccountEngine:
    """
    Runs all strategies for a single trading account.
    """

    def __init__(self, account_id: int, broker: BrokerClient,
                 risk_pct: float, log_callback, strategy: str = "both"):
        self.account_id   = account_id
        self.broker       = broker
        self.risk_pct     = risk_pct
        self.strategy     = strategy
        self.log          = log_callback
        self.running      = False

        # Improvement 2 — Duplicate trade guard
        self._active_symbols: Set[str] = set()

        # Improvement 3 — Re-entry cooldown: symbol -> last trade time
        self._last_trade_time: Dict[str, datetime] = {}

        # Improvement 1 — Trade manager
        self.trade_manager = TradeManager(broker)

        StrategyEngine, ScalpingStrategy, A2_NewsBot, NewsFetcher, RiskManager = _load_ea_modules()
        self._ea_ok     = StrategyEngine is not None
        self._NewsBot   = A2_NewsBot
        self._NewsFetch = NewsFetcher
        if self._ea_ok:
            self.smc_engine   = StrategyEngine(risk_pct=risk_pct, symbol="XAUUSDm")
            self.scalper      = ScalpingStrategy(risk_pct=risk_pct)
            self.risk_manager = RiskManager(risk_pct=risk_pct)
            global SCALP_SYMBOLS
            self._all_symbols = list(set(SMC_SYMBOLS + SCALP_SYMBOLS))
        else:
            self._all_symbols = SMC_SYMBOLS

    # ------------------------------------------------------------------
    # Main Loop
    # ------------------------------------------------------------------

    async def run(self):
        self.running = True
        await self.log("INFO", f"Engine started | risk={self.risk_pct:.1%} | strategy={self.strategy}")

        while self.running:
            try:
                # Improvement 4 — Weekend filter
                if not _is_trading_session():
                    await self.log("INFO", "Outside trading session (weekend) — sleeping 15 min")
                    await asyncio.sleep(900)
                    continue

                balance = self.broker.get_balance()

                # Improvement 1 — manage open trades (breakeven SL)
                if self._ea_ok:
                    self.trade_manager.manage_open_trades()

                for symbol in self._all_symbols:
                    if not self.running:
                        break
                    await self._evaluate_symbol(symbol, balance)
                    await asyncio.sleep(0.5)

            except Exception as e:
                await self.log("ERROR", f"Engine error: {e}")

            await asyncio.sleep(60)

        await self.log("INFO", "Engine stopped")

    def stop(self):
        self.running = False

    # ------------------------------------------------------------------
    # Guards
    # ------------------------------------------------------------------

    def _is_duplicate(self, symbol: str) -> bool:
        """Improvement 2 — block if we already placed a trade this cycle."""
        return symbol in self._active_symbols

    def _in_cooldown(self, symbol: str) -> bool:
        """Improvement 3 — block if within cooldown window after last trade."""
        last = self._last_trade_time.get(symbol)
        if last is None:
            return False
        elapsed = (datetime.now(timezone.utc) - last).total_seconds() / 60
        return elapsed < REENTRY_COOLDOWN_MINUTES

    def _record_trade(self, symbol: str, entry: float):
        self._active_symbols.add(symbol)
        self._last_trade_time[symbol] = datetime.now(timezone.utc)
        self.trade_manager.record_trade(symbol, entry)

    def _reset_cycle(self):
        """Clear duplicate guard at start of each scan cycle."""
        self._active_symbols.clear()

    # ------------------------------------------------------------------
    # Per-Symbol Evaluation
    # ------------------------------------------------------------------

    async def _evaluate_symbol(self, symbol: str, balance: float):
        try:
            # Improvement 2 — duplicate guard
            if self._is_duplicate(symbol):
                return

            # Improvement 3 — re-entry cooldown
            if self._in_cooldown(symbol):
                return

            if self.broker.has_open_position(symbol):
                return
            if self.broker.get_spread(symbol) > MAX_SPREAD:
                return

            df_h1  = self.broker.get_ohlc(symbol, "H1",  200)
            df_m15 = self.broker.get_ohlc(symbol, "M15", 100)
            df_m5  = self.broker.get_ohlc(symbol, "M5",  100)
            df_m1  = self.broker.get_ohlc(symbol, "M1",  100)

            if df_h1.empty or df_m15.empty or df_m5.empty:
                return
            if not self._ea_ok:
                return

            signal     = None
            signal_tag = ""

            # Strategy 3: News Bot (highest priority)
            if self._NewsBot and self._NewsFetch and self.strategy in ("both", "news"):
                active_event = self._NewsFetch.get_active_event()
                if active_event and not df_m1.empty:
                    nb  = self._NewsBot(symbol=symbol, balance=balance)
                    sig = nb.evaluate_news_setup(active_event, df_m1)
                    if sig:
                        signal     = type('S', (), {
                            'direction': sig['direction'],
                            'entry':     sig['entry'],
                            'sl':        sig['sl'],
                            'tp':        sig['tp'],
                            'rr':        round(abs(sig['tp']-sig['entry']) / max(abs(sig['sl']-sig['entry']), 0.0001), 2),
                        })()
                        signal_tag = f"NEWS-T{sig['tier']} {sig['event'][:12]}"

            # Strategy 1: SMC + CRT
            if signal is None and self.strategy in ("both", "smc") and symbol in SMC_SYMBOLS:
                self.smc_engine.symbol  = symbol
                self.smc_engine.balance = balance
                sig = self.smc_engine.evaluate(df_h1, df_m15, df_m5, df_m1)
                if sig:
                    signal     = sig
                    signal_tag = "RE-ENTRY" if sig.reentry else f"SMC-{sig.timeframe}"

            # Strategy 2: Scalping
            if signal is None and self.strategy in ("both", "scalp") and symbol in SCALP_SYMBOLS:
                self.scalper.symbol = symbol
                scalp = self.scalper.evaluate(df_m15, df_m5, df_m1, balance=balance)
                if scalp:
                    signal     = scalp
                    signal_tag = "SCALP"

            if signal:
                await self.log("SIGNAL",
                    f"[{signal_tag}] {symbol} {signal.direction.upper()} "
                    f"SL={signal.sl} TP={signal.tp} RR={signal.rr:.2f}",
                    symbol=symbol, direction=signal.direction,
                    sl=signal.sl, tp=signal.tp, strategy_tag=signal_tag
                )
                lot    = self.risk_manager.lot_size(balance, signal.entry, signal.sl, symbol=symbol)
                result = self.broker.place_order(symbol, signal.direction, lot, signal.sl, signal.tp)
                if result["success"]:
                    # Improvement 2 & 3 — record trade
                    self._record_trade(symbol, signal.entry)
                    await self.log("TRADE",
                        f"[{signal_tag}] {symbol} {signal.direction.upper()} "
                        f"lot={lot} ticket={result['ticket']}",
                        symbol=symbol, direction=signal.direction,
                        lot=lot, entry=signal.entry,
                        sl=signal.sl, tp=signal.tp, ticket=result["ticket"],
                        strategy_tag=signal_tag
                    )
                else:
                    await self.log("ERROR", f"{symbol} order failed: {result['message']}",
                        symbol=symbol, strategy_tag=signal_tag)

        except Exception as e:
            await self.log("ERROR", f"{symbol} error: {e}")
