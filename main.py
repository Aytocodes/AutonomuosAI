# =============================================================================
# backend/main.py -- FastAPI Application Entry Point
# =============================================================================

import os
import asyncio
import logging
import psutil
from contextlib import asynccontextmanager
from logging.handlers import RotatingFileHandler

from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, PlainTextResponse

from database import init_db
from auth import get_current_user
from routers.auth_router     import router as auth_router
from routers.accounts_router import router as accounts_router
from routers.bot_router      import router as bot_router
from routers.ai_router       import router as ai_router
from routers.settings_router import router as settings_router
from routers.positions_router import router as positions_router

# ------------------------------------------------------------------
# Logging -- rotating file + console
# ------------------------------------------------------------------

LOG_FILE = os.path.abspath(os.path.join(os.path.dirname(__file__), "autonomusai.log"))

_handler = RotatingFileHandler(LOG_FILE, maxBytes=5 * 1024 * 1024, backupCount=3, delay=True)
_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))

logging.basicConfig(
    level=logging.INFO,
    handlers=[_handler, logging.StreamHandler()],
)
logger = logging.getLogger("autonomusai")

# ------------------------------------------------------------------
# Memory watchdog -- restart if RSS > 512 MB
# ------------------------------------------------------------------

MEMORY_LIMIT_MB = int(os.getenv("MEMORY_LIMIT_MB", "512"))

async def _memory_watchdog():
    proc = psutil.Process(os.getpid())
    while True:
        await asyncio.sleep(300)  # check every 5 min
        rss_mb = proc.memory_info().rss / 1024 / 1024
        if rss_mb > MEMORY_LIMIT_MB:
            logger.warning(f"Memory {rss_mb:.0f} MB > {MEMORY_LIMIT_MB} MB limit — exiting for systemd restart")
            os._exit(1)

# ------------------------------------------------------------------
# Lifespan
# ------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    asyncio.create_task(_memory_watchdog())
    # Auto-start accounts that have auto_start=True
    async def _auto_start():
        await asyncio.sleep(3)  # wait for server to fully start
        try:
            from database import SessionLocal, Account
            from trading.bot_manager import bot_manager
            db = SessionLocal()
            accounts = db.query(Account).filter(
                Account.active == True,
                Account.auto_start == True
            ).all()
            db.close()
            for acc in accounts:
                logger.info(f"Auto-starting account {acc.id} ({acc.broker_name})")
                await bot_manager.start_account(acc.id)
        except Exception as e:
            logger.warning(f"Auto-start failed: {e}")
    asyncio.create_task(_auto_start())
    logger.info("AutonomusAI Web Trader started")
    logger.info("Dashboard: http://0.0.0.0:8000")
    yield
    logger.info("AutonomusAI Web Trader shutting down")

# ------------------------------------------------------------------
# App
# ------------------------------------------------------------------

app = FastAPI(
    title="AutonomusAI Web Trader",
    description="SMC + CRT Multi-Account Trading Platform",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ------------------------------------------------------------------
# Routers
# ------------------------------------------------------------------

app.include_router(auth_router)
app.include_router(accounts_router)
app.include_router(bot_router)
app.include_router(ai_router)
app.include_router(settings_router)
app.include_router(positions_router)

# ------------------------------------------------------------------
# Health check
# ------------------------------------------------------------------

@app.get("/health")
def health():
    proc = psutil.Process(os.getpid())
    return {
        "status": "ok",
        "platform": "AutonomusAI Web Trader",
        "memory_mb": round(proc.memory_info().rss / 1024 / 1024, 1),
        "cpu_pct": proc.cpu_percent(interval=0.1),
    }

# ------------------------------------------------------------------
# Log viewer endpoint
# ------------------------------------------------------------------

@app.get("/logs", response_class=PlainTextResponse)
def get_logs(lines: int = 200, _user=Depends(get_current_user)):
    log_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "autonomusai.log"))
    if not os.path.exists(log_path):
        return "No log file found."
    with open(log_path, "r", errors="replace") as f:
        all_lines = f.readlines()
    return "".join(all_lines[-lines:])

# ------------------------------------------------------------------
# Serve Frontend
# ------------------------------------------------------------------

FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "../frontend")
if os.path.exists(FRONTEND_DIR):
    app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")

    @app.get("/")
    def serve_frontend():
        return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))
