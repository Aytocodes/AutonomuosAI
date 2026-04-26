# =============================================================================
# backend/routers/ai_router.py -- AI Trading Assistant
# =============================================================================

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Optional
from auth import get_current_user
from database import User

router = APIRouter(prefix="/ai", tags=["AI"])

SYSTEM_KNOWLEDGE = """
You are AutonomusAI's built-in trading assistant. You have deep knowledge of:

TRADING STRATEGIES:
- SMC (Smart Money Concepts): order blocks, fair value gaps, liquidity sweeps, break of structure, change of character
- CRT (Candle Range Theory): manipulation candles, range highs/lows, displacement
- ICT concepts: killzones, optimal trade entry, premium/discount arrays
- First candle scalping: opening range breakout, NY session 8:30-11:00
- Price action: support/resistance, trend analysis, candlestick patterns

RISK MANAGEMENT:
- Position sizing based on account balance and risk %
- Stop loss placement: below/above order blocks, swing highs/lows
- Take profit: 1:2, 1:3 RR minimum, CRT targets
- Max daily loss limits, drawdown management
- Lot size calculation formula: Risk$ / (SL pips x pip value)

FOREX & CFD MARKETS:
- Major pairs: EURUSD, GBPUSD, USDJPY, USDCHF
- Commodities: XAUUSD (Gold), XAGUSD (Silver), USOIL
- Indices: US30 (Dow Jones), NAS100 (Nasdaq), US500 (S&P500)
- Sessions: Sydney, Tokyo, London (3am-12pm EST), New York (8am-5pm EST)
- High impact news: NFP, CPI, FOMC, GDP

TECHNICAL ANALYSIS:
- Timeframe analysis: HTF bias (H4/D1), LTF entry (M15/M5/M1)
- Market structure: HH, HL (bullish), LH, LL (bearish)
- Liquidity: equal highs/lows, stop hunts, inducement
- Volume analysis, spread monitoring

METATRADER 5:
- How to use MT5, place orders, set SL/TP
- Expert advisors, algo trading settings
- Account types: demo vs live, leverage, margin

AUTONOMUSAI BOT:
- Runs SMC+CRT and First Candle Scalping strategies
- Scans 8 symbols every 60 seconds
- Minimum RR: 1.5, Max spread: 30 points
- Magic number: 20250101
- Supports multiple accounts simultaneously

Always give practical, actionable advice. Be concise but thorough.
If asked about specific trades, analyze based on SMC/CRT principles.
Never give financial advice that guarantees profits — always mention risk.
"""

QUICK_ANSWERS = {
    "what is smc": "SMC (Smart Money Concepts) is a trading methodology that follows institutional order flow. Key concepts: Order Blocks (OB) — zones where institutions placed large orders, Fair Value Gaps (FVG) — imbalances in price, Liquidity Sweeps — price taking out stop losses before reversing, Break of Structure (BOS) — confirmation of trend change.",
    "what is crt": "CRT (Candle Range Theory) identifies manipulation candles that sweep liquidity before a real move. The bot looks for: 1) A candle that sweeps a high/low (manipulation), 2) Displacement away from that level, 3) Entry on retracement into the range.",
    "what is rr": "Risk-Reward Ratio (RR) measures potential profit vs potential loss. A 1:2 RR means risking 1 to make 2. AutonomusAI requires minimum 1.5 RR before entering any trade.",
    "what is an order block": "An Order Block is the last bullish/bearish candle before a strong move in the opposite direction. Institutions leave unfilled orders there. Price often returns to these zones — that's where the bot looks for entries.",
    "what is liquidity": "Liquidity in trading refers to stop loss clusters. Equal highs/lows, previous day highs/lows, and swing points are liquidity pools. Smart money sweeps these levels to fill their large orders before the real move.",
    "what is spread": "Spread is the difference between bid and ask price — your cost to enter a trade. AutonomusAI checks spread before every trade and skips if spread > 30 points to avoid high-cost entries.",
    "what is a pip": "A pip is the smallest price movement in forex. For most pairs it's 0.0001 (4th decimal). For JPY pairs it's 0.01 (2nd decimal). Gold (XAUUSD) uses points — 1 point = $0.01.",
    "what is leverage": "Leverage lets you control a larger position with less capital. 1:2000 leverage (like your Exness account) means $1 controls $2000. It amplifies both profits AND losses — always use proper risk management.",
    "what is a lot": "A lot is the unit of trade size. 1 standard lot = 100,000 units. 0.01 lot (micro) = 1,000 units. AutonomusAI calculates lot size automatically based on your risk % and stop loss distance.",
    "best time to trade": "Best trading times: London session (3am-12pm EST) for EUR/GBP pairs, New York session (8am-5pm EST) for USD pairs and Gold, London-NY overlap (8am-12pm EST) is highest volume. Avoid trading 30 min before/after major news.",
}


class ChatRequest(BaseModel):
    message: str
    accounts: Optional[int] = 0
    running:  Optional[int] = 0


