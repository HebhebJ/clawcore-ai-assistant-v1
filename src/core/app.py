from fastapi import FastAPI

from src.api.chat import router as chat_router
from src.core.logging import setup_logging

setup_logging()

app = FastAPI(title="ClawCore", version="0.1.0")
app.include_router(chat_router)
