from fastapi import FastAPI

from src.api.chat import router as chat_router
from src.api.telegram import router as telegram_router
from src.channels.telegram_autosetup import TelegramAutoSetup
from src.core.logging import setup_logging

setup_logging()

app = FastAPI(title="ClawCore", version="0.1.0")
app.include_router(chat_router)
app.include_router(telegram_router)


@app.on_event("startup")
def _startup_hooks() -> None:
    setup = TelegramAutoSetup()
    app.state.telegram_auto_setup = setup
    info = setup.startup()
    if info.get("ran"):
        app.state.telegram_public_base_url = info.get("public_base_url", "")


@app.on_event("shutdown")
def _shutdown_hooks() -> None:
    setup = getattr(app.state, "telegram_auto_setup", None)
    if setup:
        setup.shutdown()