def generate_response(message: str, accounts: int, running: int) -> str:
    msg = message.lower().strip()

    # Check quick answers first
    for key, answer in QUICK_ANSWERS.items():
        if key in msg:
            return answer

    # Bot status context
    if any(w in msg for w in ["status", "running", "bot", "trading"]):
        if running > 0:
            return f"Your bot is currently active — {running} account{'s' if running > 1 else ''} trading live. The bot scans {8} symbols every 60 seconds using SMC+CRT and Scalping strategies. Check your Trade Logs for recent activity."
        else:
            return f"Your bot is currently stopped. You have {accounts} account{'s' if accounts > 1 else ''} configured. Click ▶ on any account to start trading."

    # Gold/XAUUSD
    if any(w in msg for w in ["gold", "xauusd", "xau"]):
        return "Gold (XAUUSD) is one of the best SMC instruments. Key levels to watch: previous day high/low, weekly open, round numbers (2300, 2350 etc). Gold respects order blocks very well. Best sessions: London open and NY open. Spread can be high during off-hours — AutonomusAI checks spread before every entry."

    # US30/Dow
    if any(w in msg for w in ["us30", "dow", "dow jones"]):
        return "US30 (Dow Jones) is highly liquid during NY session (9:30am-4pm EST). It follows SMC principles well — look for liquidity sweeps at previous day highs/lows before the real move. Avoid trading during pre-market unless you have a clear setup."

    # Risk management
    if any(w in msg for w in ["risk", "lot size", "position size", "how much"]):
        return "Risk Management formula: Lot Size = (Account Balance × Risk%) / (SL in pips × Pip Value). Example: $1000 account, 1% risk, 20 pip SL on EURUSD = (1000 × 0.01) / (20 × $1) = 0.5 lots. AutonomusAI calculates this automatically. Recommended: 1-2% risk per trade, never exceed 5%."

    # Strategy questions
    if any(w in msg for w in ["strategy", "how does", "how do", "explain"]):
        return "AutonomusAI runs 3 strategies: 1) SMC+CRT — H1 bias + M15/M5/M1 cascade, CRT manipulation + liquidity sweep + OB/FVG entry, min 1.5 RR. 2) First Candle Scalping — NY open 8:30-11am ET, first candle range + sweep + OB/FVG entry, min 2.0 RR. 3) News Bot — highest priority, live Forex Factory events, Tier 1/2/3 classification, TREND or FADE strategy based on deviation. All 3 run simultaneously."

    # Profit/loss questions
    if any(w in msg for w in ["profit", "loss", "pnl", "performance", "result"]):
        return "Check the Profitability charts on your dashboard — they show all bot trades grouped by day, month or year. The cumulative line shows your overall growth. Remember: consistent small gains compound over time. Focus on RR and win rate, not individual trades."

    # News/fundamental
    if any(w in msg for w in ["news", "nfp", "cpi", "fomc", "fed", "interest rate", "news bot"]):
        return "AutonomusAI has a built-in News Bot (Strategy 3 — highest priority). It fetches live events from Forex Factory, classifies them by tier: Tier 1 (NFP, CPI, FOMC, ECB/BoE/BoJ rates), Tier 2 (GDP, Retail Sales, ISM), Tier 3 (Jobless Claims, JOLTS). It computes actual vs forecast deviation and trades either TREND (strong deviation) or FADE (rejection wick). FOMC waits 30 minutes for Powell speech before trading. News trades appear in logs as [NEWS-T1], [NEWS-T2], [NEWS-T3]."

    # Session questions
    if any(w in msg for w in ["session", "time", "when", "market open"]):
        return "Forex sessions (EST): Sydney 5pm-2am, Tokyo 7pm-4am, London 3am-12pm, New York 8am-5pm. Best time: London-NY overlap (8am-12pm EST) — highest volume and best setups. AutonomusAI's scalping strategy specifically targets NY open (8:30-11am EST)."

    # Broker questions
    if any(w in msg for w in ["broker", "exness", "icmarkets", "deposit", "withdraw"]):
        return "For AutonomusAI, use a broker that supports MT5 with low spreads. Recommended: Exness (your current broker), ICMarkets, Pepperstone. Key requirements: MT5 platform, ECN/Raw spread account, fast execution. Always start on a demo account before going live."

    # Default intelligent response
    responses = [
        f"That's a great trading question. Based on SMC principles, the key is always to follow institutional order flow — identify where smart money is accumulating/distributing, wait for liquidity sweeps, then enter on displacement. What specific aspect would you like me to elaborate on?",
        f"In trading, context is everything. The same setup can be valid or invalid depending on the higher timeframe bias. Always check H4/D1 for direction before looking for entries on M15/M5. What market or setup are you analyzing?",
        f"Risk management is the foundation of consistent trading. Even with a 50% win rate, a 1:2 RR makes you profitable. AutonomusAI requires minimum 1.5 RR on every trade. Would you like me to explain any specific concept?",
    ]
    import hashlib
    idx = int(hashlib.md5(message.encode()).hexdigest(), 16) % len(responses)
    return responses[idx]


@router.post("/chat")
def chat(req: ChatRequest, user: User = Depends(get_current_user)):
    reply = generate_response(req.message, req.accounts or 0, req.running or 0)
    return {"reply": reply}
