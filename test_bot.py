import asyncio, sys, traceback
sys.stderr = sys.stdout

async def test():
    from database import SessionLocal, Account
    from trading.bot_manager import bot_manager

    db = SessionLocal()
    acc = db.query(Account).filter(Account.id == 4).first()
    db.close()
    print(f"Account: {acc.account_login} | Server: {acc.server} | Active: {acc.active}")

    result = await bot_manager.start_account(4)
    print("Start result:", result)

    await asyncio.sleep(5)
    print("Status:", bot_manager.get_status())

    # Check task exception
    task = bot_manager._tasks.get(4)
    if task and task.done():
        exc = task.exception()
        print("Task exception:", exc)
        if exc:
            traceback.print_exception(type(exc), exc, exc.__traceback__)

try:
    asyncio.run(test())
except Exception:
    traceback.print_exc()
